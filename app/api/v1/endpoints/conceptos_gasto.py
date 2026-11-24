from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.usuario import Usuario
from app.schemas.concepto_gasto import ConceptoGastoCreate, ConceptoGastoUpdate, ConceptoGastoResponse
from app.repositories.concepto_gasto_repository import ConceptoGastoRepository
from app.services.auditoria_service import AuditoriaService

router = APIRouter(prefix="/conceptos-gasto", tags=["Conceptos de Gasto"])


@router.get("", response_model=List[ConceptoGastoResponse])
def get_conceptos_gasto(empresa_id: Optional[int] = None, db: Session = Depends(get_db)):
    return ConceptoGastoRepository.get_all(db, empresa_id=empresa_id)


@router.post("", response_model=ConceptoGastoResponse)
def create_concepto_gasto(
    payload: ConceptoGastoCreate,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.tiene_permiso("puede_gestionar_catalogos"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No cuenta con permiso para gestionar conceptos de gasto.",
        )

    concepto = ConceptoGastoRepository.create(db, payload.model_dump())

    AuditoriaService.registrar_evento(
        db=db,
        accion="CREAR_CONCEPTO_GASTO",
        modulo="CATALOGOS",
        usuario=current_user,
        entidad="ConceptoGasto",
        entidad_id=concepto.id,
        detalles={"nombre": concepto.nombre, "tipo": concepto.tipo},
        request=request,
    )
    return concepto


@router.put("/{id}", response_model=ConceptoGastoResponse)
def update_concepto_gasto(
    id: int,
    payload: ConceptoGastoUpdate,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.tiene_permiso("puede_gestionar_catalogos"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No cuenta con permiso para modificar conceptos de gasto.",
        )

    concepto = ConceptoGastoRepository.update(db, id, payload.model_dump(exclude_unset=True))
    if not concepto:
        raise HTTPException(status_code=404, detail="Concepto de gasto no encontrado")

    AuditoriaService.registrar_evento(
        db=db,
        accion="ACTUALIZAR_CONCEPTO_GASTO",
        modulo="CATALOGOS",
        usuario=current_user,
        entidad="ConceptoGasto",
        entidad_id=concepto.id,
        detalles={"nombre": concepto.nombre, "tipo": concepto.tipo},
        request=request,
    )
    return concepto


@router.delete("/{id}")
def delete_concepto_gasto(
    id: int,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.tiene_permiso("puede_gestionar_catalogos"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No cuenta con permiso para eliminar conceptos de gasto.",
        )

    ok = ConceptoGastoRepository.delete(db, id)
    if not ok:
        raise HTTPException(status_code=404, detail="Concepto de gasto no encontrado")

    AuditoriaService.registrar_evento(
        db=db,
        accion="ELIMINAR_CONCEPTO_GASTO",
        modulo="CATALOGOS",
        usuario=current_user,
        entidad="ConceptoGasto",
        entidad_id=id,
        request=request,
    )
    return {"status": "ok", "message": "Concepto de gasto desactivado correctamente"}
