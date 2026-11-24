from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Numeric, Boolean, DateTime, ForeignKey, CheckConstraint, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from app.core.database import Base


def utc_now():
    return datetime.now(timezone.utc)


from app.models.producto_empaque import ProductoEmpaque



class Producto(Base):
    """
    Catalogo maestro de productos y fruver.
    Estandariza codigos, nombres, categorias, unidad de medida base y empaque sugerido.
    """
    __tablename__ = "productos"

    id = Column(Integer, primary_key=True, index=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id", ondelete="CASCADE"), nullable=True, index=True)
    codigo = Column(String(50), nullable=True, index=True)
    nombre = Column(String(150), nullable=False, index=True)
    categoria = Column(String(100), nullable=True, index=True)
    unidad_medida_id = Column(Integer, ForeignKey("unidades_medida.id", ondelete="SET NULL"), nullable=True)
    tipo_empaque_id = Column(Integer, ForeignKey("tipos_empaque.id", ondelete="SET NULL"), nullable=True)
    pos_item_id = Column(String(50), nullable=True, index=True)
    precio_pos_actual = Column(Numeric(14, 2, asdecimal=False), default=0.0, nullable=False)
    precio_costo_referencia = Column(Numeric(14, 2, asdecimal=False), default=0.0, nullable=False)
    precio_venta_referencia = Column(Numeric(14, 2, asdecimal=False), default=0.0, nullable=False)
    merma_esperada_pct = Column(Numeric(6, 2, asdecimal=False), default=0.0, nullable=False)
    activo = Column(Boolean, default=True, index=True, nullable=False)
    creado_en = Column(DateTime, default=utc_now, nullable=False)
    actualizado_en = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    empresa = relationship("Empresa", foreign_keys=[empresa_id])
    unidad_medida = relationship("UnidadMedida", foreign_keys=[unidad_medida_id])
    tipo_empaque = relationship("TipoEmpaque", foreign_keys=[tipo_empaque_id])
    empaques_rel = relationship("ProductoEmpaque", back_populates="producto", cascade="all, delete-orphan")

    @property
    def empaques_permitidos(self):
        res = []
        for pe in (self.empaques_rel or []):
            if pe.tipo_empaque:
                custom_kg = float(pe.peso_kg) if pe.peso_kg is not None else float(pe.tipo_empaque.peso_kg or 0.0)
                res.append({
                    "id": pe.tipo_empaque.id,
                    "nombre": pe.tipo_empaque.nombre,
                    "peso_kg": custom_kg,
                    "peso_lb": round(custom_kg * 2, 2),
                    "peso_kg_default": float(pe.tipo_empaque.peso_kg or 0.0),
                    "descripcion": pe.tipo_empaque.descripcion,
                    "activo": bool(pe.tipo_empaque.activo),
                    "creado_en": pe.tipo_empaque.creado_en,
                    "actualizado_en": pe.tipo_empaque.actualizado_en,
                })
        return res

    @empaques_permitidos.setter
    def empaques_permitidos(self, value):
        self.empaques_rel.clear()
        for item in (value or []):
            if hasattr(item, "id"):
                self.empaques_rel.append(ProductoEmpaque(tipo_empaque=item))
            elif isinstance(item, dict):
                tid = item.get("tipo_empaque_id") or item.get("id")
                pkg = item.get("peso_kg")
                self.empaques_rel.append(ProductoEmpaque(tipo_empaque_id=tid, peso_kg=pkg))
            elif isinstance(item, int):
                self.empaques_rel.append(ProductoEmpaque(tipo_empaque_id=item))

    __table_args__ = (
        CheckConstraint("precio_costo_referencia >= 0", name="chk_prod_costo_positivo"),
        CheckConstraint("precio_venta_referencia >= 0", name="chk_prod_venta_positivo"),
        CheckConstraint("merma_esperada_pct >= 0", name="chk_prod_merma_positivo"),
        UniqueConstraint("nombre", name="uq_productos_nombre"),
        Index("ix_productos_activo_nombre", "activo", "nombre"),
        Index("ix_productos_empresa_activo_nombre", "empresa_id", "activo", "nombre"),
    )
