from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models.concepto_gasto import ConceptoGasto


class ConceptoGastoRepository:

    @staticmethod
    def get_all(db: Session, empresa_id: Optional[int] = None, activo_only: bool = True) -> List[ConceptoGasto]:
        query = db.query(ConceptoGasto)
        if activo_only:
            query = query.filter(ConceptoGasto.activo == True)
        if empresa_id is not None:
            query = query.filter(or_(ConceptoGasto.empresa_id == empresa_id, ConceptoGasto.empresa_id == None))
        return query.order_by(ConceptoGasto.nombre.asc()).all()

    @staticmethod
    def get_by_id(db: Session, concepto_id: int) -> Optional[ConceptoGasto]:
        return db.query(ConceptoGasto).filter(ConceptoGasto.id == concepto_id).first()

    @staticmethod
    def get_by_nombre(db: Session, nombre: str, empresa_id: Optional[int] = None) -> Optional[ConceptoGasto]:
        clean = nombre.strip().upper()
        query = db.query(ConceptoGasto).filter(ConceptoGasto.nombre.ilike(clean))
        if empresa_id is not None:
            query = query.filter(or_(ConceptoGasto.empresa_id == empresa_id, ConceptoGasto.empresa_id == None))
        return query.first()

    @staticmethod
    def create(db: Session, data: Dict[str, Any]) -> ConceptoGasto:
        concepto = ConceptoGasto(
            empresa_id=data.get("empresa_id"),
            codigo=data.get("codigo"),
            nombre=data.get("nombre", "").strip(),
            tipo=data.get("tipo", "OPERATIVO").strip().upper(),
            distribuir_por_defecto=data.get("distribuir_por_defecto", True),
            activo=data.get("activo", True),
        )
        db.add(concepto)
        db.commit()
        db.refresh(concepto)
        return concepto

    @staticmethod
    def update(db: Session, concepto_id: int, data: Dict[str, Any]) -> Optional[ConceptoGasto]:
        concepto = db.query(ConceptoGasto).filter(ConceptoGasto.id == concepto_id).first()
        if not concepto:
            return None
        for k, v in data.items():
            if v is not None:
                setattr(concepto, k, v)
        db.commit()
        db.refresh(concepto)
        return concepto

    @staticmethod
    def delete(db: Session, concepto_id: int) -> bool:
        concepto = db.query(ConceptoGasto).filter(ConceptoGasto.id == concepto_id).first()
        if not concepto:
            return False
        concepto.activo = False
        db.commit()
        return True

    @classmethod
    def seed_default_concepts_if_empty(cls, db: Session) -> int:
        """Siembra conceptos de gastos predeterminados si el catálogo está vacío."""
        if db.query(ConceptoGasto).count() > 0:
            return 0

        default_concepts = [
            {"nombre": "Flete", "tipo": "TRANSPORTE", "distribuir_por_defecto": True},
            {"nombre": "Cargue y Descargue", "tipo": "LOGISTICO", "distribuir_por_defecto": True},
            {"nombre": "Empaques y Canastillas", "tipo": "OPERATIVO", "distribuir_por_defecto": True},
            {"nombre": "Peajes", "tipo": "TRANSPORTE", "distribuir_por_defecto": True},
            {"nombre": "Mano de Obra", "tipo": "OPERATIVO", "distribuir_por_defecto": True},
            {"nombre": "Combustible", "tipo": "TRANSPORTE", "distribuir_por_defecto": True},
            {"nombre": "Otros", "tipo": "OPERATIVO", "distribuir_por_defecto": True},
        ]
        created = 0
        for c in default_concepts:
            concepto = ConceptoGasto(**c, activo=True)
            db.add(concepto)
            created += 1
        db.commit()
        return created
