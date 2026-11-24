from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from app.core.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class Cliente(Base):
    __tablename__ = "clientes"

    id = Column(Integer, primary_key=True, index=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id", ondelete="CASCADE"), nullable=True, index=True)
    razon_social = Column(String(255), nullable=False, index=True)
    nit = Column(String(100), nullable=False, index=True)
    direccion = Column(Text, nullable=True)
    telefono = Column(String(100), nullable=True)
    email = Column(String(150), nullable=True)
    consecutivo_remision_actual = Column(Integer, default=1, nullable=False)
    activo = Column(Boolean, default=True, index=True, nullable=False)
    creado_en = Column(DateTime, default=utc_now, nullable=False)
    actualizado_en = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    empresa = relationship("Empresa", foreign_keys=[empresa_id])
    pedidos = relationship("Pedido", back_populates="cliente")
    atributos = relationship("ClienteAtributo", back_populates="cliente", cascade="all, delete-orphan")

    @property
    def campos_extra(self):
        return [{"id": str(a.id), "clave": a.clave, "valor": a.valor} for a in (self.atributos or [])]

    @campos_extra.setter
    def campos_extra(self, val):
        pass

    __table_args__ = (
        UniqueConstraint("nit", name="uq_clientes_nit"),
        Index("ix_clientes_activo_razon_social", "activo", "razon_social"),
        Index("ix_clientes_activo_nit", "activo", "nit"),
        Index("ix_clientes_empresa_activo_razon", "empresa_id", "activo", "razon_social"),
    )
