from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Numeric, Boolean, DateTime, ForeignKey, CheckConstraint, Index
from sqlalchemy.orm import relationship
from app.core.database import Base


def utc_now():
    return datetime.now(timezone.utc)


def redondear_centena(valor: float) -> float:
    if valor is None:
        return 0.0
    return round(float(valor) / 100.0) * 100.0


class PedidoItem(Base):
    """
    Línea de detalle relacional de un pedido (3NF estricta).
    Desacopla la unidad de medida del contenedor de empaque y elimina columnas redundantes
    o derivadas (valor_compra_total y valor_total_venta son @property calculadas dinámicamente).
    """
    __tablename__ = "pedido_items"

    id = Column(Integer, primary_key=True, index=True)
    pedido_id = Column(Integer, ForeignKey("pedidos.id", ondelete="CASCADE"), nullable=False)
    producto_id = Column(Integer, ForeignKey("productos.id", ondelete="SET NULL"), nullable=True, index=True)
    cantidad = Column(Numeric(12, 3, asdecimal=False), nullable=False, default=1.0)
    unidad_medida_id = Column(Integer, ForeignKey("unidades_medida.id", ondelete="SET NULL"), nullable=True)
    tipo_empaque_id = Column(Integer, ForeignKey("tipos_empaque.id", ondelete="SET NULL"), nullable=True)
    precio_costo_unitario = Column(Numeric(14, 2, asdecimal=False), default=0.0, nullable=False)
    precio_venta_unitario = Column(Numeric(14, 2, asdecimal=False), default=0.0, nullable=False)
    peso_neto = Column(Numeric(12, 3, asdecimal=False), default=0.0, nullable=False)
    porcentaje_utilidad = Column(Numeric(6, 2, asdecimal=False), default=30.0, nullable=False)
    costo_real_kilo = Column(Numeric(14, 2, asdecimal=False), default=0.0, nullable=False)
    gasto_asignado_kilo = Column(Numeric(14, 2, asdecimal=False), default=0.0, nullable=False)
    precio_venta_manual = Column(Boolean, default=False, nullable=False)
    surtido = Column(Boolean, default=False, nullable=False)
    producto_nombre = Column(String(200), nullable=True)
    notas = Column(String(255), nullable=True)
    activo = Column(Boolean, default=True, index=True, nullable=False)
    orden = Column(Integer, default=0, nullable=False)
    creado_en = Column(DateTime, default=utc_now, nullable=False)
    actualizado_en = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    pedido = relationship("Pedido", back_populates="items")
    producto = relationship("Producto", foreign_keys=[producto_id])
    unidad_medida = relationship("UnidadMedida", foreign_keys=[unidad_medida_id])
    tipo_empaque = relationship("TipoEmpaque", foreign_keys=[tipo_empaque_id])

    # =========================================================================
    # PROPIEDADES CALCULADAS DINÁMICAMENTE (3NF ESTRICTA - CERO REDUNDANCIA)
    # =========================================================================
    @property
    def descripcion_historica(self) -> str:
        """Nombre del producto derivado de la relación directa (3NF) o texto guardado."""
        if self.producto:
            return self.producto.nombre
        return self.producto_nombre or self.notas or "Producto"

    @descripcion_historica.setter
    def descripcion_historica(self, val: str):
        if not self.notas and val:
            self.notas = val
        if val:
            self.producto_nombre = val

    @property
    def valor_compra_total(self) -> float:
        cant_kilos = float(self.peso_neto if (self.peso_neto and self.peso_neto > 0) else (self.cantidad or 0.0))
        return redondear_centena(cant_kilos * float(self.precio_costo_unitario or 0.0))

    @valor_compra_total.setter
    def valor_compra_total(self, val):
        pass

    @property
    def valor_total_venta(self) -> float:
        cant_kilos = float(self.peso_neto if (self.peso_neto and self.peso_neto > 0) else (self.cantidad or 0.0))
        return redondear_centena(cant_kilos * float(self.precio_venta_unitario or 0.0))

    @valor_total_venta.setter
    def valor_total_venta(self, val):
        pass

    # Propiedades de compatibilidad para esquemas
    @property
    def peso_bruto(self) -> float:
        return float(self.peso_neto or 0.0)

    @peso_bruto.setter
    def peso_bruto(self, val):
        pass

    @property
    def tara(self) -> float:
        return 0.0

    @tara.setter
    def tara(self, val):
        pass

    __table_args__ = (
        CheckConstraint("cantidad >= 0", name="chk_pedido_item_cantidad_positiva"),
        CheckConstraint("precio_costo_unitario >= 0", name="chk_pedido_item_costo_positivo"),
        CheckConstraint("precio_venta_unitario >= 0", name="chk_pedido_item_venta_positiva"),
        CheckConstraint("peso_neto >= 0", name="chk_pedido_item_peso_neto_positivo"),
        Index("ix_pedido_items_pedido_orden", "pedido_id", "orden"),
        Index("ix_pedido_items_pedido_activo", "pedido_id", "activo"),
    )
