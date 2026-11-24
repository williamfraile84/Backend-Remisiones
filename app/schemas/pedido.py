from typing import List, Optional, Any, Dict
from pydantic import BaseModel, ConfigDict


class ProductoItem(BaseModel):
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


class GastoItem(BaseModel):
    id: Optional[str] = None
    concepto: str
    valor: float
    aplicado: bool = True


class ResumenLiquidacion(BaseModel):
    total_kilos: float
    total_compras: float
    total_gastos: float
    total_ventas: float
    ganancia: float
    margen_global_porcentaje: float


class LiquidacionSchema(BaseModel):
    items: List[Dict[str, Any]]
    resumen: ResumenLiquidacion


class PedidoSavePayload(BaseModel):
    id: Optional[int] = None
    cliente_id: int
    numero_oc: Optional[str] = ""
    numero_remision: Optional[str] = ""
    fecha_emision: Optional[str] = ""
    fecha_entrega: Optional[str] = ""
    numero_canastas: Optional[str] = ""
    numero_canastillas: Optional[str] = ""
    observaciones: Optional[str] = ""
    archivo_original_path: Optional[str] = None
    archivo_origen_path: Optional[str] = None
    productos: List[Dict[str, Any]] = []
    gastos: List[Dict[str, Any]] = []
    utilidad_global: Optional[float] = 30.0
    porcentaje_utilidad_global: Optional[float] = 30.0
    liquidacion: Optional[Dict[str, Any]] = None


class ExportPayloadSchema(BaseModel):
    cliente_id: int
    cliente_id: Optional[int] = None
    numero_remision: str
    numero_oc: Optional[str] = ""
    fecha_entrega: Optional[str] = ""
    numero_canastas: Optional[str] = ""
    numero_canastillas: Optional[str] = ""
    observaciones: Optional[str] = ""
    productos: List[Dict[str, Any]] = []
    gastos: Optional[List[Dict[str, Any]]] = []
    utilidad_global: Optional[float] = 30.0
    porcentaje_utilidad_global: Optional[float] = 30.0
    liquidacion: Optional[Dict[str, Any]] = None


class PedidoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cliente_id: int
    numero_oc: Optional[str] = None
    numero_remision: str
    fecha_emision: Optional[str] = None
    fecha_entrega: Optional[str] = None
    numero_canastas: Optional[str] = None
    observaciones: Optional[str] = None
    productos: Optional[List[Dict[str, Any]]] = []
    gastos: Optional[List[Dict[str, Any]]] = []
    utilidad_global: Optional[float] = 30.0
    liquidacion: Optional[Dict[str, Any]] = None
    archivo_origen_path: Optional[str] = None
    factura_cargada: Optional[bool] = False
    factura_archivo_path: Optional[str] = None
    factura_archivo_nombre: Optional[str] = None
    remision_firmada_cargada: Optional[bool] = False
    remision_firmada_path: Optional[str] = None
    remision_firmada_nombre: Optional[str] = None
    completado: Optional[bool] = False
    activo: Optional[bool] = True