from typing import Optional, Callable
from fastapi import Depends, HTTPException, status, Header, Request, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.usuario import Usuario
from app.repositories.usuario_repository import UsuarioRepository


from app.core.config import settings
from app.repositories.sesion_repository import SesionRepository


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
    token_query: Optional[str] = Query(None, alias="token"),
) -> Usuario:
    """
    Extrae el token Bearer del encabezado Authorization o del parámetro de consulta 'token',
    valida el JWT y retorna el usuario activo.
    valida el JWT, comprueba el estado activo de la sesión en DB y retorna el usuario activo.
    """
    raw_token = None
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            raw_token = parts[1]
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Formato de token de autorización inválido. Use 'Bearer <token>'.",
                headers={"WWW-Authenticate": "Bearer"},
            )
    elif token_query:
        raw_token = token_query.strip()

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticación requerida. Inicie sesión para continuar.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(raw_token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de acceso inválido o expirado. Inicie sesión nuevamente.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = int(payload["sub"])
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token corrupto o usuario inválido.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validar persistencia de sesión en DB si está habilitada y el token posee JTI
    token_jti = payload.get("jti")
    request.state.token_jti = token_jti
    request.state.raw_token = raw_token

    if settings.ENFORCE_DB_SESSION_VALIDATION and token_jti:
        sesion = SesionRepository.get_active_by_jti(db, token_jti)
        if not sesion:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Sesión cerrada, revocada o no encontrada. Inicie sesión nuevamente.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Validar expiración por inactividad si está configurada
        if settings.SESSION_INACTIVITY_TIMEOUT_MINUTES:
            from datetime import datetime, timezone, timedelta
            limite_inactividad = sesion.ultimo_acceso + timedelta(minutes=settings.SESSION_INACTIVITY_TIMEOUT_MINUTES)
            if datetime.now(timezone.utc) > limite_inactividad:
                SesionRepository.revocar_sesion(db, token_jti)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Sesión expirada por inactividad. Inicie sesión nuevamente.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        
        # Actualizar timestamp de último acceso
        SesionRepository.update_ultimo_acceso(db, token_jti)
        # Actualizar timestamp de último acceso con throttling
        SesionRepository.update_ultimo_acceso(db, token_jti, sesion_obj=sesion)

    user = UsuarioRepository.get_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El usuario asociado a la sesión ya no existe.",
        )

    if not user.activo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Su cuenta ha sido desactivada. Contacte al administrador.",
        )

    return user


def get_optional_current_user(
    request: Request,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
    token_query: Optional[str] = Query(None, alias="token"),
) -> Optional[Usuario]:
    """Retorna el usuario si el token es provisto y válido; de lo contrario retorna None sin lanzar excepción."""
    raw_token = None
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            raw_token = parts[1]
    elif token_query:
        raw_token = token_query.strip()

    if not raw_token:
        return None

    try:
        payload = decode_access_token(raw_token)
        if payload and "sub" in payload:
            token_jti = payload.get("jti")
            if settings.ENFORCE_DB_SESSION_VALIDATION and token_jti:
                sesion = SesionRepository.get_active_by_jti(db, token_jti)
                if not sesion:
                    return None
            user_id = int(payload["sub"])
            user = UsuarioRepository.get_by_id(db, user_id)
            if user and user.activo:
                return user
    except Exception:
        pass
    return None


def get_current_admin(current_user: Usuario = Depends(get_current_user)) -> Usuario:
    """Verifica que el usuario actual tenga rol de Administrador."""
    if current_user.rol != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso restringido: Se requieren privilegios de Administrador para esta acción.",
        )
    return current_user


def require_permission(permission_key: str) -> Callable[[Usuario], Usuario]:
    """Factory de dependencias para verificar permisos granulares."""
    def permission_checker(current_user: Usuario = Depends(get_current_user)) -> Usuario:
        if not current_user.tiene_permiso(permission_key):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permiso denegado: No cuenta con el permiso requerido ({permission_key}).",
            )
        return current_user

    return permission_checker


def resolve_empresa_id(
    db: Session,
    request: Optional[Request] = None,
    current_user: Optional[Usuario] = None,
    explicit_id: Optional[int] = None,
) -> Optional[int]:
    """
    Resuelve el ID de la empresa activa con la siguiente precedencia:
    1. explicit_id (si es provisto y válido)
    2. Header 'X-Empresa-Id' de la petición HTTP
    3. current_user.empresa_id (si el usuario está vinculado a una empresa)
    4. Primera empresa activa en base de datos (fallback)
    """
    from app.models.empresa import Empresa

    if explicit_id:
        return explicit_id

    if request:
        header_val = request.headers.get("X-Empresa-Id")
        if header_val:
            try:
                val = int(header_val)
                if val > 0:
                    return val
            except (ValueError, TypeError):
                pass

    if current_user and current_user.empresa_id:
        return current_user.empresa_id

    empresa_activa = db.query(Empresa).filter(Empresa.activo == True).first()
    if empresa_activa:
        return empresa_activa.id

    return None
