from abc import ABC, abstractmethod
from typing import Optional, BinaryIO, AsyncIterator, Dict, Any
from fastapi.responses import Response


class BaseStorageProvider(ABC):
    """
    Contrato base abstracto para proveedores de almacenamiento.
    Permite desacoplar el almacenamiento físico (Local, Google Drive, File Server)
    de los controladores y lógica de negocio.
    """

    @abstractmethod
    async def save_file(
        self,
        relative_path: str,
        content: bytes,
        content_type: str = "application/octet-stream"
    ) -> str:
        """
        Persiste un archivo binario en el medio de almacenamiento.
        Retorna la ruta relativa unificada o identificador del archivo.
        """
        pass

    @abstractmethod
    async def get_file_bytes(self, relative_path: str) -> bytes:
        """
        Obtiene los bytes íntegros del archivo a partir de su ruta relativa.
        """
        pass

    @abstractmethod
    async def file_exists(self, relative_path: str) -> bool:
        """
        Verifica si un archivo existe en el medio de persistencia.
        """
        pass

    @abstractmethod
    async def delete_file(self, relative_path: str) -> bool:
        """
        Elimina un archivo del medio de persistencia.
        """
        pass

    @abstractmethod
    def get_response(
        self,
        relative_path: str,
        filename: Optional[str] = None,
        media_type: Optional[str] = None,
        inline: bool = True
    ) -> Response:
        """
        Genera y retorna una respuesta HTTP de FastAPI adecuada para el proveedor
        (FileResponse, StreamingResponse o RedirectResponse).
        """
        pass

    @abstractmethod
    async def get_public_url(self, relative_path: str) -> Optional[str]:
        """
        Retorna una URL accesible públicamente o firmada si el medio lo soporta.
        """
        pass

