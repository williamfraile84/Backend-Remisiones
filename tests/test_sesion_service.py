import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.core.security import get_password_hash
from app.models.usuario import Usuario, DEFAULT_ADMIN_PERMISSIONS
from app.models.sesion import Sesion
from app.repositories.sesion_repository import SesionRepository
from app.services.auth_service import AuthService


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSession()

    user = Usuario(
        username="test_session_user",
        nombre_completo="Usuario de Prueba Sesion",
        email="sesion@fruver.com",
        hashed_password=get_password_hash("pass123"),
        rol="admin",
        permisos=DEFAULT_ADMIN_PERMISSIONS.copy(),
        activo=True,
    )
    db.add(user)
    db.commit()

    yield db
    db.close()


def test_sesion_creation_and_lookup(db_session):
    user = db_session.query(Usuario).filter_by(username="test_session_user").first()
    
    # Generar token y persistir sesión
    token_data = AuthService.generar_token_acceso(user, db=db_session)
    assert "access_token" in token_data
    
    # Debe existir registro en SesionRepository
    activas = SesionRepository.get_active_by_user(db_session, user.id)
    assert len(activas) == 1
    sesion = activas[0]
    assert sesion.usuario_id == user.id
    assert sesion.activo is True
    assert sesion.token_jti is not None

    # Consulta por JTI
    found = SesionRepository.get_active_by_jti(db_session, sesion.token_jti)
    assert found is not None
    assert found.id == sesion.id


def test_sesion_soft_delete_revocation(db_session):
    user = db_session.query(Usuario).filter_by(username="test_session_user").first()
    
    token_data = AuthService.generar_token_acceso(user, db=db_session)
    activas = SesionRepository.get_active_by_user(db_session, user.id)
    assert len(activas) == 1
    jti = activas[0].token_jti

    # Revocar sesión (logout)
    ok = AuthService.revocar_sesion(db_session, jti)
    assert ok is True

    # Ya no debe retornar como activa
    active_after = SesionRepository.get_active_by_jti(db_session, jti)
    assert active_after is None

    # Debe permanecer en base de datos con soft delete
    sesion_in_db = SesionRepository.get_by_jti(db_session, jti)
    assert sesion_in_db is not None
    assert sesion_in_db.activo is False
    assert sesion_in_db.eliminado_en is not None


def test_sesion_expiration_check(db_session):
    user = db_session.query(Usuario).filter_by(username="test_session_user").first()
    
    # Crear sesión expirada manualmente
    sesion_expirada = Sesion(
        usuario_id=user.id,
        token_jti="expired_jti_123",
        activo=True,
        expira_en=datetime.now(timezone.utc) - timedelta(hours=1),
        ultimo_acceso=datetime.now(timezone.utc) - timedelta(hours=2),
    )
    db_session.add(sesion_expirada)
    db_session.commit()

    # get_active_by_jti debe ignorar la sesión expirada
    active = SesionRepository.get_active_by_jti(db_session, "expired_jti_123")
    assert active is None

