import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.models.pedido import Pedido
from app.models.cliente import Cliente
from app.models.usuario import Usuario
from app.repositories.usuario_repository import UsuarioRepository
from app.repositories.pedido_repository import PedidoRepository
from app.services.auth_service import AuthService


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()


def test_soft_delete_user(test_db):
    user = AuthService.crear_usuario(
        db=test_db,
        username="operador_baja",
        nombre_completo="Operador Baja",
        password="pass",
        rol="operador",
    )
    assert user.activo is True

    # Desactivar (Baja lógica)
    UsuarioRepository.set_active_status(test_db, user.id, activo=False)

    # Verificar que el registro NO fue eliminado físicamente
    raw_user = test_db.query(Usuario).filter(Usuario.id == user.id).first()
    assert raw_user is not None
    assert raw_user.activo is False


def test_soft_delete_pedido(test_db):
    cliente = Cliente(razon_social="Cliente Prueba", nit="123456", activo=True)
    test_db.add(cliente)
    test_db.commit()
    test_db.refresh(cliente)

    pedido = Pedido(
        cliente_id=cliente.id,
        numero_remision="REM-100",
        activo=True,
    )
    test_db.add(pedido)
    test_db.commit()
    test_db.refresh(pedido)

    # Baja lógica
    res = PedidoRepository.soft_delete(test_db, pedido.id)
    assert res is True

    # Registro sigue existiendo en BD pero con activo=False
    db_pedido = test_db.query(Pedido).filter(Pedido.id == pedido.id).first()
    assert db_pedido is not None
    assert db_pedido.activo is False

    # Get by id repositorio solo trae activos
    assert PedidoRepository.get_by_id(test_db, pedido.id) is None

