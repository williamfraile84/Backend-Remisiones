from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.usuario import Usuario
from app.schemas.role import RoleCreate, RoleUpdate, RoleResponse
from app.schemas.permiso import PermisoResponse
from app.services.role_service import RoleService

router = APIRouter(prefix="/roles", tags=["Roles y Permisos RBAC"])


@router.get("", response_model=List[RoleResponse])
def listar_roles(
    activo_only: bool = Query(True, description="Filtrar solo roles activos"),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return RoleService.listar_roles(db, activo_only=activo_only)


@router.get("/permisos", response_model=List[PermisoResponse])
def listar_permisos(
    modulo: Optional[str] = Query(None, description="Filtrar permisos por módulo"),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return RoleService.listar_permisos(db, modulo=modulo)


@router.get("/{role_id}", response_model=RoleResponse)
def obtener_rol(
    role_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rol = RoleService.obtener_rol(db, role_id)
    if not rol:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rol no encontrado")
    return rol


@router.post("", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
def crear_rol(
    payload: RoleCreate,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.tiene_permiso("puede_gestionar_catalogos"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No cuenta con permiso para gestionar roles")
    return RoleService.crear_rol(db, payload.model_dump(exclude={"permiso_ids"}), payload.permiso_ids)


@router.put("/{role_id}", response_model=RoleResponse)
def actualizar_rol(
    role_id: int,
    payload: RoleUpdate,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.tiene_permiso("puede_gestionar_catalogos"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No cuenta con permiso para gestionar roles")
    rol = RoleService.actualizar_rol(db, role_id, payload.model_dump(exclude={"permiso_ids"}, exclude_unset=True), payload.permiso_ids)
    if not rol:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rol no encontrado")
    return rol


@router.delete("/{role_id}", status_code=status.HTTP_200_OK)
def eliminar_rol(
    role_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.tiene_permiso("puede_gestionar_catalogos"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No cuenta con permiso para gestionar roles")
    ok = RoleService.eliminar_rol(db, role_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rol no encontrado")
    return {"status": "ok", "message": "Rol dado de baja exitosamente (Soft Delete)."}

