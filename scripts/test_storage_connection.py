"""
Script de Diagnóstico y Verificación de Proveedor de Almacenamiento
(Local, S3 / Supabase Storage, Google Drive, File Server)
"""
import sys
import asyncio
from pathlib import Path

# Agregar backend al path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.services.storage.storage_factory import get_storage_provider


async def test_storage():
    provider_name = settings.effective_storage_provider
    print("=" * 65)
    print("  VERIFICADOR DE ALMACENAMIENTO DE ARCHIVOS - FRUVER")
    print("=" * 65)
    print(f"[*] Proveedor Activo : {provider_name.upper()}")

    if provider_name in ("s3", "supabase", "supabase_storage", "aws_s3", "r2", "minio"):
        print(f"[*] S3 Endpoint      : {settings.S3_ENDPOINT_URL or 'AWS S3 Default'}")
        print(f"[*] S3 Region        : {settings.S3_REGION_NAME}")
        print(f"[*] S3 Bucket        : {settings.S3_BUCKET_NAME}")
        key_masked = (settings.S3_ACCESS_KEY_ID[:4] + "******") if settings.S3_ACCESS_KEY_ID else "No definido"
        print(f"[*] Access Key ID    : {key_masked}")
    elif provider_name == "local":
        print(f"[*] Directorio Local : {settings.STORAGE_BASE_DIR}")
    print("-" * 65)

    try:
        provider = get_storage_provider(force_new=True)

        test_path = "uploads/healthcheck_test.txt"
        test_payload = b"Sistema Fruver - Verificacion de Storage OK"

        print("[1/5] Subiendo archivo de prueba...")
        saved_path = await provider.save_file(test_path, test_payload, content_type="text/plain")
        print(f"   -> Archivo guardado en: {saved_path}")

        print("[2/5] Verificando existencia de archivo...")
        exists = await provider.file_exists(test_path)
        if not exists:
            raise RuntimeError("El archivo subido no figura como existente.")
        print("   -> Archivo verificado como existente.")

        print("[3/5] Descargando y validando integridad de bytes...")
        downloaded = await provider.get_file_bytes(test_path)
        if downloaded != test_payload:
            raise RuntimeError("El contenido descargado difiere del original.")
        print(f"   -> Bytes descargados con éxito ({len(downloaded)} bytes).")

        print("[4/5] Generando URL pública / presigned...")
        url = await provider.get_public_url(test_path)
        print(f"   -> URL Generada: {url}")

        print("[5/5] Eliminando archivo de prueba temporal...")
        deleted = await provider.delete_file(test_path)
        print(f"   -> Eliminado: {deleted}")

        print("=" * 65)
        print(" STATUS: ALMACENAMIENTO OPERACIONAL 100% OK")
        print("=" * 65)
        return True

    except Exception as e:
        print("=" * 65)
        print(" ERROR EN EL PROVEEDOR DE ALMACENAMIENTO:")
        print(f" {type(e).__name__}: {e}")
        print("=" * 65)
        print("\nSugerencias de depuración:")
        print(" 1. Si usas Supabase Storage vía S3 protocol, obtén tus credenciales S3 Access Key y Secret Key en:")
        print("    Supabase Dashboard -> Project Settings -> Storage -> S3 Access Keys.")
        print(" 2. El endpoint debe ser: https://[project-ref].storage.supabase.co/storage/v1/s3")
        print(" 3. Asegúrate de que el bucket (ej: fruver-storage) exista en el panel de Supabase Storage.")
        print(" 4. Para cambiar a almacenamiento local, configura: STORAGE_PROVIDER=local en .env.")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_storage())
    sys.exit(0 if success else 1)

