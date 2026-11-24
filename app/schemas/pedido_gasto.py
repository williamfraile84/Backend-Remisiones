from datetime import datetime
from typing import Optional, Any, Dict
from pydantic import BaseModel, Field, ConfigDict
from app.schemas.concepto_gasto import ConceptoGastoResponse


class PedidoGastoBase(BaseModel):
    pedido_id: Optional[int] = None
    concepto_gasto_id: Optional[int] = None
    descripcion: str = Field(..., min_length=1, max_length=255)
    monto: float = Field(0.0, ge=0.0)
    distribuir_en_costo: bool = True
    metadata_extra: Optional[Dict[str, Any]] = None


class PedidoGastoCreate(PedidoGastoBase):
    pass


class PedidoGastoUpdate(BaseModel):
    concepto_gasto_id: Optional[int] = None
    descripcion: Optional[str] = None
    monto: Optional[float] = None
    distribuir_en_costo: Optional[bool] = None
    metadata_extra: Optional[Dict[str, Any]] = None


class PedidoGastoResponse(PedidoGastoBase):
    id: int
    creado_en: Optional[datetime] = None
    actualizado_en: Optional[datetime] = None
    concepto: Optional[ConceptoGastoResponse] = None

    model_config = ConfigDict(from_attributes=True)
