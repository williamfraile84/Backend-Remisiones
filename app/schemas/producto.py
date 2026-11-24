from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict
from app.schemas.unidad_medida import UnidadMedidaResponse
from app.schemas.empaque import TipoEmpaqueResponse


class ProductoBase(BaseModel):
    empresa_id: Optional[int] = None
    codigo: Optional[str] = None
    nombre: str = Field(..., min_length=1, max_length=150, description="Nombre del producto o fruver")
    categoria: Optional[str] = Field(None, description="FRUTAS, VERDURAS, TUBERCULOS, HIERBAS, OTROS")
    unidad_medida_id: Optional[int] = None
    tipo_empaque_id: Optional[int] = None
    pos_item_id: Optional[str] = Field(None, description="ID del producto en el sistema POS externo")
    precio_pos_actual: Optional[float] = Field(0.0, ge=0.0, description="Precio de venta actual en el sistema POS")
    precio_costo_referencia: Optional[float] = Field(0.0, ge=0.0)
    precio_venta_referencia: Optional[float] = Field(0.0, ge=0.0)
    merma_esperada_pct: Optional[float] = Field(0.0, ge=0.0, le=100.0)
    activo: Optional[bool] = True


class ProductoEmpaqueItem(BaseModel):
    tipo_empaque_id: int
    peso_kg: Optional[float] = Field(None, ge=0.0, description="Peso específico en Kg para este producto (null = usa catálogo)")


class ProductoCreate(ProductoBase):
    empaque_ids: Optional[List[int]] = None
    empaques_config: Optional[List[ProductoEmpaqueItem]] = None


class ProductoUpdate(BaseModel):
    codigo: Optional[str] = None
    nombre: Optional[str] = None
    categoria: Optional[str] = None
    unidad_medida_id: Optional[int] = None
    tipo_empaque_id: Optional[int] = None
    pos_item_id: Optional[str] = None
    precio_pos_actual: Optional[float] = None
    precio_costo_referencia: Optional[float] = None
    precio_venta_referencia: Optional[float] = None
    merma_esperada_pct: Optional[float] = None
    activo: Optional[bool] = None
    empaque_ids: Optional[List[int]] = None
    empaques_config: Optional[List[ProductoEmpaqueItem]] = None


class ProductoResponse(ProductoBase):
    id: int
    creado_en: Optional[datetime] = None
    actualizado_en: Optional[datetime] = None
    unidad_medida: Optional[UnidadMedidaResponse] = None
    tipo_empaque: Optional[TipoEmpaqueResponse] = None
    empaques_permitidos: Optional[List[TipoEmpaqueResponse]] = []

    model_config = ConfigDict(from_attributes=True)


class ProductoEmpaquesBatchItem(BaseModel):
    producto_id: int
    tipo_empaque_id: Optional[int] = None
    empaques_config: List[ProductoEmpaqueItem]


class BatchEmpaquesRequest(BaseModel):
    items: List[ProductoEmpaquesBatchItem]


class BatchEmpaquesResponse(BaseModel):
    status: str
    actualizados: int
    detalles: Optional[str] = None

