from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models.unidad_medida import UnidadMedida


class UnidadMedidaRepository:

    @staticmethod
    def get_all(db: Session, activo_only: bool = True) -> List[UnidadMedida]:
        query = db.query(UnidadMedida)
        if activo_only:
            query = query.filter(UnidadMedida.activo == True)
        return query.order_by(UnidadMedida.codigo.asc()).all()

    @staticmethod
    def get_by_id(db: Session, unidad_id: int) -> Optional[UnidadMedida]:
        return db.query(UnidadMedida).filter(UnidadMedida.id == unidad_id).first()

    @staticmethod
    def get_by_codigo(db: Session, codigo: str) -> Optional[UnidadMedida]:
        clean = codigo.strip().upper()
        return db.query(UnidadMedida).filter(UnidadMedida.codigo == clean).first()

    @staticmethod
    def create(db: Session, data: Dict[str, Any]) -> UnidadMedida:
        codigo = data.get("codigo", "").strip().upper()
        unidad = UnidadMedida(
            codigo=codigo,
            nombre=data.get("nombre", "").strip(),
            tipo_magnitud=data.get("tipo_magnitud", "PESO").strip().upper(),
            factor_conversion_kg=float(data.get("factor_conversion_kg") or 1.0),
            activo=data.get("activo", True),
        )
        db.add(unidad)
        db.commit()
        db.refresh(unidad)
        return unidad

    @staticmethod
    def update(db: Session, unidad_id: int, data: Dict[str, Any]) -> Optional[UnidadMedida]:
        unidad = db.query(UnidadMedida).filter(UnidadMedida.id == unidad_id).first()
        if not unidad:
            return None
        for k, v in data.items():
            if v is not None:
                if k == "codigo":
                    v = v.strip().upper()
                setattr(unidad, k, v)
        db.commit()
        db.refresh(unidad)
        return unidad

    @staticmethod
    def delete(db: Session, unidad_id: int) -> bool:
        unidad = db.query(UnidadMedida).filter(UnidadMedida.id == unidad_id).first()
        if not unidad:
            return False
        unidad.activo = False
        db.commit()
        return True

    @classmethod
    def seed_default_units_if_empty(cls, db: Session) -> int:
        """Siembra unidades estándar si el catálogo está vacío."""
        if db.query(UnidadMedida).count() > 0:
            return 0

        default_units = [
            {"codigo": "KG", "nombre": "Kilogramo", "tipo_magnitud": "PESO", "factor_conversion_kg": 1.0},
            {"codigo": "LB", "nombre": "Libra", "tipo_magnitud": "PESO", "factor_conversion_kg": 0.5},
            {"codigo": "GR", "nombre": "Gramo", "tipo_magnitud": "PESO", "factor_conversion_kg": 0.001},
            {"codigo": "UND", "nombre": "Unidad", "tipo_magnitud": "UNIDAD", "factor_conversion_kg": 0.0},
            {"codigo": "ATD", "nombre": "Atado", "tipo_magnitud": "UNIDAD", "factor_conversion_kg": 0.0},
            {"codigo": "DOC", "nombre": "Docena", "tipo_magnitud": "UNIDAD", "factor_conversion_kg": 0.0},
            {"codigo": "MANO", "nombre": "Mano (5 unds)", "tipo_magnitud": "UNIDAD", "factor_conversion_kg": 0.0},
        ]
        created = 0
        for u in default_units:
            unidad = UnidadMedida(**u, activo=True)
            db.add(unidad)
            created += 1
        db.commit()
        return created
