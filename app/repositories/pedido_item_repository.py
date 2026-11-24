from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.pedido_item import PedidoItem


class PedidoItemRepository:
    """
    Repositorio atómico para líneas de pedido (PedidoItem).
    Cumple con el Principio de Responsabilidad Única (SRP).
    Implementa política de eliminación cero (Soft-Delete estricto).
    """

    @staticmethod
    def get_by_id(db: Session, item_id: int) -> Optional[PedidoItem]:
        return db.query(PedidoItem).filter(PedidoItem.id == item_id).first()

    @staticmethod
    def get_by_pedido_id(db: Session, pedido_id: int, activo_only: bool = True) -> List[PedidoItem]:
        query = db.query(PedidoItem).filter(PedidoItem.pedido_id == pedido_id)
        if activo_only:
            query = query.filter(PedidoItem.activo == True)
        return query.order_by(PedidoItem.orden.asc()).all()

    @staticmethod
    def create(db: Session, data: Dict[str, Any]) -> PedidoItem:
        data_clean = data.copy()
        if "activo" not in data_clean:
            data_clean["activo"] = True
        item = PedidoItem(**data_clean)
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    @staticmethod
    def update(db: Session, item_id: int, data: Dict[str, Any]) -> Optional[PedidoItem]:
        item = db.query(PedidoItem).filter(PedidoItem.id == item_id).first()
        if not item:
            return None
        for key, value in data.items():
            if value is not None and hasattr(item, key):
                setattr(item, key, value)
        db.commit()
        db.refresh(item)
        return item

    @staticmethod
    def soft_delete(db: Session, item_id: int) -> bool:
        """Baja lógica de ítem de pedido. Nunca elimina físicamente el registro."""
        item = db.query(PedidoItem).filter(PedidoItem.id == item_id).first()
        if not item:
            return False
        item.activo = False
        db.commit()
        return True

