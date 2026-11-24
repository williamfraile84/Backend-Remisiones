import io
import csv
import json
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_admin
from app.models.usuario import Usuario
from app.schemas.auditoria import AuditoriaListResponse
from app.services.auditoria_service import AuditoriaService

router = APIRouter(prefix="/auditoria", tags=["Auditoría del Sistema (Admin)"])


@router.get("", response_model=AuditoriaListResponse)
def get_audit_logs(
    modulo: Optional[str] = Query(None, description="Filtrar por módulo del sistema"),
    accion: Optional[str] = Query(None, description="Filtrar por tipo de acción"),
    usuario_id: Optional[int] = Query(None, description="Filtrar por ID de usuario"),
    search: Optional[str] = Query(None, description="Búsqueda libre por texto"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    admin: Usuario = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Consulta registros del log inmutable de auditoría. Exclusivo para administradores."""
    total, items = AuditoriaService.consultar_logs(
        db=db,
        modulo=modulo,
        accion=accion,
        usuario_id=usuario_id,
        search=search,
        limit=limit,
        offset=offset,
    )
    return {
        "total": total,
        "items": items,
    }


@router.get("/total-count")
def get_audit_total_count(
    admin: Usuario = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Retorna el conteo total de logs en auditoría de forma rápida y optimizada."""
    total = AuditoriaService.consultar_total_logs(db=db)
    return {"total": total}


@router.get("/export-csv")
def export_audit_csv(
    modulo: Optional[str] = Query(None),
    accion: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    admin: Usuario = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Exporta el historial de auditoría en formato CSV para reportes de trazabilidad."""
    _, items = AuditoriaService.consultar_logs(
        db=db,
        modulo=modulo,
        accion=accion,
        search=search,
        limit=5000,
        offset=0,
    )

    output = io.StringIO()
    writer = csv.writer(output)
    # Encabezados
    writer.writerow([
        "ID",
        "Fecha y Hora (UTC)",
        "Usuario ID",
        "Usuario Nombre",
        "Rol",
        "Modulo",
        "Accion",
        "Entidad",
        "Entidad ID",
        "IP Origen",
        "Detalles JSON"
    ])

    for log in items:
        writer.writerow([
            log.id,
            log.creado_en.isoformat() if log.creado_en else "",
            log.usuario_id or "",
            log.usuario_nombre or "Sistema",
            log.usuario_rol or "",
            log.modulo,
            log.accion,
            log.entidad or "",
            log.entidad_id or "",
            log.ip_address or "",
            json.dumps(log.detalles, ensure_ascii=False) if log.detalles else ""
        ])

    csv_data = output.getvalue()
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"auditoria_{date_str}.csv"

    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
