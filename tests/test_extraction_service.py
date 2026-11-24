import pytest
from typing import Optional
from app.services.document_parser import (
    normalize_product_name,
    normalize_unit_and_description,
    clean_razon_social,
    extract_metadata_from_text,
)


def test_clean_razon_social():
    assert clean_razon_social("UNION TEMPORAL JL SERVCACOL NOMBRE") == "UNION TEMPORAL JL SERVCACOL"
    assert clean_razon_social("UNION TEMPORAL JL SERVCACOL") == "UNION TEMPORAL JL SERVCACOL"
    assert clean_razon_social("UNION TEMPORAL JL SERVCACOL CEDULA") == "UNION TEMPORAL JL SERVCACOL"
    assert clean_razon_social("FRUVER DEL YANUBA | NIT") == "FRUVER DEL YANUBA"


def test_normalize_product_name():
    assert normalize_product_name("1. PAPA PASTUSA") == "PAPA PASTUSA"
    assert normalize_product_name("01 - PLATANO VERDE") == "PLATANO VERDE"
    assert normalize_product_name("#12 CEBOLLA CABEZONA") == "CEBOLLA CABEZONA"
    assert normalize_product_name("  TORNILLO HEXAGONAL 1/2   ") == "TORNILLO HEXAGONAL 1/2"
    assert normalize_product_name("GUANTES DE LATEX CAJA X 100 NIT: 12345") == "GUANTES DE LATEX CAJA X 100"
    assert normalize_product_name("ACETAMINOFEN 500MG TABLETAS") == "ACETAMINOFEN 500MG TABLETAS"
    assert normalize_product_name("ARVEJA VERDE - ") == "ARVEJA VERDE"


def test_metadata_extraction_clean():
    sample_text = """
    ORDEN DE COMPRA
    UNION TEMPORAL JL SERVCACOL
    DATOS PROVEEDOR
    EMPRESA: FRUVER DEL YANUBA
    FACTURAR A
    RAZÓN SOCIAL: UNION TEMPORAL JL SERVCACOL NOMBRE
    NIT: 902765531-8
    EMAIL: uniontemporaljlservcacol@gmail.com
    NÚMERO DE OC: 11
    FECHA: 20/08/2026
    CENTRO COSTO: MTZ
    DATOS DE ENTREGA
    FECHA: 22/08/2026
    OBSERVACIONES:
    Al realizar la factura en observaciones escribir: MTZ
    """

    meta = extract_metadata_from_text(sample_text)
    assert meta["cliente"]["razon_social"] == "UNION TEMPORAL JL SERVCACOL"
    assert meta["cliente"]["nit"] == "902765531-8"
    assert meta["numero_oc"] == "11"
    assert meta["fecha_entrega"] == "22/08/2026"
    assert meta["observaciones"] == ""


def test_normalize_unit_and_description():
    u, d = normalize_unit_and_description("Kg", "")
    assert u == "Kg"
    assert d == ""

    u, d = normalize_unit_and_description("", "Kg")
    assert u == "Kg"
    assert d == ""

    u, d = normalize_unit_and_description("Unidades", "5 cubetas A")
    assert u == "Und"
    assert "5 cubetas A" in d

    u, d = normalize_unit_and_description("", "Litros")
    assert u == "Litro"
    assert d == ""

    u, d = normalize_unit_and_description("", "Bloque 2,5 Kg")
    assert u == "Bloque"
    assert "2,5 Kg" in d


def test_extract_products_from_pdf_tables_avoids_kg_as_product():
    from app.services.document_parser import extract_products_from_pdf_tables

    sample_table = [
        ["PRODUCTO", "CANTIDAD", "UNIDAD", "DESCRIPCIÓN", "VALOR UNITARIO", "IVA", "SUBTOTAL"],
        ["PAPA PASTUSA", "20", "Kg", "", "", "", ""],
        ["PLATANO MADURO", "15", "Kg", "", "", "", ""],
        ["ARVEJA VERDE", "4", "Kg", "Desgranada", "", "", ""],
        ["HUEVOS", "150", "Unidades", "5 cubetas A", "", "", ""],
    ]

    prods = extract_products_from_pdf_tables([sample_table])
    assert len(prods) == 4
    assert prods[0]["producto"] == "PAPA PASTUSA"
    assert prods[0]["cantidad"] == 20.0
    assert prods[0]["unidad"] == "Kg"

    assert prods[1]["producto"] == "PLATANO MADURO"
    assert prods[1]["cantidad"] == 15.0
    assert prods[1]["unidad"] == "Kg"

    assert prods[2]["producto"] == "ARVEJA VERDE"
    assert prods[2]["cantidad"] == 4.0
    assert prods[2]["unidad"] == "Kg"
    assert "Desgranada" in prods[2]["descripcion"]

    assert prods[3]["producto"] == "HUEVOS"
    assert prods[3]["cantidad"] == 150.0
    assert prods[3]["unidad"] == "Und"
    assert "5 cubetas A" in prods[3]["descripcion"]


