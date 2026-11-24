from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.usuario import Usuario, DEFAULT_ADMIN_PERMISSIONS, DEFAULT_OPERATOR_PERMISSIONS
from app.repositories.usuario_repository import UsuarioRepository
from app.core.security import verify_password, get_password_hash, create_access_token
from app.core.config import settings


class AuthService:

    @staticmethod
    def autenticar_usuario(db: Session, username: str, password: str) -> Usuario:
        user = UsuarioRepository.get_by_username(db, username)
        if not user:
            # También permitir login por email
            user = UsuarioRepository.get_by_email(db, username)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales incorrectas: usuario o correo no encontrado.",
            )
        
        if not user.activo:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Esta cuenta de usuario ha sido desactivada. Contacte al administrador.",
            )

        if not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales incorrectas: contraseña inválida.",
            )

        # Actualizar último login
        UsuarioRepository.update_last_login(db, user.id)
        return user

    @staticmethod
    def generar_token_acceso(
        usuario: Usuario,
        db: Optional[Session] = None,
        request: Optional[Any] = None,
    ) -> Dict[str, Any]:
        import uuid
        from datetime import datetime, timezone, timedelta
        from app.repositories.sesion_repository import SesionRepository

        session_jti = uuid.uuid4().hex
        payload = {
            "sub": str(usuario.id),
            "username": usuario.username,
            "rol": usuario.rol,
            "nombre": usuario.nombre_completo,
            "jti": session_jti,
        }
        token = create_access_token(payload)

        # Si se proporciona sesión de base de datos, persistir en la tabla sesiones
        if db is not None:
            ip = None
            user_agent = None
            if request is not None:
                ip = request.client.host if getattr(request, "client", None) else None
                forwarded = request.headers.get("x-forwarded-for")
                if forwarded:
                    ip = forwarded.split(",")[0].strip()
                user_agent = request.headers.get("user-agent")

            expira_en = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
            SesionRepository.create(
                db,
                {
                    "usuario_id": usuario.id,
                    "empresa_id": usuario.empresa_id,
                    "token_jti": session_jti,
                    "ip_address": ip,
                    "user_agent": user_agent,
                    "activo": True,
                    "expira_en": expira_en,
                },
            )

        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": usuario.id,
                "username": usuario.username,
                "email": usuario.email,
                "nombre_completo": usuario.nombre_completo,
                "rol": usuario.rol,
                "permisos": usuario.permisos or (DEFAULT_ADMIN_PERMISSIONS if usuario.rol == "admin" else DEFAULT_OPERATOR_PERMISSIONS),
                "activo": usuario.activo,
            }
        }

    @staticmethod
    def revocar_sesion(db: Session, token_jti: str) -> bool:
        from app.repositories.sesion_repository import SesionRepository
        return SesionRepository.revocar_sesion(db, token_jti)

    @staticmethod
    def revocar_todas_sesiones_usuario(db: Session, usuario_id: int, except_jti: Optional[str] = None) -> int:
        from app.repositories.sesion_repository import SesionRepository
        return SesionRepository.revocar_todas_usuario(db, usuario_id, except_jti=except_jti)

    @staticmethod
    def crear_usuario(
        db: Session,
        username: str,
        nombre_completo: str,
        password: str,
        email: Optional[str] = None,
        rol: str = "operador",
        permisos: Optional[Dict[str, Any]] = None,
    ) -> Usuario:
        # Validar duplicados
        if UsuarioRepository.get_by_username(db, username):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El nombre de usuario '{username}' ya está registrado.",
            )
        if email and UsuarioRepository.get_by_email(db, email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El correo electrónico '{email}' ya está registrado.",
            )

        if permisos is None:
            permisos = DEFAULT_ADMIN_PERMISSIONS.copy() if rol == "admin" else DEFAULT_OPERATOR_PERMISSIONS.copy()

        from app.models.role import Role
        rol_obj = db.query(Role).filter(Role.codigo == rol).first()

        data = {
            "username": username.strip(),
            "nombre_completo": nombre_completo.strip(),
            "email": email.strip() if email else None,
            "hashed_password": get_password_hash(password),
            "rol": rol,
            "rol_id": rol_obj.id if rol_obj else None,
            "permisos": permisos,
            "activo": True,
        }
        return UsuarioRepository.create(db, data)

    @staticmethod
    def actualizar_usuario(
        db: Session,
        user_id: int,
        nombre_completo: Optional[str] = None,
        email: Optional[str] = None,
        rol: Optional[str] = None,
        permisos: Optional[Dict[str, Any]] = None,
        activo: Optional[bool] = None,
    ) -> Usuario:
        user = UsuarioRepository.get_by_id(db, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        # Evitar desactivar al último administrador activo
        if activo is False and user.rol == "admin":
            total_admins = UsuarioRepository.count_admins(db)
            if total_admins <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No se puede desactivar al único administrador del sistema.",
                )

        # Validar email único si cambió
        if email and email.strip() != (user.email or ""):
            existing = UsuarioRepository.get_by_email(db, email.strip())
            if existing and existing.id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"El correo electrónico '{email}' ya está en uso por otro usuario.",
                )

        data = {}
        if nombre_completo is not None:
            data["nombre_completo"] = nombre_completo.strip()
        if email is not None:
            data["email"] = email.strip() if email else None
        if rol is not None:
            data["rol"] = rol
            from app.models.role import Role
            rol_obj = db.query(Role).filter(Role.codigo == rol).first()
            if rol_obj:
                data["rol_id"] = rol_obj.id
        if permisos is not None:
            data["permisos"] = permisos
        if activo is not None:
            data["activo"] = activo

        return UsuarioRepository.update(db, user_id, data)

    @staticmethod
    def cambiar_password(db: Session, user_id: int, current_pass: str, new_pass: str) -> None:
        user = UsuarioRepository.get_by_id(db, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        if not verify_password(current_pass, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La contraseña actual no es correcta.",
            )

        if len(new_pass) < 6:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La nueva contraseña debe tener al menos 6 caracteres.",
            )

        UsuarioRepository.update(db, user_id, {"hashed_password": get_password_hash(new_pass)})

    @staticmethod
    def reset_password_admin(db: Session, user_id: int, new_pass: str) -> None:
        user = UsuarioRepository.get_by_id(db, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        if len(new_pass) < 6:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La nueva contraseña debe tener al menos 6 caracteres.",
            )

        UsuarioRepository.update(db, user_id, {"hashed_password": get_password_hash(new_pass)})

    @classmethod
    def asegurar_roles_y_permisos(cls, db: Session) -> None:
        """Siembra los roles y permisos normalizados (RBAC 3NF) y los asocia a los usuarios."""
        from app.models.role import Role, Permiso
        """Siembra los roles y permisos normalizados (RBAC 3NF) delegando al servicio atómico RoleService."""
        from app.services.role_service import RoleService
        RoleService.asegurar_roles_y_permisos(db)

        permisos_meta = [
            ("puede_crear_pedidos", "Crear Pedidos", "PEDIDOS", "Permite registrar nuevos pedidos y remisiones"),
            ("puede_editar_pedidos", "Editar Pedidos", "PEDIDOS", "Permite modificar pedidos existentes y su liquidación"),
            ("puede_desactivar_pedidos", "Desactivar Pedidos", "PEDIDOS", "Permite anular o realizar baja lógica de pedidos"),
            ("puede_cargar_documentos", "Cargar Documentos", "DOCUMENTOS", "Permite importar archivos OCR / Excel / PDF"),
            ("puede_cargar_facturas", "Cargar Facturas", "DOCUMENTOS", "Permite adjuntar facturas escaneadas"),
            ("puede_cargar_remisiones_firmadas", "Cargar Remisiones Firmadas", "DOCUMENTOS", "Permite adjuntar remisiones con firma"),
            ("puede_gestionar_clientes", "Gestionar Clientes", "CLIENTES", "Permite registrar y editar clientes"),
            ("puede_editar_empresa", "Editar Empresa", "ADMIN", "Permite actualizar perfil y logo corporativo"),
            ("puede_ver_financiero", "Ver Financiero", "FINANCIERO", "Permite visualizar márgenes, costos y rentabilidad"),
            ("puede_exportar", "Exportar Documentos", "EXPORTACIONES", "Permite generar PDFs y archivos Excel"),
            ("puede_gestionar_catalogos", "Gestionar Catálogos", "CATALOGOS", "Permite crear y modificar productos y empaques"),
            ("puede_cerrar_pedidos", "Cerrar Pedidos", "PEDIDOS", "Permite formalizar y cerrar pedidos completados"),
        ]

        permisos_map = {}
        for cod, nom, mod, desc in permisos_meta:
            p = db.query(Permiso).filter(Permiso.codigo == cod).first()
            if not p:
                p = Permiso(codigo=cod, nombre=nom, modulo=mod, descripcion=desc, activo=True)
                db.add(p)
                db.flush()
            permisos_map[cod] = p

        rol_admin = db.query(Role).filter(Role.codigo == "admin").first()
        if not rol_admin:
            rol_admin = Role(codigo="admin", nombre="Administrador", descripcion="Control total del sistema", activo=True)
            db.add(rol_admin)
            db.flush()
        rol_admin.permisos = list(permisos_map.values())

        rol_operador = db.query(Role).filter(Role.codigo == "operador").first()
        if not rol_operador:
            rol_operador = Role(codigo="operador", nombre="Operador", descripcion="Operación logística y pedidos", activo=True)
            db.add(rol_operador)
            db.flush()

        operador_perms = [
            permisos_map[k] for k in DEFAULT_OPERATOR_PERMISSIONS.keys()
            if k in permisos_map and DEFAULT_OPERATOR_PERMISSIONS[k]
        ]
        if "puede_gestionar_catalogos" in permisos_map:
            operador_perms.append(permisos_map["puede_gestionar_catalogos"])
        if "puede_cerrar_pedidos" in permisos_map:
            operador_perms.append(permisos_map["puede_cerrar_pedidos"])
        rol_operador.permisos = operador_perms

        # Asignar rol_id a usuarios que no lo tengan
        usuarios = db.query(Usuario).all()
        for u in usuarios:
            if not u.rol_id:
                u.rol_id = rol_admin.id if u.rol == "admin" else rol_operador.id
        db.commit()

    @classmethod
    def asegurar_admin_inicial(cls, db: Session) -> Optional[Usuario]:
        """Crea un usuario administrador inicial si no existe ningún usuario en el sistema."""
        cls.asegurar_roles_y_permisos(db)

        from app.models.empresa import Empresa
        empresa_existente = db.query(Empresa).first()

        total_users = UsuarioRepository.count_total(db)
        if total_users == 0:
            from app.models.role import Role
            rol_admin = db.query(Role).filter(Role.codigo == "admin").first()
            admin = AuthService.crear_usuario(
                db=db,
                username=settings.INITIAL_ADMIN_USERNAME,
                nombre_completo=settings.INITIAL_ADMIN_NAME,
                password=settings.INITIAL_ADMIN_PASSWORD,
                email=settings.INITIAL_ADMIN_EMAIL,
                rol="admin",
                permisos=DEFAULT_ADMIN_PERMISSIONS.copy(),
            )
            if rol_admin:
                admin.rol_id = rol_admin.id
            if empresa_existente:
                admin.empresa_id = empresa_existente.id
            db.commit()
            return admin
        return None
