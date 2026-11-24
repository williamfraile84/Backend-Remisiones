from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class ConceptoGastoBase(BaseModel):
    empresa_id: Optional[int] = None
    codigo: Optional[str] = None
    nombre: str = Field(..., min_length=1, max_length=100, description="Concepto: Flete, Cargue/Descargue, etc.")
    tipo: str = Field("OPERATIVO", description="OPERATIVO, LOGISTICO, ADMINISTRATIVO")
    distribuir_por_defecto: bool = Field(True, description="¿Se distribuye en el costo unitario?")
    activo: Optional[bool] = True


class ConceptoGastoCreate(ConceptoGastoBase):
    pass


class ConceptoGastoUpdate(BaseModel):
    nombre: Optional[str] = None
    tipo: Optional[str] = None
    distribuir_por_defecto: Optional[bool] = None
    activo: Optional[bool] = None


class ConceptoGastoResponse(ConceptoGastoBase):
    id: int
    creado_en: Optional[datetime] = None
    actualizado_en: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
