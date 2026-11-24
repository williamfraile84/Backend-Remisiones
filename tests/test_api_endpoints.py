import pytest
import io
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.core.database import Base, get_db
from app.core.security import get_password_hash
from app.models.usuario import Usuario, DEFAULT_ADMIN_PERMISSIONS, DEFAULT_OPERATOR_PERMISSIONS
from app.models.cliente import Cliente
from app.models.empresa import Empresa
from app.models.pedido import Pedido


# Configurar SQLite en memoria compartido para pruebas
engine_test = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine_test)
    db = TestingSessionLocal()
    
    # Crear admin inicial
    admin = Usuario(
        username="admin_api",
        nombre_completo="Administrador Test",
        email="admin@fruver.com",
        hashed_password=get_password_hash("admin123"),
        rol="admin",
        permisos=DEFAULT_ADMIN_PERMISSIONS.copy(),
        activo=True,
    )
    db.add(admin)

    # Crear operador
    operador = Usuario(
        username="operador_api",
        nombre_completo="Operador Test",
        email="operador@fruver.com",
        hashed_password=get_password_hash("operador123"),
        rol="operador",
        permisos=DEFAULT_OPERATOR_PERMISSIONS.copy(),
        activo=True,
    )
    db.add(operador)

    # Crear empresa
    empresa = Empresa(
        nombre="Fruver Logistics SAS",
        nit="900123456-7",
        direccion="Calle 10 # 20-30",
        telefono="3001234567",
    )
    db.add(empresa)

    # Crear cliente
    cliente = Cliente(
        razon_social="Cliente Principal SAS",
        nit="901999888-1",
        direccion="Carrera 5 # 10-20",
        activo=True,
    )
    db.add(cliente)

    db.commit()
    yield
    db.close()
    Base.metadata.drop_all(bind=engine_test)


@pytest.fixture
def client():
    return TestClient(app)


def test_auth_login_and_me(client):
    # Login exitoso
    res = client.post("/api/auth/login", json={"username": "admin_api", "password": "admin123"})
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    token = data["access_token"]

    # Consultar perfil /me
    res_me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res_me.status_code == 200
    assert res_me.json()["username"] == "admin_api"
    assert res_me.json()["rol"] == "admin"


def test_admin_create_and_manage_users(client):
    # Obtener token de admin
    login_res = client.post("/api/auth/login", json={"username": "admin_api", "password": "admin123"})
    admin_token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Crear nuevo usuario operador
    res_create = client.post(
        "/api/usuarios",
        headers=headers,
        json={
            "username": "nuevo_usuario",
            "nombre_completo": "Nuevo Operador",
            "email": "nuevo@fruver.com",
            "password": "password456",
            "rol": "operador",
            "permisos": {"puede_crear_pedidos": True, "puede_desactivar_pedidos": False},
        },
    )
    assert res_create.status_code == 200
    new_user_id = res_create.json()["id"]

    # Listar usuarios
    res_list = client.get("/api/usuarios", headers=headers)
    assert res_list.status_code == 200
    assert len(res_list.json()) >= 3

    # Baja lógica de usuario
    res_status = client.patch(f"/api/usuarios/{new_user_id}/status", headers=headers, json={"activo": False})
    assert res_status.status_code == 200
    assert res_status.json()["activo"] is False


def test_pedidos_flow_and_soft_delete_rule(client):
    # Login admin
    login_res = client.post("/api/auth/login", json={"username": "admin_api", "password": "admin123"})
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Obtener cliente existente con autenticación
    res_clientes = client.get("/api/clientes", headers=headers)
    assert res_clientes.status_code == 200
    cliente_id = res_clientes.json()[0]["id"]

    # Guardar pedido nuevo
    res_save = client.post(
        "/api/pedidos/guardar",
        headers=headers,
        json={
            "cliente_id": cliente_id,
            "numero_remision": "REM-200",
            "productos": [
                {"producto": "PAPA PASTUSA", "cantidad": 50, "unidad": "Kg", "valor_compra_total": 100000}
            ],
            "gastos": [],
            "utilidad_global": 30.0,
        },
    )
    assert res_save.status_code == 200
    save_data = res_save.json()
    pedido_id = save_data.get("id")
    assert pedido_id is not None

    # Simular carga de factura (cierre)
    fake_file = io.BytesIO(b"%PDF-1.4 Fake PDF Content")
    res_factura = client.post(
        f"/api/pedidos/{pedido_id}/factura",
        headers=headers,
        files={"file": ("factura.pdf", fake_file, "application/pdf")},
    )
    assert res_factura.status_code == 200

    # Desactivar pedido lógicamente (debe ser EXITOSO con baja lógica)
    res_del = client.delete(f"/api/pedidos/{pedido_id}", headers=headers)
    assert res_del.status_code == 200
    assert "desactivado" in res_del.json()["message"].lower()


