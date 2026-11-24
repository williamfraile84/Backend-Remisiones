from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.usuario import Usuario, DEFAULT_OPERATOR_PERMISSIONS, DEFAULT_ADMIN_PERMISSIONS


def utc_now():
    return datetime.now(timezone.utc)


class UsuarioRepository:

    @staticmethod
    def get_by_id(db: Session, user_id: int) -> Optional[Usuario]:
        return db.query(Usuario).filter(Usuario.id == user_id).first()

    @staticmethod
    def get_by_username(db: Session, username: str) -> Optional[Usuario]:
        return db.query(Usuario).filter(Usuario.username == username).first()

    @staticmethod
    def get_by_email(db: Session, email: str) -> Optional[Usuario]:
        if not email:
            return None
        return db.query(Usuario).filter(Usuario.email == email).first()

    @staticmethod
    def get_all(db: Session, include_inactive: bool = True) -> List[Usuario]:
        query = db.query(Usuario)
        if not include_inactive:
            query = query.filter(Usuario.activo == True)
        return query.order_by(Usuario.id.asc()).all()

    @staticmethod
    def create(db: Session, data: Dict[str, Any]) -> Usuario:
        rol = data.get("rol", "operador")
        if "permisos" not in data or not data["permisos"]:
            data["permisos"] = DEFAULT_ADMIN_PERMISSIONS.copy() if rol == "admin" else DEFAULT_OPERATOR_PERMISSIONS.copy()
        user = Usuario(**data)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def update(db: Session, user_id: int, data: Dict[str, Any]) -> Optional[Usuario]:
        user = db.query(Usuario).filter(Usuario.id == user_id).first()
        if user:
            for key, value in data.items():
                if value is not None:
                    setattr(user, key, value)
            user.actualizado_en = utc_now()
            db.commit()
            db.refresh(user)
        return user

    @staticmethod
    def set_active_status(db: Session, user_id: int, activo: bool) -> Optional[Usuario]:
        """Baja lógica o reactivación de cuenta."""
        user = db.query(Usuario).filter(Usuario.id == user_id).first()
        if user:
            user.activo = activo
            user.actualizado_en = utc_now()
            db.commit()
            db.refresh(user)
        return user

    @staticmethod
    def update_last_login(db: Session, user_id: int) -> None:
        user = db.query(Usuario).filter(Usuario.id == user_id).first()
        if user:
            user.ultimo_login = utc_now()
            db.commit()

    @staticmethod
    def count_total(db: Session) -> int:
        return db.query(Usuario).count()

    @staticmethod
    def count_admins(db: Session) -> int:
        return db.query(Usuario).filter(Usuario.rol == "admin", Usuario.activo == True).count()
