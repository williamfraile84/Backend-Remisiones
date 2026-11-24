from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class PermisoBase(BaseModel):
    codigo: str = Field(..., min_length=1, max_length=100, description="Código único del permiso")
    nombre: str = Field(..., min_length=1, max_length=150, description="Nombre legible del permiso")
    modulo_id: Optional[int] = Field(None, description="ID del módulo al que pertenece (3NF)")
    modulo: Optional[str] = Field(None, description="Código del módulo al que pertenece")
    descripcion: Optional[str] = Field(None, max_length=255)
    activo: Optional[bool] = True


class PermisoCreate(PermisoBase):
    pass


class PermisoResponse(PermisoBase):
    id: int
    creado_en: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
