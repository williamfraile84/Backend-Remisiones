import io
import pytest
from app.models.empresa import Empresa
from app.models.cliente import Cliente
from app.services.export_service import (
    generar_pdf_remision,
    generar_excel_remision,
    generar_pdf_informe,
    generar_excel_informe,
)


@pytest.fixture
def mock_empresa():
    emp = Empresa()
    emp.id = 1
    emp.nombre = "FRUVER PRUEBA SAS"
    emp.nit = "900.123.456-7"
    emp.direccion = "Calle 100 # 15-20"
    emp.telefono = "3101234567"
    emp.email = "contacto@fruverprueba.com"
    emp.logo_path = None
    return emp


@pytest.fixture
def mock_cliente():
    cli = Cliente()
    cli.id = 1
    cli.razon_social = "RESTAURANTE EL SABOR"
    cli.nit = "800.987.654-3"
    cli.direccion = "Carrera 7 # 45-67"
    cli.telefono = "3209876543"
    cli.email = "compras@elsabor.com"
    return cli


@pytest.fixture
def sample_payload():
    return {
        "cliente_id": 1,
        "numero_remision": "REM-2026-001",
        "numero_oc": "OC-9988",
        "fecha_entrega": "2026-08-30",
        "numero_canastas": "8",
        "observaciones": "Entrega en puerta trasera antes de las 8am",
        "productos": [
            {
                "producto": "PAPA PASTUSA",
                "cantidad": 50,
                "unidad": "Kg",
                "descripcion": "Bulto limpio",
                "kilos": 50,
                "valor_compra_total": 80000,
                "costo_real_kilo": 1600,
                "porcentaje_utilidad": 30,
                "precio_venta_kilo": 2080,
                "valor_total_venta": 104000,
            },
            {
                "producto": "TOMATE CHONTO",
                "cantidad": 20,
                "unidad": "Kg",
                "descripcion": "Maduro seleccionado",
                "kilos": 20,
                "valor_compra_total": 40000,
                "costo_real_kilo": 2000,
                "porcentaje_utilidad": 35,
                "precio_venta_kilo": 2700,
                "valor_total_venta": 54000,
            }
        ],
        "liquidacion": {
            "resumen": {
                "total_kilos": 70,
                "total_compras": 120000,
                "total_gastos": 5000,
                "total_ventas": 158000,
                "ganancia": 33000,
                "margen_global_porcentaje": 21.5,
            }
        }
    }


def test_generar_pdf_remision_valido(mock_empresa, mock_cliente, sample_payload):
    pdf_bytes = generar_pdf_remision(mock_empresa, mock_cliente, sample_payload)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 500
    assert pdf_bytes.startswith(b"%PDF")


def test_generar_pdf_remision_sin_observaciones(mock_empresa, mock_cliente, sample_payload):
    sample_payload["observaciones"] = ""
    pdf_bytes = generar_pdf_remision(mock_empresa, mock_cliente, sample_payload)
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF")


def test_generar_excel_remision_valido(mock_empresa, mock_cliente, sample_payload):
    excel_bytes = generar_excel_remision(mock_empresa, mock_cliente, sample_payload)
    assert isinstance(excel_bytes, bytes)
    assert len(excel_bytes) > 500
    assert excel_bytes.startswith(b"PK")  # Archivo zip/openpyxl


def test_generar_pdf_informe_valido(mock_empresa, mock_cliente, sample_payload):
    pdf_bytes = generar_pdf_informe(mock_empresa, mock_cliente, sample_payload)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 500
    assert pdf_bytes.startswith(b"%PDF")


def test_generar_excel_informe_valido(mock_empresa, mock_cliente, sample_payload):
    excel_bytes = generar_excel_informe(mock_empresa, mock_cliente, sample_payload)
    assert isinstance(excel_bytes, bytes)
    assert len(excel_bytes) > 500
    assert excel_bytes.startswith(b"PK")
