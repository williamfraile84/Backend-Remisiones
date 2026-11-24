from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.modulo import Modulo


DEFAULT_MODULOS = [
    {"codigo": "PEDIDOS", "nombre": "Gestión de Pedidos", "descripcion": "Creación, edición y control de pedidos y remisiones"},
    {"codigo": "CLIENTES", "nombre": "Clientes", "descripcion": "Directorio y administración de clientes"},
    {"codigo": "CATALOGO", "nombre": "Catálogo de Productos", "descripcion": "Maestro de productos, precios y referencias fruver"},
    {"codigo": "EMPAQUES", "nombre": "Empaques y Medidas", "descripcion": "Unidades de medida y tipos de empaque estandarizados"},
    {"codigo": "GASTOS", "nombre": "Gastos Operativos", "descripcion": "Conceptos y registro de gastos operacionales y fletes"},
    {"codigo": "FINANCIERO", "nombre": "Módulo Financiero", "descripcion": "Costeo, liquidación y márgenes de rentabilidad"},
    {"codigo": "DOCUMENTOS", "nombre": "Gestión Documental", "descripcion": "Cargue de facturas y remisiones firmadas"},
    {"codigo": "EMPRESA", "nombre": "Configuración de Empresa", "descripcion": "Datos institucionales y perfil corporativo"},
    {"codigo": "SEGURIDAD", "nombre": "Usuarios y Seguridad", "descripcion": "Gestión de usuarios, roles y permisos de acceso"},
    {"codigo": "AUDITORIA", "nombre": "Auditoría del Sistema", "descripcion": "Pista de auditoría e historial de cambios"},
]


class ModuloRepository:
    """
    Repositorio atómico para gestión de módulos del sistema (SRP).
    """

    @staticmethod
    def get_all(db: Session, activo_only: bool = True) -> List[Modulo]:
        query = db.query(Modulo)
        if activo_only:
            query = query.filter(Modulo.activo == True)
        return query.order_by(Modulo.nombre.asc()).all()

    @staticmethod
    def get_by_id(db: Session, modulo_id: int) -> Optional[Modulo]:
        return db.query(Modulo).filter(Modulo.id == modulo_id).first()

    @staticmethod
    def get_by_codigo(db: Session, codigo: str) -> Optional[Modulo]:
        clean = (codigo or "").strip().upper()
        return db.query(Modulo).filter(Modulo.codigo == clean).first()

    @staticmethod
    def find_or_create(db: Session, codigo: str, nombre: Optional[str] = None, descripcion: Optional[str] = None) -> Modulo:
        clean = (codigo or "").strip().upper()
        existente = db.query(Modulo).filter(Modulo.codigo == clean).first()
        if existente:
            return existente
        return ModuloRepository.create(db, {
            "codigo": clean,
            "nombre": nombre or clean.title(),
            "descripcion": descripcion,
            "activo": True
        })

    @staticmethod
    def create(db: Session, data: Dict[str, Any]) -> Modulo:
        data_clean = data.copy()
        data_clean["codigo"] = str(data_clean.get("codigo", "")).strip().upper()
        modulo = Modulo(**data_clean)
        db.add(modulo)
        db.commit()
        db.refresh(modulo)
        return modulo

    @staticmethod
    def seed_default_modulos(db: Session) -> int:
        """Siembra los módulos iniciales del sistema si no existen."""
        existentes = {m.codigo: m for m in db.query(Modulo).all()}
        nuevos = []
        for mod_data in DEFAULT_MODULOS:
            if mod_data["codigo"] not in existentes:
                nuevos.append(Modulo(**mod_data))
        if nuevos:
            db.add_all(nuevos)
            db.commit()
        return len(nuevos)

