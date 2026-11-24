import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.models.usuario import Usuario
from app.services.auditoria_service import AuditoriaService


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()


def test_auditoria_immutable_logging(test_db):
    user = Usuario(
        username="admin_test",
        nombre_completo="Admin Test",
        hashed_password="hash",
        rol="admin",
        activo=True,
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)

    # Registrar evento
    log_entry = AuditoriaService.registrar_evento(
        db=test_db,
        accion="CREAR_PEDIDO",
        modulo="PEDIDOS",
        usuario=user,
        entidad="Pedido",
        entidad_id=101,
        detalles={"remision": "REM-001", "total": 150000},
    )

    assert log_entry.id is not None
    assert log_entry.usuario_id == user.id
    assert log_entry.usuario_nombre == "Admin Test"
    assert log_entry.usuario_rol == "admin"
    assert log_entry.accion == "CREAR_PEDIDO"
    assert log_entry.entidad_id == "101"

    # Consultar logs con filtros
    total, items = AuditoriaService.consultar_logs(test_db, modulo="PEDIDOS")
    assert total == 1
    assert items[0].accion == "CREAR_PEDIDO"
    assert items[0].detalles["remision"] == "REM-001"

