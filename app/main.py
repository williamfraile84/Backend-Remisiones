import os
import time
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from app.core.config import settings
from app.core.logging_config import setup_logging
from app.core.database import Base, engine, SessionLocal
import app.models  # Asegura registro de todos los modelos relacionales en Base.metadata
from app.core.security import get_file_media_type
from app.api.api_router import api_router
from app.services.auth_service import AuthService
from app.services.migration_service import DatabaseMigrationService
from app.services.storage_migration_service import StorageMigrationService
from app.services.storage.storage_factory import get_storage_provider
from app.repositories.unidad_medida_repository import UnidadMedidaRepository
from app.repositories.concepto_gasto_repository import ConceptoGastoRepository
from app.repositories.empaque_repository import EmpaqueRepository
from app.repositories.producto_repository import ProductoRepository

# Inicializar logging
logger = setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # En modo de pruebas unitarias/integración, omitir migraciones y calentamiento de modelos
    is_testing = os.getenv("TESTING", "").lower() in ("1", "true") or settings.APP_ENV == "testing"
    if is_testing:
        yield
        return

    # 1. Crear tablas en el motor activo con reintentos para conexiones remotas / poolers
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("Tablas de base de datos verificadas/creadas exitosamente.")
            break
        except Exception as db_init_err:
            if attempt < max_retries:
                logger.warning(
                    f"Intento {attempt}/{max_retries} al verificar tablas falló ({db_init_err}). Reintentando en 2s..."
                )
                time.sleep(2)
            else:
                logger.error(
                    f"Error crítico al verificar tablas en base de datos tras {max_retries} intentos: {db_init_err}"
                )

    # 2. Migración automática de base de datos opcional (si AUTO_MIGRATE_DB=True)
    if settings.AUTO_MIGRATE_DB:
        logger.info("Iniciando migración automática de base de datos (AUTO_MIGRATE_DB=True)...")
        migration_res = DatabaseMigrationService.run_auto_migration_if_enabled()
        if migration_res.get("success"):
            logger.info(f"Migración de BD completada con éxito: {migration_res.get('records_migrated')}")
        else:
            logger.error(f"Fallo en la migración de BD: {migration_res.get('error')}")

    # 2. Migración automática de archivos de storage opcional (si AUTO_MIGRATE_STORAGE=True)
    if settings.AUTO_MIGRATE_STORAGE:
        logger.info("Iniciando migración automática de almacenamiento (AUTO_MIGRATE_STORAGE=True)...")
        storage_res = StorageMigrationService.run_auto_storage_migration_if_enabled()
        if storage_res.get("success"):
            logger.info(f"Migración de Storage completada con éxito: {storage_res.get('stats')}")
        else:
            logger.error(f"Fallo en la migración de Storage: {storage_res.get('error')}")

    # 3. Garantizar catálogos iniciales y administrador al arrancar (con reintentos)
    for attempt in range(1, max_retries + 1):
        try:
            with SessionLocal() as db:
                AuthService.asegurar_admin_inicial(db)

                if settings.AUTO_SEED_CATALOGS:
                    UnidadMedidaRepository.seed_default_units_if_empty(db)
                    ConceptoGastoRepository.seed_default_concepts_if_empty(db)
                    EmpaqueRepository.seed_default_tipos_if_empty(db)

                if settings.AUTO_SEED_MASSIVE_PRODUCTS:
                    ProductoRepository.seed_catalog_if_empty(db)

                DatabaseMigrationService.normalize_existing_pedidos_to_relational(db)
                DatabaseMigrationService.auto_link_3nf_relations(db)
            logger.info("Catálogos, relaciones 3NF y usuario administrador verificados exitosamente.")
            break
        except Exception as seed_err:
            if attempt < max_retries:
                logger.warning(
                    f"Intento {attempt}/{max_retries} al sembrar catálogos falló ({seed_err}). Reintentando en 2s..."
                )
                time.sleep(2)
            else:
                logger.error(f"Aviso al sembrar catálogos iniciales tras {max_retries} intentos: {seed_err}")

    logger.info(f"Sistema Backend listo.")
    logger.info(f"Base de Datos conectada: [{engine.dialect.name.upper()}] {settings.mask_database_url()}")
    logger.info(f"Storage de Archivos: [{settings.effective_storage_provider.upper()}]")
    yield


app = FastAPI(
    title="Sistema de Gestión de Pedidos y Remisiones",
    version="2.2.0",
    lifespan=lifespan,
)

# Middleware de Cabeceras de Seguridad y Protección de Recursos
@app.middleware("http")
async def add_security_and_performance_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(self), microphone=()"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    GZipMiddleware,
    minimum_size=1000,
)

# Enrutador centralizado unificado
app.include_router(api_router, prefix="/api")


@app.get("/health", tags=["Salud"])
@app.get("/api/health", include_in_schema=False)
async def health_check():
    return {
        "status": "healthy",
        "system": "Orders & Logistics API",
        "app_env": settings.APP_ENV,
        "version": "2.2.0",
        "port": getattr(settings, "SERVER_PORT", getattr(settings, "API_PORT", 8001)),
        "db_engine": engine.dialect.name,
        "storage_provider": settings.effective_storage_provider,
        "default_margin": settings.DEFAULT_PROFIT_MARGIN
    }


