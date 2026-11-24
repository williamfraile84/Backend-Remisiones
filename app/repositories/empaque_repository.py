"""
Módulo fachada para compatibilidad del repositorio de empaques (3NF estricta).
Delega directamente en la entidad y repositorio canónico TipoEmpaqueRepository.
"""
from app.repositories.tipo_empaque_repository import TipoEmpaqueRepository

EmpaqueRepository = TipoEmpaqueRepository

__all__ = ["EmpaqueRepository", "TipoEmpaqueRepository"]
