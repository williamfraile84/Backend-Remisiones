from typing import Optional
from pydantic import BaseModel, ConfigDict


class AuditoriaCambioResponse(BaseModel):
    id: int
    auditoria_id: int
    campo: str
    valor_anterior: Optional[str] = None
    valor_nuevo: Optional[str] = None
    tipo_dato: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