def test_normalize_extended_units():
    u, d = normalize_unit_and_description("Cubetas A", "")
    assert u == "Cubeta"

    u, d = normalize_unit_and_description("CANASTILLAS", "")
    assert u == "Canastilla"

    u, d = normalize_unit_and_description("BOLSAS", "")
    assert u == "Bolsa"

    u, d = normalize_unit_and_description("GALON", "")
    assert u == "Galon"


def _find_sample_file(filename: str) -> Optional[str]:
    import os
    candidates = [
        os.path.join(os.path.dirname(__file__), "..", "..", "ejemplo archivos carga", filename),
        os.path.join("ejemplo archivos carga", filename),
        os.path.join("d:/sistema_fruver/ejemplo archivos carga", filename),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def test_extract_data_from_real_excel_file():
    from app.services.document_parser import extraer_datos_documento

    sample_path = _find_sample_file("PEDIDO 4 FRUVER.xlsx")
    if sample_path:
        with open(sample_path, "rb") as f:
            file_bytes = f.read()

        data = extraer_datos_documento(file_bytes, "PEDIDO 4 FRUVER.xlsx")
        assert data["cliente"]["razon_social"] == "UNION TEMPORAL JL SERVCACOL"
        assert data["cliente"]["nit"] == "902765531-8"
        assert data["cliente"]["email"] == "uniontemporaljlservcacol@gmail.com"
        assert str(data["numero_oc"]) == "3"
        assert data["fecha_entrega"] in ["2026-07-23", "23/07/2026"]
        assert data["observaciones"] == ""
        assert len(data["productos"]) > 0

        # Verificar que los productos con cantidad 0 no estén incluidos
        prod_names = [p["producto"] for p in data["productos"]]
        assert "PAPA PASTUSA" not in prod_names  # Cantidad era 0
        assert "PAPA CRIOLLA" not in prod_names  # Cantidad era 0
        assert "PLATANO VERDE" in prod_names     # Cantidad era 40
        assert "CEBOLLA LARGA" in prod_names     # Cantidad era 10
        assert "MAZORCA" in prod_names           # Cantidad era 40

        # Verificar normalización de unidades
        for p in data["productos"]:
            assert p["cantidad"] > 0
            assert p["kilos"] == p["cantidad"]


def test_extract_data_from_sample_pdfs():
    from app.services.document_parser import extraer_datos_documento

    sample_pdfs = ["PEDIDO1.pdf", "PEDIDO2.pdf", "PEDIDO3.pdf"]
    for pdf_name in sample_pdfs:
        pdf_path = _find_sample_file(pdf_name)
        if pdf_path:
            with open(pdf_path, "rb") as f:
                file_bytes = f.read()
            data = extraer_datos_documento(file_bytes, pdf_name)
            assert isinstance(data["productos"], list)
            assert "cliente" in data
            assert "numero_oc" in data


def test_gemini_routing_for_scanned_documents():
    from unittest.mock import MagicMock, patch
    from app.services.document_parser import extraer_datos_documento

    # 1. Excel nunca llama a Gemini
    with patch("app.services.document_parser.GeminiOrderVisionEngine") as mock_engine_cls:
        excel_path = _find_sample_file("PEDIDO 4 FRUVER.xlsx")
        if excel_path:
            with open(excel_path, "rb") as f:
                extraer_datos_documento(f.read(), "PEDIDO 4 FRUVER.xlsx")
            mock_engine_cls.assert_not_called()

    # 2. Imagen enruta a Gemini Vision
    with patch("app.services.document_parser.GeminiOrderVisionEngine") as mock_engine_cls:
        mock_instance = MagicMock()
        mock_instance.is_available.return_value = True
        mock_instance.extract_order_from_image.return_value = {
            "cliente": {"razon_social": "TEST CLIENT", "nit": "123"},
            "numero_oc": "99",
            "fecha_emision": "2026-11-21",
            "fecha_entrega": "2026-11-22",
            "observaciones": "",
            "productos": [{"id": 1, "producto": "TOMATE", "cantidad": 10.0, "unidad": "Kg"}]
        }
        mock_engine_cls.return_value = mock_instance

        fake_image_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF"
        res = extraer_datos_documento(fake_image_bytes, "factura.jpg")
        assert res["cliente"]["razon_social"] == "TEST CLIENT"
        assert res["productos"][0]["producto"] == "TOMATE"
        mock_instance.extract_order_from_image.assert_called_once()