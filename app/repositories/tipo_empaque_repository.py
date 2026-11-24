from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models.tipo_empaque import TipoEmpaque


class TipoEmpaqueRepository:
    """
    Repositorio atómico para gestión de Tipos de Empaque (Bulto, Pony, Canastilla, etc.).
    Cumple con el Principio de Responsabilidad Única (SRP).
    Implementa política de eliminación cero (Soft-Delete estricto).
    """

    @staticmethod
    def get_all(db: Session, search: Optional[str] = None, activo_only: bool = True) -> List[TipoEmpaque]:
        query = db.query(TipoEmpaque)
        if activo_only:
            query = query.filter(TipoEmpaque.activo == True)
        if search and search.strip():
            term = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    TipoEmpaque.nombre.ilike(term),
                    TipoEmpaque.descripcion.ilike(term)
                )
            )
        return query.order_by(TipoEmpaque.nombre.asc()).all()

    @staticmethod
    def get_by_id(db: Session, tipo_id: int) -> Optional[TipoEmpaque]:
        return db.query(TipoEmpaque).filter(TipoEmpaque.id == tipo_id).first()

    @staticmethod
    def get_by_nombre(db: Session, nombre: str) -> Optional[TipoEmpaque]:
        return db.query(TipoEmpaque).filter(TipoEmpaque.nombre.ilike(nombre.strip())).first()

    @staticmethod
    def create(db: Session, data: Dict[str, Any]) -> TipoEmpaque:
        peso_kg = float(data.get("peso_kg") or 0.0)
        peso_lb = float(data.get("peso_lb") or (peso_kg * 2.0))
        peso_lb = round(peso_kg * 2.0, 2)
        tipo = TipoEmpaque(
            nombre=data.get("nombre", "").strip(),
            peso_kg=peso_kg,
            peso_lb=peso_lb,
            descripcion=data.get("descripcion"),
            activo=data.get("activo", True),
        )
        db.add(tipo)
        db.commit()
        db.refresh(tipo)
        return tipo

    @staticmethod
    def update(db: Session, tipo_id: int, data: Dict[str, Any]) -> Optional[TipoEmpaque]:
        tipo = db.query(TipoEmpaque).filter(TipoEmpaque.id == tipo_id).first()
        if not tipo:
            return None
        for key, value in data.items():
            if value is not None:
                if key == "nombre":
                    setattr(tipo, key, str(value).strip())
                elif key == "peso_kg":
                    setattr(tipo, key, float(value))
                    if "peso_lb" not in data or data["peso_lb"] is None:
                        tipo.peso_lb = float(value) * 2.0
                    tipo.peso_lb = round(float(value) * 2.0, 2)
                elif key == "peso_lb":
                    setattr(tipo, key, float(value))
                    # Conservar coherencia con peso_kg
                    pass
                else:
                    setattr(tipo, key, value)
        if tipo.peso_kg:
            tipo.peso_lb = round(tipo.peso_kg * 2.0, 2)
        db.commit()
        db.refresh(tipo)
        return tipo

    @staticmethod
    def delete(db: Session, tipo_id: int, hard: bool = False) -> bool:
        """
        Baja lógica estricta (Soft Delete) por defecto.
        Si hard=True se elimina físicamente de la base de datos (para tests o purga explícita).
        """
        tipo = db.query(TipoEmpaque).filter(TipoEmpaque.id == tipo_id).first()
        if not tipo:
            return False
        if hard:
            db.delete(tipo)
            db.commit()
            return True
        tipo.activo = False
        db.commit()
        return True

    @staticmethod
    def seed_default_tipos_if_empty(db: Session) -> int:
        count = db.query(TipoEmpaque).count()
        if count > 0:
            return 0

        default_tipos = [
            {"nombre": "Bulto", "peso_kg": 50.0, "peso_lb": 100.0, "descripcion": "Bulto completo estándar tradicional (50 kg / 100 lb)"},
            {"nombre": "Pony", "peso_kg": 25.0, "peso_lb": 50.0, "descripcion": "Medio bulto estándar seleccionado (25 kg / 50 lb)"},
            {"nombre": "Canastilla", "peso_kg": 22.0, "peso_lb": 44.0, "descripcion": "Canastilla plástica estándar de fruver (22 kg / 44 lb)"},
            {"nombre": "Caja", "peso_kg": 15.0, "peso_lb": 30.0, "descripcion": "Caja de cartón o madera corrugada (15 kg / 30 lb)"},
            {"nombre": "Saco", "peso_kg": 30.0, "peso_lb": 60.0, "descripcion": "Saco ventilado o parafinado (30 kg / 60 lb)"},
            {"nombre": "Bolsa", "peso_kg": 5.0, "peso_lb": 10.0, "descripcion": "Bolsa plástica o paquete sellado (5 kg / 10 lb)"},
            {"nombre": "Rollo / Atado", "peso_kg": 12.0, "peso_lb": 24.0, "descripcion": "Manojo, atado o rollo de hierbas u hortalizas (12 kg / 24 lb)"},
            {"nombre": "Arroba", "peso_kg": 12.5, "peso_lb": 25.0, "descripcion": "Medida tradicional colombiana de 25 libras (12.5 kg / 25 lb)"},
            {"nombre": "Malla", "peso_kg": 3.0, "peso_lb": 6.0, "descripcion": "Malla tubular transpirable para cítricos o cebollas (3 kg / 6 lb)"},
            {"nombre": "Cubeta", "peso_kg": 2.0, "peso_lb": 4.0, "descripcion": "Cubeta rígida de plástico o cartón (2 kg / 4 lb)"},
            {"nombre": "Huacal", "peso_kg": 20.0, "peso_lb": 40.0, "descripcion": "Huacal tradicional de madera para transporte (20 kg / 40 lb)"},
        ]

        for item in default_tipos:
            t = TipoEmpaque(**item)
            db.add(t)
        db.commit()
        return len(default_tipos)

