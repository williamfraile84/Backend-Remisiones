from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user, resolve_empresa_id
from app.models.cliente import Cliente
from app.models.usuario import Usuario
from app.schemas.cliente import ClienteCreate, ClienteResponse
from app.services.auditoria_service import AuditoriaService

router = APIRouter(prefix="/clientes", tags=["Clientes"])


@router.get("", response_model=List[ClienteResponse])
def get_clientes(
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    emp_id = resolve_empresa_id(db, request=request, current_user=current_user)
    query = db.query(Cliente).filter(Cliente.activo == True)
    if emp_id:
        # Filtrar por empresa o clientes globales
        query = query.filter((Cliente.empresa_id == emp_id) | (Cliente.empresa_id == None))
    return query.order_by(Cliente.razon_social.asc()).all()


@router.post("", response_model=ClienteResponse)
def save_cliente(
    payload: ClienteCreate,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.tiene_permiso("puede_gestionar_clientes"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No cuenta con permiso para registrar o editar clientes.",
        )

    empresa_id = resolve_empresa_id(db, request=request, current_user=current_user)
    es_edicion = bool(payload.id)

    if payload.id:
        cliente = db.query(Cliente).filter(Cliente.id == payload.id).first()
        if not cliente:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")
        for k, v in payload.model_dump(exclude_unset=True).items():
            setattr(cliente, k, v)
        if not cliente.empresa_id and empresa_id:
            cliente.empresa_id = empresa_id
    else:
        # Validar si ya existe por NIT
        existente = db.query(Cliente).filter(Cliente.nit == payload.nit, Cliente.activo == True).first()
        if existente:
            es_edicion = True
            for k, v in payload.model_dump(exclude={"id"}).items():
                setattr(existente, k, v)
            if not existente.empresa_id and empresa_id:
                existente.empresa_id = empresa_id
            cliente = existente
        else:
            data = payload.model_dump(exclude={"id"})
            if not data.get("empresa_id"):
                data["empresa_id"] = empresa_id
            cliente = Cliente(**data)
            db.add(cliente)

    db.commit()
    db.refresh(cliente)

    AuditoriaService.registrar_evento(
        db=db,
        accion="EDITAR_CLIENTE" if es_edicion else "CREAR_CLIENTE",
        modulo="CLIENTES",
        usuario=current_user,
        entidad="Cliente",
        entidad_id=cliente.id,
        detalles={
            "razon_social": cliente.razon_social,
            "nit": cliente.nit,
            "empresa_id": cliente.empresa_id,
            "consecutivo_actual": cliente.consecutivo_remision_actual,
        },
        request=request,
    )

    return cliente
