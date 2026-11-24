from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, selectinload
from app.models.role import Role
from app.models.permiso import Permiso


class RoleRepository:
    """
    Repositorio atómico para gestión de Roles RBAC.
    Cumple con el Principio de Responsabilidad Única (SRP).
    Implementa política de eliminación cero (Soft-Delete).
    """

    @staticmethod
    def get_all(db: Session, activo_only: bool = True) -> List[Role]:
        query = db.query(Role).options(selectinload(Role.permisos))
        if activo_only:
            query = query.filter(Role.activo == True)
        return query.order_by(Role.nombre.asc()).all()

    @staticmethod
    def get_by_id(db: Session, role_id: int) -> Optional[Role]:
        return db.query(Role).options(selectinload(Role.permisos)).filter(Role.id == role_id).first()

    @staticmethod
    def get_by_codigo(db: Session, codigo: str) -> Optional[Role]:
        return db.query(Role).options(selectinload(Role.permisos)).filter(Role.codigo == codigo.strip().lower()).first()

    @staticmethod
    def create(db: Session, data: Dict[str, Any], permiso_ids: Optional[List[int]] = None) -> Role:
        role = Role(
            codigo=data.get("codigo", "").strip().lower(),
            nombre=data.get("nombre", "").strip(),
            descripcion=data.get("descripcion"),
            activo=data.get("activo", True),
        )
        if permiso_ids:
            perms = db.query(Permiso).filter(Permiso.id.in_(permiso_ids)).all()
            role.permisos = perms
        db.add(role)
        db.commit()
        db.refresh(role)
        return role

    @staticmethod
    def update(db: Session, role_id: int, data: Dict[str, Any], permiso_ids: Optional[List[int]] = None) -> Optional[Role]:
        role = db.query(Role).filter(Role.id == role_id).first()
        if not role:
            return None
        for key, value in data.items():
            if value is not None and hasattr(role, key):
                setattr(role, key, value)
        if permiso_ids is not None:
            perms = db.query(Permiso).filter(Permiso.id.in_(permiso_ids)).all()
            role.permisos = perms
        db.commit()
        db.refresh(role)
        return role

    @staticmethod
    def delete(db: Session, role_id: int) -> bool:
        """Baja lógica estricta (Soft Delete)."""
        role = db.query(Role).filter(Role.id == role_id).first()
        if not role:
            return False
        role.activo = False
        db.commit()
        return True

