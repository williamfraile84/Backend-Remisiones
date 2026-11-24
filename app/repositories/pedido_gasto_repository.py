from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.pedido_gasto import PedidoGasto


class PedidoGastoRepository:
    """
    Repositorio atómico para gastos de pedido (PedidoGasto).
    Cumple con el Principio de Responsabilidad Única (SRP).
    Implementa política de eliminación cero (Soft-Delete estricto).
    """

    @staticmethod
    def get_by_id(db: Session, gasto_id: int) -> Optional[PedidoGasto]:
        return db.query(PedidoGasto).filter(PedidoGasto.id == gasto_id).first()

    @staticmethod
    def get_by_pedido_id(db: Session, pedido_id: int, activo_only: bool = True) -> List[PedidoGasto]:
        query = db.query(PedidoGasto).filter(PedidoGasto.pedido_id == pedido_id)
        if activo_only:
            query = query.filter(PedidoGasto.activo == True)
        return query.all()

    @staticmethod
    def create(db: Session, data: Dict[str, Any]) -> PedidoGasto:
        data_clean = data.copy()
        if "activo" not in data_clean:
            data_clean["activo"] = True
        gasto = PedidoGasto(**data_clean)
        db.add(gasto)
        db.commit()
        db.refresh(gasto)
        return gasto

    @staticmethod
    def update(db: Session, gasto_id: int, data: Dict[str, Any]) -> Optional[PedidoGasto]:
        gasto = db.query(PedidoGasto).filter(PedidoGasto.id == gasto_id).first()
        if not gasto:
            return None
        for key, value in data.items():
            if value is not None and hasattr(gasto, key):
                setattr(gasto, key, value)
        db.commit()
        db.refresh(gasto)
        return gasto

    @staticmethod
    def soft_delete(db: Session, gasto_id: int) -> bool:
        """Baja lógica de gasto de pedido. Nunca elimina físicamente el registro."""
        gasto = db.query(PedidoGasto).filter(PedidoGasto.id == gasto_id).first()
        if not gasto:
            return False
        gasto.activo = False
        db.commit()
        return True

