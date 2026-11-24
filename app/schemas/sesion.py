from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class SesionResponse(BaseModel):
    id: int
    usuario_id: int
    empresa_id: Optional[int] = None
    token_jti: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    activo: bool
    expira_en: datetime
    ultimo_acceso: datetime
    creado_en: datetime

    model_config = ConfigDict(from_attributes=True)


class SesionesListResponse(BaseModel):
    total_activas: int
    sesiones: List[SesionResponse]

