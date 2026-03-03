"""Tests for database operations."""

import sqlite3

import pytest

from src.storage.database import (
    get_connection,
    init_db,
    upsert_complaint,
    upsert_recall,
    upsert_investigation,
    insert_cross_link,
    upsert_vehicle,
    get_stats,
)


@pytest.fixture
def db():
    """Create an in-memory test database."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


class TestInitDB:
    def test_creates_tables(self, db):
        tables = [r[0] for r in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()]
        assert "complaints" in tables
        assert "recalls" in tables
        assert "investigations" in tables
        assert "cross_links" in tables
        assert "vehicles" in tables


class TestUpsertComplaint:
    def test_insert(self, db):
        rec = {
            "odi_number": 11111111,
            "manufacturer": "Toyota",
            "make": "TOYOTA",
            "model": "CAMRY",
            "model_year": 2023,
            "crash": 0, "fire": 0,
            "num_injuries": 0, "num_deaths": 0,
            "date_of_incident": "2024-01-01",
            "date_complaint_filed": "2024-01-15",
            "components": "ENGINE",
            "summary": "Engine stalled.",
            "vin_prefix": "4T1K1234",
            "quality_score": 0.85,
        }
        upsert_complaint(db, rec)
        db.commit()
        row = db.execute("SELECT * FROM complaints WHERE odi_number = 11111111").fetchone()
        assert row is not None
        assert row["make"] == "TOYOTA"
        assert row["quality_score"] == 0.85

    def test_upsert_update(self, db):
        rec = {
            "odi_number": 11111111,
            "manufacturer": "Toyota",
            "make": "TOYOTA",
            "model": "CAMRY",
            "model_year": 2023,
            "crash": 0, "fire": 0,
            "num_injuries": 0, "num_deaths": 0,
            "date_of_incident": "",
            "date_complaint_filed": "2024-01-15",
            "components": "",
            "summary": "Initial.",
            "vin_prefix": "",
            "quality_score": 0.5,
        }
        upsert_complaint(db, rec)
        db.commit()

        rec["components"] = "BRAKES"
        rec["summary"] = "Updated summary."
        rec["quality_score"] = 0.9
        upsert_complaint(db, rec)
        db.commit()

        row = db.execute("SELECT * FROM complaints WHERE odi_number = 11111111").fetchone()
        assert row["components"] == "BRAKES"
        assert row["quality_score"] == 0.9


class TestUpsertRecall:
    def test_insert(self, db):
        rec = {
            "campaign_number": "23V432000",
            "manufacturer": "Toyota",
            "make": "TOYOTA",
            "model": "CAMRY",
            "model_year": 2023,
            "report_received_date": "2023-06-15",
            "component": "WHEELS",
            "summary": "Lug nuts loose.",
            "consequence": "Wheel detachment.",
            "remedy": "Tighten lug nuts.",
            "notes": "",
            "num_potentially_affected": 5000,
            "park_it": 1, "park_outside": 0,
            "quality_score": 0.95,
        }
        upsert_recall(db, rec)
        db.commit()
        row = db.execute("SELECT * FROM recalls WHERE campaign_number = '23V432000'").fetchone()
        assert row is not None
        assert row["num_potentially_affected"] == 5000


class TestUpsertInvestigation:
    def test_insert(self, db):
        rec = {
            "investigation_number": "PE24001",
            "nhtsa_id": "102047",
            "make": "FORD",
            "model": "F-150",
            "model_year_start": 2015,
            "model_year_end": 2017,
            "investigation_type": "PE",
            "status": "Closed",
            "open_date": "2024-01-15",
            "close_date": "2024-06-01",
            "subject": "Transmission downshift",
            "description": "Sudden downshift without warning.",
            "num_complaints": 329,
            "num_vehicles": 1000000,
            "components": "POWER TRAIN",
            "quality_score": 0.9,
        }
        upsert_investigation(db, rec)
        db.commit()
        row = db.execute("SELECT * FROM investigations WHERE investigation_number = 'PE24001'").fetchone()
        assert row is not None
        assert row["make"] == "FORD"


class TestCrossLinks:
    def test_insert(self, db):
        rec = {
            "source_type": "complaint",
            "source_id": "11111111",
            "target_type": "recall",
            "target_id": "23V432000",
            "link_method": "make_model_year",
            "confidence": 0.85,
        }
        link_id = insert_cross_link(db, rec)
        db.commit()
        assert link_id is not None

    def test_duplicate(self, db):
        rec = {
            "source_type": "complaint",
            "source_id": "11111111",
            "target_type": "recall",
            "target_id": "23V432000",
            "link_method": "make_model_year",
            "confidence": 0.85,
        }
        insert_cross_link(db, rec)
        db.commit()
        link_id = insert_cross_link(db, rec)
        assert link_id is None


class TestVehicles:
    def test_insert(self, db):
        vid = upsert_vehicle(db, "Toyota", "Camry", "TOYOTA", "CAMRY")
        db.commit()
        assert vid > 0

    def test_dedup(self, db):
        v1 = upsert_vehicle(db, "Toyota", "Camry", "TOYOTA", "CAMRY")
        v2 = upsert_vehicle(db, "TOYOTA", "CAMRY", "TOYOTA", "CAMRY")
        assert v1 == v2


class TestGetStats:
    def test_empty_db(self, db):
        s = get_stats(db)
        assert s["complaint_count"] == 0
        assert s["recall_count"] == 0

    def test_with_data(self, db):
        upsert_complaint(db, {
            "odi_number": 11111111,
            "manufacturer": "Toyota",
            "make": "TOYOTA", "model": "CAMRY", "model_year": 2023,
            "crash": 1, "fire": 0, "num_injuries": 1, "num_deaths": 0,
            "date_of_incident": "", "date_complaint_filed": "2024-01-15",
            "components": "ENGINE", "summary": "Test", "vin_prefix": "",
            "quality_score": 0.8,
        })
        db.commit()
        s = get_stats(db)
        assert s["complaint_count"] == 1
        assert s["crash_count"] == 1
        assert s["injury_total"] == 1
