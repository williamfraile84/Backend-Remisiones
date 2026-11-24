from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class TipoEmpaqueBase(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=100, description="Nombre estándar del empaque (ej: Bulto, Pony, Canastilla)")
    peso_kg: float = Field(..., gt=0, description="Capacidad o peso neto estándar en kilogramos")
    peso_lb: Optional[float] = Field(None, description="Capacidad o peso en libras (por defecto peso_kg * 2)")
    descripcion: Optional[str] = Field(None, max_length=255)
    activo: Optional[bool] = True


class TipoEmpaqueCreate(TipoEmpaqueBase):
    pass


class TipoEmpaqueUpdate(BaseModel):
    nombre: Optional[str] = None
    peso_kg: Optional[float] = None
    peso_lb: Optional[float] = None
    descripcion: Optional[str] = None
    activo: Optional[bool] = None


class TipoEmpaqueResponse(TipoEmpaqueBase):
    id: int
    peso_kg_default: Optional[float] = None
    creado_en: Optional[datetime] = None
    actualizado_en: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

