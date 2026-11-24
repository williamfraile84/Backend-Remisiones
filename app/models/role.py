from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.rol_permiso import rol_permisos
from app.models.permiso import Permiso


def utc_now():
    return datetime.now(timezone.utc)


class Role(Base):
    """
    Catálogo maestro atómico de roles del sistema (3NF).
    Estandariza los perfiles de usuario ('admin', 'operador', etc.).
    Cumple con SRP (Single Responsibility Principle).
    """
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String(50), unique=True, nullable=False, index=True)
    nombre = Column(String(100), nullable=False)
    descripcion = Column(String(255), nullable=True)
    activo = Column(Boolean, default=True, index=True, nullable=False)
    creado_en = Column(DateTime, default=utc_now, nullable=False)
    actualizado_en = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    permisos = relationship("Permiso", secondary=rol_permisos, back_populates="roles")
    usuarios = relationship("Usuario", back_populates="rol_rel")


# Re-exportar para compatibilidad hacia atrás
__all__ = ["Role", "Permiso", "rol_permisos"]

