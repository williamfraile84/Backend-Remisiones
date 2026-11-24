from typing import Optional, Dict, Type
from app.core.config import settings
from app.services.storage.base import BaseStorageProvider
from app.services.storage.local_provider import LocalStorageProvider
from app.services.storage.google_drive_provider import GoogleDriveStorageProvider
from app.services.storage.file_server_provider import RemoteFileServerProvider
from app.services.storage.s3_provider import S3StorageProvider

_storage_provider_instance: Optional[BaseStorageProvider] = None


def create_storage_provider(provider_name: Optional[str] = None) -> BaseStorageProvider:
    """
    Crea e inicializa una instancia de cualquier proveedor de almacenamiento solicitado.
    Opciones: 'local', 's3' (o 'supabase', 'aws_s3', 'r2', 'minio'), 'google_drive', 'file_server'.
    """
    ptype = (provider_name or settings.effective_storage_provider).lower().strip()

    if ptype in ("s3", "supabase", "supabase_storage", "aws_s3", "r2", "minio", "spaces"):
        return S3StorageProvider(
            endpoint_url=settings.S3_ENDPOINT_URL,
            region_name=settings.S3_REGION_NAME,
            access_key_id=settings.S3_ACCESS_KEY_ID,
            secret_access_key=settings.S3_SECRET_ACCESS_KEY,
            bucket_name=settings.S3_BUCKET_NAME,
            use_ssl=settings.S3_USE_SSL,
            public_url_prefix=settings.S3_PUBLIC_URL_PREFIX,
            presigned_expiration=settings.S3_PRESIGNED_EXPIRATION_SECONDS,
        )

    if ptype == "google_drive":
        return GoogleDriveStorageProvider(
            folder_id=settings.GOOGLE_DRIVE_FOLDER_ID,
            service_account_file=settings.GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE,
            service_account_json=settings.GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON,
        )

    if ptype == "file_server":
        return RemoteFileServerProvider(
            server_url=settings.FILE_SERVER_URL,
            api_key=settings.FILE_SERVER_API_KEY,
        )

    # Por defecto: almacenamiento local en disco
    return LocalStorageProvider(
        base_dir=settings.STORAGE_BASE_DIR
    )


def get_storage_provider(force_new: bool = False) -> BaseStorageProvider:
    """
    Obtiene la instancia del proveedor de almacenamiento activo según STORAGE_PROVIDER.
    """
    global _storage_provider_instance
    if _storage_provider_instance is None or force_new:
        _storage_provider_instance = create_storage_provider()
    return _storage_provider_instance
