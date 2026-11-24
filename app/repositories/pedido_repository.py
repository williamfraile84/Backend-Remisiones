from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.pedido import Pedido


class PedidoRepository:

    @staticmethod
    def get_by_id(db: Session, pedido_id: int) -> Optional[Pedido]:
        return db.query(Pedido).filter(Pedido.id == pedido_id, Pedido.activo == True).first()

    @staticmethod
    def get_by_cliente_id(db: Session, cliente_id: int) -> List[Pedido]:
        return (
            db.query(Pedido)
            .filter(Pedido.cliente_id == cliente_id, Pedido.activo == True)
            .order_by(Pedido.id.desc())
            .all()
        )

    @staticmethod
    def create(db: Session, data: Dict[str, Any]) -> Pedido:
        pedido = Pedido(**data)
        db.add(pedido)
        db.commit()
        db.refresh(pedido)
        return pedido

    @staticmethod
    def update(db: Session, pedido_id: int, data: Dict[str, Any]) -> Optional[Pedido]:
        pedido = db.query(Pedido).filter(Pedido.id == pedido_id).first()
        if pedido:
            for key, value in data.items():
                setattr(pedido, key, value)
            db.commit()
            db.refresh(pedido)
        return pedido

    @staticmethod
    def soft_delete(db: Session, pedido_id: int) -> bool:
        pedido = db.query(Pedido).filter(Pedido.id == pedido_id).first()
        if pedido:
            pedido.activo = False
            db.commit()
            return True
        return False

    @staticmethod
    def attach_factura(db: Session, pedido_id: int, path: str, filename: str) -> Optional[Pedido]:
        pedido = db.query(Pedido).filter(Pedido.id == pedido_id).first()
        if pedido:
            pedido.factura_cargada = True
            pedido.factura_archivo_path = path
            pedido.factura_archivo_nombre = filename
            db.commit()
            db.refresh(pedido)
        return pedido

    @staticmethod
    def attach_remision_firmada(db: Session, pedido_id: int, path: str, filename: str) -> Optional[Pedido]:
        pedido = db.query(Pedido).filter(Pedido.id == pedido_id).first()
        if pedido:
            pedido.remision_firmada_cargada = True
            pedido.remision_firmada_path = path
            pedido.remision_firmada_nombre = filename
            db.commit()
            db.refresh(pedido)
        return pedido