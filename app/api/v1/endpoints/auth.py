from fastapi import APIRouter, Depends, Request, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.usuario import Usuario
from app.schemas.auth import (
    LoginRequest,
    TokenResponse,
    UserSessionResponse,
    ChangePasswordRequest,
    InitialAdminSetupRequest,
)
from app.services.auth_service import AuthService
from app.services.auditoria_service import AuditoriaService
from app.repositories.usuario_repository import UsuarioRepository

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.get("/setup-status")
def get_setup_status(db: Session = Depends(get_db)):
    """Verifica si el sistema ya cuenta con administradores o usuarios registrados."""
    total = UsuarioRepository.count_total(db)
    admins = UsuarioRepository.count_admins(db)
    return {
        "needs_initial_admin": total == 0 or admins == 0,
        "total_users": total,
        "total_admins": admins,
    }


@router.post("/setup-initial-admin", response_model=TokenResponse)
def setup_initial_admin(
    payload: InitialAdminSetupRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Crea el primer administrador del sistema si no existe ninguno."""
    total_users = UsuarioRepository.count_total(db)
    total_admins = UsuarioRepository.count_admins(db)
    if total_users > 0 and total_admins > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El sistema ya cuenta con un administrador configurado.",
        )

    admin = AuthService.crear_usuario(
        db=db,
        username=payload.username,
        nombre_completo=payload.nombre_completo,
        email=payload.email,
        password=payload.password,
        rol="admin",
    )

    # Auditar creación inicial
    AuditoriaService.registrar_evento(
        db=db,
        accion="SETUP_INICIAL_ADMIN",
        modulo="AUTENTICACION",
        usuario=admin,
        entidad="Usuario",
        entidad_id=admin.id,
        detalles={"username": admin.username, "rol": "admin"},
        request=request,
    )

    token_data = AuthService.generar_token_acceso(admin, db=db, request=request)
    return token_data


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Inicia sesión, retorna el token JWT persistido en DB y registra el evento en auditoría."""
    user = AuthService.autenticar_usuario(db, payload.username, payload.password)

    AuditoriaService.registrar_evento(
        db=db,
        accion="LOGIN",
        modulo="AUTENTICACION",
        usuario=user,
        entidad="Usuario",
        entidad_id=user.id,
        detalles={"username": user.username, "rol": user.rol},
        request=request,
    )

    return AuthService.generar_token_acceso(user, db=db, request=request)


@router.get("/me", response_model=UserSessionResponse)
def get_me(current_user: Usuario = Depends(get_current_user)):
    """Retorna la información del usuario en sesión activa."""
    return UserSessionResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        nombre_completo=current_user.nombre_completo,
        rol=current_user.rol,
        permisos=current_user.permisos or {},
        activo=current_user.activo,
    )


@router.post("/logout")
def logout(
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cierra la sesión activa actual, invalidando el token en la base de datos (soft-delete)."""
    token_jti = getattr(request.state, "token_jti", None)
    if token_jti:
        AuthService.revocar_sesion(db, token_jti)

    AuditoriaService.registrar_evento(
        db=db,
        accion="LOGOUT",
        modulo="AUTENTICACION",
        usuario=current_user,
        entidad="Usuario",
        entidad_id=current_user.id,
        detalles={"username": current_user.username, "jti": token_jti},
        request=request,
    )

    return {"status": "ok", "message": "Sesión cerrada correctamente"}


@router.get("/sesiones")
def get_sesiones_activas(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retorna la lista de sesiones activas del usuario actual."""
    from app.repositories.sesion_repository import SesionRepository
    from app.schemas.sesion import SesionResponse, SesionesListResponse

    activas = SesionRepository.get_active_by_user(db, current_user.id)
    return {
        "total_activas": len(activas),
        "sesiones": [
            {
                "id": s.id,
                "usuario_id": s.usuario_id,
                "empresa_id": s.empresa_id,
                "token_jti": s.token_jti,
                "ip_address": s.ip_address,
                "user_agent": s.user_agent,
                "activo": s.activo,
                "expira_en": s.expira_en.isoformat() if s.expira_en else None,
                "ultimo_acceso": s.ultimo_acceso.isoformat() if s.ultimo_acceso else None,
                "creado_en": s.creado_en.isoformat() if s.creado_en else None,
            }
            for s in activas
        ],
    }


@router.post("/logout-all")
def logout_all_sessions(
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Inactiva todas las demás sesiones del usuario."""
    token_jti = getattr(request.state, "token_jti", None)
    revocadas = AuthService.revocar_todas_sesiones_usuario(db, current_user.id, except_jti=token_jti)
    return {"status": "ok", "message": f"{revocadas} sesiones inactivadas"}


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Permite al usuario autenticado cambiar su propia contraseña."""
    AuthService.cambiar_password(
        db=db,
        user_id=current_user.id,
        current_pass=payload.current_password,
        new_pass=payload.new_password,
    )

    AuditoriaService.registrar_evento(
        db=db,
        accion="CAMBIO_PASSWORD_PROPIO",
        modulo="AUTENTICACION",
        usuario=current_user,
        entidad="Usuario",
        entidad_id=current_user.id,
        detalles={"motivo": "Autogestión de credenciales"},
        request=request,
    )

    return {"status": "ok", "message": "Contraseña actualizada correctamente"}

