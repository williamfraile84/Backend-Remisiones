from typing import List, Optional, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ClienteBase(BaseModel):
    razon_social: str
    nit: str
    direccion: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    consecutivo_remision_actual: Optional[int] = 1
    campos_extra: Optional[List[Any]] = []


class ClienteCreate(ClienteBase):
    id: Optional[int] = None


class ClienteUpdate(BaseModel):
    razon_social: Optional[str] = None
    nit: Optional[str] = None
    direccion: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    consecutivo_remision_actual: Optional[int] = None
    campos_extra: Optional[List[Any]] = None


class ClienteResponse(ClienteBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    activo: bool
    creado_en: Optional[datetime] = None