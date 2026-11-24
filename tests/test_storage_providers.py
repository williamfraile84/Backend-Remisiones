import asyncio
import os
import shutil
from app.core.config import settings
from app.services.storage.local_provider import LocalStorageProvider
from app.services.storage.storage_factory import get_storage_provider


def test_local_storage_provider_lifecycle():
    def run_coro(coro):
        try:
            coro.send(None)
        except StopIteration as e:
            return e.value

    test_dir = "./storage_data/test_storage"
    os.makedirs(test_dir, exist_ok=True)
    provider = LocalStorageProvider(base_dir=test_dir)

    test_path = "uploads/sample_test.txt"
    content = b"Prueba unitaria de almacenamiento desacoplado Fruver 2026"

    # 1. Guardar archivo
    saved_path = run_coro(provider.save_file(test_path, content, "text/plain"))
    assert saved_path == "uploads/sample_test.txt"

    # 2. Verificar existencia
    exists = run_coro(provider.file_exists(test_path))
    assert exists is True

    # 3. Leer bytes
    read_bytes = run_coro(provider.get_file_bytes(test_path))
    assert read_bytes == content

    # 4. Obtener Response de FastAPI
    response = provider.get_response(test_path, filename="sample.txt", inline=True)
    assert response.status_code == 200

    # 5. Eliminar archivo
    deleted = run_coro(provider.delete_file(test_path))
    assert deleted is True
    assert run_coro(provider.file_exists(test_path)) is False

    # Limpiar directorio de test
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir, ignore_errors=True)


def test_storage_factory_singleton():
    provider1 = get_storage_provider()
    provider2 = get_storage_provider()
    assert provider1 is provider2
    assert provider1 is not None


def test_storage_factory_create_s3():
    from app.services.storage.storage_factory import create_storage_provider
    from app.services.storage.s3_provider import S3StorageProvider
    s3_provider = create_storage_provider("s3")
    assert isinstance(s3_provider, S3StorageProvider)
    assert s3_provider.region_name == (settings.S3_REGION_NAME or "ca-central-1")
    assert s3_provider.bucket_name == (settings.S3_BUCKET_NAME or "fruver-storage")


def test_local_storage_list_all_files():
    test_dir = "./storage_data/test_storage_list"
    os.makedirs(os.path.join(test_dir, "uploads"), exist_ok=True)
    file1 = os.path.join(test_dir, "uploads", "test1.txt")
    with open(file1, "w") as f:
        f.write("archivo de prueba")

    provider = LocalStorageProvider(base_dir=test_dir)
    files = provider.list_all_files("uploads")
    assert len(files) == 1
    assert "uploads/test1.txt" in files[0].replace("\\", "/")

    if os.path.exists(test_dir):
        shutil.rmtree(test_dir, ignore_errors=True)

