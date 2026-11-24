import os
from typing import Optional, List
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Request, Header, Query, status
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.security import validate_file_upload, generate_secure_storage_path, ALLOWED_IMAGE_EXTENSIONS
from app.models.empresa import Empresa
from app.models.usuario import Usuario
from app.repositories.empresa_repository import EmpresaRepository
from app.schemas.empresa import EmpresaCreate, EmpresaResponse, EmpresaStatusResponse
from app.services.auditoria_service import AuditoriaService
from app.services.storage.storage_factory import get_storage_provider

router = APIRouter(prefix="/empresa", tags=["Empresa"])


@router.get("/status", response_model=EmpresaStatusResponse)
def get_empresa_status(
    x_empresa_id: Optional[str] = Header(None, alias="X-Empresa-Id"),
    empresa_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Retorna el estado de configuración de empresas, indicando la empresa activa,
    el total de empresas registradas y la lista de empresas disponibles.
    """
    empresas = EmpresaRepository.get_all(db, solo_activas=True)
    
    # Resolver ID de empresa activa solicitada
    target_id = empresa_id
    if target_id is None and x_empresa_id:
        try:
            target_id = int(x_empresa_id)
        except (ValueError, TypeError):
            pass

    empresa_activa = None
    if target_id:
        empresa_activa = next((e for e in empresas if e.id == target_id), None)

    # Fallback a la primera empresa disponible si no se especificó o no se encontró
    if not empresa_activa and empresas:
        empresa_activa = empresas[0]

    return {
        "configurada": len(empresas) > 0,
        "empresa": empresa_activa,
        "total_empresas": len(empresas),
        "empresas": empresas,
    }


@router.get("", response_model=List[EmpresaResponse])
@router.get("/todas", response_model=List[EmpresaResponse])
def get_todas_las_empresas(db: Session = Depends(get_db)):
    """Lista todas las empresas activas registradas en el sistema."""
    return EmpresaRepository.get_all(db, solo_activas=True)


@router.post("", response_model=EmpresaStatusResponse)
def save_empresa(
    payload: EmpresaCreate,
    request: Request,
    empresa_id: Optional[int] = Query(None, description="ID de la empresa a actualizar. Si no se provee, se crea una nueva."),
    x_empresa_id: Optional[str] = Header(None, alias="X-Empresa-Id"),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Crea una nueva empresa (setup inicial o adición multi-empresa) o actualiza una existente.
    """
    if not current_user.tiene_permiso("puede_editar_empresa") and current_user.rol != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No cuenta con permiso para registrar o editar empresas.",
        )

    # Determinar si es una actualización de una empresa específica
    target_id = empresa_id
    if target_id is None and x_empresa_id:
        try:
            target_id = int(x_empresa_id)
        except (ValueError, TypeError):
            pass

    todas = EmpresaRepository.get_all(db, solo_activas=False)
    es_primer_inicio = len(todas) == 0

    if target_id and not es_primer_inicio:
        # Actualizar empresa existente
        empresa = EmpresaRepository.update(db, target_id, payload.model_dump())
        if not empresa:
            raise HTTPException(status_code=404, detail="Empresa no encontrada para actualizar.")
        accion_audit = "ACTUALIZAR_EMPRESA"
    elif es_primer_inicio:
        # Primer inicio: crear la primera empresa
        empresa = EmpresaRepository.create(db, payload.model_dump())
        accion_audit = "CONFIGURAR_EMPRESA_INICIAL"
        if not current_user.empresa_id:
            current_user.empresa_id = empresa.id
            db.commit()
    else:
        # Creación de una nueva empresa en entorno multi-empresa
        empresa = EmpresaRepository.create(db, payload.model_dump())
        accion_audit = "CREAR_NUEVA_EMPRESA"

    AuditoriaService.registrar_evento(
        db=db,
        accion=accion_audit,
        modulo="EMPRESA",
        usuario=current_user,
        entidad="Empresa",
        entidad_id=empresa.id,
        detalles={"nombre": empresa.nombre, "nit": empresa.nit},
        request=request,
    )

    empresas_actualizadas = EmpresaRepository.get_all(db, solo_activas=True)
    return {
        "configurada": True,
        "empresa": empresa,
        "total_empresas": len(empresas_actualizadas),
        "empresas": empresas_actualizadas,
    }


@router.post("/logo")
async def upload_logo(
    request: Request,
    file: UploadFile = File(...),
    empresa_id: Optional[int] = Query(None),
    x_empresa_id: Optional[str] = Header(None, alias="X-Empresa-Id"),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.tiene_permiso("puede_editar_empresa") and current_user.rol != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No cuenta con permiso para modificar el logo de la empresa.",
        )

    target_id = empresa_id
    if target_id is None and x_empresa_id:
        try:
            target_id = int(x_empresa_id)
        except (ValueError, TypeError):
            pass

    empresa = EmpresaRepository.get_empresa(db, target_id)
    if not empresa:
        raise HTTPException(status_code=400, detail="Empresa no encontrada o no configurada.")

    contents = await file.read()
    validate_file_upload(file, ALLOWED_IMAGE_EXTENSIONS, header_bytes=contents[:16])

    rel_path, _ = generate_secure_storage_path("logos", file.filename)

    storage = get_storage_provider()
    await storage.save_file(rel_path, contents, content_type=file.content_type or "image/png")

    empresa.logo_path = rel_path
    db.commit()

    AuditoriaService.registrar_evento(
        db=db,
        accion="SUBIR_LOGO_EMPRESA",
        modulo="EMPRESA",
        usuario=current_user,
        entidad="Empresa",
        entidad_id=empresa.id,
        detalles={"logo_path": rel_path, "archivo_original": file.filename},
        request=request,
    )

    return {"logo_path": rel_path, "empresa_id": empresa.id}


@router.get("/logo")
async def get_empresa_logo(
    empresa_id: Optional[int] = Query(None),
    x_empresa_id: Optional[str] = Header(None, alias="X-Empresa-Id"),
    db: Session = Depends(get_db),
):
    """Sirve el logo corporativo de la empresa activa o indicada."""
    target_id = empresa_id
    if target_id is None and x_empresa_id:
        try:
            target_id = int(x_empresa_id)
        except (ValueError, TypeError):
            pass

    empresa = EmpresaRepository.get_empresa(db, target_id)
    if not empresa or not empresa.logo_path:
        raise HTTPException(status_code=404, detail="La empresa no tiene un logo configurado.")

    storage = get_storage_provider()
    clean_path = empresa.logo_path.replace("\\", "/").lstrip("/")
    if not await storage.file_exists(clean_path):
        local_path = os.path.join(settings.STORAGE_BASE_DIR, clean_path)
        if os.path.isfile(local_path):
            from fastapi.responses import FileResponse
            from app.core.security import get_file_media_type
            return FileResponse(local_path, media_type=get_file_media_type(local_path))
        raise HTTPException(status_code=404, detail="Archivo físico de logo no encontrado en almacenamiento.")

    return storage.get_response(clean_path, inline=True)
