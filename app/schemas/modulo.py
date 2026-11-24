from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class ModuloBase(BaseModel):
    codigo: str = Field(..., min_length=1, max_length=50, description="Código único del módulo")
    nombre: str = Field(..., min_length=1, max_length=100, description="Nombre legible del módulo")
    descripcion: Optional[str] = Field(None, max_length=255)
    activo: Optional[bool] = True


class ModuloCreate(ModuloBase):
    pass


class ModuloUpdate(BaseModel):
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    activo: Optional[bool] = None


class ModuloResponse(ModuloBase):
    id: int
    creado_en: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

