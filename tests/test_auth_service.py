import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.core.security import verify_password, get_password_hash, create_access_token, decode_access_token
from app.services.auth_service import AuthService
from app.repositories.usuario_repository import UsuarioRepository


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()


def test_password_hashing():
    pwd = "secretpassword123"
    hashed = get_password_hash(pwd)
    assert hashed != pwd
    assert verify_password(pwd, hashed) is True
    assert verify_password("wrongpassword", hashed) is False


def test_jwt_token_creation_and_decoding():
    payload = {"sub": "123", "username": "carlos_admin", "rol": "admin"}
    token = create_access_token(payload)
    assert isinstance(token, str)
    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded["sub"] == "123"
    assert decoded["username"] == "carlos_admin"
    assert decoded["rol"] == "admin"


def test_create_and_authenticate_user(test_db):
    user = AuthService.crear_usuario(
        db=test_db,
        username="operador1",
        nombre_completo="Juan Perez",
        password="password123",
        email="juan@fruver.com",
        rol="operador",
    )
    assert user.id is not None
    assert user.username == "operador1"
    assert user.rol == "operador"
    assert user.activo is True

    # Autenticación exitosa
    auth_user = AuthService.autenticar_usuario(test_db, "operador1", "password123")
    assert auth_user.id == user.id

    # Token response
    token_resp = AuthService.generar_token_acceso(auth_user)
    assert "access_token" in token_resp
    assert token_resp["user"]["username"] == "operador1"

