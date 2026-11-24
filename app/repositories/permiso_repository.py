from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.permiso import Permiso
from app.models.modulo import Modulo


class PermisoRepository:
    """
    Repositorio atómico para consulta y administración de Permisos RBAC (3NF estricta).
    Cumple con el Principio de Responsabilidad Única (SRP).
    Implementa política de eliminación cero (Soft-Delete).
    """

    @staticmethod
    def get_all(db: Session, activo_only: bool = True, modulo: Optional[str] = None) -> List[Permiso]:
        query = db.query(Permiso)
        if activo_only:
            query = query.filter(Permiso.activo == True)
        if modulo:
            clean = modulo.strip().upper()
            query = query.join(Permiso.modulo_rel).filter(Modulo.codigo == clean)
        return query.order_by(Permiso.modulo_id.asc(), Permiso.codigo.asc()).all()

    @staticmethod
    def get_by_id(db: Session, permiso_id: int) -> Optional[Permiso]:
        return db.query(Permiso).filter(Permiso.id == permiso_id).first()

    @staticmethod
    def get_by_codigo(db: Session, codigo: str) -> Optional[Permiso]:
        return db.query(Permiso).filter(Permiso.codigo == codigo.strip()).first()

    @staticmethod
    def create(db: Session, data: Dict[str, Any]) -> Permiso:
        mod_cod = str(data.get("modulo", "SISTEMA")).strip().upper()
        modulo_id = data.get("modulo_id")
        if not modulo_id:
            mod_obj = db.query(Modulo).filter(Modulo.codigo == mod_cod).first()
            if not mod_obj:
                mod_obj = Modulo(codigo=mod_cod, nombre=mod_cod.capitalize(), activo=True)
                db.add(mod_obj)
                db.flush()
            modulo_id = mod_obj.id

        permiso = Permiso(
            codigo=data.get("codigo", "").strip(),
            nombre=data.get("nombre", "").strip(),
            modulo_id=modulo_id,
            descripcion=data.get("descripcion"),
            activo=data.get("activo", True),
        )
        db.add(permiso)
        db.commit()
        db.refresh(permiso)
        return permiso

    @staticmethod
    def delete(db: Session, permiso_id: int) -> bool:
        """Baja lógica estricta (Soft Delete)."""
        p = db.query(Permiso).filter(Permiso.id == permiso_id).first()
        if not p:
            return False
        p.activo = False
        db.commit()
        return True
