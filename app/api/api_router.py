from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth, usuarios, roles, auditoria, empresa, clientes,
    pedidos, exportaciones, empaques, unidades_medida, conceptos_gasto,
    productos, pos
)

api_router = APIRouter()

# Registrar submódulos de seguridad y administración
api_router.include_router(auth.router)
api_router.include_router(usuarios.router)
api_router.include_router(roles.router)
api_router.include_router(auditoria.router)

# Registrar submódulos operativos del sistema Fruver
api_router.include_router(empresa.router)
api_router.include_router(clientes.router)
api_router.include_router(pedidos.router)
api_router.include_router(empaques.router)
api_router.include_router(unidades_medida.router)
api_router.include_router(conceptos_gasto.router)
api_router.include_router(productos.router)
api_router.include_router(pos.router)

# Soporte para ambas rutas de exportación: /api/pedidos/exportar/* y /api/exportar/*
api_router.include_router(exportaciones.router, prefix="/pedidos")
api_router.include_router(exportaciones.router)