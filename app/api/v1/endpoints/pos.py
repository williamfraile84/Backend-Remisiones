import asyncio
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.usuario import Usuario
from app.models.producto import Producto
from app.services.pos_service import POSService
from app.schemas.pos import (
    PosStatusResponse,
    ProductSearchResponse,
    PosItemDetailResponse,
    SinglePriceUpdateRequest,
    PriceUpdateResponse,
    PosConciliarRequest
)
from app.services.auditoria_service import AuditoriaService
from app.repositories.producto_repository import ProductoRepository

router = APIRouter(prefix="/pos", tags=["Sistema POS"])


def get_pos_service() -> POSService:
    return POSService.get_instance()


@router.get("/status", response_model=PosStatusResponse)
async def get_pos_status(
    pos_service: POSService = Depends(get_pos_service)
):
    """Consulta el estado del servicio POS externo."""
    if not pos_service.is_initialized and not pos_service.last_error:
        try:
            await asyncio.wait_for(pos_service.initialize(), timeout=8.0)
        except Exception as e:
            pos_service.last_error = f"Error conectando con POS: {str(e) or type(e).__name__}"
    status_info = await pos_service.get_status()
    return PosStatusResponse(**status_info)


@router.get("/search", response_model=ProductSearchResponse)
async def search_pos_products(
    query: str = Query("", description="Término o nombre de producto a buscar en POS"),
    pos_service: POSService = Depends(get_pos_service)
):
    """Busca productos en el catálogo en vivo de CSOPOS."""
    try:
        results = await pos_service.search_products(query)
        return results
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error durante la búsqueda de productos en POS: {str(e)}"
        )


@router.get("/items/{item_id}", response_model=PosItemDetailResponse)
async def get_pos_item_detail(
    item_id: str,
    pos_service: POSService = Depends(get_pos_service)
):
    """Obtiene los detalles completos de un producto directamente desde CSOPOS."""
    try:
        data = await pos_service.get_pos_item_details(item_id)
        if not data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró el producto con ID '{item_id}' en CSOPOS."
            )
        return PosItemDetailResponse(**data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener el producto de CSOPOS: {str(e)}"
        )


@router.post("/update-price", response_model=PriceUpdateResponse)
async def update_single_price_endpoint(
    payload: SinglePriceUpdateRequest,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    pos_service: POSService = Depends(get_pos_service),
    db: Session = Depends(get_db)
):
    """
    Modifica el precio de venta de un producto en el POS y sincroniza la base de datos local.
    """
    try:
        # 1. Actualizar en el sistema POS
        response = await pos_service.update_single_price(
            barcode=payload.barcode,
            new_price=payload.new_price,
            item_id=payload.item_id,
            modal_barcode=payload.modal_barcode
        )
    except Exception as e:
        # Si el POS falla o está offline, registramos el error pero permitimos actualizar en local
        response = PriceUpdateResponse(
            success=False,
            message=f"No se pudo contactar al POS: {e}",
            new_price=payload.new_price,
            formatted_new_price=f"${int(payload.new_price):,}".replace(",", ".")
        )

    # 2. Sincronizar en catálogo local SQLite
    if payload.item_id:
        prod = db.query(Producto).filter(Producto.pos_item_id == str(payload.item_id)).first()
        if not prod and payload.barcode:
            prod = db.query(Producto).filter(Producto.codigo == str(payload.barcode)).first()
        if prod:
            prod.precio_pos_actual = float(payload.new_price)
            prod.precio_venta_referencia = float(payload.new_price)
            db.commit()
            ProductoRepository.invalidate_cache()

    AuditoriaService.registrar_evento(
        db=db,
        accion="ACTUALIZAR_PRECIO_POS",
        modulo="CATALOGOS",
        usuario=current_user,
        entidad="Producto",
        detalles={"item_id": payload.item_id, "barcode": payload.barcode, "new_price": payload.new_price},
        request=request
    )

    return response


@router.post("/conciliar")
async def conciliar_precios_pos_endpoint(
    payload: PosConciliarRequest,
    request: Request,
    current_user: Usuario = Depends(get_current_user),
    pos_service: POSService = Depends(get_pos_service),
    db: Session = Depends(get_db)
):
    """
    Concilia y actualiza en lote los precios de venta en el Sistema POS y en el Catálogo Maestro local.
    """
    actualizados = []
    errores = []

    for item in payload.items:
        try:
            pos_id_str = str(item.pos_item_id).strip() if item.pos_item_id else None
            barcode_str = str(item.barcode).strip() if item.barcode else None
            nuevo_precio = float(item.nuevo_precio_venta)

            pos_updated = False
            # Intentar actualizar en CSOPOS si hay ID de POS o código
            if pos_id_str or barcode_str:
                try:
                    res_pos = await pos_service.update_single_price(
                        barcode=barcode_str or pos_id_str,
                        new_price=nuevo_precio,
                        item_id=pos_id_str
                    )
                    pos_updated = getattr(res_pos, "success", False)
                except Exception as pos_err:
                    pos_updated = False

            # Actualizar en BD local SQLite
            prod = None
            if item.producto_id:
                prod = db.query(Producto).filter(Producto.id == item.producto_id).first()
            if not prod and pos_id_str:
                prod = db.query(Producto).filter(Producto.pos_item_id == pos_id_str).first()
            if not prod and item.nombre:
                prod = ProductoRepository.get_by_nombre(db, item.nombre)

            if prod and payload.actualizar_catalogo_local:
                prod.precio_pos_actual = nuevo_precio
                prod.precio_venta_referencia = nuevo_precio
                if item.nuevo_costo is not None and float(item.nuevo_costo) > 0:
                    prod.precio_costo_referencia = float(item.nuevo_costo)
                if pos_id_str and not prod.pos_item_id:
                    prod.pos_item_id = pos_id_str
                if barcode_str and not prod.codigo:
                    prod.codigo = barcode_str

            actualizados.append({
                "nombre": item.nombre,
                "pos_item_id": pos_id_str,
                "nuevo_precio": nuevo_precio,
                "pos_sincronizado": pos_updated
            })
        except Exception as it_err:
            errores.append({"nombre": item.nombre, "error": str(it_err)})

    try:
        db.commit()
        ProductoRepository.invalidate_cache()
    except Exception as db_err:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error guardando cambios en la base de datos: {str(db_err)}"
        )

    AuditoriaService.registrar_evento(
        db=db,
        accion="CONCILIACION_PRECIOS_POS",
        modulo="CATALOGOS",
        usuario=current_user,
        entidad="Producto",
        detalles={"total": len(actualizados), "errores": len(errores)},
        request=request
    )

    return {
        "success": True,
        "total_procesados": len(payload.items),
        "total_actualizados": len(actualizados),
        "actualizados": actualizados,
        "errores": errores
    }
