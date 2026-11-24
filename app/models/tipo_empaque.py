from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, CheckConstraint, Index
from app.core.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class TipoEmpaque(Base):
    """
    Modelo atómico único para estandarizar los Tipos de Empaque disponibles (3NF estricta).
    (Bulto, Pony, Canastilla, Caja, Saco, Arroba, Bolsa, etc.)
    Cumple con el Principio de Responsabilidad Única (SRP) y Fuente Única de Verdad.
    """
    __tablename__ = "tipos_empaque"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False, unique=True, index=True)
    peso_kg = Column(Float, nullable=False, default=0.0)
    peso_lb = Column(Float, nullable=False, default=0.0)
    descripcion = Column(String(255), nullable=True)
    activo = Column(Boolean, default=True, index=True, nullable=False)
    creado_en = Column(DateTime, default=utc_now, nullable=False)
    actualizado_en = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)



    __table_args__ = (
        CheckConstraint("peso_kg >= 0", name="chk_tipo_empaque_peso_kg_positivo"),
        CheckConstraint("peso_lb >= 0", name="chk_tipo_empaque_peso_lb_positivo"),
        Index("ix_tipos_empaque_activo_nombre", "activo", "nombre"),
    )
