"""
Script Universal de Migración y Sincronización de Archivos de Almacenamiento
(Local <-> S3 / Supabase Storage <-> Google Drive <-> File Server)
"""
import sys
import asyncio
import argparse
from pathlib import Path

# Agregar backend al path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.services.storage_migration_service import StorageMigrationService


def main():
    parser = argparse.ArgumentParser(
        description="Herramienta de sincronización y migración de archivos físicos para Sistema Fruver."
    )
    parser.add_argument(
        "--source",
        type=str,
        default=None,
        help="Proveedor de origen ('local', 's3', 'google_drive', 'file_server'). Si se omite, usa MIGRATE_STORAGE_SOURCE de .env."
    )
    parser.add_argument(
        "--target",
        type=str,
        default=None,
        help="Proveedor de destino ('local', 's3', 'google_drive', 'file_server'). Si se omite, usa STORAGE_PROVIDER activo de .env."
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        default=None,
        help="Fuerza la sobrescritura de archivos que ya existan en destino (por defecto solo copia nuevos/faltantes)."
    )
    parser.add_argument(
        "--local-to-s3",
        action="store_true",
        help="Acceso rápido: Copia todos los archivos locales (storage_data/) hacia el bucket S3 / Supabase Storage."
    )
    parser.add_argument(
        "--s3-to-local",
        action="store_true",
        help="Acceso rápido: Descarga todos los archivos del bucket S3 / Supabase Storage hacia el almacenamiento local."
    )

    args = parser.parse_args()

    source = args.source
    target = args.target

    if args.local_to_s3:
        source = "local"
        target = "s3"
    elif args.s3_to_local:
        source = "s3"
        target = "local"

    print("=" * 65)
    print("  SINCRONIZACIÓN DE ALMACENAMIENTO DE ARCHIVOS - FRUVER")
    print("=" * 65)

    res = asyncio.run(StorageMigrationService.migrate_storage(
        source_name=source,
        target_name=target,
        overwrite=args.overwrite
    ))

    print("=" * 65)
    if res.get("success"):
        stats = res.get("stats", {})
        print(" RESULTADO: SINCRONIZACIÓN EXITOSA")
        print("-" * 65)
        print(f"[*] Origen             : {res.get('source').upper()}")
        print(f"[*] Destino            : {res.get('target').upper()}")
        print(f"[*] Archivos copiados  : {stats.get('transferred', 0)}")
        print(f"[*] Archivos omitidos  : {stats.get('skipped', 0)} (ya existían)")
        print(f"[*] Archivos fallidos  : {stats.get('failed', 0)}")
        print("=" * 65)
        sys.exit(0)
    else:
        print(" RESULTADO: HUBO ADVERTENCIAS O ERRORES")
        print("-" * 65)
        print(f"[*] Detalle: {res.get('error', 'Revisar logs')}")
        if res.get("stats"):
            stats = res["stats"]
            print(f"[*] Copiados: {stats.get('transferred')}, Fallidos: {stats.get('failed')}")
            for det in stats.get("details", [])[:5]:
                print(f"    - {det}")
        print("=" * 65)
        sys.exit(1)


if __name__ == "__main__":
    main()

