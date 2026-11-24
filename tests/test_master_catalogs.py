import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.database import Base
from app.models.unidad_medida import UnidadMedida
from app.models.concepto_gasto import ConceptoGasto
from app.models.producto import Producto
from app.models.empaque import TipoEmpaque
from app.models.cliente import Cliente
from app.models.pedido import Pedido
from app.models.pedido_item import PedidoItem
from app.models.pedido_gasto import PedidoGasto
from app.repositories.unidad_medida_repository import UnidadMedidaRepository
from app.repositories.concepto_gasto_repository import ConceptoGastoRepository
from app.repositories.producto_repository import ProductoRepository
from app.services.migration_service import DatabaseMigrationService

# In-memory shared test database
engine_test = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)


@pytest.fixture(autouse=True)
def init_test_db():
    Base.metadata.create_all(bind=engine_test)
    yield
    Base.metadata.drop_all(bind=engine_test)


def test_seed_and_crud_unidades_medida():
    db = TestingSession()
    try:
        # Seed defaults
        seeded = UnidadMedidaRepository.seed_default_units_if_empty(db)
        assert seeded >= 5

        units = UnidadMedidaRepository.get_all(db)
        codigos = [u.codigo for u in units]
        assert "KG" in codigos
        assert "LB" in codigos
        assert "UND" in codigos

        # KG factor is 1.0
        kg = UnidadMedidaRepository.get_by_codigo(db, "KG")
        assert kg is not None
        assert kg.factor_conversion_kg == 1.0

        # LB factor is 0.5
        lb = UnidadMedidaRepository.get_by_codigo(db, "LB")
        assert lb is not None
        assert lb.factor_conversion_kg == 0.5

        # Create custom unit
        custom = UnidadMedidaRepository.create(db, {
            "codigo": "CAJA_10",
            "nombre": "Caja 10 Kilos",
            "tipo_magnitud": "PESO",
            "factor_conversion_kg": 10.0
        })
        assert custom.id is not None
        assert custom.codigo == "CAJA_10"

        # Update
        updated = UnidadMedidaRepository.update(db, custom.id, {"nombre": "Caja de 10 Kilogramos"})
        assert updated.nombre == "Caja de 10 Kilogramos"

        # Delete (soft)
        deleted = UnidadMedidaRepository.delete(db, custom.id)
        assert deleted is True
        assert UnidadMedidaRepository.get_by_id(db, custom.id).activo is False
    finally:
        db.close()


def test_seed_and_crud_conceptos_gasto():
    db = TestingSession()
    try:
        seeded = ConceptoGastoRepository.seed_default_concepts_if_empty(db)
        assert seeded >= 5

        concepts = ConceptoGastoRepository.get_all(db)
        nombres = [c.nombre for c in concepts]
        assert "Flete" in nombres
        assert "Cargue y Descargue" in nombres

        # Create custom concept
        custom = ConceptoGastoRepository.create(db, {
            "nombre": "Alquiler de Bodega",
            "tipo": "LOGISTICO",
            "distribuir_por_defecto": False
        })
        assert custom.id is not None
        assert custom.tipo == "LOGISTICO"
        assert custom.distribuir_por_defecto is False

        # Soft delete
        deleted = ConceptoGastoRepository.delete(db, custom.id)
        assert deleted is True
        assert ConceptoGastoRepository.get_by_id(db, custom.id).activo is False
    finally:
        db.close()


def test_crud_producto_and_empaques():
    db = TestingSession()
    try:
        UnidadMedidaRepository.seed_default_units_if_empty(db)
        kg = UnidadMedidaRepository.get_by_codigo(db, "KG")

        # Create packaging types
        bulto = TipoEmpaque(nombre="Bulto", peso_kg=50.0, peso_lb=100.0, activo=True)
        canastilla = TipoEmpaque(nombre="Canastilla", peso_kg=22.0, peso_lb=44.0, activo=True)
        db.add(bulto)
        db.add(canastilla)
        db.commit()
        db.refresh(bulto)
        db.refresh(canastilla)

        # Create product with permitted packagings
        prod = ProductoRepository.create(
            db,
            {
                "nombre": "PAPA PASTUSA",
                "categoria": "TUBERCULOS",
                "unidad_medida_id": kg.id,
                "tipo_empaque_id": bulto.id,
                "precio_costo_referencia": 120000.0,
                "precio_venta_referencia": 150000.0,
            },
            empaque_ids=[bulto.id, canastilla.id]
        )
        assert prod.id is not None
        assert prod.nombre == "PAPA PASTUSA"
        assert len(prod.empaques_permitidos) == 2

        # Find or create
        existing = ProductoRepository.find_or_create_by_name(db, "PAPA PASTUSA")
        assert existing.id == prod.id

        new_prod = ProductoRepository.find_or_create_by_name(db, "TOMATE CHONTO", unidad_str="KG", empaque_str="Canastilla")
        assert new_prod.id != prod.id
        assert new_prod.nombre == "TOMATE CHONTO"
        assert new_prod.unidad_medida_id == kg.id
        assert new_prod.tipo_empaque_id == canastilla.id
    finally:
        db.close()


