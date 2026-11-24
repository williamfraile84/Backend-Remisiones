import math
from typing import List, Dict, Any, Optional
from app.core.config import settings


def redondear_centena_cercana(valor: float) -> int:
    """
    Redondea al 100 siguiente o anterior dependiendo del caso.
    Regla estándar de negocio:
    - 251 se redondea a 300
    - 249 se redondea a 200
    - 250 se redondea a 300
    """
    if not valor or valor <= 0:
        return 0
    return int(math.floor((valor / 100.0) + 0.5)) * 100


def recalcular_liquidacion(
    productos: List[Dict[str, Any]],
    gastos: List[Dict[str, Any]],
    utilidad_global: Optional[float] = None
) -> Dict[str, Any]:
    """
    Ejecuta el cálculo matemático del negocio:
    1. Prorrateo de gastos operativos por kilo con redondeo a centena más cercana (251->300, 249->200).
    2. Asignación del gasto por kilo a cada ítem.
    3. Cálculo del costo real por kilo redondeado a centena más cercana.
    4. Cálculo del precio de venta por producto y redondeo a centena.
    5. Balance general de compras, gastos y margen de ganancia.
    """
    if utilidad_global is None:
        utilidad_global = settings.DEFAULT_PROFIT_MARGIN

    total_kilos = sum(
        float(p.get("kilos", 0) or p.get("cantidad", 0))
        for p in productos
        if float(p.get("kilos", 0) or p.get("cantidad", 0)) > 0
    ) or 1.0

    total_gastos_aplicados = sum(
        float(g.get("valor", 0))
        for g in gastos
        if g.get("aplicado", True)
    )

    # Prorrateo con redondeo al 100 siguiente o anterior
    gasto_por_kilo_exacto = total_gastos_aplicados / total_kilos if total_kilos > 0 else 0.0
    gasto_por_kilo = redondear_centena_cercana(gasto_por_kilo_exacto)

    total_compras = 0.0
    total_ventas = 0.0
    items_calculados = []

    for p in productos:
        kilos = float(p.get("kilos", 0) or p.get("cantidad", 0))
        raw_costo = p.get("costo_compra_kilo")
        raw_total_compra = p.get("valor_compra_total")

        if raw_costo is not None and str(raw_costo).strip() != "" and float(raw_costo) > 0:
            costo_compra_kilo = redondear_centena_cercana(float(raw_costo))
            valor_compra_total = redondear_centena_cercana(costo_compra_kilo * kilos) if (raw_total_compra is None or str(raw_total_compra).strip() == "") else redondear_centena_cercana(float(raw_total_compra))
        elif raw_total_compra is not None and str(raw_total_compra).strip() != "" and float(raw_total_compra) > 0 and kilos > 0:
            valor_compra_total = redondear_centena_cercana(float(raw_total_compra))
            costo_compra_kilo = redondear_centena_cercana(valor_compra_total / kilos)
        else:
            costo_compra_kilo = 0.0
            valor_compra_total = 0.0

        costo_real_kilo = redondear_centena_cercana(costo_compra_kilo + gasto_por_kilo) if kilos > 0 else 0

        util_item = int(round(float(p.get("porcentaje_utilidad", utilidad_global) if p.get("porcentaje_utilidad") is not None else utilidad_global)))

        precio_venta_directo = p.get("precio_venta_kilo")
        if precio_venta_directo is not None and str(precio_venta_directo).strip() != "" and float(precio_venta_directo) > 0:
            precio_venta_kilo = redondear_centena_cercana(float(precio_venta_directo))
        elif costo_real_kilo > 0:
            precio_venta_kilo = redondear_centena_cercana(costo_real_kilo * (1 + (util_item / 100.0)))
        else:
            precio_venta_kilo = 0

        raw_total_venta = p.get("valor_total_venta")
        if bool(p.get("precio_venta_manual")) and raw_total_venta is not None and str(raw_total_venta).strip() != "" and float(raw_total_venta) > 0:
            valor_total_venta = redondear_centena_cercana(float(raw_total_venta))
        else:
            valor_total_venta = redondear_centena_cercana(precio_venta_kilo * kilos)

        total_compras += valor_compra_total
        total_ventas += valor_total_venta

        item_dict = dict(p)
        item_dict.update({
            "kilos": kilos,
            "costo_compra_kilo": float(costo_compra_kilo),
            "valor_compra_total": float(valor_compra_total),
            "gasto_asignado_kilo": int(gasto_por_kilo),
            "gasto_exacto_kilo": round(gasto_por_kilo_exacto, 2),
            "costo_real_kilo": int(costo_real_kilo),
            "precio_venta_kilo": int(precio_venta_kilo),
            "valor_total_venta": float(valor_total_venta),
            "porcentaje_utilidad": util_item
        })
        items_calculados.append(item_dict)

    ganancia = redondear_centena_cercana(total_ventas - (total_compras + total_gastos_aplicados))
    margen_global = (ganancia / total_ventas * 100.0) if total_ventas > 0 else 0.0

    return {
        "items": items_calculados,
        "resumen": {
            "total_kilos": round(total_kilos, 2),
            "total_compras": float(redondear_centena_cercana(total_compras)),
            "total_gastos": float(total_gastos_aplicados),
            "gasto_por_kilo": int(gasto_por_kilo),
            "gasto_por_kilo_exacto": round(gasto_por_kilo_exacto, 2),
            "total_ventas": float(redondear_centena_cercana(total_ventas)),
            "ganancia": float(ganancia),
            "margen_global_porcentaje": round(margen_global, 2)
        }
    }