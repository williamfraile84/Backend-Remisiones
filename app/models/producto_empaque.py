from sqlalchemy import Column, Integer, ForeignKey, Table, Index, Numeric
from sqlalchemy.orm import relationship
from app.core.database import Base

producto_empaques = Table(
    "producto_empaques",
    Base.metadata,
    Column("producto_id", Integer, ForeignKey("productos.id", ondelete="CASCADE"), primary_key=True),
    Column("tipo_empaque_id", Integer, ForeignKey("tipos_empaque.id", ondelete="CASCADE"), primary_key=True),
    Column("peso_kg", Numeric(10, 2), nullable=True),
    Index("ix_producto_empaques_tipo_id", "tipo_empaque_id"),
)


class ProductoEmpaque(Base):
    __table__ = producto_empaques

    producto = relationship("Producto", back_populates="empaques_rel")
    tipo_empaque = relationship("TipoEmpaque")

