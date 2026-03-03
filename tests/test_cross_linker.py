"""Tests for cross-linking logic."""

import sqlite3

import pytest

from src.storage.database import (
    init_db,
    upsert_complaint,
    upsert_recall,
    upsert_investigation,
)
from src.normalization.cross_linker import (
    link_complaints_to_recalls,
    link_complaints_to_investigations,
    link_recalls_to_investigations,
    cross_link_all,
)


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


class TestLinkComplaintsToRecalls:
    def test_basic_link(self, db):
        upsert_complaint(db, {
            "odi_number": 1001,
            "manufacturer": "Toyota", "make": "TOYOTA", "model": "CAMRY",
            "model_year": 2023, "crash": 0, "fire": 0,
            "num_injuries": 0, "num_deaths": 0,
            "date_of_incident": "", "date_complaint_filed": "2024-01-15",
            "components": "WHEELS", "summary": "Wheel noise",
            "vin_prefix": "", "quality_score": 0.8,
        })
        upsert_recall(db, {
            "campaign_number": "23V432000",
            "manufacturer": "Toyota", "make": "TOYOTA", "model": "CAMRY",
            "model_year": 2023, "report_received_date": "2023-06-15",
            "component": "WHEELS:LUGS/NUTS/BOLTS/STUDS",
            "summary": "Loose lug nuts",
            "consequence": "", "remedy": "", "notes": "",
            "num_potentially_affected": 5000,
            "park_it": 0, "park_outside": 0, "quality_score": 0.9,
        })
        db.commit()

        count = link_complaints_to_recalls(db)
        db.commit()
        assert count >= 1

        links = db.execute("SELECT * FROM cross_links WHERE source_type = 'complaint'").fetchall()
        assert len(links) >= 1
        assert links[0]["target_id"] == "23V432000"

    def test_no_match_different_model(self, db):
        upsert_complaint(db, {
            "odi_number": 2001,
            "manufacturer": "Toyota", "make": "TOYOTA", "model": "COROLLA",
            "model_year": 2023, "crash": 0, "fire": 0,
            "num_injuries": 0, "num_deaths": 0,
            "date_of_incident": "", "date_complaint_filed": "2024-01-15",
            "components": "ENGINE", "summary": "Engine issue",
            "vin_prefix": "", "quality_score": 0.8,
        })
        upsert_recall(db, {
            "campaign_number": "23V999000",
            "manufacturer": "Toyota", "make": "TOYOTA", "model": "CAMRY",
            "model_year": 2023, "report_received_date": "2023-06-15",
            "component": "ENGINE",
            "summary": "Engine stall",
            "consequence": "", "remedy": "", "notes": "",
            "num_potentially_affected": 1000,
            "park_it": 0, "park_outside": 0, "quality_score": 0.9,
        })
        db.commit()

        count = link_complaints_to_recalls(db)
        assert count == 0


class TestLinkComplaintsToInvestigations:
    def test_year_range_match(self, db):
        upsert_complaint(db, {
            "odi_number": 3001,
            "manufacturer": "Ford", "make": "FORD", "model": "F-150",
            "model_year": 2016, "crash": 0, "fire": 0,
            "num_injuries": 0, "num_deaths": 0,
            "date_of_incident": "", "date_complaint_filed": "2024-01-15",
            "components": "POWER TRAIN", "summary": "Transmission issue",
            "vin_prefix": "", "quality_score": 0.8,
        })
        upsert_investigation(db, {
            "investigation_number": "PE25002",
            "nhtsa_id": "102047", "make": "FORD", "model": "F-150",
            "model_year_start": 2015, "model_year_end": 2017,
            "investigation_type": "PE", "status": "Open",
            "open_date": "2025-03-21", "close_date": "",
            "subject": "Unexpected transmission downshift",
            "description": "Investigating downshift without driver input.",
            "num_complaints": 329, "num_vehicles": 1000000,
            "components": "POWER TRAIN", "quality_score": 0.9,
        })
        db.commit()

        count = link_complaints_to_investigations(db)
        db.commit()
        assert count >= 1


class TestCrossLinkAll:
    def test_runs_all(self, db):
        # Just verify it doesn't error on empty DB
        results = cross_link_all(db)
        assert "complaint_to_recall" in results
        assert "complaint_to_investigation" in results
        assert "recall_to_investigation" in results
