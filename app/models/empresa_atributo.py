from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from app.core.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class EmpresaAtributo(Base):
    """
    Atributos dinamicos relacionales para la empresa (3NF).
    Reemplaza campos_extra JSON asegurando atomicidad y consultas estructuradas.
    """
    __tablename__ = "empresa_atributos"

    id = Column(Integer, primary_key=True, index=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False)
    clave = Column(String(100), nullable=False, index=True)
    valor = Column(Text, nullable=False)
    creado_en = Column(DateTime, default=utc_now, nullable=False)

    empresa = relationship("Empresa", back_populates="atributos")

    __table_args__ = (
        UniqueConstraint("empresa_id", "clave", name="uq_empresa_atributos_empresa_clave"),
        Index("ix_empresa_atributos_empresa_clave", "empresa_id", "clave"),
    )
