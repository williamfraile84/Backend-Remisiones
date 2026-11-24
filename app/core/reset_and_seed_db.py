"""
Script integral para vaciar, recrear y sembrar la base de datos de forma limpia (3NF estricta).
Satisface las directivas del usuario:
1. Vaciar completamente la base de datos (PostgreSQL / Supabase / SQLite).
2. Corregir/eliminar vistas con SECURITY DEFINER (v_pedidos_resumen).
3. Recrear el esquema relacional normalizado 3NF sin redundancias.
4. Sembrar catálogos maestros:
   - Modulos
   - Roles y permisos (vinculados formalmente a modulos)
   - Unidades de medida
   - Tipos de empaque estándar
   - Conceptos de gasto
   - Catálogo extenso de productos con nombres colombianos estándar
   - Usuario Administrador inicial
5. DEJAR CERO EMPRESAS (para que el sistema exija el registro en el primer inicio).
"""
import sys
import logging
from sqlalchemy import text
from app.core.database import engine, SessionLocal, Base
from app.core.config import settings
from app.core.security import get_password_hash
import app.models  # Carga todos los modelos normalizados

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("reset_and_seed_db")


def reset_and_seed():
    logger.info("=== INICIANDO VACIADO Y RECREACIÓN LIMPIA DE BASE DE DATOS ===")
    is_postgres = "postgres" in settings.effective_database_url.lower()

    # 1. Resolver vistas y seguridad de Supabase / PostgreSQL
    with engine.connect() as conn:
        if is_postgres:
            logger.info("Limpiando vistas y funciones de seguridad en PostgreSQL...")
            try:
                conn.execute(text("DROP VIEW IF EXISTS public.v_pedidos_resumen CASCADE;"))
                conn.commit()
                logger.info("Vista v_pedidos_resumen eliminada/resuelta exitosamente.")
            except Exception as e:
                logger.warning(f"Aviso al procesar v_pedidos_resumen: {e}")

            try:
                conn.execute(text("ALTER FUNCTION public.rls_auto_enable() SECURITY INVOKER;"))
                conn.commit()
            except Exception:
                pass

            logger.info("Vaciando tablas mediante DROP SCHEMA public CASCADE...")
            try:
                conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
                conn.commit()
                logger.info("Esquema public vaciado completamente.")
            except Exception as e:
                logger.warning(f"Fallo drop schema: {e}. Intentando Base.metadata.drop_all...")
                Base.metadata.drop_all(bind=engine)
        else:
            logger.info("Vaciando base de datos SQLite...")
            Base.metadata.drop_all(bind=engine)

    # 2. Recrear todas las tablas con modelos 3NF
    logger.info("Recreando todas las tablas en base de datos...")
    Base.metadata.create_all(bind=engine)
    logger.info("Tablas recreadas exitosamente.")

    db = SessionLocal()
    try:
        from app.models.usuario import Usuario
        from app.models.role import Role
        from app.repositories.modulo_repository import ModuloRepository
        from app.repositories.unidad_medida_repository import UnidadMedidaRepository
        from app.repositories.empaque_repository import EmpaqueRepository
        from app.repositories.concepto_gasto_repository import ConceptoGastoRepository
        from app.repositories.producto_repository import ProductoRepository
        from app.services.role_service import RoleService

        # 3. Sembrar Módulos funcionales
        logger.info("Sembrando catálogo de Módulos (3NF)...")
        num_modulos = ModuloRepository.seed_default_modulos(db)
        logger.info(f"Módulos sembrados: {num_modulos}")

        # 4. Sembrar Roles y Permisos (vinculados a Módulos)
        logger.info("Sembrando Roles y Permisos RBAC...")
        RoleService.asegurar_roles_y_permisos(db)
        logger.info("Roles y Permisos sembrados correctamente.")

        # 5. Sembrar Unidades de Medida
        logger.info("Sembrando Unidades de Medida...")
        num_unidades = UnidadMedidaRepository.seed_default_units_if_empty(db)
        logger.info(f"Unidades de medida sembradas: {num_unidades}")

        # 6. Sembrar Tipos de Empaque Estandarizados
        logger.info("Sembrando Tipos de Empaque...")
        num_empaques = EmpaqueRepository.seed_default_tipos_if_empty(db)
        logger.info(f"Tipos de empaque sembrados: {num_empaques}")

        # 7. Sembrar Conceptos de Gasto
        logger.info("Sembrando Conceptos de Gasto...")
        num_gastos = ConceptoGastoRepository.seed_default_concepts_if_empty(db)
        logger.info(f"Conceptos de gasto sembrados: {num_gastos}")

        # 8. Sembrar Usuario Administrador Inicial
        logger.info("Creando Usuario Administrador Inicial...")
        admin_user = db.query(Usuario).filter(Usuario.username == settings.INITIAL_ADMIN_USERNAME).first()
        rol_admin = db.query(Role).filter(Role.codigo == "admin").first()
        if not admin_user:
            admin_user = Usuario(
                username=settings.INITIAL_ADMIN_USERNAME,
                email=settings.INITIAL_ADMIN_EMAIL,
                nombre_completo=settings.INITIAL_ADMIN_NAME,
                hashed_password=get_password_hash(settings.INITIAL_ADMIN_PASSWORD),
                rol="admin",
                rol_id=rol_admin.id if rol_admin else None,
                activo=True,
            )
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)
            logger.info(f"Usuario Administrador '{admin_user.username}' creado con éxito.")
        else:
            if rol_admin and admin_user.rol_id != rol_admin.id:
                admin_user.rol_id = rol_admin.id
                db.commit()

        # 9. Sembrar Catálogo Extenso de Productos con nombres comerciales limpios
        logger.info("Sembrando Catálogo Extenso de Productos Fruver...")
        num_prods = ProductoRepository.seed_massive_catalog(db)
        logger.info(f"Productos sembrados: {num_prods}")

        # 10. Confirmación de Empresas = 0
        from app.models.empresa import Empresa
        count_empresas = db.query(Empresa).count()
        logger.info(f"Empresas registradas en DB: {count_empresas} (Debe ser 0 para arranque inicial)")
        assert count_empresas == 0, "Error: Se esperaba que la base de datos arrancara con 0 empresas."

        logger.info("=== BASE DE DATOS REINICIALIZADA Y SEMBRADA CON ÉXITO ===")
    except Exception as e:
        logger.error(f"Error durante la inicialización de base de datos: {e}", exc_info=True)
        db.rollback()
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    reset_and_seed()

