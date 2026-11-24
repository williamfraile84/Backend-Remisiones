from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from app.models.sesion import Sesion, utc_now


class SesionRepository:

    @staticmethod
    def create(db: Session, data: Dict[str, Any]) -> Sesion:
        sesion = Sesion(**data)
        db.add(sesion)
        db.commit()
        db.refresh(sesion)
        return sesion

    @staticmethod
    def get_by_id(db: Session, sesion_id: int) -> Optional[Sesion]:
        return db.query(Sesion).filter(Sesion.id == sesion_id).first()

    @staticmethod
    def get_by_jti(db: Session, token_jti: str) -> Optional[Sesion]:
        return db.query(Sesion).filter(Sesion.token_jti == token_jti).first()

    @staticmethod
    def get_active_by_jti(db: Session, token_jti: str) -> Optional[Sesion]:
        now = datetime.now(timezone.utc)
        return (
            db.query(Sesion)
            .filter(
                Sesion.token_jti == token_jti,
                Sesion.activo == True,
                Sesion.expira_en > now,
            )
            .first()
        )

    @staticmethod
    def get_active_by_user(db: Session, usuario_id: int) -> List[Sesion]:
        now = datetime.now(timezone.utc)
        return (
            db.query(Sesion)
            .filter(
                Sesion.usuario_id == usuario_id,
                Sesion.activo == True,
                Sesion.expira_en > now,
            )
            .order_by(Sesion.ultimo_acceso.desc())
            .all()
        )

    @staticmethod
    def update_ultimo_acceso(db: Session, token_jti: str) -> Optional[Sesion]:
        sesion = db.query(Sesion).filter(Sesion.token_jti == token_jti, Sesion.activo == True).first()
    def update_ultimo_acceso(
        db: Session,
        token_jti: str,
        sesion_obj: Optional[Sesion] = None,
        min_interval_seconds: int = 60
    ) -> Optional[Sesion]:
        sesion = sesion_obj or db.query(Sesion).filter(Sesion.token_jti == token_jti, Sesion.activo == True).first()
        if sesion:
            sesion.ultimo_acceso = utc_now()
            now = utc_now()
            # Throttling: solo actualizar en base de datos si pasaron más de min_interval_seconds
            if sesion.ultimo_acceso:
                # Normalizar timestamps con o sin timezone para comparación segura
                last = sesion.ultimo_acceso
                if last.tzinfo is None:
                    last = last.replace(tzinfo=timezone.utc)
                diff = (now - last).total_seconds()
                if diff < min_interval_seconds:
                    return sesion

            sesion.ultimo_acceso = now
            db.commit()
            db.refresh(sesion)
        return sesion

    @staticmethod
    def revocar_sesion(db: Session, token_jti: str) -> bool:
        """Realiza baja lógica (soft delete) de la sesión identificada por token_jti."""
        sesion = db.query(Sesion).filter(Sesion.token_jti == token_jti).first()
        if sesion and sesion.activo:
            sesion.activo = False
            sesion.eliminado_en = utc_now()
            db.commit()
            return True
        return False

    @staticmethod
    def revocar_todas_usuario(db: Session, usuario_id: int, except_jti: Optional[str] = None) -> int:
        """Inactiva todas las sesiones de un usuario (exceptuando opcionalmente la actual)."""
        now = utc_now()
        query = db.query(Sesion).filter(Sesion.usuario_id == usuario_id, Sesion.activo == True)
        if except_jti:
            query = query.filter(Sesion.token_jti != except_jti)
        
        sesiones = query.all()
        count = len(sesiones)
        for s in sesiones:
            s.activo = False
            s.eliminado_en = now
        
        if count > 0:
            db.commit()
        return count

    @staticmethod
    def contar_activas(db: Session, usuario_id: int) -> int:
        now = datetime.now(timezone.utc)
        return (
            db.query(Sesion)
            .filter(
                Sesion.usuario_id == usuario_id,
                Sesion.activo == True,
                Sesion.expira_en > now,
            )
            .count()
        )

