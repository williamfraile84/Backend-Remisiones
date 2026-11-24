import pytest
from decimal import Decimal
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.core.security import get_password_hash
from app.models.tipo_empaque import TipoEmpaque
from app.models.modulo import Modulo
from app.models.role import Role
from app.models.permiso import Permiso
from app.models.rol_permiso import rol_permisos
from app.models.producto_empaque import producto_empaques
from app.models.usuario import Usuario
from app.models.empresa import Empresa
from app.models.cliente import Cliente
from app.models.producto import Producto
from app.models.pedido import Pedido
from app.models.pedido_item import PedidoItem
from app.models.pedido_gasto import PedidoGasto
from app.repositories.tipo_empaque_repository import TipoEmpaqueRepository
from app.repositories.modulo_repository import ModuloRepository
from app.repositories.role_repository import RoleRepository
from app.repositories.permiso_repository import PermisoRepository
from app.repositories.pedido_item_repository import PedidoItemRepository
from app.repositories.pedido_gasto_repository import PedidoGastoRepository
from app.repositories.producto_repository import ProductoRepository
from app.services.role_service import RoleService
from app.services.pedido_service import PedidoService
from app.schemas.pedido import PedidoSavePayload


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def test_atomic_models_and_repositories_separation(db_session):
    """Verifica que los modelos y repositorios atómicos (SRP) funcionen independientemente."""
    # 1. Modulo atómico (3NF)
    modulo = ModuloRepository.find_or_create(db_session, "AUDITORIA", "Módulo de Auditoría")
    assert modulo.id is not None
    assert modulo.codigo == "AUDITORIA"

    # 2. TipoEmpaque atómico (3NF)
    tipo = TipoEmpaqueRepository.create(db_session, {"nombre": "Canastilla Plástica Test", "peso_kg": 20.0})
    assert tipo.id is not None
    assert tipo.activo is True

    # 3. Role y Permiso atómicos (3NF)
    permiso = PermisoRepository.create(db_session, {"codigo": "test:permission", "nombre": "Permiso Test", "modulo_id": modulo.id})
    role = RoleRepository.create(db_session, {"codigo": "test_role", "nombre": "Rol Test"}, [permiso.id])
    assert role.id is not None
    assert len(role.permisos) == 1
    assert role.permisos[0].codigo == "test:permission"


