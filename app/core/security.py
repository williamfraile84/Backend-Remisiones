import os
import re
import uuid
import mimetypes
from typing import Set, Optional, Dict, Any
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, UploadFile
import bcrypt
import jwt
from app.core.config import settings

ALLOWED_IMAGE_EXTENSIONS: Set[str] = {".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_DOC_EXTENSIONS: Set[str] = {
    ext.strip().lower()
    for ext in settings.ALLOWED_DOC_EXTENSIONS.split(",")
    if ext.strip()
}
ALLOWED_CLOSURE_EXTENSIONS: Set[str] = {
    ext.strip().lower()
    for ext in settings.ALLOWED_CLOSURE_EXTENSIONS.split(",")
    if ext.strip()
}

MAX_FILE_SIZE_MB = settings.MAX_FILE_SIZE_MB
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# Firmas binarias (Magic Bytes) conocidas
MAGIC_BYTES_MAP = {
    ".pdf": [b"%PDF"],
    ".png": [b"\x89PNG\r\n\x1a\n", b"\x89PNG"],
    ".jpg": [b"\xff\xd8\xff"],
    ".jpeg": [b"\xff\xd8\xff"],
    ".webp": [b"RIFF"],
    ".xlsx": [b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"],
    ".xls": [b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"],
}


def sanitize_filename(filename: str) -> str:
    """
    Limpia el nombre del archivo para prevenir ataques de Path Traversal
    y caracteres inválidos en sistemas de archivos.
    """
    base_name = os.path.basename(filename)
    clean_name = re.sub(r"[^a-zA-Z0-9_\.\-]", "_", base_name)
    return clean_name


def generate_secure_storage_path(subfolder: str, original_filename: str) -> tuple[str, str]:
    """
    Genera una ruta relativa única e inyectable en disco.
    Retorna (ruta_relativa, nombre_limpio).
    """
    clean_name = sanitize_filename(original_filename)
    unique_prefix = uuid.uuid4().hex[:8]
    relative_path = f"{subfolder}/{unique_prefix}_{clean_name}"
    return relative_path, clean_name


def validate_file_content_header(header_bytes: bytes, ext: str) -> bool:
    """
    Verifica los primeros bytes del archivo (magic bytes) para validar
    que el contenido binario coincide con la extensión declarada.
    """
    if not header_bytes or ext not in MAGIC_BYTES_MAP:
        return True  # Si no hay firmas mapeadas, no bloquear
    expected_signatures = MAGIC_BYTES_MAP[ext]
    return any(header_bytes.startswith(sig) for sig in expected_signatures)


def validate_file_upload(file: UploadFile, allowed_extensions: Set[str], header_bytes: Optional[bytes] = None) -> str:
    """
    Valida la extensión del archivo y opcionalmente su firma binaria.
    Lanza HTTPException si el archivo no cumple con el formato permitido.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Nombre de archivo inválido.")
    
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Formato no permitido ({ext}). Formatos aceptados: {', '.join(sorted(allowed_extensions))}"
        )

    if header_bytes and not validate_file_content_header(header_bytes, ext):
        raise HTTPException(
            status_code=400,
            detail=f"El contenido del archivo no corresponde a un archivo {ext} válido."
        )

    return ext


def get_file_media_type(filename: str) -> str:
    """Detecta el tipo MIME correcto para previsualización o descarga."""
    ext = os.path.splitext(filename)[1].lower()
    mime, _ = mimetypes.guess_type(filename)
    if mime:
        return mime
    if ext == ".pdf":
        return "application/pdf"
    if ext == ".png":
        return "image/png"
    if ext in [".jpg", ".jpeg"]:
        return "image/jpeg"
    if ext == ".webp":
        return "image/webp"
    if ext == ".xlsx":
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if ext == ".xls":
        return "application/vnd.ms-excel"
    return "application/octet-stream"


# ==========================================
# Criptografía, Hashing y Manejo de Tokens JWT
# ==========================================

def get_password_hash(password: str) -> str:
    """Genera un hash seguro con bcrypt para la contraseña proporcionada."""
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica si la contraseña en texto plano coincide con el hash almacenado."""
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Crea y firma un token JWT con tiempo de expiración."""
    to_encode = data.copy()
    now_utc = datetime.now(timezone.utc)
    if expires_delta:
        expire = now_utc + expires_delta
    else:
        expire = now_utc + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decodifica y valida la firma y expiración de un token JWT."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except Exception:
        return None