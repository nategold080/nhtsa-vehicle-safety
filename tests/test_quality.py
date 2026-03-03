"""Tests for quality scoring."""

import pytest

from src.validation.quality import (
    score_complaint,
    score_recall,
    score_investigation,
    MIN_THRESHOLD,
)


class TestScoreComplaint:
    def test_full_record(self):
        rec = {
            "odi_number": 12345678,
            "manufacturer": "Toyota",
            "make": "TOYOTA",
            "model": "CAMRY",
            "model_year": 2023,
            "date_complaint_filed": "2024-01-15",
            "components": "ENGINE",
            "summary": "Engine stalled while driving on highway at 60mph.",
            "vin_prefix": "4T1K1234567",
        }
        qs = score_complaint(rec)
        assert qs.score == 1.0

    def test_minimal_record(self):
        rec = {
            "odi_number": 12345678,
            "make": "TOYOTA",
            "model": "CAMRY",
            "model_year": 2023,
        }
        qs = score_complaint(rec)
        assert qs.score >= MIN_THRESHOLD

    def test_empty_record(self):
        rec = {}
        qs = score_complaint(rec)
        assert qs.score == 0.0

    def test_partial_record(self):
        rec = {
            "odi_number": 12345678,
            "make": "FORD",
            "model": "F-150",
            "model_year": 2022,
            "components": "BRAKES",
            "summary": "Short",
        }
        qs = score_complaint(rec)
        assert 0.4 < qs.score < 1.0


class TestScoreRecall:
    def test_full_record(self):
        rec = {
            "campaign_number": "23V432000",
            "manufacturer": "Toyota",
            "make": "TOYOTA",
            "model": "CAMRY",
            "model_year": 2023,
            "report_received_date": "2023-06-15",
            "component": "WHEELS",
            "summary": "Lug nuts may be loose on certain vehicles.",
            "consequence": "Wheel detachment may cause a crash.",
            "remedy": "Dealers will inspect and tighten lug nuts.",
        }
        qs = score_recall(rec)
        assert qs.score == 1.0

    def test_empty(self):
        rec = {}
        qs = score_recall(rec)
        assert qs.score == 0.0


class TestScoreInvestigation:
    def test_full_record(self):
        rec = {
            "investigation_number": "PE24001",
            "investigation_type": "PE",
            "status": "Closed",
            "open_date": "2024-01-15",
            "subject": "Transmission sudden downshift without warning",
            "description": "NHTSA opened investigation into instances of unexpected downshifting.",
            "make": "FORD",
        }
        qs = score_investigation(rec)
        assert qs.score == 1.0

    def test_empty(self):
        rec = {}
        qs = score_investigation(rec)
        assert qs.score == 0.0
