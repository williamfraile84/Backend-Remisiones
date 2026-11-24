from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.core.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class Sesion(Base):
    __tablename__ = "sesiones"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id", ondelete="SET NULL"), nullable=True, index=True)
    token_jti = Column(String(64), unique=True, index=True, nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    activo = Column(Boolean, default=True, nullable=False, index=True)
    expira_en = Column(DateTime, nullable=False)
    ultimo_acceso = Column(DateTime, default=utc_now, nullable=False)
    creado_en = Column(DateTime, default=utc_now, nullable=False)
    actualizado_en = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)
    eliminado_en = Column(DateTime, nullable=True)

    usuario_rel = relationship("Usuario", foreign_keys=[usuario_id])
    empresa_rel = relationship("Empresa", foreign_keys=[empresa_id])

    __table_args__ = (
        Index("ix_sesiones_usuario_activo", "usuario_id", "activo"),
        Index("ix_sesiones_token_jti_activo", "token_jti", "activo"),
    )

