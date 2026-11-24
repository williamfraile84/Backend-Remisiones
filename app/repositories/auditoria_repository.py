from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import or_, desc
from app.models.auditoria import Auditoria
from app.models.auditoria_cambio import AuditoriaCambio


class AuditoriaRepository:

    @staticmethod
    def log(
        db: Session,
        accion: str,
        modulo: str,
        usuario_id: Optional[int] = None,
        usuario_nombre: Optional[str] = None,
        usuario_rol: Optional[str] = None,
        entidad: Optional[str] = None,
        entidad_id: Optional[str] = None,
        detalles: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> Auditoria:
        """Registra un evento inmutable en el log de auditoria y desglosa los cambios en auditoria_cambios (3NF)."""
        audit_entry = Auditoria(
            usuario_id=usuario_id,
            usuario_nombre=usuario_nombre or "Sistema",
            usuario_rol=usuario_rol or "sistema",
            accion=accion,
            modulo=modulo,
            entidad=entidad,
            entidad_id=str(entidad_id) if entidad_id is not None else None,
            ip_address=ip_address,
        )
        db.add(audit_entry)
        db.flush()

        if detalles and isinstance(detalles, dict):
            for k, v in detalles.items():
                tipo = "str"
                if isinstance(v, bool):
                    tipo = "bool"
                elif isinstance(v, int):
                    tipo = "int"
                elif isinstance(v, float):
                    tipo = "float"
                cambio = AuditoriaCambio(
                    auditoria_id=audit_entry.id,
                    campo=str(k),
                    valor_anterior=None,
                    valor_nuevo=str(v) if v is not None else None,
                    tipo_dato=tipo,
                )
                db.add(cambio)

        db.commit()
        return audit_entry

    @staticmethod
    def get_logs(
        db: Session,
        modulo: Optional[str] = None,
        accion: Optional[str] = None,
        usuario_id: Optional[int] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[int, List[Auditoria]]:
        """Consulta registros de auditoria ordenados cronologicamente descendente con filtros y carga ansiosa de cambios optimizada."""
        base_query = db.query(Auditoria)

        if modulo:
            base_query = base_query.filter(Auditoria.modulo == modulo)
        if accion:
            base_query = base_query.filter(Auditoria.accion == accion)
        if usuario_id:
            base_query = base_query.filter(Auditoria.usuario_id == usuario_id)
        if search:
            search_pattern = f"%{search}%"
            base_query = base_query.filter(
                or_(
                    Auditoria.usuario_nombre.ilike(search_pattern),
                    Auditoria.accion.ilike(search_pattern),
                    Auditoria.modulo.ilike(search_pattern),
                    Auditoria.entidad.ilike(search_pattern),
                    Auditoria.entidad_id.ilike(search_pattern),
                )
            )

        # Conteo optimizado sin JOIN de cambios
        total = base_query.count()

        # Carga paginada ansiosa de cambios optimizada (evita producto cartesiano de joinedload con limit/offset)
        items = (
            base_query.options(selectinload(Auditoria.cambios))
            .order_by(desc(Auditoria.id))
            .offset(offset)
            .limit(limit)
            .all()
        )
        return total, items

    @staticmethod
    def count_total(db: Session) -> int:
        """Conteo rapido del total de logs inmutables."""
        return db.query(Auditoria.id).count()
