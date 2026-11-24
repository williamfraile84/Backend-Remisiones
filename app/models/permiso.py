from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.rol_permiso import rol_permisos


def utc_now():
    return datetime.now(timezone.utc)


class Permiso(Base):
    """
    Catálogo maestro atómico de permisos granulares del sistema (3NF estricta).
    Vinculado formalmente a la entidad Modulo (modulos.id) cumpliendo con 3FN y SRP.
    """
    __tablename__ = "permisos"

    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String(100), unique=True, nullable=False, index=True)
    nombre = Column(String(150), nullable=False)
    modulo_id = Column(Integer, ForeignKey("modulos.id", ondelete="CASCADE"), nullable=False, index=True)
    descripcion = Column(String(255), nullable=True)
    activo = Column(Boolean, default=True, index=True, nullable=False)
    creado_en = Column(DateTime, default=utc_now, nullable=False)

    modulo_rel = relationship("Modulo", back_populates="permisos")
    roles = relationship("Role", secondary=rol_permisos, back_populates="permisos")

    @property
    def modulo(self) -> str:
        return self.modulo_rel.codigo if self.modulo_rel else ""
