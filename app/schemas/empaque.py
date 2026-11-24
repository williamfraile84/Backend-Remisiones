"""
Módulo fachada para esquemas de empaques (3NF estricta).
La entidad canónica y única de empaques es TipoEmpaque.
"""
from app.schemas.tipo_empaque import (
    TipoEmpaqueBase,
    TipoEmpaqueCreate,
    TipoEmpaqueUpdate,
    TipoEmpaqueResponse,
)

# Alias canónicos que apuntan directamente a TipoEmpaque
EmpaqueBase = TipoEmpaqueBase
EmpaqueCreate = TipoEmpaqueCreate
EmpaqueUpdate = TipoEmpaqueUpdate
EmpaqueResponse = TipoEmpaqueResponse

__all__ = [
    "TipoEmpaqueBase",
    "TipoEmpaqueCreate",
    "TipoEmpaqueUpdate",
    "TipoEmpaqueResponse",
    "EmpaqueBase",
    "EmpaqueCreate",
    "EmpaqueUpdate",
    "EmpaqueResponse",
]
