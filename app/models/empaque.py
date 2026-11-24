"""
Módulo fachada para compatibilidad hacia atrás.
La entidad atómica estándar de empaques es:
- app.models.tipo_empaque.TipoEmpaque
"""
from app.models.tipo_empaque import TipoEmpaque

__all__ = ["TipoEmpaque"]
