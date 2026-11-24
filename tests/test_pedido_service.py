import pytest
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.database import Base
from app.models.usuario import Usuario
from app.models.cliente import Cliente
from app.models.empresa import Empresa
from app.models.pedido import Pedido
from app.models.pedido_item import PedidoItem
from app.models.pedido_gasto import PedidoGasto
from app.models.producto import Producto
from app.schemas.pedido import PedidoSavePayload
from app.services.pedido_service import PedidoService
from app.services.export_service import ExportContext, PdfRemisionStrategy, ExcelRemisionStrategy

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


def test_pedido_service_lifecycle():
    db = TestingSession()
    try:
        # Create registered product in catalog
        prod = Producto(nombre="MANZANA GALA", activo=True)
        db.add(prod)

        # Create user
        user = Usuario(
            username="test_serv",
            nombre_completo="Test Service",
            email="test_serv@fruver.com",
            hashed_password="hash",
            rol="admin",
            permisos={"puede_crear_pedidos": True, "puede_cerrar_pedidos": True, "puede_desactivar_pedidos": True},
            activo=True,
        )
        db.add(user)

        # Create client
        cliente = Cliente(
            razon_social="FRUVER LA 80",
            nit="800999000-1",
            consecutivo_remision_actual=101,
            activo=True,
        )
        db.add(cliente)
        db.commit()
        db.refresh(cliente)

        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers = {}

        # 1. Guardar nuevo pedido
        payload = PedidoSavePayload(
            cliente_id=cliente.id,
            numero_oc="OC-555",
            productos=[
                {
                    "nombre": "MANZANA GALA",
                    "cantidad": 10.0,
                    "unidad": "KG",
                    "empaque": "Caja",
                    "costo": 4000.0,
                    "venta": 5500.0,
                    "surtido": True,
                    "peso_neto": 10.0,
                }
            ],
            gastos=[
                {
                    "concepto": "Flete Urbano",
                    "monto": 15000.0,
                    "distribuir": True,
                }
            ],
            utilidad_global=30.0,
        )

        pedido = PedidoService.guardar_pedido(db, payload, user, mock_request)
        assert pedido.id is not None
        assert pedido.numero_remision == "101"
        assert cliente.consecutivo_remision_actual == 102

        # Verify relational items created
        assert len(pedido.items) == 1
        item = pedido.items[0]
        assert item.descripcion_historica == "MANZANA GALA"
        assert item.surtido is True
        assert item.producto is not None

        # Verify relational gastos created
        assert len(pedido.gastos_rel) == 1
        gasto = pedido.gastos_rel[0]
        assert gasto.descripcion == "Flete Urbano"
        assert gasto.distribuir_en_costo is True

        # 2. Cerrar pedido formalmente
        cerrado = PedidoService.cerrar_pedido(db, pedido.id, user, mock_request)
        assert cerrado.completado is True

        # 3. Eliminar pedido (soft delete)
        res = PedidoService.eliminar_pedido(db, pedido.id, user, mock_request)
        assert res["status"] == "ok"
        db.refresh(pedido)
        assert pedido.activo is False
    finally:
        db.close()


def test_export_strategy_context():
    # Verify strategies are registered and resolve properly
    pdf_strat = ExportContext.get_strategy("pdf-remision")
    assert isinstance(pdf_strat, PdfRemisionStrategy)
    assert pdf_strat.media_type == "application/pdf"
    assert pdf_strat.file_extension == "pdf"

    excel_strat = ExportContext.get_strategy("excel-remision")
    assert isinstance(excel_strat, ExcelRemisionStrategy)
    assert "spreadsheetml" in excel_strat.media_type
    assert excel_strat.file_extension == "xlsx"

    # Test unknown strategy raises ValueError
    with pytest.raises(ValueError):
        ExportContext.get_strategy("formato-inexistente")

