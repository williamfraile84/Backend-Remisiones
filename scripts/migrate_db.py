"""
Script Universal de Migración de Base de Datos - Sistema Fruver
Permite migrar datos entre cualquier combinación de motores:
(SQLite <-> PostgreSQL/Supabase <-> MySQL <-> Oracle, etc.)
"""
import sys
import argparse
from pathlib import Path

# Agregar backend al path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.services.migration_service import DatabaseMigrationService


def main():
    parser = argparse.ArgumentParser(
        description="Herramienta de migración bidireccional y agnóstica de base de datos para Sistema Fruver."
    )
    parser.add_argument(
        "--source",
        type=str,
        default=None,
        help="URL de la base de datos de origen (ej: sqlite:///./storage_data/app.db). Si se omite, usa MIGRATE_SOURCE_URL de .env."
    )
    parser.add_argument(
        "--target",
        type=str,
        default=None,
        help="URL de la base de datos de destino. Si se omite, usa MIGRATE_TARGET_URL o la base activa de .env."
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        default=None,
        help="Limpia/reinicia las tablas de destino antes de insertar (por defecto realiza merge/upsert seguro)."
    )
    parser.add_argument(
        "--cloud-to-sqlite",
        action="store_true",
        help="Acceso rápido: Copia datos desde la nube (Postgres/MySQL activo) hacia SQLite local (storage_data/app.db)."
    )
    parser.add_argument(
        "--sqlite-to-cloud",
        action="store_true",
        help="Acceso rápido: Copia datos desde SQLite local (storage_data/app.db) hacia la base activa en la nube."
    )

    args = parser.parse_args()

    source_url = args.source
    target_url = args.target

    if args.cloud_to_sqlite:
        source_url = settings.effective_database_url
        target_url = "sqlite:///./storage_data/app.db"
    elif args.sqlite_to_cloud:
        source_url = "sqlite:///./storage_data/app.db"
        target_url = settings.effective_database_url

    print("=" * 65)
    print("  MIGRACIÓN UNIVERSAL DE BASE DE DATOS - SISTEMA FRUVER")
    print("=" * 65)

    resultado = DatabaseMigrationService.execute_migration(
        source_url=source_url,
        target_url=target_url,
        reset_destination=args.reset
    )

    print("=" * 65)
    if resultado.get("success"):
        print(" RESULTADO: MIGRACIÓN EXITOSA")
        print("-" * 65)
        print(f"[*] Origen : {resultado.get('source')}")
        print(f"[*] Destino: {resultado.get('target')}")
        print(f"[*] Registros transferidos:")
        for tabla, cantidad in resultado.get("records_migrated", {}).items():
            print(f"    - {tabla.capitalize():<12}: {cantidad} registros")
        print("=" * 65)
        sys.exit(0)
    else:
        print(" RESULTADO: ERROR EN LA MIGRACIÓN")
        print("-" * 65)
        print(f"[*] Detalle: {resultado.get('error')}")
        print("=" * 65)
        sys.exit(1)


if __name__ == "__main__":
    main()

