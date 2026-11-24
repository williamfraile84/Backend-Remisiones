from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class AuditoriaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    usuario_id: Optional[int] = None
    usuario_nombre: Optional[str] = None
    usuario_rol: Optional[str] = None
    accion: str
    modulo: str
    entidad: Optional[str] = None
    entidad_id: Optional[str] = None
    detalles: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    creado_en: datetime


class AuditoriaListResponse(BaseModel):
    total: int
    items: List[AuditoriaResponse]
