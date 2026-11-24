from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.core.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class AuditoriaCambio(Base):
    """
    Detalle relacional de cambios y atributos de auditoria (3NF pura).
    Elimina el uso de blobs JSON no estructurados y permite indexacion y consultas analiticas forenses.
    """
    __tablename__ = "auditoria_cambios"

    id = Column(Integer, primary_key=True, index=True)
    auditoria_id = Column(Integer, ForeignKey("auditorias.id", ondelete="CASCADE"), nullable=False, index=True)
    campo = Column(String(100), nullable=False, index=True)
    valor_anterior = Column(Text, nullable=True)
    valor_nuevo = Column(Text, nullable=True)
    tipo_dato = Column(String(20), default="str", nullable=False)
    creado_en = Column(DateTime, default=utc_now, nullable=False)

    auditoria = relationship("Auditoria", back_populates="cambios")

    __table_args__ = (
        Index("ix_auditoria_cambios_auditoria_campo", "auditoria_id", "campo"),
    )
