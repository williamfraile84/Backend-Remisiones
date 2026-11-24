from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, CheckConstraint, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from app.core.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class ConceptoGasto(Base):
    """
    Catalogo maestro de conceptos de gastos operativos, logisticos y administrativos.
    Permite parametrizar si se distribuye por defecto en los costos de los productos.
    """
    __tablename__ = "conceptos_gasto"

    id = Column(Integer, primary_key=True, index=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id", ondelete="CASCADE"), nullable=True, index=True)
    codigo = Column(String(50), nullable=True)
    nombre = Column(String(100), nullable=False, index=True)
    tipo = Column(String(50), default="OPERATIVO", nullable=False)  # OPERATIVO, LOGISTICO, ADMINISTRATIVO, OTRO
    distribuir_por_defecto = Column(Boolean, default=True, nullable=False)
    activo = Column(Boolean, default=True, index=True, nullable=False)
    creado_en = Column(DateTime, default=utc_now, nullable=False)
    actualizado_en = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    empresa = relationship("Empresa", foreign_keys=[empresa_id])

    __table_args__ = (
        CheckConstraint("tipo IN ('OPERATIVO', 'LOGISTICO', 'TRANSPORTE', 'ADMINISTRATIVO', 'OTRO')", name="chk_concepto_gasto_tipo"),
        UniqueConstraint("nombre", name="uq_conceptos_gasto_nombre"),
        Index("ix_conceptos_gasto_activo_nombre", "activo", "nombre"),
        Index("ix_conceptos_gasto_empresa_activo_nombre", "empresa_id", "activo", "nombre"),
    )
