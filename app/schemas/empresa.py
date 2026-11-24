from typing import List, Optional, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class EmpresaBase(BaseModel):
    nombre: str
    nit: str
    direccion: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    logo_path: Optional[str] = None
    campos_extra: Optional[List[Any]] = []


class EmpresaCreate(EmpresaBase):
    pass


class EmpresaUpdate(BaseModel):
    nombre: Optional[str] = None
    nit: Optional[str] = None
    direccion: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    campos_extra: Optional[List[Any]] = None


class EmpresaResponse(EmpresaBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    creado_en: Optional[datetime] = None


class EmpresaStatusResponse(BaseModel):
    configurada: bool
    empresa: Optional[EmpresaResponse] = None
    total_empresas: int = 0
    empresas: List[EmpresaResponse] = []