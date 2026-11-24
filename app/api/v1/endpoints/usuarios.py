from typing import List
from fastapi import APIRouter, Depends, Request, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_admin
from app.models.usuario import Usuario
from app.schemas.usuario import (
    UsuarioCreate,
    UsuarioUpdate,
    UsuarioResponse,
    UsuarioStatusUpdate,
    ResetPasswordRequest,
)
from app.repositories.usuario_repository import UsuarioRepository
from app.services.auth_service import AuthService
from app.services.auditoria_service import AuditoriaService

router = APIRouter(prefix="/usuarios", tags=["Gestión de Usuarios (Admin)"])


@router.get("", response_model=List[UsuarioResponse])
def list_usuarios(
    admin: Usuario = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Lista todos los usuarios (activos e inactivos) del sistema. Exclusivo para administradores."""
    return UsuarioRepository.get_all(db, include_inactive=True)


@router.post("", response_model=UsuarioResponse)
def create_usuario(
    payload: UsuarioCreate,
    request: Request,
    admin: Usuario = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Crea un nuevo usuario con rol y permisos configurables. Exclusivo para administradores."""
    nuevo_usuario = AuthService.crear_usuario(
        db=db,
        username=payload.username,
        nombre_completo=payload.nombre_completo,
        password=payload.password,
        email=payload.email,
        rol=payload.rol or "operador",
        permisos=payload.permisos,
    )

    AuditoriaService.registrar_evento(
        db=db,
        accion="CREAR_USUARIO",
        modulo="USUARIOS",
        usuario=admin,
        entidad="Usuario",
        entidad_id=nuevo_usuario.id,
        detalles={
            "nuevo_username": nuevo_usuario.username,
            "nombre_completo": nuevo_usuario.nombre_completo,
            "rol": nuevo_usuario.rol,
            "permisos": nuevo_usuario.permisos,
        },
        request=request,
    )

    return nuevo_usuario


@router.put("/{id}", response_model=UsuarioResponse)
def update_usuario(
    id: int,
    payload: UsuarioUpdate,
    request: Request,
    admin: Usuario = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Edita datos, rol o permisos de un usuario existente. Exclusivo para administradores."""
    usuario_actualizado = AuthService.actualizar_usuario(
        db=db,
        user_id=id,
        nombre_completo=payload.nombre_completo,
        email=payload.email,
        rol=payload.rol,
        permisos=payload.permisos,
        activo=payload.activo,
    )

    AuditoriaService.registrar_evento(
        db=db,
        accion="EDITAR_USUARIO",
        modulo="USUARIOS",
        usuario=admin,
        entidad="Usuario",
        entidad_id=id,
        detalles={
            "username": usuario_actualizado.username,
            "cambios": payload.model_dump(exclude_unset=True),
        },
        request=request,
    )

    return usuario_actualizado


@router.patch("/{id}/status", response_model=UsuarioResponse)
def toggle_usuario_status(
    id: int,
    payload: UsuarioStatusUpdate,
    request: Request,
    admin: Usuario = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Activa o desactiva (Baja Lógica) una cuenta de usuario sin eliminar físicamente registros."""
    usuario_modificado = AuthService.actualizar_usuario(
        db=db,
        user_id=id,
        activo=payload.activo,
    )

    accion = "ACTIVAR_USUARIO" if payload.activo else "DESACTIVAR_USUARIO"
    AuditoriaService.registrar_evento(
        db=db,
        accion=accion,
        modulo="USUARIOS",
        usuario=admin,
        entidad="Usuario",
        entidad_id=id,
        detalles={
            "username": usuario_modificado.username,
            "nuevo_estado_activo": payload.activo,
            "tipo_operacion": "baja_logica" if not payload.activo else "reactivacion",
        },
        request=request,
    )

    return usuario_modificado


@router.post("/{id}/reset-password")
def reset_password(
    id: int,
    payload: ResetPasswordRequest,
    request: Request,
    admin: Usuario = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Restablece la contraseña de un usuario por parte del administrador."""
    target_user = UsuarioRepository.get_by_id(db, id)
    if not target_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    AuthService.reset_password_admin(db, id, payload.new_password)

    AuditoriaService.registrar_evento(
        db=db,
        accion="RESET_PASSWORD_ADMIN",
        modulo="USUARIOS",
        usuario=admin,
        entidad="Usuario",
        entidad_id=id,
        detalles={"target_username": target_user.username},
        request=request,
    )

    return {"status": "ok", "message": f"Contraseña del usuario {target_user.username} restablecida con éxito"}