def test_auditoria_logs_recorded(client):
    # Login admin
    login_res = client.post("/api/auth/login", json={"username": "admin_api", "password": "admin123"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Consultar auditoría
    res_audit = client.get("/api/auditoria", headers=headers)
    assert res_audit.status_code == 200
    audit_data = res_audit.json()
    assert audit_data["total"] > 0
    acciones = [item["accion"] for item in audit_data["items"]]
    assert "LOGIN" in acciones


def test_auditoria_csv_export(client):
    # Login admin
    login_res = client.post("/api/auth/login", json={"username": "admin_api", "password": "admin123"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Exportar CSV
    res_csv = client.get("/api/auditoria/export-csv", headers=headers)
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers["content-type"]
    assert "Fecha y Hora" in res_csv.text
    assert "LOGIN" in res_csv.text


def test_magic_bytes_file_validation(client):
    # Login admin
    login_res = client.post("/api/auth/login", json={"username": "admin_api", "password": "admin123"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Archivo con extensión .pdf pero contenido corrupto que no es PDF
    corrupt_file = io.BytesIO(b"NOT_A_REAL_PDF_HEADER_12345")
    res_corrupt = client.post(
        "/api/pedidos/upload-documento",
        headers=headers,
        files={"file": ("pedido_falso.pdf", corrupt_file, "application/pdf")},
    )
    assert res_corrupt.status_code == 400
    assert "no corresponde" in res_corrupt.json()["detail"].lower()


def test_security_unauthenticated_endpoints_blocked(client):
    """Verifica que todos los endpoints críticos rechacen conexiones anónimas con 401."""
    # 1. Clientes
    assert client.get("/api/clientes").status_code == 401
    
    # 2. Historial de pedidos
    assert client.get("/api/pedidos/historial/1").status_code == 401
    
    # 3. Previsualización y descarga de facturas y remisiones
    assert client.get("/api/pedidos/1/factura/preview").status_code == 401
    assert client.get("/api/pedidos/1/factura/descargar").status_code == 401
    assert client.get("/api/pedidos/1/remision-firmada/preview").status_code == 401
    assert client.get("/api/pedidos/1/remision-firmada/descargar").status_code == 401
    
    # 4. Mutaciones de empaque
    assert client.post("/api/empaques/tipos", json={"nombre": "FakeTipo"}).status_code == 401
    assert client.put("/api/empaques/tipos/1", json={"nombre": "FakeTipo"}).status_code == 401
    assert client.delete("/api/empaques/tipos/1").status_code == 401
    assert client.post("/api/empaques", json={"presentacion": "Fake", "peso_kg": 10}).status_code == 401


def test_query_param_token_preview(client):
    """Verifica que el parámetro query ?token=<jwt> autentique válidamente previsualizaciones."""
    # Obtener token válido
    login_res = client.post("/api/auth/login", json={"username": "admin_api", "password": "admin123"})
    token = login_res.json()["access_token"]
    
    # Si el pedido no existe, debe responder 404 (no 401) demostrando que la autenticación fue exitosa
    res = client.get(f"/api/pedidos/9999/factura/preview?token={token}")
    assert res.status_code == 404
    assert res.status_code != 401


def test_multi_empresa_api_endpoints(client):
    """Verifica creación de múltiples empresas y conmutación con X-Empresa-Id."""
    login_res = client.post("/api/auth/login", json={"username": "admin_api", "password": "admin123"})
    admin_token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # 1. Crear una nueva empresa adicional
    res1 = client.post(
        "/api/empresa",
        json={"nombre": "Empresa Frutas del Valle", "nit": "901111111-1", "direccion": "Valle"},
        headers=headers,
    )
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["configurada"] is True
    assert data1["total_empresas"] >= 1
    emp1_id = data1["empresa"]["id"]

    # 2. Crear otra empresa adicional
    res2 = client.post(
        "/api/empresa",
        json={"nombre": "Empresa Hortalizas de la Sabana", "nit": "902222222-2", "direccion": "Sabana"},
        headers=headers,
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["total_empresas"] >= 2
    emp2_id = data2["empresa"]["id"]

    # 3. Listar todas
    res_list = client.get("/api/empresa", headers=headers)
    assert res_list.status_code == 200
    assert len(res_list.json()) >= 2

    # 4. Status con X-Empresa-Id apuntando a la empresa 2
    res_status = client.get("/api/empresa/status", headers={**headers, "X-Empresa-Id": str(emp2_id)})
    assert res_status.status_code == 200
    status_data = res_status.json()
    assert status_data["empresa"]["id"] == emp2_id
    assert status_data["empresa"]["nombre"] == "Empresa Hortalizas de la Sabana"


def test_logout_and_session_invalidation(client):
    """Verifica que /api/auth/logout invalide la sesión y subsecuentes peticiones retornen 401."""
    # 1. Iniciar sesión
    login_res = client.post("/api/auth/login", json={"username": "admin_api", "password": "admin123"})
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Consultar sesiones activas
    res_ses = client.get("/api/auth/sesiones", headers=headers)
    assert res_ses.status_code == 200
    assert res_ses.json()["total_activas"] >= 1

    # 3. Petición autenticada válida
    res_me = client.get("/api/auth/me", headers=headers)
    assert res_me.status_code == 200

    # 4. Cerrar sesión
    res_logout = client.post("/api/auth/logout", headers=headers)
    assert res_logout.status_code == 200
    assert res_logout.json()["status"] == "ok"

    # 5. Intentar acceder nuevamente con el token revocado -> Debe retornar 401
    res_revocado = client.get("/api/auth/me", headers=headers)
    assert res_revocado.status_code == 401




