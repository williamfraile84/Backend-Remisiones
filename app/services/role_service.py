from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.role import Role
from app.models.permiso import Permiso
from app.models.usuario import Usuario, DEFAULT_ADMIN_PERMISSIONS, DEFAULT_OPERATOR_PERMISSIONS
from app.repositories.role_repository import RoleRepository
from app.repositories.permiso_repository import PermisoRepository


class RoleService:
    """
    Servicio atómico para la orquestación y administración de Roles y Permisos (RBAC 3NF).
    Cumple con el Principio de Responsabilidad Única (SRP).
    """

    @staticmethod
    def listar_roles(db: Session, activo_only: bool = True) -> List[Role]:
        return RoleRepository.get_all(db, activo_only)

    @staticmethod
    def obtener_rol(db: Session, role_id: int) -> Optional[Role]:
        return RoleRepository.get_by_id(db, role_id)

    @staticmethod
    def crear_rol(db: Session, data: Dict[str, Any], permiso_ids: Optional[List[int]] = None) -> Role:
        return RoleRepository.create(db, data, permiso_ids)

    @staticmethod
    def actualizar_rol(db: Session, role_id: int, data: Dict[str, Any], permiso_ids: Optional[List[int]] = None) -> Optional[Role]:
        return RoleRepository.update(db, role_id, data, permiso_ids)

    @staticmethod
    def eliminar_rol(db: Session, role_id: int) -> bool:
        """Baja lógica de rol."""
        return RoleRepository.delete(db, role_id)

    @staticmethod
    def listar_permisos(db: Session, modulo: Optional[str] = None) -> List[Permiso]:
        return PermisoRepository.get_all(db, activo_only=True, modulo=modulo)

    @classmethod
    def asegurar_roles_y_permisos(cls, db: Session) -> None:
        """Siembra y asegura la existencia de roles y permisos estándar del sistema."""
        permisos_meta = [
            # 1. Operación & Pedidos
            ("puede_crear_pedidos", "Crear Pedidos", "PEDIDOS", "Permite registrar nuevos pedidos y remisiones"),
            ("puede_editar_pedidos", "Editar Pedidos", "PEDIDOS", "Permite modificar pedidos existentes y su liquidación"),
            ("puede_desactivar_pedidos", "Desactivar Pedidos", "PEDIDOS", "Permite anular o realizar baja lógica de pedidos"),
            ("puede_cerrar_pedidos", "Cerrar Pedidos", "PEDIDOS", "Permite formalizar y cerrar pedidos completados"),
            ("puede_ver_historial", "Historial de Pedidos", "PEDIDOS", "Permite consultar y auditar pedidos históricos"),
            # 2. Surtido & Compras
            ("puede_ver_surtido", "Ver Surtido & Compras", "SURTIDO", "Permite ingresar al módulo de surtido y compras"),
            ("puede_crear_surtido", "Armar Pedido Surtido", "SURTIDO", "Permite armar listas de compra y abastecimiento de plaza"),
            ("puede_verificar_checklist", "Checklist de Llegada", "SURTIDO", "Permite registrar peso y novedades de llegada de compras"),
            ("puede_liquidar_surtido", "Liquidar Costos Surtido", "SURTIDO", "Permite liquidar costos por kilo y fijar precios de venta"),
            ("puede_conciliar_pos", "Conciliación Precios POS", "SURTIDO", "Permite sincronizar tarifas calculadas con el Sistema POS"),
            ("puede_aplicar_precios_catalogo", "Aplicar Precios al Catálogo", "SURTIDO", "Permite actualizar catálogo maestro con precios de surtido"),
            # 3. Liquidación & Gastos Financieros
            ("puede_ver_financiero", "Ver Financiero", "FINANCIERO", "Permite visualizar márgenes, costos y rentabilidad"),
            ("puede_editar_costos", "Modificar Costos Compra", "FINANCIERO", "Permite editar costos unitarios de adquisición"),
            ("puede_modificar_margenes", "Modificar Márgenes Utilidad", "FINANCIERO", "Permite cambiar porcentajes de utilidad global o por producto"),
            ("puede_gestionar_gastos", "Gestionar Gastos Comerciales", "FINANCIERO", "Permite registrar fletes y gastos operativos"),
            ("puede_exportar", "Exportar Documentos", "EXPORTACIONES", "Permite generar PDFs y archivos Excel"),
            # 4. Salidas, Documentos & OCR
            ("puede_ver_documentos", "Ver Módulo Documentos", "DOCUMENTOS", "Permite acceder al repositorio documental"),
            ("puede_cargar_documentos", "Cargar Documentos & OCR", "DOCUMENTOS", "Permite importar archivos con Gemini Vision o Excel"),
            ("puede_cargar_facturas", "Cargar Facturas", "DOCUMENTOS", "Permite adjuntar facturas escaneadas"),
            ("puede_cargar_remisiones_firmadas", "Cargar Remisiones Firmadas", "DOCUMENTOS", "Permite adjuntar remisiones con firma"),
            ("puede_descargar_documentos", "Descargar Soportes", "DOCUMENTOS", "Permite descargar remisiones y facturas archivadas"),
            # 5. Clientes & Terceros
            ("puede_gestionar_clientes", "Gestionar Clientes", "CLIENTES", "Permite registrar y editar clientes"),
            ("puede_cambiar_cliente", "Cambiar Cliente en Pedido", "CLIENTES", "Permite asignar o reasignar cliente en pedido activo"),
            # 6. Catálogos Maestros
            ("puede_gestionar_catalogos", "Gestionar Catálogos", "CATALOGOS", "Permite crear y modificar productos y códigos de barra"),
            ("puede_gestionar_empaques", "Empaques & Medidas", "CATALOGOS", "Permite configurar ponys, canastillas, bultos y cajas"),
            ("puede_gestionar_conceptos_gasto", "Gestionar Conceptos de Gasto", "CATALOGOS", "Permite registrar categorías y conceptos de gasto"),
            # 7. Sistema & Administración
            ("puede_editar_empresa", "Editar Empresa", "ADMIN", "Permite actualizar perfil y logo corporativo"),
            ("puede_administrar_usuarios", "Administrar Usuarios", "ADMIN", "Permite crear usuarios, editar roles y matriz de permisos"),
            ("puede_ver_auditoria", "Ver Auditoría & Logs", "ADMIN", "Permite consultar eventos y trazabilidad del sistema"),
        ]

        permisos_map = {}
        for cod, nom, mod, desc in permisos_meta:
            p = PermisoRepository.get_by_codigo(db, cod)
            if not p:
                p = PermisoRepository.create(db, {"codigo": cod, "nombre": nom, "modulo": mod, "descripcion": desc, "activo": True})
            permisos_map[cod] = p

        rol_admin = RoleRepository.get_by_codigo(db, "admin")
        if not rol_admin:
            rol_admin = RoleRepository.create(
                db,
                {"codigo": "admin", "nombre": "Administrador", "descripcion": "Control total del sistema", "activo": True},
                [p.id for p in permisos_map.values()]
            )
        else:
            rol_admin.permisos = list(permisos_map.values())
            db.commit()

        rol_operador = RoleRepository.get_by_codigo(db, "operador")
        operador_perms = [
            permisos_map[k] for k in DEFAULT_OPERATOR_PERMISSIONS.keys()
            if k in permisos_map and DEFAULT_OPERATOR_PERMISSIONS[k]
        ]
        if "puede_gestionar_catalogos" in permisos_map:
            operador_perms.append(permisos_map["puede_gestionar_catalogos"])
        if "puede_cerrar_pedidos" in permisos_map:
            operador_perms.append(permisos_map["puede_cerrar_pedidos"])

        if not rol_operador:
            rol_operador = RoleRepository.create(
                db,
                {"codigo": "operador", "nombre": "Operador", "descripcion": "Operación logística y pedidos", "activo": True},
                [p.id for p in operador_perms]
            )
        else:
            rol_operador.permisos = operador_perms
            db.commit()

        # Asignar rol_id a usuarios que no lo tengan
        usuarios = db.query(Usuario).all()
        for u in usuarios:
            if not u.rol_id:
                u.rol_id = rol_admin.id if u.rol == "admin" else rol_operador.id
        db.commit()

