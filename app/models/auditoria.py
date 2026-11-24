from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.core.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class Auditoria(Base):
    __tablename__ = "auditorias"

    id = Column(Integer, primary_key=True, index=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id", ondelete="CASCADE"), nullable=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True, index=True)
    usuario_nombre = Column(String(200), nullable=True)
    usuario_rol = Column(String(50), nullable=True)
    accion = Column(String(100), nullable=False, index=True)
    modulo_id = Column(Integer, ForeignKey("modulos.id", ondelete="SET NULL"), nullable=True, index=True)
    modulo = Column(String(100), nullable=True, index=True)
    entidad = Column(String(100), nullable=True)
    entidad_id = Column(String(100), nullable=True)
    ip_address = Column(String(100), nullable=True)
    creado_en = Column(DateTime, default=utc_now, index=True, nullable=False)

    empresa = relationship("Empresa", foreign_keys=[empresa_id])
    usuario = relationship("Usuario", foreign_keys=[usuario_id])
    modulo_rel = relationship("Modulo", foreign_keys=[modulo_id])
    cambios = relationship("AuditoriaCambio", back_populates="auditoria", cascade="all, delete-orphan")

    @property
    def detalles(self):
        if self.cambios:
            result = {}
            for c in self.cambios:
                val = c.valor_nuevo
                if c.tipo_dato == "int" and val is not None:
                    try:
                        val = int(val)
                    except Exception:
                        pass
                elif c.tipo_dato == "float" and val is not None:
                    try:
                        val = float(val)
                    except Exception:
                        pass
                elif c.tipo_dato == "bool" and val is not None:
                    val = val.lower() == "true"
                result[c.campo] = val
            return result
        return {}

    __table_args__ = (
        Index("ix_auditorias_modulo_texto_id", "modulo", "id"),
        Index("ix_auditorias_empresa_fecha", "empresa_id", "creado_en"),
        Index("ix_auditorias_modulo_accion_fecha", "modulo", "accion", "creado_en"),
        Index("ix_auditorias_usuario_fecha", "usuario_id", "creado_en"),
    )
