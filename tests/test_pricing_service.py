import pytest
from app.services.pricing_service import recalcular_liquidacion, redondear_centena_cercana


def test_redondear_centena_cercana():
    assert redondear_centena_cercana(251) == 300
    assert redondear_centena_cercana(249) == 200
    assert redondear_centena_cercana(250) == 300
    assert redondear_centena_cercana(100) == 100
    assert redondear_centena_cercana(149) == 100
    assert redondear_centena_cercana(151) == 200
    assert redondear_centena_cercana(0) == 0


def test_recalcular_liquidacion_sin_gastos():
    productos = [
        {
            "id": 1,
            "producto": "PAPA PASTUSA",
            "cantidad": 20,
            "kilos": 20,
            "valor_compra_total": 100000,
            "porcentaje_utilidad": 30
        }
    ]
    gastos = []

    resultado = recalcular_liquidacion(productos, gastos, utilidad_global=30)
    items = resultado["items"]
    resumen = resultado["resumen"]

    # 100.000 / 20 = 5.000 costo compra
    assert items[0]["costo_compra_kilo"] == 5000.0
    assert items[0]["gasto_asignado_kilo"] == 0
    assert items[0]["costo_real_kilo"] == 5000
    # 5.000 * 1.30 = 6.500
    assert items[0]["precio_venta_kilo"] == 6500
    # 6.500 * 20 = 130.000
    assert items[0]["valor_total_venta"] == 130000.0

    assert resumen["total_kilos"] == 20.0
    assert resumen["total_compras"] == 100000.0
    assert resumen["total_gastos"] == 0.0
    assert resumen["total_ventas"] == 130000.0
    assert resumen["ganancia"] == 30000.0
    assert resumen["margen_global_porcentaje"] == pytest.approx(23.08, 0.01)


def test_recalcular_liquidacion_con_prorrateo_gastos_y_redondeo():
    productos = [
        {
            "id": 1,
            "producto": "TOMATE",
            "cantidad": 10,
            "kilos": 10,
            "valor_compra_total": 25000,  # 2.500 / kg
            "porcentaje_utilidad": 30
        },
        {
            "id": 2,
            "producto": "CEBOLLA",
            "cantidad": 10,
            "kilos": 10,
            "valor_compra_total": 15000,  # 1.500 / kg
            "porcentaje_utilidad": 30
        }
    ]
    gastos = [
        {"id": "g1", "concepto": "Transporte", "valor": 5000, "aplicado": True},
        {"id": "g2", "concepto": "No Aplicado", "valor": 10000, "aplicado": False}
    ]

    # Total kilos: 20 Kg. Total gastos aplicados: 5.000 -> 250 / Kg -> Redondeado a 300 / Kg
    resultado = recalcular_liquidacion(productos, gastos, utilidad_global=30)
    items = resultado["items"]
    resumen = resultado["resumen"]

    # TOMATE:
    # Costo compra/kg: 2.500. Gasto/kg: 300.
    # Costo real: 2.800
    # Precio venta: 2.800 * 1.30 = 3.640 -> Redondeo centena: 3.600
    assert items[0]["gasto_asignado_kilo"] == 300
    assert items[0]["costo_real_kilo"] == 2800
    assert items[0]["precio_venta_kilo"] == 3600
    assert items[0]["valor_total_venta"] == 36000.0

    # CEBOLLA:
    # Costo compra/kg: 1.500. Gasto/kg: 300.
    # Costo real: 1.800
    # Precio venta: 1.800 * 1.30 = 2.340 -> Redondeo centena: 2.300
    assert items[1]["gasto_asignado_kilo"] == 300
    assert items[1]["costo_real_kilo"] == 1800
    assert items[1]["precio_venta_kilo"] == 2300
    assert items[1]["valor_total_venta"] == 23000.0

    assert resumen["total_kilos"] == 20.0
    assert resumen["total_compras"] == 40000.0
    assert resumen["total_gastos"] == 5000.0
    assert resumen["gasto_por_kilo"] == 300


def test_recalcular_gastos_casos_especificos_251_y_249():
    productos = [{"id": 1, "producto": "PAPA", "cantidad": 20, "kilos": 20, "valor_compra_total": 40000}]
    
    # Caso 251: gastos 5.020 / 20 = 251 -> Redondea a 300
    res_251 = recalcular_liquidacion(productos, [{"valor": 5020, "aplicado": True}])
    assert res_251["resumen"]["gasto_por_kilo"] == 300
    assert res_251["items"][0]["gasto_asignado_kilo"] == 300

    # Caso 249: gastos 4.980 / 20 = 249 -> Redondea a 200
    res_249 = recalcular_liquidacion(productos, [{"valor": 4980, "aplicado": True}])
    assert res_249["resumen"]["gasto_por_kilo"] == 200
    assert res_249["items"][0]["gasto_asignado_kilo"] == 200


def test_recalcular_liquidacion_lista_vacia():
    resultado = recalcular_liquidacion([], [])
    assert resultado["items"] == []
    assert resultado["resumen"]["total_kilos"] == 1.0
    assert resultado["resumen"]["total_ventas"] == 0.0
    assert resultado["resumen"]["ganancia"] == 0.0