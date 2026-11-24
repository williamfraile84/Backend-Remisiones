import logging
from typing import Dict, Any, Optional, List
from fastapi import HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models.pedido import Pedido
from app.models.cliente import Cliente
from app.models.usuario import Usuario
from app.models.producto import Producto
from app.models.unidad_medida import UnidadMedida
from app.models.empaque import TipoEmpaque
from app.models.concepto_gasto import ConceptoGasto
from app.models.pedido_item import PedidoItem
from app.models.pedido_gasto import PedidoGasto
from app.schemas.pedido import PedidoSavePayload
from app.services.pricing_service import recalcular_liquidacion
from app.services.auditoria_service import AuditoriaService
from app.services.storage.storage_factory import get_storage_provider
from app.core.security import generate_secure_storage_path, validate_file_upload, ALLOWED_CLOSURE_EXTENSIONS
from app.core.config import settings
from app.repositories.producto_repository import ProductoRepository
from app.repositories.concepto_gasto_repository import ConceptoGastoRepository

logger = logging.getLogger(__name__)


class PedidoService:
    """
    Capa de servicio y orquestación de negocio para Pedidos (Service Layer / DDD).
    Encapsula lógica de liquidación, sincronización relacional (3NF) y JSON,
    gestión de consecutivos, cierre formal y auditoría.
    """

    @classmethod
    def guardar_pedido(
        cls,
        db: Session,
        payload: PedidoSavePayload,
        current_user: Usuario,
        request: Request,
    ) -> Pedido:
        if not payload.cliente_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El cliente es obligatorio para registrar un pedido."
            )

        # Bloqueo pesimista para evitar colisiones concurrentes en el consecutivo
        cliente = db.query(Cliente).filter(Cliente.id == payload.cliente_id).with_for_update().first()
        if not cliente:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado")

        pedido_existente = None
        if payload.id:
            pedido_existente = db.query(Pedido).filter(Pedido.id == payload.id).first()

        es_nuevo = pedido_existente is None

        # Gestión estricta de consecutivo de remisión
        if es_nuevo:
            if not payload.numero_remision:
                rem_num = str(cliente.consecutivo_remision_actual)
                cliente.consecutivo_remision_actual += 1
            else:
                rem_num = str(payload.numero_remision)
                if rem_num.isdigit():
                    num_val = int(rem_num)
                    if num_val >= cliente.consecutivo_remision_actual:
                        cliente.consecutivo_remision_actual = num_val + 1
        else:
            rem_num = payload.numero_remision or pedido_existente.numero_remision

        util_val = (
            payload.utilidad_global
            if payload.utilidad_global is not None
            else (payload.porcentaje_utilidad_global or 30.0)
        )
        canastas_val = payload.numero_canastas or payload.numero_canastillas or ""
        archivo_val = payload.archivo_origen_path or payload.archivo_original_path or None

        # Cálculo centralizado y sincronizado de liquidación
        liquidacion = recalcular_liquidacion(
            productos=payload.productos,
            gastos=payload.gastos,
            utilidad_global=util_val,
        )

        productos_guardar = liquidacion.get("items", payload.productos)

        user_id = current_user.id if current_user else None
        from app.core.dependencies import resolve_empresa_id
        emp_id = (
            cliente.empresa_id
            or (current_user.empresa_id if current_user else None)
            or resolve_empresa_id(db, request=request, current_user=current_user)
        )
        if emp_id and not cliente.empresa_id:
            cliente.empresa_id = emp_id

        if es_nuevo:
            pedido = Pedido(
                empresa_id=emp_id,
                usuario_id=user_id,
                cliente_id=cliente.id,
                numero_remision=rem_num,
                numero_oc=payload.numero_oc,
                fecha_emision=payload.fecha_emision,
                fecha_entrega=payload.fecha_entrega,
                observaciones=payload.observaciones,
                numero_canastas=canastas_val,
                utilidad_global=util_val,
                archivo_origen_path=archivo_val,
            )
            db.add(pedido)
            db.flush()  # Obtener ID para ítems relacionales
        else:
            pedido = pedido_existente
            pedido.cliente_id = cliente.id
            if emp_id:
                pedido.empresa_id = emp_id
            if user_id:
                pedido.usuario_id = user_id
            pedido.numero_remision = rem_num
            pedido.numero_oc = payload.numero_oc
            pedido.fecha_emision = payload.fecha_emision
            pedido.fecha_entrega = payload.fecha_entrega
            pedido.observaciones = payload.observaciones
            pedido.numero_canastas = canastas_val
            pedido.utilidad_global = util_val
            if archivo_val:
                pedido.archivo_origen_path = archivo_val

        # Salvaguarda: si se intenta actualizar un pedido existente con 0 productos
        # pero el pedido ya tenía ítems, no borrar los ítems existentes por error de sincronización
        if not es_nuevo and len(productos_guardar) == 0:
            existing_count = db.query(PedidoItem).filter(PedidoItem.pedido_id == pedido.id).count()
            if existing_count > 0:
                logger.warning(
                    f"Aviso de seguridad: Se evitó vaciado accidental de {existing_count} ítems en pedido {pedido.id}."
                )
                db.commit()
                db.refresh(pedido)
                return pedido

        # Sincronización relacional 3NF: PedidoItem y PedidoGasto
        cls._sincronizar_items_relacionales(db, pedido, productos_guardar)
        cls._sincronizar_gastos_relacionales(db, pedido, payload.gastos)

        db.commit()
        db.refresh(pedido)

        totales = liquidacion.get("resumen", {})
        AuditoriaService.registrar_evento(
            db=db,
            accion="CREAR_PEDIDO" if es_nuevo else "ACTUALIZAR_PEDIDO",
            modulo="PEDIDOS",
            usuario=current_user,
            entidad="Pedido",
            entidad_id=pedido.id,
            detalles={
                "numero_remision": pedido.numero_remision,
                "cliente_id": cliente.id,
                "total_venta": totales.get("total_ventas", 0.0),
                "total_kilos": totales.get("total_kilos", 0.0),
            },
            request=request,
        )
        return pedido

    @classmethod
    def _sincronizar_items_relacionales(cls, db: Session, pedido: Pedido, productos: List[Dict[str, Any]]):
        """
        Sincroniza los ítems relacionales en tabla pedido_items (3NF) de forma no destructiva (Upsert diferencial).
        Preserva los IDs primarios existentes evitando bloat y consumo innecesario de secuencias.
        """
        existing_items = {item.id: item for item in db.query(PedidoItem).filter(PedidoItem.pedido_id == pedido.id).all()}
        processed_ids = set()

        # Precarga agregada de catálogos para evitar N+1 en bucle
        unidades_list = db.query(UnidadMedida).all()
        unidades_by_code = {u.codigo.upper(): u for u in unidades_list if u.codigo}
        unidades_by_name = {u.nombre.strip().upper(): u for u in unidades_list if u.nombre}
        empaques_list = db.query(TipoEmpaque).all()
        empaques_by_name = {e.nombre.strip().upper(): e for e in empaques_list if e.nombre}
        pedido_gasto_kilo = float(pedido.gasto_por_kilo or 0.0)

        for idx, prod_raw in enumerate(productos or []):
            if not isinstance(prod_raw, dict):
                continue

            nombre = prod_raw.get("nombre") or prod_raw.get("producto") or f"Ítem {idx + 1}"
            unidad_str = prod_raw.get("unidad") or "KG"
            empaque_str = prod_raw.get("empaque") or prod_raw.get("tipo_empaque")

            # Buscar producto en catálogo maestro sin auto-crear para evitar errores tipográficos
            producto_obj = ProductoRepository.find_or_create_by_name(
                db,
                nombre=nombre,
                unidad_str=unidad_str,
                empaque_str=empaque_str,
                auto_create=False,
            )

            # Resolver unidad_medida_id
            u_obj = db.query(UnidadMedida).filter(
                or_(UnidadMedida.codigo == str(unidad_str).upper(), UnidadMedida.nombre.ilike(str(unidad_str)))
            ).first()
            # Resolver unidad_medida_id desde mapa en memoria
            u_key = str(unidad_str).strip().upper()
            u_obj = unidades_by_code.get(u_key) or unidades_by_name.get(u_key)

            # Resolver tipo_empaque_id
            emp_obj = None
            if empaque_str:
                emp_obj = db.query(TipoEmpaque).filter(
                    TipoEmpaque.nombre.ilike(str(empaque_str).strip())
                ).first()
            # Resolver tipo_empaque_id desde mapa en memoria
            emp_obj = empaques_by_name.get(str(empaque_str).strip().upper()) if empaque_str else None

            cant = float(prod_raw.get("cantidad") or prod_raw.get("kilos") or 1.0)
            kilos = float(prod_raw.get("peso_neto") or prod_raw.get("kilos") or cant)
            costo = float(prod_raw.get("costo_compra_kilo") or prod_raw.get("costo") or 0.0)
            venta = float(prod_raw.get("precio_venta_kilo") or prod_raw.get("venta") or 0.0)
            util = float(prod_raw.get("porcentaje_utilidad") or pedido.utilidad_global or 30.0)
            c_real = float(prod_raw.get("costo_real_kilo") or (costo + pedido.gasto_por_kilo))
            g_asig = float(prod_raw.get("gasto_asignado_kilo") or pedido.gasto_por_kilo)
            c_real = float(prod_raw.get("costo_real_kilo") or (costo + pedido_gasto_kilo))
            g_asig = float(prod_raw.get("gasto_asignado_kilo") or pedido_gasto_kilo)
            v_compra = float(prod_raw.get("valor_compra_total") or (costo * kilos))
            v_venta = float(prod_raw.get("valor_total_venta") or (venta * kilos))
            manual = bool(prod_raw.get("precio_venta_manual", False))

            raw_id = prod_raw.get("id")
            existing_item = None
            if raw_id is not None:
                try:
                    int_id = int(raw_id)
                    existing_item = existing_items.get(int_id)
                except (ValueError, TypeError):
                    pass

            notas_val = str(prod_raw.get("notas") or prod_raw.get("descripcion") or "").strip() or None
            if notas_val and (notas_val.upper() == nombre.upper() or notas_val.upper() == f"ÍTEM {idx + 1}"):
                notas_val = None

            if existing_item:
                if producto_obj:
                    existing_item.producto_id = producto_obj.id
                existing_item.producto_nombre = nombre
                existing_item.cantidad = cant
                if u_obj:
                    existing_item.unidad_medida_id = u_obj.id
                if emp_obj:
                    existing_item.tipo_empaque_id = emp_obj.id
                existing_item.precio_costo_unitario = costo
                existing_item.precio_venta_unitario = venta
                existing_item.peso_neto = kilos
                existing_item.porcentaje_utilidad = util
                existing_item.costo_real_kilo = c_real
                existing_item.gasto_asignado_kilo = g_asig
                existing_item.precio_venta_manual = manual
                existing_item.surtido = bool(prod_raw.get("surtido", False))
                existing_item.notas = notas_val
                existing_item.activo = True
                existing_item.orden = idx
                processed_ids.add(existing_item.id)
            else:
                new_item = PedidoItem(
                    pedido_id=pedido.id,
                    producto_id=producto_obj.id if producto_obj else None,
                    producto_nombre=nombre,
                    cantidad=cant,
                    unidad_medida_id=u_obj.id if u_obj else None,
                    tipo_empaque_id=emp_obj.id if emp_obj else None,
                    precio_costo_unitario=costo,
                    precio_venta_unitario=venta,
                    peso_neto=kilos,
                    porcentaje_utilidad=util,
                    costo_real_kilo=c_real,
                    gasto_asignado_kilo=g_asig,
                    precio_venta_manual=manual,
                    surtido=bool(prod_raw.get("surtido", False)),
                    notas=notas_val,
                    activo=True,
                    orden=idx,
                )
                db.add(new_item)

        # Política de Eliminación Cero (Soft Delete estricto): marcar inactivos los ítems que ya no vienen en la lista
        for item_id, item in existing_items.items():
            if item_id not in processed_ids:
                item.activo = False

    @classmethod
    def _sincronizar_gastos_relacionales(cls, db: Session, pedido: Pedido, gastos: List[Dict[str, Any]]):
        """
        Sincroniza los gastos relacionales en tabla pedido_gastos (3NF) de forma no destructiva (Upsert diferencial).
        """
        existing_gastos = {g.id: g for g in db.query(PedidoGasto).filter(PedidoGasto.pedido_id == pedido.id).all()}
        processed_ids = set()

        # Precarga en memoria de conceptos de gasto para evitar N+1 queries
        conceptos_list = db.query(ConceptoGasto).all()
        conceptos_map = {c.nombre.strip().upper(): c for c in conceptos_list if c.nombre}

        for idx, gasto_raw in enumerate(gastos or []):
            if not isinstance(gasto_raw, dict):
                continue

            concepto_str = gasto_raw.get("concepto") or gasto_raw.get("nombre") or f"Gasto {idx + 1}"
            monto = float(gasto_raw.get("monto") or gasto_raw.get("valor") or 0.0)
            distribuir = bool(gasto_raw.get("distribuir", gasto_raw.get("distribuir_en_costo", True)))

            concepto_obj = ConceptoGastoRepository.get_by_nombre(db, concepto_str)
            c_key = concepto_str.strip().upper()
            concepto_obj = conceptos_map.get(c_key)
            if not concepto_obj:
                concepto_obj = ConceptoGastoRepository.create(
                    db,
                    {"nombre": concepto_str, "tipo": "OPERATIVO", "distribuir_por_defecto": distribuir}
                )
                conceptos_map[c_key] = concepto_obj

            raw_id = gasto_raw.get("id")
            existing_gasto = None
            if raw_id is not None:
                try:
                    int_id = int(raw_id)
                    existing_gasto = existing_gastos.get(int_id)
                except (ValueError, TypeError):
                    pass

            if existing_gasto:
                existing_gasto.concepto_gasto_id = concepto_obj.id if concepto_obj else existing_gasto.concepto_gasto_id
                existing_gasto.descripcion = concepto_str
                existing_gasto.monto = monto
                existing_gasto.distribuir_en_costo = distribuir
                existing_gasto.activo = True
                processed_ids.add(existing_gasto.id)
            else:
                new_gasto = PedidoGasto(
                    pedido_id=pedido.id,
                    concepto_gasto_id=concepto_obj.id if concepto_obj else None,
                    descripcion=concepto_str,
                    monto=monto,
                    distribuir_en_costo=distribuir,
                    activo=True,
                )
                db.add(new_gasto)

        # Política de Eliminación Cero (Soft Delete estricto): marcar inactivos los gastos retirados
        for gasto_id, gasto in existing_gastos.items():
            if gasto_id not in processed_ids:
                gasto.activo = False

    @classmethod
    def cerrar_pedido(cls, db: Session, pedido_id: int, current_user: Usuario, request: Request) -> Pedido:
        pedido = db.query(Pedido).filter(Pedido.id == pedido_id).first()
        if not pedido:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido no encontrado")

        pedido.completado = True

        # Actualizar automáticamente precios de referencia en el catálogo de productos
        productos_actualizados = 0
        for item in pedido.items_activos:
            if item.producto_id and item.producto:
                costo_u = float(item.precio_costo_unitario or 0.0)
                venta_u = float(item.precio_venta_unitario or 0.0)
                if costo_u > 0:
                    item.producto.precio_costo_referencia = costo_u
                if venta_u > 0:
                    item.producto.precio_venta_referencia = venta_u
                productos_actualizados += 1

        db.commit()
        db.refresh(pedido)

        AuditoriaService.registrar_evento(
            db=db,
            accion="CERRAR_PEDIDO",
            modulo="PEDIDOS",
            usuario=current_user,
            entidad="Pedido",
            entidad_id=pedido.id,
            detalles={
                "numero_remision": pedido.numero_remision,
                "factura_cargada": pedido.factura_cargada,
                "remision_firmada_cargada": pedido.remision_firmada_cargada,
                "productos_referencia_actualizados": productos_actualizados,
            },
            request=request,
        )
        return pedido

    @classmethod
    def eliminar_pedido(cls, db: Session, pedido_id: int, current_user: Usuario, request: Request) -> Dict[str, Any]:
        pedido = db.query(Pedido).filter(Pedido.id == pedido_id, Pedido.activo == True).first()
        if not pedido:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido no encontrado o ya desactivado")

        pedido.activo = False
        db.commit()

        AuditoriaService.registrar_evento(
            db=db,
            accion="DESACTIVAR_PEDIDO_LOGICO",
            modulo="PEDIDOS",
            usuario=current_user,
            entidad="Pedido",
            entidad_id=pedido_id,
            detalles={
                "numero_remision": pedido.numero_remision,
                "cliente_id": pedido.cliente_id,
            },
            request=request,
        )
        return {"status": "ok", "message": f"Pedido {pedido.numero_remision} desactivado correctamente."}

    @classmethod
    async def subir_factura(
        cls,
        db: Session,
        pedido_id: int,
        file: UploadFile,
        current_user: Usuario,
        request: Request
    ) -> Dict[str, Any]:
        contents = await file.read()
        validate_file_upload(file, ALLOWED_CLOSURE_EXTENSIONS, header_bytes=contents[:16])

        pedido = db.query(Pedido).filter(Pedido.id == pedido_id).first()
        if not pedido:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido no encontrado")

        rel_path, clean_name = generate_secure_storage_path("facturas", file.filename)
        storage = get_storage_provider()
        await storage.save_file(rel_path, contents, content_type=file.content_type or "application/octet-stream")

        pedido.factura_cargada = True
        pedido.factura_archivo_path = rel_path
        pedido.factura_archivo_nombre = clean_name
        db.commit()
        db.refresh(pedido)

        AuditoriaService.registrar_evento(
            db=db,
            accion="SUBIR_FACTURA_PEDIDO",
            modulo="PEDIDOS",
            usuario=current_user,
            entidad="Pedido",
            entidad_id=pedido_id,
            detalles={
                "archivo": clean_name,
                "numero_remision": pedido.numero_remision,
            },
            request=request,
        )
        return {
            "status": "ok",
            "path": rel_path,
            "nombre": clean_name,
            "pedido": pedido,
        }

    @classmethod
    async def subir_remision_firmada(
        cls,
        db: Session,
        pedido_id: int,
        file: UploadFile,
        current_user: Usuario,
        request: Request
    ) -> Dict[str, Any]:
        contents = await file.read()
        validate_file_upload(file, ALLOWED_CLOSURE_EXTENSIONS, header_bytes=contents[:16])

        pedido = db.query(Pedido).filter(Pedido.id == pedido_id).first()
        if not pedido:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido no encontrado")

        rel_path, clean_name = generate_secure_storage_path("remisiones_firmadas", file.filename)
        storage = get_storage_provider()
        await storage.save_file(rel_path, contents, content_type=file.content_type or "application/octet-stream")

        pedido.remision_firmada_cargada = True
        pedido.remision_firmada_path = rel_path
        pedido.remision_firmada_nombre = clean_name
        db.commit()
        db.refresh(pedido)

        AuditoriaService.registrar_evento(
            db=db,
            accion="SUBIR_REMISION_FIRMADA",
            modulo="PEDIDOS",
            usuario=current_user,
            entidad="Pedido",
            entidad_id=pedido_id,
            detalles={
                "archivo": clean_name,
                "numero_remision": pedido.numero_remision,
            },
            request=request,
        )
        return {
            "status": "ok",
            "path": rel_path,
            "nombre": clean_name,
            "pedido": pedido,
        }
