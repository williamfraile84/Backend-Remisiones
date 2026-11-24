from datetime import datetime, timezone
from typing import List, Dict, Any
from sqlalchemy import Column, Integer, String, Text, Boolean, Numeric, DateTime, ForeignKey, Index, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import relationship
from app.core.database import Base


def utc_now():
    return datetime.now(timezone.utc)


def redondear_centena(valor: float) -> float:
    """Redondea un valor numerico al 100 mas cercano (regla de negocio Fruver)."""
    if valor is None:
        return 0.0
    return round(float(valor) / 100.0) * 100.0


class Pedido(Base):
    """
    Cabecera del Pedido / Remision (3NF Estricta).
    Almacena unicamente hechos atomicos de cabecera. CERO columnas JSON de negocio y CERO
    totales quemados redundantes. Todos los agregados financieros se calculan dinamicamente
    a partir de las tablas hijas pedido_items y pedido_gastos.
    """
    __tablename__ = "pedidos"

    id = Column(Integer, primary_key=True, index=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id", ondelete="CASCADE"), nullable=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id", ondelete="RESTRICT"), nullable=False, index=True)
    numero_oc = Column(String(100), nullable=True, index=True)
    numero_remision = Column(String(100), nullable=False, index=True)
    fecha_emision = Column(String(50), nullable=True)
    fecha_entrega = Column(String(50), nullable=True)
    numero_canastas = Column(String(50), nullable=True)
    observaciones = Column(Text, nullable=True)
    utilidad_global = Column(Numeric(6, 2, asdecimal=False), default=30.0, nullable=False)
    archivo_origen_path = Column(String(500), nullable=True)
    factura_cargada = Column(Boolean, default=False, nullable=False)
    factura_archivo_path = Column(String(500), nullable=True)
    factura_archivo_nombre = Column(String(255), nullable=True)
    remision_firmada_cargada = Column(Boolean, default=False, nullable=False)
    remision_firmada_path = Column(String(500), nullable=True)
    remision_firmada_nombre = Column(String(255), nullable=True)
    completado = Column(Boolean, default=False, nullable=False)
    activo = Column(Boolean, default=True, index=True, nullable=False)
    creado_en = Column(DateTime, default=utc_now, nullable=False)
    actualizado_en = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    empresa = relationship("Empresa", foreign_keys=[empresa_id])
    usuario = relationship("Usuario", foreign_keys=[usuario_id])
    cliente = relationship("Cliente", back_populates="pedidos")
    items = relationship("PedidoItem", back_populates="pedido", cascade="all, delete-orphan", order_by="PedidoItem.orden")
    gastos_rel = relationship("PedidoGasto", back_populates="pedido", cascade="all, delete-orphan")


    # =====================================================================
    # CALCULOS DINAMICOS (3NF Estricta - Sin Totales Quemados)
    # CALCULOS DINAMICOS (3NF Estricta - Optimizados en una sola pasada)
    # =====================================================================
    @property
    def items_activos(self) -> List[Any]:
        return [i for i in (self.items or []) if getattr(i, "activo", True)]

    @property
    def gastos_activos(self) -> List[Any]:
        return [g for g in (self.gastos_rel or []) if getattr(g, "activo", True)]

    def _calcular_metricas_resumen(self) -> Dict[str, float]:
        """Calcula todas las métricas agregadas en una única iteración eficiente."""
        t_kilos = 0.0
        t_costo = 0.0
        t_venta = 0.0
        for i in self.items_activos:
            k = float(i.peso_neto or i.cantidad or 0.0)
            t_kilos += k
            c_unit = float(i.precio_costo_unitario or 0.0)
            v_unit = float(i.precio_venta_unitario or 0.0)
            t_costo += float(i.valor_compra_total if i.valor_compra_total is not None else (k * c_unit))
            t_venta += float(i.valor_total_venta if i.valor_total_venta is not None else (k * v_unit))

        t_gastos = sum(float(g.monto or 0.0) for g in self.gastos_activos if g.distribuir_en_costo)
        g_kilo = redondear_centena(t_gastos / t_kilos) if t_kilos > 0 else 0.0
        util_pesos = t_venta - (t_costo + t_gastos)
        util_pct = round((util_pesos / t_costo) * 100.0, 2) if t_costo > 0 else float(self.utilidad_global or 30.0)

        return {
            "total_kilos": t_kilos,
            "total_costo": t_costo,
            "total_venta": t_venta,
            "total_gastos": t_gastos,
            "gasto_por_kilo": g_kilo,
            "utilidad_pesos": util_pesos,
            "utilidad_porcentaje": util_pct,
        }

    @property
    def total_kilos(self) -> float:
        return sum(float(i.peso_neto or i.cantidad or 0.0) for i in self.items_activos)

    @property
    def total_costo(self) -> float:
        return sum(
            float(i.valor_compra_total or (float(i.peso_neto or i.cantidad or 0.0) * float(i.precio_costo_unitario or 0.0)))
            for i in self.items_activos
        )

    @property
    def total_venta(self) -> float:
        return sum(
            float(i.valor_total_venta or (float(i.peso_neto or i.cantidad or 0.0) * float(i.precio_venta_unitario or 0.0)))
            for i in self.items_activos
        )

    @property
    def total_gastos(self) -> float:
        return sum(float(g.monto or 0.0) for g in self.gastos_activos if g.distribuir_en_costo)

    @property
    def gasto_por_kilo(self) -> float:
        tk = self.total_kilos
        if tk > 0:
            return redondear_centena(self.total_gastos / tk)
        return 0.0

    @property
    def utilidad_pesos(self) -> float:
        return self.total_venta - (self.total_costo + self.total_gastos)

    @property
    def utilidad_porcentaje(self) -> float:
        tc = self.total_costo
        if tc > 0:
            return round((self.utilidad_pesos / tc) * 100.0, 2)
        return float(self.utilidad_global or 30.0)

    # =====================================================================
    # PROPIEDADES DE COMPATIBILIDAD CON FRONTEND Y EXPORTADORES
    # ====================================================================
    @property
    def productos(self) -> List[Dict[str, Any]]:
        active_items = self.items_activos
        if active_items:
            result = []
            g_kilo = self.gasto_por_kilo
            for item in active_items:
                cant = float(item.cantidad or 1.0)
                kilos = float(item.peso_neto or cant)
                costo = float(item.precio_costo_unitario or 0.0)
                venta = float(item.precio_venta_unitario or 0.0)
                util = float(item.porcentaje_utilidad if item.porcentaje_utilidad is not None else (self.utilidad_global or 30.0))
                costo_real = item.costo_real_kilo or redondear_centena(costo + g_kilo)
                v_compra = item.valor_compra_total or redondear_centena(costo * kilos)
                v_venta = item.valor_total_venta or redondear_centena(venta * kilos)


                prod_name = (
                    item.producto.nombre
                    if item.producto
                    else (item.producto_nombre or item.descripcion_historica or "Producto")
                )
                desc_text = item.notas or item.producto_nombre or item.descripcion_historica or ""
                result.append({
                    "id": item.id,
                    "producto_id": item.producto_id,
                    "producto": prod_name,
                    "nombre": prod_name,
                    "cantidad": cant,
                    "unidad": item.unidad_medida.codigo if item.unidad_medida else "Kg",
                    "empaque": item.tipo_empaque.nombre if item.tipo_empaque else "",
                    "descripcion": desc_text,
                    "kilos": kilos,
                    "costo_compra_kilo": costo,
                    "gasto_asignado_kilo": g_kilo,
                    "costo_real_kilo": costo_real,
                    "porcentaje_utilidad": util,
                    "precio_venta_kilo": venta,
                    "valor_compra_total": v_compra,
                    "valor_total_venta": v_venta,
                    "precio_venta_manual": bool(item.precio_venta_manual),
                    "peso_bruto": float(item.peso_bruto or 0.0),
                    "tara": float(item.tara or 0.0),
                    "peso_neto": kilos,
                    "surtido": bool(item.surtido),
                    "orden": item.orden,
                })
            return result
        return getattr(self, "_legacy_productos", []) or []

    @productos.setter
    def productos(self, val):
        self._legacy_productos = val

    @property
    def gastos(self) -> List[Dict[str, Any]]:
        active_gastos = self.gastos_activos
        if active_gastos:
            return [
                {
                    "id": str(g.id),
                    "concepto": g.descripcion,
                    "valor": float(g.monto or 0.0),
                    "aplicado": bool(g.distribuir_en_costo),
                    "concepto_gasto_id": g.concepto_gasto_id,
                }
                for g in active_gastos
            ]
        return getattr(self, "_legacy_gastos", []) or []

    @gastos.setter
    def gastos(self, val):
        self._legacy_gastos = val

    @property
    def liquidacion(self) -> Dict[str, Any]:
        metricas = self._calcular_metricas_resumen()
        return {
            "resumen": {
                "total_kilos": metricas["total_kilos"],
                "total_compras": metricas["total_costo"],
                "total_gastos": metricas["total_gastos"],
                "total_ventas": metricas["total_venta"],
                "ganancia": metricas["utilidad_pesos"],
                "margen_global_porcentaje": metricas["utilidad_porcentaje"],
                "gasto_por_kilo": metricas["gasto_por_kilo"],
            },
            "items": self.productos,
            "gastos": self.gastos,
        }


    @liquidacion.setter
    def liquidacion(self, val):
        pass

    __table_args__ = (
        UniqueConstraint("cliente_id", "numero_remision", name="uq_pedidos_cliente_remision"),
        CheckConstraint("utilidad_global >= 0", name="chk_pedidos_utilidad_positiva"),
        Index("ix_pedidos_cliente_activo_id", "cliente_id", "activo", "id"),
        Index("ix_pedidos_cliente_remision", "cliente_id", "numero_remision"),
        Index("ix_pedidos_activo_fecha_entrega", "activo", "fecha_entrega"),
        Index("ix_pedidos_empresa_activo", "empresa_id", "activo"),
    )
