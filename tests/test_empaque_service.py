import pytest
from app.core.database import SessionLocal, engine, Base
from app.models.tipo_empaque import TipoEmpaque
from app.repositories.empaque_repository import EmpaqueRepository


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    # Limpiar empaques creados en tests previos
    db.query(TipoEmpaque).delete()
    db.commit()
    yield
    db.close()


def test_seed_default_tipos():
    db = SessionLocal()
    try:
        seeded = EmpaqueRepository.seed_default_tipos_if_empty(db)
        assert seeded > 0
        all_items = EmpaqueRepository.get_all(db)
        assert len(all_items) >= seeded

        # Verificar tipos de empaque estandarizados
        ponys = [e for e in all_items if "Pony" in e.nombre or "Canastilla" in e.nombre]
        assert len(ponys) > 0
    finally:
        db.close()


def test_crud_empaque():
    db = SessionLocal()
    try:
        # Create
        data = {
            "nombre": "Caja de importación 18 Kg",
            "peso_kg": 18.0,
            "peso_lb": 36.0,
            "descripcion": "Caja de importación 18 Kg"
        }
        item = EmpaqueRepository.create(db, data)
        assert item.id is not None
        assert item.nombre == "Caja de importación 18 Kg"
        assert item.peso_kg == 18.0

        # Read
        fetched = EmpaqueRepository.get_by_id(db, item.id)
        assert fetched is not None
        assert fetched.nombre == "Caja de importación 18 Kg"

        # Update
        updated = EmpaqueRepository.update(db, item.id, {"peso_kg": 20.0, "descripcion": "Caja 20 Kg"})
        assert updated.peso_kg == 20.0
        assert updated.peso_lb == 40.0  # Auto-synced if not provided

        # Search
        results = EmpaqueRepository.get_all(db, search="Caja")
        assert len(results) >= 1
        assert any("Caja" in r.nombre for r in results)

        # Delete
        EmpaqueRepository.delete(db, item.id, hard=True)
        assert EmpaqueRepository.get_by_id(db, item.id) is None
    finally:
        db.close()

