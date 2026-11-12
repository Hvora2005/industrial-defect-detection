"""Exercise startup migration against isolated legacy SQLite databases."""

import importlib.util
import json
from pathlib import Path

import pytest
import sqlalchemy
from sqlalchemy import create_engine, text


@pytest.mark.parametrize("existing_count", [0, 1, 3])
def test_startup_migration_preserves_repeated_detections(tmp_path, monkeypatch, existing_count):
    engine = create_engine(f"sqlite:///{(tmp_path / 'legacy.db').as_posix()}")
    defects = [
        {"class_name": "scratches", "confidence": 85.0, "severity": "MAJOR",
         "bbox": {"x1": x, "y1": 0, "x2": x + 5, "y2": 5}}
        for x in (0, 10, 20)
    ]
    defects.append({"class_name": "pitted_surface", "confidence": 45.0, "severity": "MINOR"})
    legacy_json = json.dumps(defects)
    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE inspections (
                id INTEGER PRIMARY KEY, timestamp DATETIME, status VARCHAR NOT NULL,
                defects_found INTEGER NOT NULL, primary_defect VARCHAR,
                primary_confidence FLOAT, severity VARCHAR, all_defects_json VARCHAR NOT NULL
            )
        """))
        connection.execute(text("""
            INSERT INTO inspections VALUES
                (1, '2026-11-11 12:00:00', 'FAIL', 4, 'scratches', 85, 'MAJOR', :defects),
                (2, '2026-11-11 12:01:00', 'NO_DETECTIONS', 0, NULL, NULL, NULL, '[]')
        """), {"defects": legacy_json})
        if existing_count:
            connection.execute(text("""
                CREATE TABLE defects (
                    id INTEGER PRIMARY KEY, inspection_id INTEGER NOT NULL
                        REFERENCES inspections(id), class_name VARCHAR NOT NULL,
                    confidence FLOAT, severity VARCHAR
                )
            """))
            for _ in range(existing_count):
                connection.execute(text("""
                    INSERT INTO defects (inspection_id, class_name, confidence, severity)
                    VALUES (1, 'scratches', 85, 'MAJOR')
                """))

    # Importing the real module must create the new table and migrate old rows.
    source = Path(__file__).resolve().parents[1] / "backend" / "database.py"
    spec = importlib.util.spec_from_file_location("migration_database", source)
    database = importlib.util.module_from_spec(spec)
    try:
        with monkeypatch.context() as patch:
            patch.setattr(sqlalchemy, "create_engine", lambda *args, **kwargs: engine)
            spec.loader.exec_module(database)

        for _ in range(2):
            with database.SessionLocal() as session:
                assert session.query(database.Defect).count() == 4
                original = session.get(database.Inspection, 1)
                assert original.all_defects_json == legacy_json
                assert original.defects_found == len(original.defects) == 4
            stats = database.get_stats()
            assert stats["defect_distribution"] == {"scratches": 3, "pitted_surface": 1}
            assert stats["avg_confidence"] == 75.0
            assert stats["total_inspected"] == 2
            assert stats["no_detections_count"] == 1
            database.migrate_legacy_defects()

        # New writes already populate both representations; migration must not duplicate them.
        database.save_inspection({"status": "FAIL", "defects_found": 4,
                                  "severity": "MAJOR", "defects": defects})
        database.migrate_legacy_defects()
        with database.SessionLocal() as session:
            assert session.query(database.Defect).count() == 8
        assert database.get_stats()["defect_distribution"] == {"scratches": 6, "pitted_surface": 2}
    finally:
        engine.dispose()
