from typing import Optional, Dict, Any
from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]


class UserSessionResponse(BaseModel):
    id: int
    username: str
    email: Optional[str] = None
    nombre_completo: str
    rol: str
    permisos: Dict[str, Any]
    activo: bool


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class InitialAdminSetupRequest(BaseModel):
    username: str
    nombre_completo: str
    email: Optional[str] = None
    password: str

