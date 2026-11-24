import os
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Ensure all tests use local in-memory SQLite and local storage
os.environ["TESTING"] = "1"
os.environ["APP_ENV"] = "testing"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["DB_ENGINE"] = "sqlite"
os.environ["STORAGE_PROVIDER"] = "local"
os.environ["AUTO_MIGRATE_DB"] = "false"
os.environ["AUTO_MIGRATE_STORAGE"] = "false"
