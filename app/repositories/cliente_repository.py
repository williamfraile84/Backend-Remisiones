from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.cliente import Cliente


class ClienteRepository:

    @staticmethod
    def get_by_id(db: Session, cliente_id: int) -> Optional[Cliente]:
        return db.query(Cliente).filter(Cliente.id == cliente_id, Cliente.activo == True).first()

    @staticmethod
    def get_by_nit(db: Session, nit: str) -> Optional[Cliente]:
        return db.query(Cliente).filter(Cliente.nit == nit, Cliente.activo == True).first()

    @staticmethod
    def get_all_active(db: Session) -> List[Cliente]:
        return db.query(Cliente).filter(Cliente.activo == True).order_by(Cliente.razon_social.asc()).all()

    @staticmethod
    def create(db: Session, data: Dict[str, Any]) -> Cliente:
        cliente = Cliente(**data)
        db.add(cliente)
        db.commit()
        db.refresh(cliente)
        return cliente

    @staticmethod
    def update(db: Session, cliente_id: int, data: Dict[str, Any]) -> Optional[Cliente]:
        cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
        if cliente:
            for key, value in data.items():
                setattr(cliente, key, value)
            db.commit()
            db.refresh(cliente)
        return cliente

    @staticmethod
    def increment_consecutivo(db: Session, cliente_id: int, current_num_str: str) -> None:
        cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
        if cliente:
            try:
                num = int(current_num_str)
                cliente.consecutivo_remision_actual = num + 1
                db.commit()
            except ValueError:
                pass