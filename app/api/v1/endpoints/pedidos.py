import os
from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Response, Request, status
from sqlalchemy.orm import Session, selectinload
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.security import (
    validate_file_upload,
    generate_secure_storage_path,
    ALLOWED_DOC_EXTENSIONS,
)
from app.models.pedido import Pedido
from app.models.pedido_item import PedidoItem
from app.models.pedido_gasto import PedidoGasto
from app.models.usuario import Usuario
from app.schemas.pedido import PedidoSavePayload, PedidoResponse
from app.services.document_parser import extraer_datos_documento_async
from app.services.pricing_service import recalcular_liquidacion
from app.services.auditoria_service import AuditoriaService
from app.services.pedido_service import PedidoService
from app.services.storage.storage_factory import get_storage_provider

router = APIRouter(prefix="/pedidos", tags=["Pedidos"])


@router.get("/historial/{cliente_id}", response_model=List[PedidoResponse])
def get_historial(
    cliente_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(Pedido)
        .options(
            selectinload(Pedido.items).selectinload(PedidoItem.producto),
            selectinload(Pedido.items).selectinload(PedidoItem.unidad_medida),
            selectinload(Pedido.items).selectinload(PedidoItem.tipo_empaque),
            selectinload(Pedido.gastos_rel),
            selectinload(Pedido.gastos_rel).selectinload(PedidoGasto.concepto),
        )
        .filter(Pedido.cliente_id == cliente_id, Pedido.activo == True)
        .order_by(Pedido.id.desc())
        .all()
    )


