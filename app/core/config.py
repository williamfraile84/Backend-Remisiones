import os
import urllib.parse
from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

# Ruta absoluta al archivo .env dentro de backend
BASE_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE_PATH = str(BASE_BACKEND_DIR / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=[ENV_FILE_PATH, ".env"],
        env_file_encoding="utf-8",
        extra="allow"
    )

    APP_ENV: str = "production"
    API_PORT: int = 8001
    SERVER_PORT: int = 8001
    SERVER_HOST: str = "0.0.0.0"
    
    # Base de Datos Agnóstica (PostgreSQL / Supabase, SQLite, MySQL, Oracle, etc.)
    DATABASE_URL: Optional[str] = None
    
    # Parámetros desglosados (facilitan el manejo de contraseñas con caracteres especiales)
    DB_ENGINE: Optional[str] = "sqlite"  # "sqlite", "postgresql", "mysql", "oracle"
    DB_USER: Optional[str] = None
    DB_PASSWORD: Optional[str] = None
    DB_HOST: Optional[str] = None
    DB_PORT: Optional[int] = None
    DB_NAME: Optional[str] = None
    DB_SSLMODE: Optional[str] = None     # "require", "prefer", "disable"
    DB_USE_NULLPOOL: bool = False       # Recomendado para Supabase Pooler (Transaction/Session Pooler)
    
    # Parámetros de Migración de Base de Datos
    AUTO_MIGRATE_DB: bool = False        # Si es True, migra automáticamente en el arranque
    MIGRATE_SOURCE_URL: Optional[str] = None  # URL de origen (ej: sqlite:///./storage_data/app.db)
    MIGRATE_TARGET_URL: Optional[str] = None  # URL de destino (si está vacía, usa la base activa)
    MIGRATE_RESET_DESTINATION: bool = False   # Si es True, limpia las tablas de destino antes de migrar
    
    # Proveedor de Almacenamiento ("local", "s3", "supabase", "google_drive", "file_server")
    STORAGE_PROVIDER: str = "local"
    STORAGE_TYPE: Optional[str] = None  # Alias retrocompatible para STORAGE_PROVIDER
    STORAGE_BASE_DIR: str = "./storage_data"
    
    # Parámetros para S3 / Supabase Storage / Cloudflare R2 / AWS S3 / MinIO
    S3_ENDPOINT_URL: Optional[str] = None  # Ej: https://hlimidkqudamudntxfif.storage.supabase.co/storage/v1/s3
    S3_REGION_NAME: Optional[str] = "ca-central-1"
    S3_ACCESS_KEY_ID: Optional[str] = None
    S3_SECRET_ACCESS_KEY: Optional[str] = None
    S3_BUCKET_NAME: str = "app-storage"
    S3_USE_SSL: bool = True
    S3_PUBLIC_URL_PREFIX: Optional[str] = None
    S3_PRESIGNED_EXPIRATION_SECONDS: int = 3600
    
    # Parámetros de Migración / Sincronización de Archivos entre Proveedores
    AUTO_MIGRATE_STORAGE: bool = False
    MIGRATE_STORAGE_SOURCE: Optional[str] = "local"
    MIGRATE_STORAGE_TARGET: Optional[str] = None
    MIGRATE_STORAGE_OVERWRITE: bool = False
    
    # Parámetros para Google Drive Storage Provider
    GOOGLE_DRIVE_FOLDER_ID: Optional[str] = None
    GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE: Optional[str] = None
    GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON: Optional[str] = None
    
    # Parámetros para Remote File Server Storage Provider
    FILE_SERVER_URL: Optional[str] = None
    FILE_SERVER_API_KEY: Optional[str] = None

    CORS_ORIGINS: List[str] = ["*"]
    JWT_SECRET: str = "app-super-secure-jwt-secret-key-2026"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 horas
    SESSION_INACTIVITY_TIMEOUT_MINUTES: Optional[int] = None  # Minutos de inactividad antes de expirar (opcional)
    ENFORCE_DB_SESSION_VALIDATION: bool = True  # Valida estado activo de sesión en DB con cada petición

    # Parámetros de Negocio y Finanzas
    DEFAULT_PROFIT_MARGIN: float = 30.0

    # Límites de Archivo y Seguridad
    MAX_FILE_SIZE_MB: int = 15
    ALLOWED_DOC_EXTENSIONS: str = ".pdf,.png,.jpg,.jpeg,.webp,.xlsx,.xls"
    ALLOWED_CLOSURE_EXTENSIONS: str = ".pdf,.png,.jpg,.jpeg,.webp"

    # Usuario Administrador Inicial
    INITIAL_ADMIN_USERNAME: str = "admin"
    INITIAL_ADMIN_PASSWORD: str = "admin"
    INITIAL_ADMIN_NAME: str = "Administrador Principal"
    INITIAL_ADMIN_EMAIL: str = "admin@empresa.com"

    # Catálogos Iniciales y Auto-Siembra
    AUTO_SEED_CATALOGS: bool = True
    AUTO_SEED_MASSIVE_PRODUCTS: bool = True
    SEED_PRODUCTS_MIN_THRESHOLD: int = 50
    SEED_CATALOG_CUSTOM_PATH: Optional[str] = None

    # Integración con Sistema POS Externo (csopos.co / softwarepos.online)
    POS_PRIMARY_URL: str = "https://csopos.co/"
    POS_SECONDARY_URL: str = "https://softwarepos.online/"
    POS_USER: str = "inventario"
    POS_PASS: str = "inventario"
    POS_STORE: str = "yanuba"
    POS_REGISTER_NUM: int = 1
    POS_HEADLESS: bool = True

    # Parámetros de Procesamiento de Visión Multimodal (Gemini) y Documentos
    VISION_PROVIDER: str = "gemini"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    VISION_MAX_IMAGE_DIMENSION: int = 1600
    VISION_PDF_DPI: int = 150
    # Compatibilidad retroactiva
    OCR_MAX_IMAGE_DIMENSION: int = 1600
    OCR_PDF_DPI: int = 150

    @property
    def effective_database_url(self) -> str:
        """
        Construye la URL de conexión a la base de datos según las variables de entorno.
        Prioridad:
        1. DATABASE_URL explícita (si está definida y no vacía).
        2. Construcción dinámica a partir de DB_ENGINE, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME.
        3. Fallback a SQLite local.
        """
        if self.DATABASE_URL and self.DATABASE_URL.strip():
            url = self.DATABASE_URL.strip()
            if url.startswith("postgres://"):
                url = "postgresql+psycopg2://" + url[len("postgres://"):]
            elif url.startswith("postgresql://") and not url.startswith("postgresql+"):
                url = "postgresql+psycopg2://" + url[len("postgresql://"):]
            return url

        engine_type = (self.DB_ENGINE or "sqlite").lower().strip()
        
        if engine_type == "sqlite":
            if self.DB_NAME and self.DB_NAME.strip() and not self.DB_NAME.strip().startswith(":"):
                db_p = Path(self.DB_NAME.strip())
                if not db_p.is_absolute():
                    db_p = (BASE_BACKEND_DIR / db_p).resolve()
                db_p.parent.mkdir(parents=True, exist_ok=True)
                db_file = str(db_p)
            else:
                db_file = self.DB_NAME or ":memory:"
            return f"sqlite:///{db_file}"
        
        user_enc = urllib.parse.quote_plus(self.DB_USER) if self.DB_USER else ""
        pass_enc = urllib.parse.quote_plus(self.DB_PASSWORD) if self.DB_PASSWORD else ""
        auth = f"{user_enc}:{pass_enc}@" if (user_enc or pass_enc) else ""
        host = self.DB_HOST or "localhost"
        
        if engine_type in ("postgresql", "postgres", "supabase"):
            port = self.DB_PORT or 5432
            db = self.DB_NAME or "postgres"
            query_params = []
            if self.DB_SSLMODE:
                query_params.append(f"sslmode={self.DB_SSLMODE}")
            query = f"?{'&'.join(query_params)}" if query_params else ""
            return f"postgresql+psycopg2://{auth}{host}:{port}/{db}{query}"
            
        if engine_type in ("mysql", "mariadb"):
            port = self.DB_PORT or 3306
            db = self.DB_NAME or "app_db"
            return f"mysql+pymysql://{auth}{host}:{port}/{db}"

        if engine_type == "oracle":
            port = self.DB_PORT or 1521
            db = self.DB_NAME or "ORCL"
            return f"oracle+oracledb://{auth}{host}:{port}/?service_name={db}"

        port_str = f":{self.DB_PORT}" if self.DB_PORT else ""
        db_str = f"/{self.DB_NAME}" if self.DB_NAME else ""
        return f"{engine_type}://{auth}{host}{port_str}{db_str}"

    def mask_url(self, url: str) -> str:
        """Oculta la contraseña en cualquier URL para impresión segura."""
        if not url:
            return ""
        if "@" in url and "://" in url:
            prefix, rest = url.split("://", 1)
            auth, host_part = rest.split("@", 1)
            if ":" in auth:
                user, _ = auth.split(":", 1)
                return f"{prefix}://{user}:******@{host_part}"
            return f"{prefix}://******@{host_part}"
        return url

    def mask_database_url(self) -> str:
        """Retorna la URL activa con la contraseña oculta para registros seguros en logs."""
        return self.mask_url(self.effective_database_url)

    @property
    def effective_migrate_source_url(self) -> str:
        """Retorna la URL de origen para migración."""
        if self.MIGRATE_SOURCE_URL and self.MIGRATE_SOURCE_URL.strip():
            url = self.MIGRATE_SOURCE_URL.strip()
            if url.startswith("postgres://"):
                url = "postgresql+psycopg2://" + url[len("postgres://"):]
            elif url.startswith("postgresql://") and not url.startswith("postgresql+"):
                url = "postgresql+psycopg2://" + url[len("postgresql://"):]
            return url
        # Fallback predeterminado a SQLite local
        return "sqlite:///./storage_data/app.db"

    @property
    def effective_migrate_target_url(self) -> str:
        """Retorna la URL de destino para migración."""
        if self.MIGRATE_TARGET_URL and self.MIGRATE_TARGET_URL.strip():
            url = self.MIGRATE_TARGET_URL.strip()
            if url.startswith("postgres://"):
                url = "postgresql+psycopg2://" + url[len("postgres://"):]
            elif url.startswith("postgresql://") and not url.startswith("postgresql+"):
                url = "postgresql+psycopg2://" + url[len("postgresql://"):]
            return url
        # Fallback a la base activa actual
        return self.effective_database_url

    @property
    def effective_storage_provider(self) -> str:
        return (self.STORAGE_PROVIDER or self.STORAGE_TYPE or "local").lower().strip()


settings = Settings()

# Asegurar directorios de almacenamiento en disco para modo local
if settings.effective_storage_provider == "local":
    os.makedirs(f"{settings.STORAGE_BASE_DIR}/logos", exist_ok=True)
    os.makedirs(f"{settings.STORAGE_BASE_DIR}/uploads", exist_ok=True)
    os.makedirs(f"{settings.STORAGE_BASE_DIR}/facturas", exist_ok=True)
    os.makedirs(f"{settings.STORAGE_BASE_DIR}/remisiones_firmadas", exist_ok=True)