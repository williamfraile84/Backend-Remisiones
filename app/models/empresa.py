from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from app.core.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class Empresa(Base):
    __tablename__ = "empresas"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(255), nullable=False)
    nit = Column(String(100), nullable=False, index=True)
    direccion = Column(Text, nullable=True)
    telefono = Column(String(100), nullable=True)
    email = Column(String(150), nullable=True)
    logo_path = Column(String(500), nullable=True)
    activo = Column(Boolean, default=True, nullable=False, index=True)
    creado_en = Column(DateTime, default=utc_now, nullable=False)
    actualizado_en = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    atributos = relationship("EmpresaAtributo", back_populates="empresa", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("nit", name="uq_empresas_nit"),
    )

    @property
    def campos_extra(self):
        return [{"id": str(a.id), "clave": a.clave, "valor": a.valor} for a in (self.atributos or [])]

    @campos_extra.setter
    def campos_extra(self, val):
        pass
