from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from app.core.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class Modulo(Base):
    """
    Catálogo maestro atómico de módulos funcionales del sistema (3NF estricta).
    Normaliza el campo 'modulo' presente en permisos y auditoría eliminando redundancias de texto.
    Cumple con el Principio de Responsabilidad Única (SRP).
    """
    __tablename__ = "modulos"

    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String(50), unique=True, nullable=False, index=True)
    nombre = Column(String(100), nullable=False)
    descripcion = Column(String(255), nullable=True)
    activo = Column(Boolean, default=True, index=True, nullable=False)
    creado_en = Column(DateTime, default=utc_now, nullable=False)

    permisos = relationship("Permiso", back_populates="modulo_rel", cascade="all, delete-orphan")

