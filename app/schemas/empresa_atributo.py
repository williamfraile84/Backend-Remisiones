from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class EmpresaAtributoBase(BaseModel):
    clave: str = Field(..., min_length=1, max_length=100)
    valor: Optional[str] = None


class EmpresaAtributoCreate(EmpresaAtributoBase):
    empresa_id: int


class EmpresaAtributoResponse(EmpresaAtributoBase):
    id: int
    empresa_id: int

    model_config = ConfigDict(from_attributes=True)

