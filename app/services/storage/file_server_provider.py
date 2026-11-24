import os
import io
import logging
from typing import Optional
import httpx
from fastapi import HTTPException
from fastapi.responses import StreamingResponse, Response
from app.services.storage.base import BaseStorageProvider
from app.core.security import get_file_media_type

logger = logging.getLogger("fruver.storage.file_server")


class RemoteFileServerProvider(BaseStorageProvider):
    """
    Proveedor de almacenamiento para servidor de archivos HTTP/REST o microservicio de persistencia.
    """

    def __init__(
        self,
        server_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.server_url = (server_url or os.getenv("FILE_SERVER_URL", "http://localhost:9000")).rstrip("/")
        self.api_key = api_key or os.getenv("FILE_SERVER_API_KEY", "")

    def _get_headers(self) -> dict:
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            headers["X-API-Key"] = self.api_key
        return headers

    async def save_file(
        self,
        relative_path: str,
        content: bytes,
        content_type: str = "application/octet-stream"
    ) -> str:
        clean_rel = relative_path.replace("\\", "/").lstrip("/")
        url = f"{self.server_url}/files/{clean_rel}"
        headers = self._get_headers()
        headers["Content-Type"] = content_type

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.put(url, content=content, headers=headers)
            if resp.status_code not in (200, 201):
                logger.error(f"Error guardando archivo en servidor remoto: {resp.status_code} - {resp.text}")
                raise HTTPException(
                    status_code=502,
                    detail=f"Falla al transferir archivo al servidor de almacenamiento: {resp.text}"
                )
        return clean_rel

    async def get_file_bytes(self, relative_path: str) -> bytes:
        clean_rel = relative_path.replace("\\", "/").lstrip("/")
        url = f"{self.server_url}/files/{clean_rel}"
        headers = self._get_headers()

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 404:
                raise HTTPException(status_code=404, detail="Archivo no encontrado en servidor remoto.")
            if resp.status_code != 200:
                raise HTTPException(status_code=502, detail="Error obteniendo archivo del servidor remoto.")
            return resp.content

    async def file_exists(self, relative_path: str) -> bool:
        clean_rel = relative_path.replace("\\", "/").lstrip("/")
        url = f"{self.server_url}/files/{clean_rel}"
        headers = self._get_headers()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.head(url, headers=headers)
                return resp.status_code == 200
        except Exception:
            return False

    async def delete_file(self, relative_path: str) -> bool:
        clean_rel = relative_path.replace("\\", "/").lstrip("/")
        url = f"{self.server_url}/files/{clean_rel}"
        headers = self._get_headers()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.delete(url, headers=headers)
                return resp.status_code in (200, 204)
        except Exception:
            return False

    def get_response(
        self,
        relative_path: str,
        filename: Optional[str] = None,
        media_type: Optional[str] = None,
        inline: bool = True
    ) -> Response:
        clean_rel = relative_path.replace("\\", "/").lstrip("/")
        url = f"{self.server_url}/files/{clean_rel}"
        headers = self._get_headers()

        resolved_media_type = media_type or get_file_media_type(filename or relative_path)
        disposition = "inline" if inline else "attachment"
        download_name = filename or os.path.basename(relative_path)

        async def stream_generator():
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream("GET", url, headers=headers) as r:
                    if r.status_code == 404:
                        raise HTTPException(status_code=404, detail="Archivo no encontrado en servidor remoto.")
                    async for chunk in r.aiter_bytes():
                        yield chunk

        return StreamingResponse(
            stream_generator(),
            media_type=resolved_media_type,
            headers={
                "Content-Disposition": f'{disposition}; filename="{download_name}"'
            }
        )

    async def get_public_url(self, relative_path: str) -> Optional[str]:
        clean_rel = relative_path.replace("\\", "/").lstrip("/")
        return f"{self.server_url}/files/{clean_rel}"

