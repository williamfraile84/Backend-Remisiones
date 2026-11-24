import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.database import Base
from app.models import (
    Empresa,
    EmpresaAtributo,
    Cliente,
    ClienteAtributo,
    Pedido,
    PedidoItem,
    PedidoGasto,
    Usuario,
    Auditoria,
    AuditoriaCambio,
    Producto,
    TipoEmpaque,
    UnidadMedida,
    ConceptoGasto,
    Modulo,
)
from app.services.auditoria_service import AuditoriaService
from app.services.migration_service import DatabaseMigrationService

engine_test = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)


@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine_test)
    yield
    Base.metadata.drop_all(bind=engine_test)


def test_empresa_and_cliente_atributos_3nf():
    db = TestingSession()
    try:
        emp = Empresa(nombre="FRUVER CORP", nit="900000001-1", activo=True)
        db.add(emp)
        db.commit()
        db.refresh(emp)

        # Add relational attribute
        at1 = EmpresaAtributo(empresa_id=emp.id, clave="REGIMEN", valor="COMUN")
        db.add(at1)
        db.commit()
        db.refresh(emp)

        assert len(emp.atributos) == 1
        assert emp.campos_extra == [{"id": str(at1.id), "clave": "REGIMEN", "valor": "COMUN"}]

        # Cliente
        cli = Cliente(razon_social="CLIENTE 1", nit="123456-7", consecutivo_remision_actual=1, activo=True)
        db.add(cli)
        db.commit()
        db.refresh(cli)

        cat1 = ClienteAtributo(cliente_id=cli.id, clave="CIUDAD", valor="BOGOTA")
        db.add(cat1)
        db.commit()
        db.refresh(cli)

        assert len(cli.atributos) == 1
        assert cli.campos_extra == [{"id": str(cat1.id), "clave": "CIUDAD", "valor": "BOGOTA"}]
    finally:
        db.close()


def test_auditoria_cambios_3nf():
    db = TestingSession()
    try:
        user = Usuario(
            username="admin_3nf",
            nombre_completo="Admin 3NF",
            hashed_password="hash",
            rol="admin",
            activo=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        # Log event with details dictionary
        audit = AuditoriaService.registrar_evento(
            db=db,
            accion="GUARDAR_PEDIDO",
            modulo="PEDIDOS",
            usuario=user,
            entidad="Pedido",
            entidad_id=1,
            detalles={"remision": "REM-101", "kilos": 500.5, "activo": True},
        )

        assert audit.id is not None
        assert len(audit.cambios) == 3

        # Property details must reconstruct the exact dictionary
        detalles = audit.detalles
        assert detalles["remision"] == "REM-101"
        assert detalles["kilos"] == 500.5
        assert detalles["activo"] is True
    finally:
        db.close()


def test_pedido_dynamic_calculations_no_burned_totals():
    db = TestingSession()
    try:
        cli = Cliente(razon_social="HOTEL CENTRAL", nit="800111222-3", activo=True)
        db.add(cli)
        db.commit()
        db.refresh(cli)

        # Create Pedido without burned totals or JSON columns
        pedido = Pedido(
            cliente_id=cli.id,
            numero_remision="REM-501",
            utilidad_global=25.0,
            activo=True,
        )
        db.add(pedido)
        db.commit()
        db.refresh(pedido)

        # Add 2 items
        item1 = PedidoItem(
            pedido_id=pedido.id,
            descripcion_historica="PAPA PASTUSA",
            cantidad=10.0,
            peso_neto=500.0,
            precio_costo_unitario=1500.0,
            precio_venta_unitario=2000.0,
            porcentaje_utilidad=25.0,
            valor_compra_total=750000.0,
            valor_total_venta=1000000.0,
        )
        item2 = PedidoItem(
            pedido_id=pedido.id,
            descripcion_historica="TOMATE CHONTO",
            cantidad=20.0,
            peso_neto=440.0,
            precio_costo_unitario=2000.0,
            precio_venta_unitario=2800.0,
            porcentaje_utilidad=25.0,
            valor_compra_total=880000.0,
            valor_total_venta=1232000.0,
        )
        db.add_all([item1, item2])

        # Add 1 expense
        gasto = PedidoGasto(
            pedido_id=pedido.id,
            descripcion="Flete Nocturno",
            monto=94000.0,
            distribuir_en_costo=True,
        )
        db.add(gasto)
        db.commit()
        db.refresh(pedido)

        # Dynamic assertions (Zero burned totals in DB!)
        assert pedido.total_kilos == 940.0
        assert pedido.total_costo == 1630000.0
        assert pedido.total_venta == 2232000.0
        assert pedido.total_gastos == 94000.0
        assert pedido.gasto_por_kilo == 100.0  # 94000 / 940 = 100.0
        assert pedido.utilidad_pesos == 2232000.0 - (1630000.0 + 94000.0)

        # Verify dynamic liquidacion structure matches frontend contract
        liq = pedido.liquidacion
        assert liq["resumen"]["total_kilos"] == 940.0
        assert liq["resumen"]["total_ventas"] == 2232000.0
        assert len(liq["items"]) == 2
        assert len(liq["gastos"]) == 1
    finally:
        db.close()


def test_modulo_and_permiso_relational_3nf():
    db = TestingSession()
    try:
        from app.repositories.modulo_repository import ModuloRepository
        from app.models.permiso import Permiso

        # Create module entity
        mod = ModuloRepository.find_or_create(db, "PEDIDOS", "Módulo de Pedidos")
        assert mod.id is not None
        assert mod.codigo == "PEDIDOS"

        # Create permission linked via FK modulo_id
        perm = Permiso(
            codigo="puede_crear_pedidos",
            nombre="Crear Pedidos",
            modulo_id=mod.id,
            activo=True
        )
        db.add(perm)
        db.commit()
        db.refresh(perm)

        assert perm.modulo_id == mod.id
        assert perm.modulo_rel.codigo == "PEDIDOS"
        assert perm.modulo == "PEDIDOS"  # backward-compatibility property
    finally:
        db.close()
