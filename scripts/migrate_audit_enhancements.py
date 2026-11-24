import os
import sys

# Asegurar que el backend esté en el PYTHONPATH
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import logging
from sqlalchemy import text
from app.core.database import engine, Base, SessionLocal
from app.models.role import Role, Permiso, rol_permisos
from app.models.empresa import Empresa
from app.models.cliente import Cliente
from app.models.usuario import Usuario
from app.models.pedido import Pedido
from app.models.producto import Producto
import app.models  # Inicializa el paquete app.models completo
from app.models import (
    Empresa,
    Cliente,
    Usuario,
    Pedido,
    Producto,
    Role,
    Permiso,
    rol_permisos,
    PedidoItem,
    PedidoGasto,
)
from app.services.role_service import RoleService
from app.services.auth_service import AuthService
from app.services.migration_service import DatabaseMigrationService
from app.repositories.producto_repository import ProductoRepository

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("migration_audit")


def ejecutar_migracion():
    dialect_name = engine.dialect.name
    logger.info(f"Iniciando sincronizacion y migracion para dialecto: {dialect_name}")

    # 1. Crear todas las tablas que no existan
    Base.metadata.create_all(bind=engine)
    logger.info("Tablas creadas/verificadas en Base.metadata.")

    with engine.connect() as conn:
        if dialect_name == "postgresql":
            # 2. Agregar columnas faltantes de forma idempotente
            logger.info("Verificando columnas en PostgreSQL...")
            columnas_ddl = [
                "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS empresa_id INTEGER REFERENCES empresas(id) ON DELETE SET NULL;",
                "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS rol_id INTEGER REFERENCES roles(id) ON DELETE SET NULL;",
                "ALTER TABLE clientes ADD COLUMN IF NOT EXISTS empresa_id INTEGER REFERENCES empresas(id) ON DELETE CASCADE;",
                "ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS empresa_id INTEGER REFERENCES empresas(id) ON DELETE CASCADE;",
                "ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS usuario_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL;",
                "ALTER TABLE pedido_items ADD COLUMN IF NOT EXISTS activo BOOLEAN DEFAULT TRUE;",
                "ALTER TABLE pedido_gastos ADD COLUMN IF NOT EXISTS activo BOOLEAN DEFAULT TRUE;",
            ]
            for ddl in columnas_ddl:
                try:
                    conn.execute(text(ddl))
                    conn.commit()
                except Exception as e:
                    logger.warning(f"Error al ejecutar DDL ({ddl}): {e}")
                    conn.rollback()

            # 3. Crear índices óptimos si no existen
            logger.info("Creando índices optimizados si no existen...")
            indices_ddl = [
                "CREATE INDEX IF NOT EXISTS ix_pedidos_empresa_activo ON pedidos(empresa_id, activo);",
                "CREATE INDEX IF NOT EXISTS ix_pedidos_usuario_id ON pedidos(usuario_id);",
                "CREATE INDEX IF NOT EXISTS ix_clientes_empresa_id ON clientes(empresa_id);",
                "CREATE INDEX IF NOT EXISTS ix_productos_activo_nombre ON productos(activo, nombre);",
                "CREATE INDEX IF NOT EXISTS ix_auditorias_modulo_id ON auditorias(modulo, registro_id);",
                "CREATE INDEX IF NOT EXISTS ix_auditorias_modulo_id ON auditorias(modulo, id);",
                "CREATE INDEX IF NOT EXISTS ix_usuarios_empresa_id ON usuarios(empresa_id);",
                "CREATE INDEX IF NOT EXISTS ix_usuarios_rol_id ON usuarios(rol_id);",
                "CREATE INDEX IF NOT EXISTS ix_pedido_items_pedido_activo ON pedido_items(pedido_id, activo);",
                "CREATE INDEX IF NOT EXISTS ix_pedido_gastos_pedido_activo ON pedido_gastos(pedido_id, activo);",
            ]
            for ddl in indices_ddl:
                try:
                    conn.execute(text(ddl))
                    conn.commit()
                except Exception as e:
                    logger.warning(f"Error al crear índice: {e}")
                    conn.rollback()

            # 4. Limpiar índices duplicados redundantes si existen
            logger.info("Eliminando índices redundantes en PostgreSQL...")
            drop_indices = [
                "DROP INDEX IF EXISTS ix_empresa_atributos_empresa_id;",
                "DROP INDEX IF EXISTS ix_cliente_atributos_cliente_id;",
                "DROP INDEX IF EXISTS ix_pedido_items_pedido_id;",
                "DROP INDEX IF EXISTS ix_pedido_gastos_pedido_id;",
            ]
            for ddl in drop_indices:
                try:
                    conn.execute(text(ddl))
                    conn.commit()
                except Exception as e:
                    logger.warning(f"Error al eliminar índice redundante: {e}")
                    conn.rollback()

            # 5. Agregar Unique y Check Constraints si no existen
            logger.info("Verificando constraints...")
            constraints = [
                ("uq_empresas_nit", "ALTER TABLE empresas ADD CONSTRAINT uq_empresas_nit UNIQUE (nit);"),
                ("uq_conceptos_gasto_nombre", "ALTER TABLE conceptos_gasto ADD CONSTRAINT uq_conceptos_gasto_nombre UNIQUE (nombre);"),
                ("chk_ped_item_tara_positiva", "ALTER TABLE pedido_items ADD CONSTRAINT chk_ped_item_tara_positiva CHECK (tara >= 0);"),
                ("chk_ped_item_peso_neto_positivo", "ALTER TABLE pedido_items ADD CONSTRAINT chk_ped_item_peso_neto_positivo CHECK (peso_neto >= 0);"),
                ("chk_ped_gasto_monto_positivo", "ALTER TABLE pedido_gastos ADD CONSTRAINT chk_ped_gasto_monto_positivo CHECK (monto >= 0);"),
            ]
            for c_name, c_sql in constraints:
                check_sql = f"SELECT 1 FROM pg_constraint WHERE conname = '{c_name}';"
                exists = conn.execute(text(check_sql)).scalar()
                if not exists:
                    try:
                        conn.execute(text(c_sql))
                        conn.commit()
                        logger.info(f"Constraint {c_name} creada exitosamente.")
                    except Exception as e:
                        logger.warning(f"No se pudo crear constraint {c_name}: {e}")
                # 5.1 Endurecimiento de Seguridad (Supabase Security Advisor / PostgreSQL RLS)
            logger.info("Aplicando políticas de seguridad y endurecimiento Supabase/Postgres...")
            security_ddl = [
                "ALTER VIEW IF EXISTS public.v_pedidos_resumen SET (security_invoker = true);",
                "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'rls_auto_enable') THEN "
                "REVOKE EXECUTE ON FUNCTION public.rls_auto_enable() FROM PUBLIC, anon, authenticated; "
                "GRANT EXECUTE ON FUNCTION public.rls_auto_enable() TO postgres, service_role; "
                "END IF; END $$;"
            ]
            for s_sql in security_ddl:
                try:
                    conn.execute(text(s_sql))
                    conn.commit()
                except Exception as e:
                    logger.warning(f"Aviso en endurecimiento de seguridad: {e}")
                    conn.rollback()

    # 6. Sembrar y sincronizar Roles y Permisos (RBAC 3NF)
    db = SessionLocal()
    try:
        logger.info("Sembrando Roles y Permisos RBAC...")
        AuthService.asegurar_roles_y_permisos(db)
        RoleService.asegurar_roles_y_permisos(db)

        # 7. Asignar empresa_id por defecto a clientes, pedidos y usuarios si están en null
        # 7. Asignar empresa_id a clientes, pedidos y usuarios solo si existe una empresa registrada
        empresa_default = db.query(Empresa).first()
        if not empresa_default:
            empresa_default = Empresa(
                nombre="EMPRESA PRINCIPAL",
                nit="900000000-1",
                direccion="Calle Principal # 1-1",
                telefono="3000000000",
                email="admin@fruver.com"
            )
            db.add(empresa_default)
            db.commit()
            db.refresh(empresa_default)
        if empresa_default:
            # Vincular empresa a clientes huérfanos
            clientes_sin_empresa = db.query(Cliente).filter(Cliente.empresa_id.is_(None)).all()
            for c in clientes_sin_empresa:
                c.empresa_id = empresa_default.id

        # Vincular empresa a clientes huérfanos
        clientes_sin_empresa = db.query(Cliente).filter(Cliente.empresa_id.is_(None)).all()
        for c in clientes_sin_empresa:
            c.empresa_id = empresa_default.id
            # Vincular empresa a usuarios huérfanos
            usuarios_sin_empresa = db.query(Usuario).filter(Usuario.empresa_id.is_(None)).all()
            for u in usuarios_sin_empresa:
                u.empresa_id = empresa_default.id

        # Vincular empresa a usuarios huérfanos
        usuarios_sin_empresa = db.query(Usuario).filter(Usuario.empresa_id.is_(None)).all()
        for u in usuarios_sin_empresa:
            u.empresa_id = empresa_default.id
            # Vincular empresa a pedidos huérfanos
            pedidos_sin_empresa = db.query(Pedido).filter(Pedido.empresa_id.is_(None)).all()
            for p in pedidos_sin_empresa:
                p.empresa_id = empresa_default.id

        # Vincular empresa a pedidos huérfanos
        pedidos_sin_empresa = db.query(Pedido).filter(Pedido.empresa_id.is_(None)).all()
        for p in pedidos_sin_empresa:
            p.empresa_id = empresa_default.id
            db.commit()
            logger.info(f"Empresa activa vinculada: {len(clientes_sin_empresa)} clientes, {len(usuarios_sin_empresa)} usuarios, {len(pedidos_sin_empresa)} pedidos.")

        db.commit()
        logger.info(f"Multi-empresa inicializada: {len(clientes_sin_empresa)} clientes, {len(usuarios_sin_empresa)} usuarios, {len(pedidos_sin_empresa)} pedidos vinculados.")

        # 8. Vincular empaques y presentaciones (3NF y limpieza de codificación)
        logger.info("Ejecutando auto-enlace 3NF de presentaciones de empaque...")
        DatabaseMigrationService.auto_link_3nf_relations(db)

        # 9. Sembrar catálogo masivo de más de 250 productos
        logger.info("Sembrando catálogo masivo de productos (más de 250 referencias)...")
        nuevos_prods = ProductoRepository.seed_massive_catalog(db)
        logger.info(f"Catálogo de productos sembrado: {nuevos_prods} nuevos productos registrados.")

        # Re-enlazar presentaciones con los nuevos productos
        DatabaseMigrationService.auto_link_3nf_relations(db)

        logger.info("Migración y sincronización completada con éxito.")
    finally:
        db.close()


if __name__ == "__main__":
    ejecutar_migracion()

