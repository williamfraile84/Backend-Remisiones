from sqlalchemy import Column, Integer, ForeignKey, Table, Index
from app.core.database import Base

rol_permisos = Table(
    "rol_permisos",
    Base.metadata,
    Column("rol_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permiso_id", Integer, ForeignKey("permisos.id", ondelete="CASCADE"), primary_key=True),
    Index("ix_rol_permisos_permiso_id", "permiso_id"),
)

