from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class PermisosSchema(BaseModel):
    puede_crear_pedidos: Optional[bool] = True
    puede_editar_pedidos: Optional[bool] = True
    puede_desactivar_pedidos: Optional[bool] = False
    puede_cargar_documentos: Optional[bool] = True
    puede_cargar_facturas: Optional[bool] = True
    puede_cargar_remisiones_firmadas: Optional[bool] = True
    puede_gestionar_clientes: Optional[bool] = True
    puede_editar_empresa: Optional[bool] = False
    puede_ver_financiero: Optional[bool] = True
    puede_exportar: Optional[bool] = True


class UsuarioBase(BaseModel):
    username: str
    nombre_completo: str
    email: Optional[str] = None
    rol: Optional[str] = "operador"  # "admin" | "operador"
    permisos: Optional[Dict[str, Any]] = None


class UsuarioCreate(UsuarioBase):
    password: str


class UsuarioUpdate(BaseModel):
    nombre_completo: Optional[str] = None
    email: Optional[str] = None
    rol: Optional[str] = None
    permisos: Optional[Dict[str, Any]] = None
    activo: Optional[bool] = None


class UsuarioStatusUpdate(BaseModel):
    activo: bool


class ResetPasswordRequest(BaseModel):
    new_password: str


class UsuarioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    nombre_completo: str
    email: Optional[str] = None
    rol: str
    permisos: Dict[str, Any]
    activo: bool
    ultimo_login: Optional[datetime] = None
    creado_en: Optional[datetime] = None
    actualizado_en: Optional[datetime] = None