@router.get("/{id}", response_model=PedidoResponse)
def get_pedido(
    id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retorna los datos completos de un pedido incluyendo productos, gastos y cálculos de liquidación."""
    pedido = (
        db.query(Pedido)
        .options(
            selectinload(Pedido.items).selectinload(PedidoItem.producto),
            selectinload(Pedido.items).selectinload(PedidoItem.unidad_medida),
            selectinload(Pedido.items).selectinload(PedidoItem.tipo_empaque),
            selectinload(Pedido.gastos_rel),
            selectinload(Pedido.gastos_rel).selectinload(PedidoGasto.concepto),
        )
        .filter(Pedido.id == id, Pedido.activo == True)
        .first()
    )
    if not pedido:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido no encontrado")
    return pedido


@router.post("/upload-documento")
async def upload_documento(
    request: Request,
    file: UploadFile = File(...),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.tiene_permiso("puede_cargar_documentos"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No cuenta con permiso para cargar documentos de pedido.",
        )

    contents = await file.read()
    validate_file_upload(file, ALLOWED_DOC_EXTENSIONS, header_bytes=contents[:16])

    rel_path, clean_name = generate_secure_storage_path("uploads", file.filename)
    
    storage = get_storage_provider()
    await storage.save_file(rel_path, contents, content_type=file.content_type or "application/octet-stream")

    datos = await extraer_datos_documento_async(contents, file.filename)

    AuditoriaService.registrar_evento(
        db=db,
        accion="SUBIR_DOCUMENTO_PEDIDO",
        modulo="PEDIDOS",
        usuario=current_user,
        entidad="Archivo",
        entidad_id=rel_path,
        detalles={
            "archivo_original": file.filename,
            "archivo_guardado": clean_name,
            "total_productos_extraidos": len(datos.get("productos", [])),
            "cliente_detectado": datos.get("cliente", {}).get("razon_social"),
            "numero_oc": datos.get("numero_oc"),
        },
        request=request,
    )

    return {"datos": datos, "archivo_path": rel_path}


@router.post("/guardar", response_model=PedidoResponse)
def guardar_pedido(
    payload: PedidoSavePayload,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not (
        current_user.tiene_permiso("puede_crear_pedidos")
        or current_user.tiene_permiso("puede_editar_pedidos")
        or current_user.tiene_permiso("puede_crear_editar_pedidos")
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No cuenta con permiso para crear o modificar pedidos.",
        )

    return PedidoService.guardar_pedido(db, payload, current_user, request)


@router.post("/recalcular")
def recalcular_pedido(payload: PedidoSavePayload):
    """Permite obtener una vista previa en memoria de los cálculos sin persistir en base de datos."""
    util_val = (
        payload.utilidad_global
        if payload.utilidad_global is not None
        else (payload.porcentaje_utilidad_global or 30.0)
    )
    return recalcular_liquidacion(
        productos=payload.productos,
        gastos=payload.gastos,
        utilidad_global=util_val,
    )


@router.post("/{id}/cerrar", response_model=PedidoResponse)
def cerrar_pedido(
    id: int,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.tiene_permiso("puede_cerrar_pedidos"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No cuenta con permiso para cerrar pedidos formalmente.",
        )

    return PedidoService.cerrar_pedido(db, id, current_user, request)


@router.delete("/{id}")
def eliminar_pedido(
    id: int,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Desactivación lógica (Soft-Delete) preservando el registro para trazabilidad y auditoría."""
    if not (
        current_user.tiene_permiso("puede_desactivar_pedidos")
        or current_user.tiene_permiso("puede_eliminar_pedidos")
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No cuenta con permiso para desactivar pedidos del sistema.",
        )

    return PedidoService.eliminar_pedido(db, id, current_user, request)


@router.post("/{id}/factura")
async def subir_factura(
    id: int,
    request: Request,
    file: UploadFile = File(...),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.tiene_permiso("puede_cargar_facturas"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No cuenta con permiso para cargar facturas.",
        )

    return await PedidoService.subir_factura(db, id, file, current_user, request)


@router.get("/{id}/factura/preview")
def previsualizar_factura(
    id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Previsualización inline de factura cargada (PDF o Imagen). Requiere autenticación."""
    pedido = db.query(Pedido).filter(Pedido.id == id).first()
    if not pedido or not pedido.factura_archivo_path:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    
    storage = get_storage_provider()
    return storage.get_response(
        pedido.factura_archivo_path,
        filename=pedido.factura_archivo_nombre,
        inline=True
    )


@router.get("/{id}/factura/descargar")
def descargar_factura(
    id: int,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Descarga explícita como attachment de factura cargada. Requiere autenticación."""
    pedido = db.query(Pedido).filter(Pedido.id == id).first()
    if not pedido or not pedido.factura_archivo_path:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    
    AuditoriaService.registrar_evento(
        db=db,
        accion="DESCARGAR_FACTURA",
        modulo="PEDIDOS",
        usuario=current_user,
        entidad="Pedido",
        entidad_id=id,
        detalles={"archivo": pedido.factura_archivo_nombre},
        request=request,
    )
    
    storage = get_storage_provider()
    return storage.get_response(
        pedido.factura_archivo_path,
        filename=pedido.factura_archivo_nombre or "factura.pdf",
        inline=False
    )


@router.post("/{id}/remision-firmada")
async def subir_remision_firmada(
    id: int,
    request: Request,
    file: UploadFile = File(...),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.tiene_permiso("puede_cargar_remisiones_firmadas"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No cuenta con permiso para cargar remisiones firmadas.",
        )

    return await PedidoService.subir_remision_firmada(db, id, file, current_user, request)


@router.get("/{id}/remision-firmada/preview")
def previsualizar_remision_firmada(
    id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Previsualización inline de remisión firmada (PDF o Imagen). Requiere autenticación."""
    pedido = db.query(Pedido).filter(Pedido.id == id).first()
    if not pedido or not pedido.remision_firmada_path:
        raise HTTPException(status_code=404, detail="Remisión firmada no encontrada")
    
    storage = get_storage_provider()
    return storage.get_response(
        pedido.remision_firmada_path,
        filename=pedido.remision_firmada_nombre,
        inline=True
    )


@router.get("/{id}/remision-firmada/descargar")
def descargar_remision_firmada(
    id: int,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Descarga explícita como attachment de remisión firmada solicitada por el usuario. Requiere autenticación."""
    pedido = db.query(Pedido).filter(Pedido.id == id).first()
    if not pedido or not pedido.remision_firmada_path:
        raise HTTPException(status_code=404, detail="Remisión firmada no encontrada")
    
    AuditoriaService.registrar_evento(
        db=db,
        accion="DESCARGAR_REMISION_FIRMADA",
        modulo="PEDIDOS",
        usuario=current_user,
        entidad="Pedido",
        entidad_id=id,
        detalles={"archivo": pedido.remision_firmada_nombre},
        request=request,
    )
    
    storage = get_storage_provider()
    return storage.get_response(
        pedido.remision_firmada_path,
        filename=pedido.remision_firmada_nombre or "remision_firmada.pdf",
        inline=False
    )
