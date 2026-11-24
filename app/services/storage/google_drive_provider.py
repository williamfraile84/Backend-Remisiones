import os
import io
import json
import logging
from typing import Optional, Dict, Any
from fastapi import HTTPException
from fastapi.responses import StreamingResponse, Response
from app.services.storage.base import BaseStorageProvider
from app.core.security import get_file_media_type

logger = logging.getLogger("fruver.storage.google_drive")


class GoogleDriveStorageProvider(BaseStorageProvider):
    """
    Proveedor de almacenamiento en la nube utilizando Google Drive API v3.
    Soporta Service Account JSON (archivo o string) y OAuth2 credentials.
    """

    def __init__(
        self,
        folder_id: Optional[str] = None,
        service_account_file: Optional[str] = None,
        service_account_json: Optional[str] = None,
    ):
        self.root_folder_id = folder_id or os.getenv("GOOGLE_DRIVE_FOLDER_ID", "root")
        self.service_account_file = service_account_file or os.getenv("GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE")
        self.service_account_json = service_account_json or os.getenv("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON")
        self._service = None
        self._folder_cache: Dict[str, str] = {}
        self._file_id_cache: Dict[str, str] = {}

    def _get_service(self):
        if self._service is not None:
            return self._service

        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            scopes = ["https://www.googleapis.com/auth/drive"]

            if self.service_account_json:
                cred_dict = json.loads(self.service_account_json)
                creds = service_account.Credentials.from_service_account_info(cred_dict, scopes=scopes)
            elif self.service_account_file and os.path.exists(self.service_account_file):
                creds = service_account.Credentials.from_service_account_file(self.service_account_file, scopes=scopes)
            else:
                # Fallback credenciales predeterminadas de entorno
                import google.auth
                creds, _ = google.auth.default(scopes=scopes)

            self._service = build("drive", "v3", credentials=creds, cache_discovery=False)
            return self._service
        except Exception as e:
            logger.error(f"Error inicializando Google Drive Service: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"No fue posible conectar con Google Drive API. Verifique credenciales: {str(e)}"
            )

    def _get_or_create_subfolder(self, folder_name: str) -> str:
        """Obtiene o crea una subcarpeta dentro del directorio raíz de Google Drive."""
        if folder_name in self._folder_cache:
            return self._folder_cache[folder_name]

        service = self._get_service()
        query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        if self.root_folder_id and self.root_folder_id != "root":
            query += f" and '{self.root_folder_id}' in parents"

        results = service.files().list(q=query, spaces="drive", fields="files(id, name)").execute()
        files = results.get("files", [])

        if files:
            folder_id = files[0]["id"]
        else:
            file_metadata = {
                "name": folder_name,
                "mimeType": "application/vnd.google-apps.folder",
            }
            if self.root_folder_id and self.root_folder_id != "root":
                file_metadata["parents"] = [self.root_folder_id]
            created = service.files().create(body=file_metadata, fields="id").execute()
            folder_id = created.get("id")

        self._folder_cache[folder_name] = folder_id
        return folder_id

    def _find_file_id(self, relative_path: str) -> Optional[str]:
        """Localiza el ID del archivo en Google Drive a partir de su ruta relativa."""
        if relative_path in self._file_id_cache:
            return self._file_id_cache[relative_path]

        service = self._get_service()
        parts = relative_path.replace("\\", "/").strip("/").split("/")
        filename = parts[-1]
        parent_id = self.root_folder_id

        if len(parts) > 1:
            subfolder_name = parts[0]
            parent_id = self._get_or_create_subfolder(subfolder_name)

        query = f"name = '{filename}' and trashed = false"
        if parent_id and parent_id != "root":
            query += f" and '{parent_id}' in parents"

        results = service.files().list(q=query, spaces="drive", fields="files(id, name)").execute()
        files = results.get("files", [])

        if files:
            file_id = files[0]["id"]
            self._file_id_cache[relative_path] = file_id
            return file_id
        return None

    async def save_file(
        self,
        relative_path: str,
        content: bytes,
        content_type: str = "application/octet-stream"
    ) -> str:
        service = self._get_service()
        from googleapiclient.http import MediaIoBaseUpload

        parts = relative_path.replace("\\", "/").strip("/").split("/")
        filename = parts[-1]
        parent_id = self.root_folder_id

        if len(parts) > 1:
            subfolder_name = parts[0]
            parent_id = self._get_or_create_subfolder(subfolder_name)

        media = MediaIoBaseUpload(io.BytesIO(content), mimetype=content_type, resumable=True)
        file_metadata = {"name": filename}
        if parent_id and parent_id != "root":
            file_metadata["parents"] = [parent_id]

        created = service.files().create(body=file_metadata, media_body=media, fields="id, name").execute()
        file_id = created.get("id")
        self._file_id_cache[relative_path] = file_id

        return relative_path.replace("\\", "/")

    async def get_file_bytes(self, relative_path: str) -> bytes:
        file_id = self._find_file_id(relative_path)
        if not file_id:
            raise HTTPException(status_code=404, detail=f"Archivo '{relative_path}' no encontrado en Google Drive.")

        service = self._get_service()
        from googleapiclient.http import MediaIoBaseDownload

        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()

        return fh.getvalue()

    async def file_exists(self, relative_path: str) -> bool:
        return self._find_file_id(relative_path) is not None

    async def delete_file(self, relative_path: str) -> bool:
        file_id = self._find_file_id(relative_path)
        if not file_id:
            return False
        try:
            service = self._get_service()
            service.files().delete(fileId=file_id).execute()
            self._file_id_cache.pop(relative_path, None)
            return True
        except Exception:
            return False

    def get_response(
        self,
        relative_path: str,
        filename: Optional[str] = None,
        media_type: Optional[str] = None,
        inline: bool = True
    ) -> Response:
        file_id = self._find_file_id(relative_path)
        if not file_id:
            raise HTTPException(status_code=404, detail="Archivo no encontrado en Google Drive.")

        service = self._get_service()
        from googleapiclient.http import MediaIoBaseDownload

        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()

        fh.seek(0)
        resolved_media_type = media_type or get_file_media_type(filename or relative_path)
        disposition = "inline" if inline else "attachment"
        download_name = filename or os.path.basename(relative_path)

        return StreamingResponse(
            fh,
            media_type=resolved_media_type,
            headers={
                "Content-Disposition": f'{disposition}; filename="{download_name}"'
            }
        )

    async def get_public_url(self, relative_path: str) -> Optional[str]:
        file_id = self._find_file_id(relative_path)
        if not file_id:
            return None
        return f"https://drive.google.com/uc?id={file_id}&export=download"