def test_producto_empaques_config_custom_weights():
    db = TestingSession()
    try:
        kg = db.query(UnidadMedida).filter(UnidadMedida.codigo == "KG").first()
        bulto = db.query(TipoEmpaque).filter(TipoEmpaque.nombre == "Bulto").first()
        if not bulto:
            bulto = TipoEmpaque(nombre="Bulto", peso_kg=50.0, peso_lb=100.0)
            db.add(bulto)
            db.commit()
            db.refresh(bulto)

        canastilla = db.query(TipoEmpaque).filter(TipoEmpaque.nombre == "Canastilla").first()
        if not canastilla:
            canastilla = TipoEmpaque(nombre="Canastilla", peso_kg=25.0, peso_lb=50.0)
            db.add(canastilla)
            db.commit()
            db.refresh(canastilla)

        # Create product with custom empaques_config (Cebolla: Bulto=45kg, Canastilla=22kg)
        prod = ProductoRepository.create(
            db,
            {
                "nombre": "CEBOLLA ROJA TEST",
                "categoria": "VERDURAS",
                "unidad_medida_id": kg.id if kg else None,
            },
            empaques_config=[
                {"tipo_empaque_id": bulto.id, "peso_kg": 45.0},
                {"tipo_empaque_id": canastilla.id, "peso_kg": 22.0},
            ]
        )
        assert prod.id is not None
        assert len(prod.empaques_permitidos) == 2

        bulto_perm = next(e for e in prod.empaques_permitidos if e["id"] == bulto.id)
        assert bulto_perm["peso_kg"] == 45.0
        assert bulto_perm["peso_lb"] == 90.0
        assert bulto_perm["peso_kg_default"] == 50.0

        canastilla_perm = next(e for e in prod.empaques_permitidos if e["id"] == canastilla.id)
        assert canastilla_perm["peso_kg"] == 22.0
        assert canastilla_perm["peso_lb"] == 44.0
        assert canastilla_perm["peso_kg_default"] == 25.0

        # Update packaging weights
        updated = ProductoRepository.update(
            db,
            prod.id,
            {},
            empaques_config=[
                {"tipo_empaque_id": bulto.id, "peso_kg": 46.5},
            ]
        )
        assert len(updated.empaques_permitidos) == 1
        assert updated.empaques_permitidos[0]["peso_kg"] == 46.5
        assert updated.empaques_permitidos[0]["peso_lb"] == 93.0
    finally:
        db.close()


def test_normalize_legacy_pedidos_to_3nf():
    db = TestingSession()
    try:
        # Create a cliente
        cliente = Cliente(
            razon_social="FRUVER EL OASIS",
            nit="900123456-1",
            activo=True
        )
        db.add(cliente)
        db.commit()
        db.refresh(cliente)

        # Create a legacy Pedido with JSON productos and JSON gastos
        pedido = Pedido(
            cliente_id=cliente.id,
            numero_remision="REM-TEST-001",
            productos=[
                {
                    "nombre": "CEBOLLA CABEZONA",
                    "cantidad": 5.0,
                    "unidad": "KG",
                    "empaque": "Bulto",
                    "costo": 2000.0,
                    "venta": 2800.0,
                    "peso_bruto": 255.0,
                    "tara": 5.0,
                    "peso_neto": 250.0,
                    "surtido": True,
                },
                {
                    "nombre": "PLATANO VERDE",
                    "cantidad": 10.0,
                    "unidad": "UND",
                    "costo": 800.0,
                    "venta": 1200.0,
                }
            ],
            gastos=[
                {
                    "concepto": "Flete Transportador",
                    "monto": 45000.0,
                    "distribuir": True,
                }
            ],
            activo=True
        )
        db.add(pedido)
        db.commit()
        db.refresh(pedido)

        # Initially items and gastos_rel are empty
        assert len(pedido.items) == 0
        assert len(pedido.gastos_rel) == 0

        # Run normalization
        stats = DatabaseMigrationService.normalize_existing_pedidos_to_relational(db)
        assert stats["items_migrated"] == 2
        assert stats["gastos_migrated"] == 1

        # Reload pedido
        db.refresh(pedido)
        assert len(pedido.items) == 2
        assert len(pedido.gastos_rel) == 1

        item1 = pedido.items[0]
        assert item1.descripcion_historica == "CEBOLLA CABEZONA"
        assert item1.cantidad == 5.0
        assert item1.peso_neto == 250.0
        assert item1.surtido is True
        assert item1.producto is not None
        assert item1.producto.nombre == "CEBOLLA CABEZONA"

        item2 = pedido.items[1]
        assert item2.descripcion_historica == "PLATANO VERDE"
        assert item2.cantidad == 10.0

        gasto1 = pedido.gastos_rel[0]
        assert gasto1.descripcion == "Flete Transportador"
        assert gasto1.monto == 45000.0
        assert gasto1.distribuir_en_costo is True
        assert gasto1.concepto is not None
    finally:
        db.close()
