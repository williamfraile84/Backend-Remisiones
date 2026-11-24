import os
import io
from typing import Optional
from fastapi import HTTPException
from fastapi.responses import FileResponse, Response
from app.services.storage.base import BaseStorageProvider
from app.core.config import settings
from app.core.security import get_file_media_type


class LocalStorageProvider(BaseStorageProvider):
    """
    Proveedor de almacenamiento local en el sistema de archivos (storage_data).
    """

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = os.path.abspath(base_dir or settings.STORAGE_BASE_DIR)
        os.makedirs(self.base_dir, exist_ok=True)

    def _resolve_full_path(self, relative_path: str) -> str:
        clean_rel = relative_path.lstrip("/\\")
        return os.path.normpath(os.path.join(self.base_dir, clean_rel))

    async def save_file(
        self,
        relative_path: str,
        content: bytes,
        content_type: str = "application/octet-stream"
    ) -> str:
        full_path = self._resolve_full_path(relative_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "wb") as f:
            f.write(content)
        return relative_path.replace("\\", "/")

    async def get_file_bytes(self, relative_path: str) -> bytes:
        full_path = self._resolve_full_path(relative_path)
        if not os.path.isfile(full_path):
            raise HTTPException(status_code=404, detail="Archivo no encontrado en almacenamiento local.")
        with open(full_path, "rb") as f:
            return f.read()

    async def file_exists(self, relative_path: str) -> bool:
        full_path = self._resolve_full_path(relative_path)
        return os.path.isfile(full_path)

    async def delete_file(self, relative_path: str) -> bool:
        full_path = self._resolve_full_path(relative_path)
        if os.path.isfile(full_path):
            try:
                os.remove(full_path)
                return True
            except OSError:
                return False
        return False

    def get_response(
        self,
        relative_path: str,
        filename: Optional[str] = None,
        media_type: Optional[str] = None,
        inline: bool = True
    ) -> Response:
        full_path = self._resolve_full_path(relative_path)
        if not os.path.isfile(full_path):
            raise HTTPException(status_code=404, detail="Archivo físico no encontrado en almacenamiento local.")

        resolved_media_type = media_type or get_file_media_type(filename or full_path)
        content_disposition = "inline" if inline else "attachment"
        download_name = filename or os.path.basename(full_path)

        return FileResponse(
            full_path,
            media_type=resolved_media_type,
            filename=download_name,
            content_disposition_type=content_disposition
        )

    async def get_public_url(self, relative_path: str) -> Optional[str]:
        # Para local, se sirve vía el mount /storage_data/
        clean_rel = relative_path.replace("\\", "/").lstrip("/")
        return f"/storage_data/{clean_rel}"

    def list_all_files(self, prefix: str = "") -> list:
        """Lista todas las rutas relativas de archivos existentes en el almacenamiento local."""
        clean_prefix = prefix.replace("\\", "/").lstrip("/")
        base_search_dir = os.path.join(self.base_dir, clean_prefix)
        file_paths = []
        if not os.path.exists(base_search_dir):
            return file_paths

        for root, _, files in os.walk(base_search_dir):
            for file in files:
                # Omitir archivos temporales o de base de datos sqlite en storage_data
                if file.endswith((".db", ".db-journal", ".db-wal", ".db-shm")):
                    continue
                full_file_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_file_path, self.base_dir).replace("\\", "/")
                file_paths.append(rel_path)
        return file_paths

