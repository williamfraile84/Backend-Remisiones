from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict
from app.schemas.permiso import PermisoResponse


class RoleBase(BaseModel):
    codigo: str = Field(..., min_length=1, max_length=50, description="Código único del rol (ej: admin, operador)")
    nombre: str = Field(..., min_length=1, max_length=100, description="Nombre legible del rol")
    descripcion: Optional[str] = Field(None, max_length=255)
    activo: Optional[bool] = True


class RoleCreate(RoleBase):
    permiso_ids: Optional[List[int]] = Field(default_factory=list)


class RoleUpdate(BaseModel):
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    activo: Optional[bool] = None
    permiso_ids: Optional[List[int]] = None


class RoleResponse(RoleBase):
    id: int
    creado_en: Optional[datetime] = None
    actualizado_en: Optional[datetime] = None
    permisos: List[PermisoResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)