@app.get("/storage_data/{file_path:path}")
@app.get("/api/storage/{file_path:path}")
async def serve_storage_file(file_path: str):
    """
    Ruta universal para servir archivos desde cualquier proveedor
    (Local, S3 / Supabase Storage, Google Drive, File Server) con soporte para imágenes, PDFs y streaming.
    """
    clean_path = file_path.replace("\\", "/").lstrip("/")
    storage = get_storage_provider()

    # 1. Si existe en el proveedor activo (S3 / Supabase / etc.), servirlo
    if await storage.file_exists(clean_path):
        return storage.get_response(clean_path, inline=True)

    # 2. Fallback a disco local si aún no se ha sincronizado a la nube
    local_path = os.path.normpath(os.path.join(settings.STORAGE_BASE_DIR, clean_path))
    abs_base = os.path.abspath(settings.STORAGE_BASE_DIR)
    abs_local = os.path.abspath(local_path)
    if not abs_local.startswith(abs_base):
        raise HTTPException(status_code=403, detail="Acceso denegado: ruta de archivo no autorizada.")

    if os.path.isfile(local_path):
        media_type = get_file_media_type(local_path)
        return FileResponse(local_path, media_type=media_type)

    raise HTTPException(status_code=404, detail=f"Archivo '{clean_path}' no encontrado en almacenamiento.")


# ==============================================================================
# Endpoint de Información y Estado del API (para monitoreo, scripts y túneles)
# ==============================================================================
@app.get("/api", tags=["Sistema"])
@app.get("/api/v1", include_in_schema=False)
def api_info():
    return {
        "status": "online",
        "system": "Orders & Logistics API",
        "version": "2.2.0",
        "database": {
            "engine": engine.dialect.name,
            "target": settings.mask_database_url(),
            "nullpool": settings.DB_USE_NULLPOOL
        },
        "storage_provider": settings.effective_storage_provider
    }


# ==============================================================================
# Servir Frontend SPA (Single Page Application) con fallback para rutas cliente
# ==============================================================================
env_dist = os.getenv("FRONTEND_DIST_DIR")
possible_dist_dirs = [
    Path(env_dist) if env_dist else None,
    Path(__file__).resolve().parent.parent.parent / "frontend" / "dist",
    Path(__file__).resolve().parent.parent / "frontend" / "dist",
    Path(__file__).resolve().parent.parent / "dist",
]
frontend_dist = next((p for p in possible_dist_dirs if p and (p / "index.html").is_file()), None)

if frontend_dist and frontend_dist.exists():
    assets_dir = frontend_dist / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/", include_in_schema=False)
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa_frontend(request: Request, full_path: str = ""):
        # Omitir rutas de API, docs, OpenAPI, storage o health que deban ser 404 si no existen
        if (
            full_path.startswith("api/")
            or full_path == "api"
            or full_path.startswith("docs")
            or full_path.startswith("openapi")
            or full_path.startswith("health")
            or full_path.startswith("storage_data/")
        ):
            raise HTTPException(status_code=404, detail="Not Found")

        req_origin = request.headers.get("origin")
        cors_headers = {
            "Access-Control-Allow-Origin": req_origin if req_origin else "*",
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }

        # Si el archivo exacto existe en dist (ej. favicon.svg, manifest.json, sw.js, iconos)
        target_file = frontend_dist / full_path
        if full_path and target_file.is_file():
            if full_path == "sw.js":
                return FileResponse(
                    target_file,
                    media_type="application/javascript",
                    headers={
                        "Cache-Control": "no-cache, no-store, must-revalidate",
                        "Pragma": "no-cache",
                        "Expires": "0",
                        "Service-Worker-Allowed": "/",
                        **cors_headers,
                    },
                )
            if full_path in ("manifest.json", "manifest.webmanifest"):
                return FileResponse(
                    target_file,
                    media_type="application/manifest+json",
                    headers={
                        "Cache-Control": "no-cache, no-store, must-revalidate",
                        "Pragma": "no-cache",
                        "Expires": "0",
                        **cors_headers,
                    },
                )
            if full_path == "index.html" or full_path.endswith(".html"):
                return FileResponse(
                    target_file,
                    media_type="text/html",
                    headers={
                        "Cache-Control": "no-cache, no-store, must-revalidate",
                        "Pragma": "no-cache",
                        "Expires": "0",
                        **cors_headers,
                    },
                )
            return FileResponse(target_file, headers=cors_headers)

        # Fallback a index.html para react-router con no-cache estricto para evitar bloqueos de versiones antiguas
        index_file = frontend_dist / "index.html"
        if index_file.is_file():
            return FileResponse(
                index_file,
                media_type="text/html",
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0",
                    **cors_headers,
                },
            )

        raise HTTPException(status_code=404, detail="Frontend index.html no disponible")

else:
    @app.get("/")
    def root():
        return {
            "status": "online",
            "system": "Orders & Logistics API",
            "version": "2.2.0",
            "database": {
                "engine": engine.dialect.name,
                "target": settings.mask_database_url(),
                "nullpool": settings.DB_USE_NULLPOOL
            },
            "storage_provider": settings.effective_storage_provider,
            "notice": "Frontend SPA no compilado o dist no encontrado. Ejecute 'npm run build' en frontend."
        }


if __name__ == "__main__":
    import uvicorn
    port = getattr(settings, "SERVER_PORT", getattr(settings, "API_PORT", 8001))
    host = getattr(settings, "SERVER_HOST", "0.0.0.0")
    uvicorn.run("app.main:app", host=host, port=port, reload=True)