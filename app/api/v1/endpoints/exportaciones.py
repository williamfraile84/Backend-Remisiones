from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Response, Request, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.usuario import Usuario
from app.repositories.empresa_repository import EmpresaRepository
from app.repositories.cliente_repository import ClienteRepository
from app.schemas.exportacion import ExportPayloadSchema
from app.services.auditoria_service import AuditoriaService
from app.services.export_service import ExportContext

router = APIRouter(prefix="/exportar", tags=["Exportaciones"])


class SurtidoCliente:
    razon_social = "SURTIDO / INVENTARIO INTERNO"
    nit = "USO INTERNO"
    direccion = "SEDE PRINCIPAL"
    telefono = "-"
    email = "-"


def _resolve_cliente(db: Session, cliente_id: Optional[int]):
    if cliente_id:
        c = ClienteRepository.get_by_id(db, cliente_id)
        if c:
            return c
    return SurtidoCliente()


def _ejecutar_exportacion(
    strategy_type: str,
    payload: ExportPayloadSchema,
    current_user: Usuario,
    request: Request,
    db: Session,
) -> Response:
    if not current_user.tiene_permiso("puede_exportar"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No cuenta con permiso para exportar documentos.",
        )

    empresa = EmpresaRepository.get_empresa(db)
    cliente = _resolve_cliente(db, payload.cliente_id)

    strategy = ExportContext.get_strategy(strategy_type)
    content_bytes = strategy.export(empresa, cliente, payload.model_dump())

    prefijo = "REMISION" if "remision" in strategy_type else "INFORME"
    filename = f"{prefijo}_{payload.numero_remision}.{strategy.file_extension}"

    AuditoriaService.registrar_evento(
        db=db,
        accion=f"EXPORTAR_{strategy_type.upper().replace('-', '_')}",
        modulo="EXPORTACIONES",
        usuario=current_user,
        entidad="Cliente",
        entidad_id=payload.cliente_id,
        detalles={"numero_remision": payload.numero_remision},
        request=request,
    )

    return Response(
        content=content_bytes,
        media_type=strategy.media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/pdf-remision")
def exportar_pdf_remision_endpoint(
    payload: ExportPayloadSchema,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _ejecutar_exportacion("pdf-remision", payload, current_user, request, db)


@router.post("/excel-remision")
def exportar_excel_remision_endpoint(
    payload: ExportPayloadSchema,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _ejecutar_exportacion("excel-remision", payload, current_user, request, db)


@router.post("/pdf-informe")
def exportar_pdf_informe_endpoint(
    payload: ExportPayloadSchema,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _ejecutar_exportacion("pdf-informe", payload, current_user, request, db)


@router.post("/excel-informe")
def exportar_excel_informe_endpoint(
    payload: ExportPayloadSchema,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _ejecutar_exportacion("excel-informe", payload, current_user, request, db)