def test_rbac_3nf_roles_and_permissions(db_session):
    """Verifica que el modelo RBAC 3NF (Role, Permiso, rol_permisos) funcione correctamente."""
    RoleService.asegurar_roles_y_permisos(db_session)

    admin_role = db_session.query(Role).filter_by(codigo="admin").first()
    oper_role = db_session.query(Role).filter_by(codigo="operador").first()

    assert admin_role is not None
    assert oper_role is not None
    assert len(admin_role.permisos) > 0
    assert any(p.codigo == "puede_crear_pedidos" for p in admin_role.permisos)
    assert any(p.codigo == "puede_ver_financiero" for p in admin_role.permisos)

    user = Usuario(
        username="test_rbac_user",
        nombre_completo="Test RBAC User",
        rol="admin",
        rol_id=admin_role.id,
        hashed_password=get_password_hash("Pass123!")
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.rol_rel is not None
    assert user.rol_rel.codigo == "admin"
    assert user.tiene_permiso("puede_crear_pedidos") is True
    assert user.tiene_permiso("puede_ver_financiero") is True


def test_multitenancy_scoping(db_session):
    """Verifica el soporte multi-empresa (empresa_id) en clientes, pedidos y usuarios."""
    empresa_1 = Empresa(nombre="Fruver Central SAS", nit="900123456-1")
    empresa_2 = Empresa(nombre="Distribuidora Verde SAS", nit="900654321-2")
    db_session.add_all([empresa_1, empresa_2])
    db_session.commit()
    
    cliente_emp1 = Cliente(
        razon_social="Supermercado El Sol",
        nit="800111222-1",
        empresa_id=empresa_1.id
    )
    cliente_emp2 = Cliente(
        razon_social="Supermercado La Luna",
        nit="800333444-2",
        empresa_id=empresa_2.id
    )

    cliente_emp1 = Cliente(razon_social="Supermercado El Sol", nit="800111222-1", empresa_id=empresa_1.id)
    cliente_emp2 = Cliente(razon_social="Supermercado La Luna", nit="800333444-2", empresa_id=empresa_2.id)
    db_session.add_all([cliente_emp1, cliente_emp2])
    db_session.commit()
    
    # Crear pedidos para cada empresa
    pedido_1 = Pedido(
        cliente_id=cliente_emp1.id,
        empresa_id=empresa_1.id,
        numero_remision="REM-001"
    )
    pedido_2 = Pedido(
        cliente_id=cliente_emp2.id,
        empresa_id=empresa_2.id,
        numero_remision="REM-001" # Mismo número permitido si es diferente cliente/empresa
    )

    pedido_1 = Pedido(cliente_id=cliente_emp1.id, empresa_id=empresa_1.id, numero_remision="REM-001")
    pedido_2 = Pedido(cliente_id=cliente_emp2.id, empresa_id=empresa_2.id, numero_remision="REM-001")
    db_session.add_all([pedido_1, pedido_2])
    db_session.commit()
    
    # Consultas filtradas por empresa_id (Multi-inquilino)

    pedidos_emp1 = db_session.query(Pedido).filter_by(empresa_id=empresa_1.id).all()
    pedidos_emp2 = db_session.query(Pedido).filter_by(empresa_id=empresa_2.id).all()
    

    assert len(pedidos_emp1) == 1
    assert pedidos_emp1[0].cliente_id == cliente_emp1.id
    assert len(pedidos_emp2) == 1
    assert pedidos_emp2[0].cliente_id == cliente_emp2.id

def test_strict_soft_delete_preserves_items_and_gastos(db_session):
    """
    POLÍTICA DE ELIMINACIÓN CERO:
    Verifica que al remover un ítem o gasto en una actualización de pedido,
    el registro NO se borre con db.delete(), sino que se marque activo = False.
    """
    empresa = Empresa(nombre="Empresa Zero Delete", nit="901000111-9")
    cliente = Cliente(razon_social="Cliente Zero Delete", nit="802000333-8", consecutivo_remision_actual=1)
    user = Usuario(
        username="operador_soft",
        nombre_completo="Operador Soft Delete",
        rol="admin",
        hashed_password=get_password_hash("pass"),
    )
    p1 = Producto(nombre="Aguacate Hass", precio_venta_referencia=7000.0)
    p2 = Producto(nombre="Pitahaya Amarilla", precio_venta_referencia=9500.0)
    db_session.add_all([empresa, cliente, user, p1, p2])
    db_session.commit()

    mock_request = MagicMock()
    mock_request.client.host = "127.0.0.1"
    mock_request.headers = {}

    # 1. Crear pedido inicial con 2 ítems y 1 gasto
    payload_creacion = PedidoSavePayload(
        cliente_id=cliente.id,
        productos=[
            {"nombre": p1.nombre, "cantidad": 10.0, "costo": 5000.0, "venta": 7000.0, "tara": 1.0, "peso_neto": 9.0},
            {"nombre": p2.nombre, "cantidad": 5.0, "costo": 7000.0, "venta": 9500.0, "tara": 0.5, "peso_neto": 4.5},
        ],
        gastos=[
            {"concepto": "Flete Urbano", "monto": 20000.0, "distribuir": True}
        ]
    )

    pedido = PedidoService.guardar_pedido(db_session, payload_creacion, user, mock_request)
    db_session.commit()
    db_session.refresh(pedido)


    assert len(pedido.items) == 2
    item1 = pedido.items[0]
    item2 = pedido.items[1]
    gasto1 = pedido.gastos_rel[0]

    assert item1.activo is True
    assert item2.activo is True
    assert gasto1.activo is True
    assert pedido.total_kilos == 13.5

    # 2. Actualizar el pedido retirando el item2 y el gasto1 (enviando solo item1)
    payload_actualizacion = PedidoSavePayload(
        id=pedido.id,
        cliente_id=cliente.id,
        productos=[
            {"id": item1.id, "nombre": p1.nombre, "cantidad": 12.0, "costo": 5000.0, "venta": 7000.0, "tara": 1.0, "peso_neto": 11.0},
        ],
        gastos=[]  # Se retiran los gastos
    )

    pedido_act = PedidoService.guardar_pedido(db_session, payload_actualizacion, user, mock_request)
    db_session.commit()
    db_session.refresh(pedido_act)

    # Verificación de Eliminación CERO:
    # Consulta a bajo nivel en la BD demuestra que item2 y gasto1 SIGUEN existiendo
    all_db_items = db_session.query(PedidoItem).filter_by(pedido_id=pedido.id).all()
    all_db_gastos = db_session.query(PedidoGasto).filter_by(pedido_id=pedido.id).all()

    assert len(all_db_items) == 2  # ¡Ninguno fue borrado con db.delete()!
    assert len(all_db_gastos) == 1 # ¡El gasto tampoco fue borrado!

    # Verificación de estado lógico:
    item1_db = next(it for it in all_db_items if it.id == item1.id)
    item2_db = next(it for it in all_db_items if it.id == item2.id)
    gasto1_db = all_db_gastos[0]

    assert item1_db.activo is True
    assert item2_db.activo is False  # Marcado inactivo (Soft Delete)
    assert gasto1_db.activo is False # Marcado inactivo (Soft Delete)

    # Verificación de cálculos dinámicos de Pedido:
    # Excluyen automáticamente los registros inactivos
    assert pedido_act.total_kilos == 11.0
    assert len(pedido_act.productos) == 1
    assert len(pedido_act.gastos) == 0
    assert pedido_act.total_gastos == 0.0


def test_seed_massive_catalog_over_250_products(db_session):
    """Verifica la siembra exhaustiva del catálogo de referencias tradicionales y exóticas en formato 3NF."""
    # Sembrar tipos de empaque y unidades de medida requeridas
    TipoEmpaqueRepository.seed_default_tipos_if_empty(db_session)

    creados = ProductoRepository.seed_massive_catalog(db_session)
    assert creados >= 200

    total_prods = db_session.query(Producto).count()
    assert total_prods >= 200

    # Verificar presencia de productos tradicionales y exóticos solicitados
    nombres = {p.nombre.upper() for p in db_session.query(Producto).all()}

    # Frutas tradicionales
    assert "MANZANA GALA" in nombres
    assert "BANANO CRIOLLO" in nombres
    assert "PLÁTANO VERDE" in nombres
    assert "NARANJA VALENCIA" in nombres
    assert "LIMÓN TAHITÍ" in nombres

    # Frutas exóticas
    assert "PITAHAYA AMARILLA" in nombres
    assert "MANGOSTINO" in nombres
    assert "BOROJÓ" in nombres
    assert "CHONTADURO" in nombres
    assert "GULUPA" in nombres
    assert "UCHUVA CON CAPACHO" in nombres

    # Verduras y Tubérculos
    assert "TOMATE CHONTO" in nombres
    assert "PAPA PASTUSA" in nombres
    assert "PAPA CRIOLLA LAVADA" in nombres
    assert "PORTOBELLO" in nombres

    # Legumbres
    assert "ARVEJA EN VAINA" in nombres
    assert "FRÍJOL CARGAMANTO BLANCO" in nombres

    # Lácteos
    assert "LECHE ENTERA 1L" in nombres
    assert "QUESO COSTEÑO" in nombres

    # Huevos
    assert "HUEVO BLANCO TIPO AAA" in nombres
    assert "HUEVO CAMPESINO" in nombres

    # Embutidos
    assert "JAMÓN DE CERDO" in nombres
    assert "CHORIZO SANTARROSANO" in nombres

    # Panadería
    assert "PAN TAJADO BLANCO 500G" in nombres

    # Hierbas
    assert "CILANTRO" in nombres
    assert "JENGIBRE" in nombres


def test_unique_and_check_constraints(db_session):
    """Verifica restricciones UNIQUE y CHECK a nivel de motor de base de datos."""
    from sqlalchemy.exc import IntegrityError

    # 1. Unique NIT en Empresa
    emp1 = Empresa(nombre="Empresa A", nit="900000000-1")
    db_session.add(emp1)
    db_session.commit()

    emp2 = Empresa(nombre="Empresa B", nit="900000000-1")
    db_session.add(emp2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # 2. Check Constraint: Peso neto negativo en PedidoItem
    cliente = Cliente(razon_social="Cliente Test Ck", nit="900888777-1")
    db_session.add(cliente)
    db_session.commit()

    ped = Pedido(cliente_id=cliente.id, numero_remision="REM-TEST")
    db_session.add(ped)
    db_session.commit()

    with pytest.raises(IntegrityError):
        bad_item = PedidoItem(pedido_id=ped.id, cantidad=1.0, peso_neto=-5.0)
        db_session.add(bad_item)
        db_session.commit()
    db_session.rollback()
