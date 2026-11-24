from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, CheckConstraint, Index
from app.core.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class UnidadMedida(Base):
    """
    Catalogo maestro de unidades de medida fisicas
    (KG, LB, UND, ATD, GR, etc.) desacoplado de empaques o canastillas.
    """
    __tablename__ = "unidades_medida"

    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String(20), unique=True, nullable=False, index=True)
    nombre = Column(String(50), nullable=False)
    tipo_magnitud = Column(String(30), default="PESO", nullable=False)
    factor_conversion_kg = Column(Float, default=1.0, nullable=False)
    activo = Column(Boolean, default=True, index=True, nullable=False)
    creado_en = Column(DateTime, default=utc_now, nullable=False)
    actualizado_en = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        CheckConstraint("factor_conversion_kg >= 0", name="chk_unidad_factor_no_negativo"),
        Index("ix_unidades_medida_activo_codigo", "activo", "codigo"),
    )
