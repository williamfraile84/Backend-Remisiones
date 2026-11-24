from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.usuario import Usuario
from app.repositories.tipo_empaque_repository import TipoEmpaqueRepository
from app.schemas.tipo_empaque import (
    TipoEmpaqueCreate,
    TipoEmpaqueUpdate,
    TipoEmpaqueResponse,
)
from app.services.auditoria_service import AuditoriaService

router = APIRouter(prefix="/empaques", tags=["Tipos de Empaque & Medidas"])


# =============================================================================
# CRUD ATÓMICO: TIPOS DE EMPAQUE (Bulto, Pony, Canastilla, Caja, etc.)
# =============================================================================

@router.get("", response_model=List[TipoEmpaqueResponse])
@router.get("/tipos", response_model=List[TipoEmpaqueResponse])
def listar_empaques(
    search: Optional[str] = Query(None, description="Término de búsqueda"),
    db: Session = Depends(get_db),
):
    """Lista todos los tipos de empaque estandarizados activos."""
    TipoEmpaqueRepository.seed_default_tipos_if_empty(db)
    return TipoEmpaqueRepository.get_all(db, search=search, activo_only=True)


@router.get("/{tipo_id}", response_model=TipoEmpaqueResponse)
@router.get("/tipos/{tipo_id}", response_model=TipoEmpaqueResponse)
def obtener_tipo_empaque(tipo_id: int, db: Session = Depends(get_db)):
    """Obtiene un tipo de empaque por su ID."""
    tipo = TipoEmpaqueRepository.get_by_id(db, tipo_id)
    if not tipo:
        raise HTTPException(status_code=404, detail="Tipo de empaque no encontrado.")
    return tipo


@router.post("", response_model=TipoEmpaqueResponse, status_code=status.HTTP_201_CREATED)
@router.post("/tipos", response_model=TipoEmpaqueResponse, status_code=status.HTTP_201_CREATED)
def crear_tipo_empaque(
    payload: TipoEmpaqueCreate,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Crea un nuevo tipo de empaque estandarizado."""
    if not current_user.tiene_permiso("puede_gestionar_catalogos"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No cuenta con permiso para gestionar catálogos de empaque.",
        )

    existente = TipoEmpaqueRepository.get_by_nombre(db, payload.nombre)
    if existente:
        if not existente.activo:
            existente.activo = True
            existente.peso_kg = payload.peso_kg
            existente.peso_lb = payload.peso_lb or (payload.peso_kg * 2.0)
            if payload.descripcion:
                existente.descripcion = payload.descripcion
            db.commit()
            db.refresh(existente)
            return existente
        raise HTTPException(status_code=400, detail=f"El tipo de empaque '{payload.nombre}' ya existe.")

    tipo = TipoEmpaqueRepository.create(db, payload.model_dump())

    AuditoriaService.registrar_evento(
        db=db,
        accion="CREAR_TIPO_EMPAQUE",
        modulo="EMPAQUES",
        usuario=current_user,
        entidad="TipoEmpaque",
        entidad_id=tipo.id,
        detalles={"nombre": tipo.nombre, "peso_kg": tipo.peso_kg, "peso_lb": tipo.peso_lb},
        request=request,
    )
    return tipo


@router.put("/{tipo_id}", response_model=TipoEmpaqueResponse)
@router.put("/tipos/{tipo_id}", response_model=TipoEmpaqueResponse)
def actualizar_tipo_empaque(
    tipo_id: int,
    payload: TipoEmpaqueUpdate,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Actualiza un tipo de empaque estandarizado."""
    if not current_user.tiene_permiso("puede_gestionar_catalogos"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No cuenta con permiso para modificar catálogos de empaque.",
        )

    tipo = TipoEmpaqueRepository.update(db, tipo_id, payload.model_dump(exclude_unset=True))
    if not tipo:
        raise HTTPException(status_code=404, detail="Tipo de empaque no encontrado.")

    AuditoriaService.registrar_evento(
        db=db,
        accion="ACTUALIZAR_TIPO_EMPAQUE",
        modulo="EMPAQUES",
        usuario=current_user,
        entidad="TipoEmpaque",
        entidad_id=tipo.id,
        detalles=payload.model_dump(exclude_unset=True),
        request=request,
    )
    return tipo


@router.delete("/{tipo_id}", status_code=status.HTTP_200_OK)
@router.delete("/tipos/{tipo_id}", status_code=status.HTTP_200_OK)
def eliminar_tipo_empaque(
    tipo_id: int,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Baja lógica (Soft Delete) de un tipo de empaque."""
    if not current_user.tiene_permiso("puede_gestionar_catalogos"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No cuenta con permiso para eliminar tipos de empaque.",
        )

    exito = TipoEmpaqueRepository.delete(db, tipo_id, hard=False)
    if not exito:
        raise HTTPException(status_code=404, detail="Tipo de empaque no encontrado.")

    AuditoriaService.registrar_evento(
        db=db,
        accion="ELIMINAR_TIPO_EMPAQUE",
        modulo="EMPAQUES",
        usuario=current_user,
        entidad="TipoEmpaque",
        entidad_id=tipo_id,
        request=request,
    )
    return {"mensaje": "Tipo de empaque desactivado correctamente.", "id": tipo_id}
