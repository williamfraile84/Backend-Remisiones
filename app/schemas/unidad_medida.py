from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class UnidadMedidaBase(BaseModel):
    codigo: str = Field(..., min_length=1, max_length=20, description="Código de la unidad: KG, LB, UND, etc.")
    nombre: str = Field(..., min_length=1, max_length=50, description="Nombre completo de la unidad")
    tipo_magnitud: str = Field("PESO", description="PESO, UNIDAD, VOLUMEN")
    factor_conversion_kg: float = Field(1.0, ge=0.0, description="Factor para normalizar a kilogramos")
    activo: Optional[bool] = True


class UnidadMedidaCreate(UnidadMedidaBase):
    pass


class UnidadMedidaUpdate(BaseModel):
    codigo: Optional[str] = None
    nombre: Optional[str] = None
    tipo_magnitud: Optional[str] = None
    factor_conversion_kg: Optional[float] = None
    activo: Optional[bool] = None


class UnidadMedidaResponse(UnidadMedidaBase):
    id: int
    creado_en: Optional[datetime] = None
    actualizado_en: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
