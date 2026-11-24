from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Numeric, Boolean, DateTime, ForeignKey, CheckConstraint, Index
from sqlalchemy.orm import relationship
from app.core.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class PedidoGasto(Base):
    """
    Registro relacional de gastos operativos aplicados a un pedido (3NF pura).
    Vinculado formalmente a un concepto de gasto estandarizado y bandera de prorrateo por kilo.
    """
    __tablename__ = "pedido_gastos"

    id = Column(Integer, primary_key=True, index=True)
    pedido_id = Column(Integer, ForeignKey("pedidos.id", ondelete="CASCADE"), nullable=False)
    concepto_gasto_id = Column(Integer, ForeignKey("conceptos_gasto.id", ondelete="SET NULL"), nullable=True, index=True)
    descripcion = Column(String(255), nullable=False)
    monto = Column(Numeric(14, 2, asdecimal=False), nullable=False, default=0.0)
    distribuir_en_costo = Column(Boolean, default=True, nullable=False)
    activo = Column(Boolean, default=True, index=True, nullable=False)
    creado_en = Column(DateTime, default=utc_now, nullable=False)
    actualizado_en = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    pedido = relationship("Pedido", back_populates="gastos_rel")
    concepto = relationship("ConceptoGasto", foreign_keys=[concepto_gasto_id])

    __table_args__ = (
        CheckConstraint("monto >= 0", name="chk_pedido_gasto_monto_positivo"),
        Index("ix_pedido_gastos_pedido_distribuir", "pedido_id", "distribuir_en_costo"),
        Index("ix_pedido_gastos_pedido_activo", "pedido_id", "activo"),
    )
