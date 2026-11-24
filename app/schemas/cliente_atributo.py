from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class ClienteAtributoBase(BaseModel):
    clave: str = Field(..., min_length=1, max_length=100)
    valor: Optional[str] = None


class ClienteAtributoCreate(ClienteAtributoBase):
    cliente_id: int


class ClienteAtributoResponse(ClienteAtributoBase):
    id: int
    cliente_id: int

    model_config = ConfigDict(from_attributes=True)

