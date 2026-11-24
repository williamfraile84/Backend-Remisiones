import io
import logging
from typing import Optional, List, Dict, Any
from fastapi import HTTPException
from fastapi.responses import StreamingResponse, Response

from app.services.storage.base import BaseStorageProvider
from app.core.config import settings
from app.core.security import get_file_media_type

logger = logging.getLogger(__name__)


class S3StorageProvider(BaseStorageProvider):
    """
    Proveedor universal de almacenamiento compatible con S3
    (Supabase Storage, AWS S3, Cloudflare R2, MinIO, Wasabi, DigitalOcean Spaces, etc.).
    """

    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        region_name: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        bucket_name: Optional[str] = None,
        use_ssl: bool = True,
        public_url_prefix: Optional[str] = None,
        presigned_expiration: int = 3600,
    ):
        self.endpoint_url = endpoint_url or settings.S3_ENDPOINT_URL
        self.region_name = region_name or settings.S3_REGION_NAME or "ca-central-1"
        self.access_key_id = access_key_id or settings.S3_ACCESS_KEY_ID
        self.secret_access_key = secret_access_key or settings.S3_SECRET_ACCESS_KEY
        self.bucket_name = bucket_name or settings.S3_BUCKET_NAME or "app-storage"
        self.use_ssl = use_ssl if use_ssl is not None else settings.S3_USE_SSL
        self.public_url_prefix = public_url_prefix or settings.S3_PUBLIC_URL_PREFIX
        self.presigned_expiration = presigned_expiration or settings.S3_PRESIGNED_EXPIRATION_SECONDS

        try:
            import boto3
            from botocore.config import Config
            from botocore.exceptions import ClientError
            self.ClientError = ClientError
        except ImportError:
            raise ImportError(
                "El paquete 'boto3' es requerido para utilizar el almacenamiento S3 / Supabase Storage. "
                "Por favor instálalo ejecutando: pip install boto3"
            )

        boto_config = Config(
            signature_version="s3v4",
            s3={"addressing_style": "auto"}
        )

        client_kwargs: Dict[str, Any] = {
            "service_name": "s3",
            "config": boto_config,
            "region_name": self.region_name,
        }

        if self.endpoint_url:
            client_kwargs["endpoint_url"] = self.endpoint_url

        if self.access_key_id and self.secret_access_key:
            client_kwargs["aws_access_key_id"] = self.access_key_id
            client_kwargs["aws_secret_access_key"] = self.secret_access_key

        if self.use_ssl is not None:
            client_kwargs["use_ssl"] = self.use_ssl

        self.s3_client = boto3.client(**client_kwargs)

    def _normalize_key(self, relative_path: str) -> str:
        """Sanitiza y normaliza la clave de objeto en S3."""
        return relative_path.replace("\\", "/").lstrip("/")

    def ensure_bucket_exists(self) -> bool:
        """Verifica que el bucket exista; si no existe, intenta crearlo."""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            return True
        except (self.ClientError, Exception) as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code in ("404", "NoSuchBucket"):
                try:
                    create_kwargs: Dict[str, Any] = {"Bucket": self.bucket_name}
                    if self.region_name and self.region_name != "us-east-1":
                        create_kwargs["CreateBucketConfiguration"] = {
                            "LocationConstraint": self.region_name
                        }
                    self.s3_client.create_bucket(**create_kwargs)
                    logger.info(f"Bucket S3 '{self.bucket_name}' creado exitosamente.")
                    return True
                except Exception as create_err:
                    logger.error(f"No se pudo crear el bucket '{self.bucket_name}': {create_err}")
                    return False
            logger.warning(f"Error verificando bucket '{self.bucket_name}': {e}")
            return False

    async def save_file(
        self,
        relative_path: str,
        content: bytes,
        content_type: str = "application/octet-stream"
    ) -> str:
        clean_key = self._normalize_key(relative_path)
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=clean_key,
                Body=content,
                ContentType=content_type
            )
            return clean_key
        except (self.ClientError, Exception) as e:
            logger.error(f"Error al guardar archivo '{clean_key}' en S3: {e}")
            raise HTTPException(status_code=500, detail=f"Error al persistir archivo en almacenamiento S3: {e}")

    async def get_file_bytes(self, relative_path: str) -> bytes:
        clean_key = self._normalize_key(relative_path)
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=clean_key
            )
            return response["Body"].read()
        except (self.ClientError, Exception) as e:
            error_code = getattr(e, "response", {}).get("Error", {}).get("Code") if hasattr(e, "response") else None
            if error_code in ("NoSuchKey", "404") or "NoSuchKey" in str(e) or "404" in str(e):
                raise HTTPException(status_code=404, detail="Archivo no encontrado en almacenamiento S3.")
            logger.error(f"Error al descargar archivo '{clean_key}' desde S3: {e}")
            raise HTTPException(status_code=500, detail=f"Error al leer archivo desde almacenamiento S3: {e}")

    async def file_exists(self, relative_path: str) -> bool:
        clean_key = self._normalize_key(relative_path)
        try:
            self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=clean_key
            )
            return True
        except (self.ClientError, Exception):
            return False

    async def delete_file(self, relative_path: str) -> bool:
        clean_key = self._normalize_key(relative_path)
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=clean_key
            )
            return True
        except (self.ClientError, Exception) as e:
            logger.warning(f"Error al eliminar archivo '{clean_key}' en S3: {e}")
            return False

    def get_response(
        self,
        relative_path: str,
        filename: Optional[str] = None,
        media_type: Optional[str] = None,
        inline: bool = True
    ) -> Response:
        clean_key = self._normalize_key(relative_path)
        try:
            s3_obj = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=clean_key
            )
        except (self.ClientError, Exception) as e:
            error_code = getattr(e, "response", {}).get("Error", {}).get("Code") if hasattr(e, "response") else None
            if error_code in ("NoSuchKey", "404") or "NoSuchKey" in str(e) or "404" in str(e):
                raise HTTPException(status_code=404, detail="Archivo no encontrado en almacenamiento S3.")
            raise HTTPException(status_code=500, detail=f"Error al acceder al archivo en S3: {e}")

        resolved_media_type = media_type or s3_obj.get("ContentType") or get_file_media_type(filename or clean_key)
        content_disposition = "inline" if inline else "attachment"
        download_name = filename or clean_key.split("/")[-1]

        headers = {
            "Content-Disposition": f'{content_disposition}; filename="{download_name}"',
        }
        if "ContentLength" in s3_obj:
            headers["Content-Length"] = str(s3_obj["ContentLength"])

        # Stream del body de S3 sin cargarlo todo en memoria RAM del servidor
        return StreamingResponse(
            s3_obj["Body"],
            media_type=resolved_media_type,
            headers=headers
        )

    async def get_public_url(self, relative_path: str) -> Optional[str]:
        clean_key = self._normalize_key(relative_path)
        if self.public_url_prefix:
            prefix = self.public_url_prefix.rstrip("/")
            return f"{prefix}/{clean_key}"

        try:
            # Generar Presigned URL firmada y temporal
            url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": clean_key},
                ExpiresIn=self.presigned_expiration
            )
            return url
        except Exception as e:
            logger.warning(f"No se pudo generar presigned URL para '{clean_key}': {e}")
            return None

    def list_all_files(self, prefix: str = "") -> List[str]:
        """Lista todas las rutas relativas de archivos existentes en el bucket S3."""
        clean_prefix = self._normalize_key(prefix) if prefix else ""
        keys: List[str] = []
        paginator = self.s3_client.get_paginator("list_objects_v2")
        try:
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=clean_prefix):
                for obj in page.get("Contents", []):
                    key = obj.get("Key")
                    if key and not key.endswith("/"):
                        keys.append(key)
        except Exception as e:
            logger.error(f"Error listando archivos en S3 '{self.bucket_name}': {e}")
        return keys
