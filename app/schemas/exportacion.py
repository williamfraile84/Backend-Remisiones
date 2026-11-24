from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ExportItemSchema(BaseModel):
    id: Optional[Any] = None
    producto: str
    cantidad: float
    unidad: Optional[str] = "Kg"
    descripcion: Optional[str] = ""
    kilos: Optional[float] = 0.0
    valor_compra_total: Optional[float] = 0.0
    porcentaje_utilidad: Optional[float] = 30.0
    costo_compra_kilo: Optional[float] = 0.0
    gasto_asignado_kilo: Optional[float] = 0.0
    costo_real_kilo: Optional[float] = 0.0
    precio_venta_kilo: Optional[float] = 0.0
    valor_total_venta: Optional[float] = 0.0


class ExportResumenSchema(BaseModel):
    total_kilos: Optional[float] = 0.0
    total_compras: Optional[float] = 0.0
    total_gastos: Optional[float] = 0.0
    total_ventas: Optional[float] = 0.0
    ganancia: Optional[float] = 0.0
    margen_global_porcentaje: Optional[float] = 0.0


class ExportLiquidacionSchema(BaseModel):
    items: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    resumen: Optional[ExportResumenSchema] = None


class ExportPayloadSchema(BaseModel):
    cliente_id: Optional[int] = None
    numero_remision: str
    numero_oc: Optional[str] = ""
    fecha_entrega: Optional[str] = ""
    numero_canastas: Optional[str] = ""
    observaciones: Optional[str] = ""
    productos: List[Dict[str, Any]] = Field(default_factory=list)
    liquidacion: Optional[Dict[str, Any]] = None