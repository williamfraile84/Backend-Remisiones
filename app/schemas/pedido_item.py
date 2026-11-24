from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from app.schemas.unidad_medida import UnidadMedidaResponse
from app.schemas.empaque import TipoEmpaqueResponse


class PedidoItemBase(BaseModel):
    pedido_id: Optional[int] = None
    producto_id: Optional[int] = None
    descripcion_historica: Optional[str] = None
    cantidad: float = Field(1.0, gt=0.0)
    unidad_medida_id: Optional[int] = None
    tipo_empaque_id: Optional[int] = None
    precio_costo_unitario: float = Field(0.0, ge=0.0)
    precio_venta_unitario: float = Field(0.0, ge=0.0)
    peso_neto: float = Field(0.0, ge=0.0)
    porcentaje_utilidad: Optional[float] = Field(30.0, ge=0.0)
    costo_real_kilo: Optional[float] = 0.0
    gasto_asignado_kilo: Optional[float] = 0.0
    precio_venta_manual: Optional[bool] = False
    notas: Optional[str] = None
    orden: int = 0
    activo: Optional[bool] = True


class PedidoItemCreate(PedidoItemBase):
    pass


class PedidoItemUpdate(BaseModel):
    producto_id: Optional[int] = None
    cantidad: Optional[float] = None
    unidad_medida_id: Optional[int] = None
    tipo_empaque_id: Optional[int] = None
    precio_costo_unitario: Optional[float] = None
    precio_venta_unitario: Optional[float] = None
    peso_neto: Optional[float] = None
    porcentaje_utilidad: Optional[float] = None
    costo_real_kilo: Optional[float] = None
    gasto_asignado_kilo: Optional[float] = None
    precio_venta_manual: Optional[bool] = None
    notas: Optional[str] = None
    orden: Optional[int] = None
    activo: Optional[bool] = None


class PedidoItemResponse(PedidoItemBase):
    id: int
    valor_compra_total: float = 0.0
    valor_total_venta: float = 0.0
    peso_bruto: Optional[float] = 0.0
    tara: Optional[float] = 0.0
    surtido: Optional[bool] = False
    creado_en: Optional[datetime] = None
    actualizado_en: Optional[datetime] = None
    unidad_medida: Optional[UnidadMedidaResponse] = None
    tipo_empaque: Optional[TipoEmpaqueResponse] = None

    model_config = ConfigDict(from_attributes=True)
