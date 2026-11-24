from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from app.models.empresa import Empresa


class EmpresaRepository:

    @staticmethod
    def get_empresa(db: Session, empresa_id: Optional[int] = None) -> Optional[Empresa]:
        """Obtiene una empresa específica por ID, o la primera activa disponible."""
        if empresa_id:
            return db.query(Empresa).filter(Empresa.id == empresa_id, Empresa.activo.is_(True)).first()
        return db.query(Empresa).filter(Empresa.activo.is_(True)).first()

    @staticmethod
    def get_by_id(db: Session, empresa_id: int) -> Optional[Empresa]:
        """Obtiene una empresa por su ID."""
        return db.query(Empresa).filter(Empresa.id == empresa_id).first()

    @staticmethod
    def get_all(db: Session, solo_activas: bool = True) -> List[Empresa]:
        """Retorna todas las empresas registradas."""
        query = db.query(Empresa)
        if solo_activas:
            query = query.filter(Empresa.activo.is_(True))
        return query.order_by(Empresa.nombre.asc()).all()

    @staticmethod
    def create(db: Session, data: Dict[str, Any]) -> Empresa:
        """Crea una nueva empresa independiente."""
        data_clean = data.copy()
        data_clean.pop("campos_extra", None)
        empresa = Empresa(**data_clean)
        db.add(empresa)
        db.commit()
        db.refresh(empresa)
        return empresa

    @staticmethod
    def update(db: Session, empresa_id: int, data: Dict[str, Any]) -> Optional[Empresa]:
        """Actualiza los datos de una empresa específica."""
        empresa = db.query(Empresa).filter(Empresa.id == empresa_id).first()
        if not empresa:
            return None
        data_clean = data.copy()
        data_clean.pop("campos_extra", None)
        for key, value in data_clean.items():
            setattr(empresa, key, value)
        db.commit()
        db.refresh(empresa)
        return empresa

    @staticmethod
    def create_or_update(db: Session, data: Dict[str, Any], empresa_id: Optional[int] = None) -> Empresa:
        """Compatibilidad: actualiza la empresa indicada o crea una nueva si no existe ninguna."""
        empresa = None
        if empresa_id:
            empresa = db.query(Empresa).filter(Empresa.id == empresa_id).first()
        if not empresa:
            empresa = db.query(Empresa).first()

        data_clean = data.copy()
        data_clean.pop("campos_extra", None)

        if not empresa:
            empresa = Empresa(**data_clean)
            db.add(empresa)
        else:
            for key, value in data_clean.items():
                setattr(empresa, key, value)
        db.commit()
        db.refresh(empresa)
        return empresa

    @staticmethod
    def update_logo(db: Session, logo_path: str, empresa_id: Optional[int] = None) -> Optional[Empresa]:
        """Actualiza el logo corporativo de la empresa indicada o de la primera disponible."""
        if empresa_id:
            empresa = db.query(Empresa).filter(Empresa.id == empresa_id).first()
        else:
            empresa = db.query(Empresa).first()

        if empresa:
            empresa.logo_path = logo_path
            db.commit()
            db.refresh(empresa)
        return empresa
