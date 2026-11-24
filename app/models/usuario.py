from datetime import datetime, timezone
from typing import Dict
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, CheckConstraint, Index
from sqlalchemy.orm import relationship
from app.core.database import Base


def utc_now():
    return datetime.now(timezone.utc)


# Permisos por defecto del sistema (Matriz Granular Exhaustiva)
DEFAULT_OPERATOR_PERMISSIONS = {
    # 1. Operación & Pedidos
    "puede_crear_pedidos": True,
    "puede_editar_pedidos": True,
    "puede_desactivar_pedidos": False,
    "puede_cerrar_pedidos": True,
    "puede_ver_historial": True,
    # 2. Surtido & Compras de Plaza
    "puede_ver_surtido": True,
    "puede_crear_surtido": True,
    "puede_verificar_checklist": True,
    "puede_liquidar_surtido": True,
    "puede_conciliar_pos": False,
    "puede_aplicar_precios_catalogo": False,
    # 3. Liquidación & Gastos Comerciales
    "puede_ver_financiero": True,
    "puede_editar_costos": True,
    "puede_modificar_margenes": False,
    "puede_gestionar_gastos": True,
    "puede_exportar": True,
    # 4. Salidas, Documentación & OCR
    "puede_ver_documentos": True,
    "puede_cargar_documentos": True,
    "puede_cargar_facturas": True,
    "puede_cargar_remisiones_firmadas": True,
    "puede_descargar_documentos": True,
    # 5. Clientes & Terceros
    "puede_gestionar_clientes": True,
    "puede_cambiar_cliente": True,
    # 6. Catálogos Maestros
    "puede_gestionar_catalogos": True,
    "puede_gestionar_empaques": True,
    "puede_gestionar_conceptos_gasto": True,
    # 7. Sistema & Administración
    "puede_editar_empresa": False,
    "puede_administrar_usuarios": False,
    "puede_ver_auditoria": False,
}

DEFAULT_ADMIN_PERMISSIONS = {k: True for k in DEFAULT_OPERATOR_PERMISSIONS}


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id", ondelete="SET NULL"), nullable=True, index=True)
    rol_id = Column(Integer, ForeignKey("roles.id", ondelete="RESTRICT"), nullable=True, index=True)
    username = Column(String(100), unique=True, index=True, nullable=False)
    email = Column(String(150), unique=True, index=True, nullable=True)
    nombre_completo = Column(String(200), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    rol = Column(String(50), default="operador", nullable=False, index=True)  # "admin" | "operador"
    activo = Column(Boolean, default=True, nullable=False, index=True)  # Baja lógica
    ultimo_login = Column(DateTime, nullable=True)
    creado_en = Column(DateTime, default=utc_now, nullable=False)
    actualizado_en = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    empresa_rel = relationship("Empresa", foreign_keys=[empresa_id])
    rol_rel = relationship("Role", back_populates="usuarios", foreign_keys=[rol_id])

    __table_args__ = (
        CheckConstraint("rol IN ('admin', 'operador')", name="chk_usuarios_rol"),
        Index("ix_usuarios_empresa_activo", "empresa_id", "activo"),
    )

    @property
    def permisos(self) -> Dict[str, bool]:
        """Calcula permisos dinámicamente según rol asignado y tabla relacional (3NF estricta)."""
        if self.rol == "admin":
            return {k: True for k in DEFAULT_ADMIN_PERMISSIONS}
        if self.rol_rel and self.rol_rel.permisos:
            res = {k: False for k in DEFAULT_OPERATOR_PERMISSIONS}
            for p in self.rol_rel.permisos:
                if p.activo:
                    res[p.codigo] = True
            return res
        return DEFAULT_OPERATOR_PERMISSIONS.copy()

    @permisos.setter
    def permisos(self, val):
        self._temp_permisos = val

    def tiene_permiso(self, permiso_nombre: str) -> bool:
        """Verifica si el usuario tiene un permiso específico. Los administradores tienen todos los permisos."""
        if self.rol == "admin":
            return True
        if self.rol_rel and self.rol_rel.permisos:
            for p in self.rol_rel.permisos:
                if p.codigo == permiso_nombre and p.activo:
                    return True
        return self.permisos.get(permiso_nombre, False)
