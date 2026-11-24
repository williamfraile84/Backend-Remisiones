from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.usuario import Usuario
from app.schemas.unidad_medida import UnidadMedidaCreate, UnidadMedidaUpdate, UnidadMedidaResponse
from app.repositories.unidad_medida_repository import UnidadMedidaRepository
from app.services.auditoria_service import AuditoriaService

router = APIRouter(prefix="/unidades-medida", tags=["Unidades de Medida"])


@router.get("", response_model=List[UnidadMedidaResponse])
def get_unidades_medida(db: Session = Depends(get_db)):
    # Auto-sembrar si está vacío
    UnidadMedidaRepository.seed_default_units_if_empty(db)
    return UnidadMedidaRepository.get_all(db)


@router.post("", response_model=UnidadMedidaResponse)
def create_unidad_medida(
    payload: UnidadMedidaCreate,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.tiene_permiso("puede_gestionar_catalogos"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No cuenta con permiso para gestionar unidades de medida.",
        )

    existente = UnidadMedidaRepository.get_by_codigo(db, payload.codigo)
    if existente:
        raise HTTPException(status_code=400, detail=f"Ya existe una unidad con el código '{payload.codigo}'")

    unidad = UnidadMedidaRepository.create(db, payload.model_dump())

    AuditoriaService.registrar_evento(
        db=db,
        accion="CREAR_UNIDAD_MEDIDA",
        modulo="CATALOGOS",
        usuario=current_user,
        entidad="UnidadMedida",
        entidad_id=unidad.id,
        detalles={"codigo": unidad.codigo, "nombre": unidad.nombre},
        request=request,
    )
    return unidad


@router.put("/{id}", response_model=UnidadMedidaResponse)
def update_unidad_medida(
    id: int,
    payload: UnidadMedidaUpdate,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.tiene_permiso("puede_gestionar_catalogos"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No cuenta con permiso para modificar unidades de medida.",
        )

    unidad = UnidadMedidaRepository.update(db, id, payload.model_dump(exclude_unset=True))
    if not unidad:
        raise HTTPException(status_code=404, detail="Unidad de medida no encontrada")

    AuditoriaService.registrar_evento(
        db=db,
        accion="ACTUALIZAR_UNIDAD_MEDIDA",
        modulo="CATALOGOS",
        usuario=current_user,
        entidad="UnidadMedida",
        entidad_id=unidad.id,
        detalles={"codigo": unidad.codigo, "nombre": unidad.nombre},
        request=request,
    )
    return unidad


@router.delete("/{id}")
def delete_unidad_medida(
    id: int,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.tiene_permiso("puede_gestionar_catalogos"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No cuenta con permiso para eliminar unidades de medida.",
        )

    ok = UnidadMedidaRepository.delete(db, id)
    if not ok:
        raise HTTPException(status_code=404, detail="Unidad de medida no encontrada")

    AuditoriaService.registrar_evento(
        db=db,
        accion="ELIMINAR_UNIDAD_MEDIDA",
        modulo="CATALOGOS",
        usuario=current_user,
        entidad="UnidadMedida",
        entidad_id=id,
        request=request,
    )
    return {"status": "ok", "message": "Unidad de medida desactivada correctamente"}
