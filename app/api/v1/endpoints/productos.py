from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.usuario import Usuario
from app.schemas.producto import (
    ProductoCreate,
    ProductoUpdate,
    ProductoResponse,
    BatchEmpaquesRequest,
    BatchEmpaquesResponse,
)
from app.repositories.producto_repository import ProductoRepository
from app.services.auditoria_service import AuditoriaService

router = APIRouter(prefix="/productos", tags=["Productos"])


@router.get("", response_model=List[ProductoResponse])
def get_productos(
    search: Optional[str] = None,
    categoria: Optional[str] = None,
    db: Session = Depends(get_db),
):
    return ProductoRepository.get_all(db, search=search, categoria=categoria)


@router.put("/batch-empaques", response_model=BatchEmpaquesResponse)
@router.post("/batch-empaques", response_model=BatchEmpaquesResponse)
def batch_update_empaques(
    payload: BatchEmpaquesRequest,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.tiene_permiso("puede_gestionar_catalogos"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No cuenta con permiso para modificar catálogos.",
        )

    count = ProductoRepository.batch_update_empaques(
        db,
        [item.model_dump() for item in payload.items],
    )

    AuditoriaService.registrar_evento(
        db=db,
        accion="ACTUALIZACION_MASIVA_EMPAQUES",
        modulo="CATALOGOS",
        usuario=current_user,
        entidad="Producto",
        entidad_id=0,
        detalles={"productos_actualizados": count},
        request=request,
    )

    return BatchEmpaquesResponse(
        status="ok",
        actualizados=count,
        detalles=f"Se actualizaron exitosamente {count} productos.",
    )


@router.get("/{id}", response_model=ProductoResponse)
def get_producto(id: int, db: Session = Depends(get_db)):
    producto = ProductoRepository.get_by_id(db, id)
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return producto


@router.post("", response_model=ProductoResponse)
def create_producto(
    payload: ProductoCreate,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.tiene_permiso("puede_gestionar_catalogos"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No cuenta con permiso para registrar productos en el catálogo.",
        )

    data = payload.model_dump(exclude={"empaque_ids", "empaques_config"})
    producto = ProductoRepository.create(
        db,
        data,
        empaque_ids=payload.empaque_ids,
        empaques_config=[item.model_dump() for item in payload.empaques_config] if payload.empaques_config is not None else None,
    )

    AuditoriaService.registrar_evento(
        db=db,
        accion="CREAR_PRODUCTO",
        modulo="CATALOGOS",
        usuario=current_user,
        entidad="Producto",
        entidad_id=producto.id,
        detalles={"nombre": producto.nombre, "categoria": producto.categoria},
        request=request,
    )
    return producto


@router.put("/{id}", response_model=ProductoResponse)
def update_producto(
    id: int,
    payload: ProductoUpdate,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.tiene_permiso("puede_gestionar_catalogos"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No cuenta con permiso para modificar productos del catálogo.",
        )

    data = payload.model_dump(exclude={"empaque_ids", "empaques_config"}, exclude_unset=True)
    producto = ProductoRepository.update(
        db,
        id,
        data,
        empaque_ids=payload.empaque_ids,
        empaques_config=[item.model_dump() for item in payload.empaques_config] if payload.empaques_config is not None else None,
    )
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    AuditoriaService.registrar_evento(
        db=db,
        accion="ACTUALIZAR_PRODUCTO",
        modulo="CATALOGOS",
        usuario=current_user,
        entidad="Producto",
        entidad_id=producto.id,
        detalles={"nombre": producto.nombre},
        request=request,
    )
    return producto


@router.delete("/{id}")
def delete_producto(
    id: int,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.tiene_permiso("puede_gestionar_catalogos"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No cuenta con permiso para eliminar productos del catálogo.",
        )

    ok = ProductoRepository.delete(db, id)
    if not ok:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    AuditoriaService.registrar_evento(
        db=db,
        accion="ELIMINAR_PRODUCTO",
        modulo="CATALOGOS",
        usuario=current_user,
        entidad="Producto",
        entidad_id=id,
        request=request,
    )
    return {"status": "ok", "message": "Producto desactivado correctamente"}
