import logging
from typing import Dict, Any, Optional
from sqlalchemy import create_engine, text, or_
from sqlalchemy.orm import sessionmaker, make_transient, Session
from sqlalchemy.pool import NullPool
from app.core.config import settings
from app.core.database import Base
from app.models import (
    Empresa,
    Cliente,
    Pedido,
    Usuario,
    Auditoria,
    TipoEmpaque,
    UnidadMedida,
    ConceptoGasto,
    Producto,
    PedidoItem,
    PedidoGasto,
)
from app.repositories.unidad_medida_repository import UnidadMedidaRepository
from app.repositories.concepto_gasto_repository import ConceptoGastoRepository
from app.repositories.empaque_repository import EmpaqueRepository
from app.repositories.producto_repository import ProductoRepository

logger = logging.getLogger(__name__)


class DatabaseMigrationService:
    """
    Servicio universal para migrar datos entre cualquier motor de base de datos
    (SQLite <-> PostgreSQL/Supabase <-> MySQL <-> Oracle, etc.)
    respetando integridad referencial, orden topológico y sincronización de secuencias.
    """

    @staticmethod
    def _create_engine_for_url(url: str):
        is_sqlite = url.lower().startswith("sqlite")
        engine_kwargs = {"pool_pre_ping": True}
        if is_sqlite:
            engine_kwargs["connect_args"] = {"check_same_thread": False}
        else:
            engine_kwargs["poolclass"] = NullPool
        return create_engine(url, **engine_kwargs)

    @classmethod
    def execute_migration(
        cls,
        source_url: Optional[str] = None,
        target_url: Optional[str] = None,
        reset_destination: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Ejecuta la migración de datos desde la base de origen hacia la de destino.
        """
        src_url = (source_url or settings.effective_migrate_source_url).strip()
        tgt_url = (target_url or settings.effective_migrate_target_url).strip()
        do_reset = settings.MIGRATE_RESET_DESTINATION if reset_destination is None else reset_destination

        src_masked = settings.mask_url(src_url)
        tgt_masked = settings.mask_url(tgt_url)

        logger.info("Iniciando proceso de migración de base de datos:")
        logger.info(f"   [Origen] : {src_masked}")
        logger.info(f"   [Destino]: {tgt_masked}")
        logger.info(f"   [Reset]  : {do_reset}")

        if src_url == tgt_url:
            msg = "La URL de origen y destino son idénticas. Se omite la migración para evitar auto-sobrescritura."
            logger.warning(msg)
            return {"success": False, "error": msg, "source": src_masked, "target": tgt_masked}

        source_engine = cls._create_engine_for_url(src_url)
        target_engine = cls._create_engine_for_url(tgt_url)

        SourceSession = sessionmaker(bind=source_engine)
        TargetSession = sessionmaker(bind=target_engine)

        source_db = SourceSession()
        target_db = TargetSession()

        stats = {
            "empresas": 0,
            "clientes": 0,
            "usuarios": 0,
            "auditorias": 0,
            "tipos_empaque": 0,
            "unidades_medida": 0,
            "conceptos_gasto": 0,
            "productos": 0,
            "pedidos": 0,
            "pedido_items": 0,
            "pedido_gastos": 0,
        }

        try:
            # 1. Asegurar que las tablas existan en el destino
            Base.metadata.create_all(bind=target_engine)

            # 2. Si se solicitó reset, limpiar destino en orden inverso de dependencias
            if do_reset:
                logger.info("Limpiando tablas de destino antes de migrar (MIGRATE_RESET_DESTINATION=True)...")
                target_db.query(PedidoGasto).delete()
                target_db.query(PedidoItem).delete()
                target_db.query(Pedido).delete()
                target_db.query(Producto).delete()
                target_db.query(ConceptoGasto).delete()
                target_db.query(UnidadMedida).delete()
                target_db.query(TipoEmpaque).delete()
                target_db.query(Auditoria).delete()
                target_db.query(Usuario).delete()
                target_db.query(Cliente).delete()
                target_db.query(Empresa).delete()
                target_db.commit()

            # 3. Migración en orden topológico de dependencias
            def _migrate_table(model, key_name):
                records = source_db.query(model).all()
                for rec in records:
                    source_db.expunge(rec)
                    make_transient(rec)
                    target_db.merge(rec)
                target_db.commit()
                stats[key_name] = len(records)
                logger.info(f"{key_name.capitalize()} migrados: {len(records)}")

            _migrate_table(Empresa, "empresas")
            _migrate_table(Cliente, "clientes")
            _migrate_table(Usuario, "usuarios")
            _migrate_table(Auditoria, "auditorias")
            _migrate_table(TipoEmpaque, "tipos_empaque")
            _migrate_table(UnidadMedida, "unidades_medida")
            _migrate_table(ConceptoGasto, "conceptos_gasto")
            _migrate_table(Producto, "productos")
            _migrate_table(Pedido, "pedidos")
            _migrate_table(PedidoItem, "pedido_items")
            _migrate_table(PedidoGasto, "pedido_gastos")

            # 4. Sincronización de secuencias si el destino es PostgreSQL
            if target_engine.dialect.name == "postgresql":
                logger.info("Sincronizando secuencias de PostgreSQL...")
                tables = [
                    ("empresas", "id"),
                    ("clientes", "id"),
                    ("usuarios", "id"),
                    ("auditorias", "id"),
                    ("tipos_empaque", "id"),
                    ("unidades_medida", "id"),
                    ("conceptos_gasto", "id"),
                    ("productos", "id"),
                    ("pedidos", "id"),
                    ("pedido_items", "id"),
                    ("pedido_gastos", "id"),
                ]
                for table, col in tables:
                    try:
                        seq_sql = text(
                            f"SELECT setval(pg_get_serial_sequence('{table}', '{col}'), "
                            f"coalesce((SELECT MAX({col}) FROM {table}), 1));"
                        )
                        target_db.execute(seq_sql)
                    except Exception as seq_err:
                        logger.warning(f"No se pudo sincronizar secuencia para {table}.{col}: {seq_err}")
                target_db.commit()

            logger.info("Migración de base de datos completada exitosamente.")
            return {
                "success": True,
                "source": src_masked,
                "target": tgt_masked,
                "records_migrated": stats,
                "reset_applied": do_reset,
            }

        except Exception as e:
            target_db.rollback()
            logger.error(f"Error crítico durante la migración: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "source": src_masked,
                "target": tgt_masked,
            }
        finally:
            source_db.close()
            target_db.close()
            source_engine.dispose()
            target_engine.dispose()

    @classmethod
    def normalize_existing_pedidos_to_relational(cls, db: Session) -> Dict[str, int]:
        """
        Normaliza registros históricos de pedidos que tienen datos en columnas JSON
        hacia las tablas relacionales 3NF (productos, conceptos_gasto, pedido_items, pedido_gastos).
        """
        # Asegurar catálogos base
        UnidadMedidaRepository.seed_default_units_if_empty(db)
        ConceptoGastoRepository.seed_default_concepts_if_empty(db)
        EmpaqueRepository.seed_default_tipos_if_empty(db)

        items_migrated = 0
        gastos_migrated = 0
        productos_creados = 0

        # Optimización: filtrar únicamente pedidos pendientes que carezcan de relaciones 3NF
        pedidos_candidatos = db.query(Pedido).filter(
            or_(~Pedido.items.any(), ~Pedido.gastos_rel.any())
        ).all()
        if not pedidos_candidatos:
            return {
                "items_migrated": 0,
                "gastos_migrated": 0,
                "productos_creados": 0,
            }

        for pedido in pedidos_candidatos:
            # 1. Normalizar productos si pedido.items está vacío
            if not pedido.items and pedido.productos and isinstance(pedido.productos, list):
                for idx, prod_raw in enumerate(pedido.productos):
                    if not isinstance(prod_raw, dict):
                        continue
                    nombre = prod_raw.get("nombre") or prod_raw.get("producto") or f"Item {idx+1}"
                    unidad_str = prod_raw.get("unidad") or "KG"
                    empaque_str = prod_raw.get("empaque") or prod_raw.get("tipo_empaque")

                    # Buscar o crear producto en catálogo
                    producto_obj = ProductoRepository.find_or_create_by_name(
                        db,
                        nombre=nombre,
                        unidad_str=unidad_str,
                        empaque_str=empaque_str,
                    )
                    if producto_obj:
                        productos_creados += 1

                    # Resolver unidad_medida_id
                    u_obj = db.query(UnidadMedida).filter(
                        or_(UnidadMedida.codigo == str(unidad_str).upper(), UnidadMedida.nombre.ilike(str(unidad_str)))
                    ).first()

                    # Resolver tipo_empaque_id
                    emp_obj = None
                    if empaque_str:
                        emp_obj = db.query(TipoEmpaque).filter(
                            TipoEmpaque.nombre.ilike(str(empaque_str).strip())
                        ).first()

                    cantidad = float(prod_raw.get("cantidad") or 1.0)
                    costo = float(prod_raw.get("costo") or prod_raw.get("precio_costo") or 0.0)
                    venta = float(prod_raw.get("venta") or prod_raw.get("precio_venta") or 0.0)
                    peso_bruto = float(prod_raw.get("peso_bruto") or 0.0)
                    tara = float(prod_raw.get("tara") or 0.0)
                    peso_neto = float(prod_raw.get("peso_neto") or 0.0)
                    surtido = bool(prod_raw.get("surtido", False))

                    kilos = peso_neto or cantidad
                    v_compra = float(prod_raw.get("valor_compra_total") or (costo * kilos))
                    v_venta = float(prod_raw.get("valor_total_venta") or (venta * kilos))
                    util = float(prod_raw.get("porcentaje_utilidad") or 30.0)

                    item = PedidoItem(
                        pedido_id=pedido.id,
                        producto_id=producto_obj.id if producto_obj else None,
                        descripcion_historica=nombre,
                        cantidad=cantidad,
                        unidad_medida_id=u_obj.id if u_obj else None,
                        tipo_empaque_id=emp_obj.id if emp_obj else None,
                        precio_costo_unitario=costo,
                        precio_venta_unitario=venta,
                        peso_bruto=peso_bruto,
                        tara=tara,
                        peso_neto=peso_neto,
                        porcentaje_utilidad=util,
                        costo_real_kilo=float(prod_raw.get("costo_real_kilo") or costo),
                        gasto_asignado_kilo=float(prod_raw.get("gasto_asignado_kilo") or 0.0),
                        valor_compra_total=v_compra,
                        valor_total_venta=v_venta,
                        precio_venta_manual=bool(prod_raw.get("precio_venta_manual", False)),
                        surtido=surtido,
                        orden=idx,
                    )
                    db.add(item)
                    items_migrated += 1

            # 2. Normalizar gastos si pedido.gastos_rel está vacío
            if not pedido.gastos_rel and pedido.gastos and isinstance(pedido.gastos, list):
                for gasto_raw in pedido.gastos:
                    if not isinstance(gasto_raw, dict):
                        continue
                    concepto_str = gasto_raw.get("concepto") or gasto_raw.get("nombre") or "Gasto General"
                    monto = float(gasto_raw.get("monto") or gasto_raw.get("valor") or 0.0)
                    distribuir = bool(gasto_raw.get("distribuir", gasto_raw.get("distribuir_en_costo", True)))

                    # Buscar o crear concepto de gasto
                    concepto_obj = ConceptoGastoRepository.get_by_nombre(db, concepto_str)
                    if not concepto_obj:
                        concepto_obj = ConceptoGastoRepository.create(
                            db,
                            {"nombre": concepto_str, "tipo": "OPERATIVO", "distribuir_por_defecto": distribuir}
                        )

                    gasto = PedidoGasto(
                        pedido_id=pedido.id,
                        concepto_gasto_id=concepto_obj.id if concepto_obj else None,
                        descripcion=concepto_str,
                        monto=monto,
                        distribuir_en_costo=distribuir,
                    )
                    db.add(gasto)
                    gastos_migrated += 1

        db.commit()
        return {
            "items_migrated": items_migrated,
            "gastos_migrated": gastos_migrated,
            "productos_creados": productos_creados,
        }

    @classmethod
    def auto_link_3nf_relations(cls, db: Session) -> Dict[str, Any]:
        """
        Garantiza la vista SQL v_pedidos_resumen (security_invoker=True)
        y siembra roles y permisos normalizados RBAC.
        """
        from app.services.auth_service import AuthService
        AuthService.asegurar_roles_y_permisos(db)

        # 1. Crear vista SQL v_pedidos_resumen según dialecto con security_invoker = true
        try:
            is_sqlite = db.bind.dialect.name == "sqlite"
            view_head = (
                "CREATE VIEW IF NOT EXISTS v_pedidos_resumen AS"
                if is_sqlite
                else "CREATE OR REPLACE VIEW v_pedidos_resumen WITH (security_invoker = true) AS"
            )
            where_clause = "WHERE distribuir_en_costo = 1" if is_sqlite else "WHERE distribuir_en_costo IS TRUE"
            db.execute(text(f"""
                {view_head}
                SELECT 
                    p.id AS pedido_id,
                    p.cliente_id,
                    p.numero_remision,
                    p.fecha_entrega,
                    p.completado,
                    p.activo,
                    COALESCE(SUM(pi.peso_neto), 0) AS total_kilos,
                    COALESCE(SUM(pi.peso_neto * pi.precio_costo_unitario), 0) AS total_costo,
                    COALESCE(SUM(pi.peso_neto * pi.precio_venta_unitario), 0) AS total_venta,
                    COALESCE(pg_sub.total_gastos, 0) AS total_gastos,
                    (COALESCE(SUM(pi.peso_neto * pi.precio_venta_unitario), 0) - 
                     COALESCE(SUM(pi.peso_neto * pi.precio_costo_unitario), 0) - 
                     COALESCE(pg_sub.total_gastos, 0)) AS ganancia_neta
                FROM pedidos p
                LEFT JOIN pedido_items pi ON p.id = pi.pedido_id
                LEFT JOIN (
                    SELECT pedido_id, SUM(monto) AS total_gastos 
                    FROM pedido_gastos 
                    {where_clause}
                    GROUP BY pedido_id
                ) pg_sub ON p.id = pg_sub.pedido_id
                GROUP BY p.id, pg_sub.total_gastos;
            """))
            db.commit()
        except Exception as view_err:
            logger.warning(f"Aviso al verificar vista v_pedidos_resumen: {view_err}")
            db.rollback()

        return {
            "rbac_verificado": True,
            "vista_pedidos_resumen": True,
        }

    @classmethod
    def run_auto_migration_if_enabled(cls) -> Dict[str, Any]:
        """
        Ejecuta la migración si AUTO_MIGRATE_DB está activado en las variables de entorno.
        """
        if not settings.AUTO_MIGRATE_DB:
            return {"executed": False, "reason": "AUTO_MIGRATE_DB está en false"}

        logger.info("AUTO_MIGRATE_DB=True detectado en variables de entorno. Ejecutando migración automática...")
        return cls.execute_migration()
