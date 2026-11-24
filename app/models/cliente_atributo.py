from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from app.core.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class ClienteAtributo(Base):
    """
    Atributos dinamicos relacionales para clientes (3NF).
    Reemplaza campos_extra JSON asegurando atomicidad y consultas estructuradas.
    """
    __tablename__ = "cliente_atributos"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False)
    clave = Column(String(100), nullable=False, index=True)
    valor = Column(Text, nullable=False)
    creado_en = Column(DateTime, default=utc_now, nullable=False)

    cliente = relationship("Cliente", back_populates="atributos")

    __table_args__ = (
        UniqueConstraint("cliente_id", "clave", name="uq_cliente_atributos_cliente_clave"),
        Index("ix_cliente_atributos_cliente_clave", "cliente_id", "clave"),
    )
