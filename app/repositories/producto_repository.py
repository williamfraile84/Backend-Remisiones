import unicodedata
from typing import List, Optional, Dict, Any
from typing import List, Optional, Dict, Any, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import or_
from app.models.producto import Producto
from app.models.producto_empaque import ProductoEmpaque
from app.models.empaque import TipoEmpaque
from app.models.unidad_medida import UnidadMedida


def strip_accents(s: str) -> str:
    if not s:
        return ""
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    ).upper().strip()


class ProductoRepository:

    @staticmethod
    def get_all(
        db: Session,
        search: Optional[str] = None,
        categoria: Optional[str] = None,
        activo_only: bool = True
    ) -> List[Producto]:
        query = (
            db.query(Producto)
            .options(
                joinedload(Producto.unidad_medida),
                joinedload(Producto.tipo_empaque),
                selectinload(Producto.empaques_rel).joinedload(ProductoEmpaque.tipo_empaque),
            )
        )
        if activo_only:
            query = query.filter(Producto.activo == True)
        if categoria and categoria.strip():
            query = query.filter(Producto.categoria.ilike(categoria.strip()))
        if search and search.strip():
            term = f"%{search.strip().upper()}%"
            query = query.filter(
                or_(
                    Producto.nombre.ilike(term),
                    Producto.codigo.ilike(term),
                    Producto.categoria.ilike(term),
                )
            )
        return query.order_by(Producto.nombre.asc()).all()

    @staticmethod
    def get_by_id(db: Session, producto_id: int) -> Optional[Producto]:
        return (
            db.query(Producto)
            .options(
                joinedload(Producto.unidad_medida),
                joinedload(Producto.tipo_empaque),
                selectinload(Producto.empaques_rel).joinedload(ProductoEmpaque.tipo_empaque),
            )
            .filter(Producto.id == producto_id)
            .first()
        )

    _cached_index: Optional[List[Tuple[int, str, str]]] = None

    @classmethod
    def invalidate_cache(cls):
        cls._cached_index = None

    @classmethod
    def _get_catalog_index(cls, db: Session) -> List[Tuple[int, str, str]]:
        if cls._cached_index is None:
            rows = db.query(Producto.id, Producto.nombre).filter(Producto.activo == True).all()
            cls._cached_index = [(r[0], r[1], strip_accents(r[1])) for r in rows if r[1]]
        return cls._cached_index

    @classmethod
    def get_by_nombre(cls, db: Session, nombre: str) -> Optional[Producto]:
        clean = (nombre or "").strip().upper()
        if not clean:
            return None

        exact = (
            db.query(Producto)
            .options(
                joinedload(Producto.unidad_medida),
                joinedload(Producto.tipo_empaque),
                selectinload(Producto.empaques_rel).joinedload(ProductoEmpaque.tipo_empaque),
            )
            .filter(Producto.nombre.ilike(clean), Producto.activo == True)
            .first()
        )
        if exact:
            return exact

        norm_target = strip_accents(clean)
        index = cls._get_catalog_index(db)
        for pid, pnombre, pnorm in index:
            if pnorm == norm_target:
                return cls.get_by_id(db, pid)
        return None

    @classmethod
    def create(
        cls,
        db: Session,
        data: Dict[str, Any],
        empaque_ids: Optional[List[int]] = None,
        empaques_config: Optional[List[Dict[str, Any]]] = None,
    ) -> Producto:
        nombre = data.get("nombre", "").strip().upper()
        if not nombre:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El nombre del producto es obligatorio."
            )

        # Validación estricta anti-duplicados en catálogo
        existente = db.query(Producto).filter(Producto.nombre.ilike(nombre), Producto.activo == True).first()
        if existente:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ya existe un producto registrado como '{existente.nombre}' en el catálogo maestro."
            )

        producto = Producto(
            empresa_id=data.get("empresa_id"),
            codigo=data.get("codigo"),
            pos_item_id=str(data.get("pos_item_id")).strip() if data.get("pos_item_id") else None,
            precio_pos_actual=float(data.get("precio_pos_actual") or 0.0),
            nombre=nombre,
            categoria=(data.get("categoria") or "").strip().upper() or None,
            unidad_medida_id=data.get("unidad_medida_id"),
            tipo_empaque_id=data.get("tipo_empaque_id"),
            precio_costo_referencia=float(data.get("precio_costo_referencia") or 0.0),
            precio_venta_referencia=float(data.get("precio_venta_referencia") or 0.0),
            merma_esperada_pct=float(data.get("merma_esperada_pct") or 0.0),
            activo=data.get("activo", True),
        )

        if empaques_config is not None:
            producto.empaques_permitidos = empaques_config
        elif empaque_ids:
            producto.empaques_permitidos = empaque_ids

        db.add(producto)
        db.commit()
        db.refresh(producto)
        cls.invalidate_cache()
        return producto

    @classmethod
    def update(
        cls,
        db: Session,
        producto_id: int,
        data: Dict[str, Any],
        empaque_ids: Optional[List[int]] = None,
        empaques_config: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Producto]:
        producto = db.query(Producto).filter(Producto.id == producto_id).first()
        if not producto:
            return None

        for k, v in data.items():
            if v is not None:
                if k == "nombre":
                    v = v.strip().upper()
                setattr(producto, k, v)

        if empaques_config is not None:
            producto.empaques_permitidos = empaques_config
        elif empaque_ids is not None:
            producto.empaques_permitidos = empaque_ids

        db.commit()
        db.refresh(producto)
        cls.invalidate_cache()
        return producto

    @classmethod
    def delete(cls, db: Session, producto_id: int) -> bool:
        producto = db.query(Producto).filter(Producto.id == producto_id).first()
        if not producto:
            return False
        producto.activo = False
        db.commit()
        cls.invalidate_cache()
        return True

    @classmethod
    def batch_update_empaques(
        cls,
        db: Session,
        items: List[Dict[str, Any]],
    ) -> int:
        count = 0
        for item in items:
            pid = item.get("producto_id")
            if not pid:
                continue
            producto = db.query(Producto).filter(Producto.id == pid).first()
            if not producto:
                continue

            if "tipo_empaque_id" in item:
                producto.tipo_empaque_id = item["tipo_empaque_id"]

            if "empaques_config" in item and item["empaques_config"] is not None:
                producto.empaques_permitidos = item["empaques_config"]

            count += 1

        if count > 0:
            db.commit()
            cls.invalidate_cache()

        return count

    @classmethod
    def find_by_name_or_similarity(
        cls,
        db: Session,
        nombre: str
    ) -> Optional[Producto]:
        """
        Busca un producto por coincidencia exacta o prefijo en el catálogo maestro.
        NO crea productos nuevos automáticamente para prevenir errores ortográficos de digitación.
        """
        clean_name = (nombre or "").strip().upper()
        if not clean_name:
            return None

        # 1. Búsqueda exacta o unaccent
        existente = cls.get_by_nombre(db, clean_name)
        if existente:
            return existente

        # 2. Búsqueda por prefijo directo
        prefijo = db.query(Producto).filter(Producto.nombre.ilike(f"{clean_name}%"), Producto.activo == True).first()
        if prefijo:
            return prefijo

        # 3. Búsqueda por prefijo / inclusión insensible a acentos usando índice liviano
        norm_target = strip_accents(clean_name)
        index = cls._get_catalog_index(db)
        for pid, pnombre, pnorm in index:
            if pnorm.startswith(norm_target) or norm_target.startswith(pnorm):
                return cls.get_by_id(db, pid)

        return None

    @classmethod
    def find_or_create_by_name(
        cls,
        db: Session,
        nombre: str,
        unidad_str: Optional[str] = None,
        empaque_str: Optional[str] = None,
        auto_create: bool = True
    ) -> Optional[Producto]:
        """
        Busca un producto en el catálogo maestro. Si no existe y auto_create=True, lo crea.
        """
        encontrado = cls.find_by_name_or_similarity(db, nombre)
        if encontrado or not auto_create:
            return encontrado

        clean_name = (nombre or "").strip().upper()
        if not clean_name:
            return None

        # Resolver unidad de medida si se especificó
        unidad_id = None
        if unidad_str:
            u_clean = unidad_str.strip().upper()
            u_obj = db.query(UnidadMedida).filter(
                or_(UnidadMedida.codigo == u_clean, UnidadMedida.nombre.ilike(u_clean))
            ).first()
            if u_obj:
                unidad_id = u_obj.id

        # Resolver tipo de empaque si se especificó
        empaque_id = None
        if empaque_str:
            emp_clean = empaque_str.strip().upper()
            emp_obj = db.query(TipoEmpaque).filter(TipoEmpaque.nombre.ilike(emp_clean)).first()
            if emp_obj:
                empaque_id = emp_obj.id

        nuevo = Producto(
            nombre=clean_name,
            unidad_medida_id=unidad_id,
            tipo_empaque_id=empaque_id,
            activo=True
        )
        db.add(nuevo)
        db.commit()
        db.refresh(nuevo)
        cls.invalidate_cache()
        return nuevo

    @classmethod
    def seed_massive_catalog(cls, db: Session, custom_path: Optional[str] = None) -> int:
        """
        Siembra el catálogo masivo y exhaustivo de productos (más de 300 referencias tradicionales y exóticas).
        Permite cargar desde un archivo JSON o CSV externo configurable en .env (SEED_CATALOG_CUSTOM_PATH)
        o desde el catálogo maestro incorporado. Es completamente idempotente.
        """
        import os
        from app.models.empresa import Empresa

        catalog_data = []
        if custom_path and os.path.isfile(custom_path):
            try:
                if custom_path.endswith(".json"):
                    import json
                    with open(custom_path, "r", encoding="utf-8") as f:
                        catalog_data = json.load(f)
                elif custom_path.endswith(".csv"):
                    import csv
                    with open(custom_path, "r", encoding="utf-8") as f:
                        reader = csv.DictReader(f)
                        catalog_data = list(reader)
            except Exception as e:
                logger.warning(f"No se pudo cargar el catálogo personalizado desde {custom_path}: {e}")

        if not catalog_data:
            from app.core.seeds.catalog_seed import CATALOGO_PRODUCTOS_EXTENSO
            catalog_data = CATALOGO_PRODUCTOS_EXTENSO

        # Precargar unidades de medida y tipos de empaque para resolución rápida en memoria
        unidades_map = {u.codigo.upper(): u.id for u in db.query(UnidadMedida).all()}
        tipos_empaque_map = {t.nombre.upper(): t.id for t in db.query(TipoEmpaque).all()}
        productos_existentes = {p.nombre.upper(): p for p in db.query(Producto).all()}
        empresa_default = db.query(Empresa).first()
        empresa_id = empresa_default.id if empresa_default else None

        nuevos = []
        for item in catalog_data:
            nombre_clean = str(item.get("nombre", "")).strip().upper()
            if not nombre_clean or nombre_clean in productos_existentes:
                continue

            u_id = unidades_map.get(str(item.get("unidad", "KG")).upper())
            t_id = tipos_empaque_map.get(str(item.get("empaque", "")).upper())

            prod = Producto(
                nombre=nombre_clean,
                categoria=item.get("categoria"),
                codigo=item.get("codigo"),
                pos_item_id=str(item.get("pos_item_id")).strip() if item.get("pos_item_id") else None,
                precio_pos_actual=float(item.get("precio_pos_actual") or item.get("venta") or 0.0),
                empresa_id=empresa_id,
                precio_costo_referencia=float(item.get("costo") or 0.0),
                precio_venta_referencia=float(item.get("venta") or 0.0),
                merma_esperada_pct=float(item.get("merma") or 0.0),
                unidad_medida_id=u_id,
                tipo_empaque_id=t_id,
                activo=True,
            )
            nuevos.append(prod)
            productos_existentes[nombre_clean] = prod

        if nuevos:
            db.add_all(nuevos)
            db.commit()
            cls.invalidate_cache()

        return len(nuevos)

    @classmethod
    def seed_catalog_if_empty(cls, db: Session) -> int:
        """
        Siembra el catálogo en el primer arranque si está habilitado en .env (AUTO_SEED_MASSIVE_PRODUCTS=true)
        y la cantidad de productos actuales es menor al umbral (SEED_PRODUCTS_MIN_THRESHOLD).
        """
        from app.core.config import settings

        if not settings.AUTO_SEED_MASSIVE_PRODUCTS:
            return 0

        total = db.query(Producto).count()
        threshold = settings.SEED_PRODUCTS_MIN_THRESHOLD
        if total < threshold:
            return cls.seed_massive_catalog(db, custom_path=settings.SEED_CATALOG_CUSTOM_PATH)
        return 0

