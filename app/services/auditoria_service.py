from typing import Optional, Dict, Any, Tuple, List
from fastapi import Request
from sqlalchemy.orm import Session
from app.repositories.auditoria_repository import AuditoriaRepository
from app.models.usuario import Usuario
from app.models.auditoria import Auditoria


class AuditoriaService:

    @staticmethod
    def get_client_ip(request: Optional[Request]) -> Optional[str]:
        if not request:
            return None
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if request.client:
            return request.client.host
        return None

    @staticmethod
    def registrar_evento(
        db: Session,
        accion: str,
        modulo: str,
        usuario: Optional[Usuario] = None,
        entidad: Optional[str] = None,
        entidad_id: Optional[Any] = None,
        detalles: Optional[Dict[str, Any]] = None,
        request: Optional[Request] = None,
    ) -> Auditoria:
        """Registra un evento de auditoría de forma atómica y consistente."""
        ip = AuditoriaService.get_client_ip(request)
        usuario_id = usuario.id if usuario else None
        usuario_nombre = usuario.nombre_completo if usuario else "Sistema"
        usuario_rol = usuario.rol if usuario else "sistema"

        return AuditoriaRepository.log(
            db=db,
            accion=accion,
            modulo=modulo,
            usuario_id=usuario_id,
            usuario_nombre=usuario_nombre,
            usuario_rol=usuario_rol,
            entidad=entidad,
            entidad_id=str(entidad_id) if entidad_id is not None else None,
            detalles=detalles or {},
            ip_address=ip,
        )

    @staticmethod
    def consultar_logs(
        db: Session,
        modulo: Optional[str] = None,
        accion: Optional[str] = None,
        usuario_id: Optional[int] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[int, List[Auditoria]]:
        return AuditoriaRepository.get_logs(
            db=db,
            modulo=modulo,
            accion=accion,
            usuario_id=usuario_id,
            search=search,
            limit=limit,
            offset=offset,
        )

    @staticmethod
    def consultar_total_logs(db: Session) -> int:
        return AuditoriaRepository.count_total(db)

