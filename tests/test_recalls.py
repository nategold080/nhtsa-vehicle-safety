"""Tests for recalls parser."""

import pytest

from src.scrapers.recalls import _parse_recall_result, _normalize_date, _safe_int


class TestParseRecallResult:
    def test_standard(self):
        item = {
            "NHTSACampaignNumber": "23V432000",
            "Manufacturer": "Toyota Motor Engineering & Manufacturing",
            "Make": "TOYOTA",
            "Model": "CAMRY",
            "ModelYear": "2023",
            "ReportReceivedDate": "15/06/2023",
            "Component": "WHEELS:LUGS/NUTS/BOLTS/STUDS",
            "Summary": "Lug nuts may be loose.",
            "Consequence": "Wheel detachment risk.",
            "Remedy": "Dealers will inspect and tighten.",
            "Notes": "Contact Toyota at 1-800-331-4331.",
            "PotentialNumberofUnitsAffected": "5000",
            "parkIt": True,
            "parkOutSide": False,
        }
        rec = _parse_recall_result(item)
        assert rec is not None
        assert rec["campaign_number"] == "23V432000"
        assert rec["manufacturer"] == "Toyota Motor Engineering & Manufacturing"
        assert rec["make"] == "TOYOTA"
        assert rec["model"] == "CAMRY"
        assert rec["model_year"] == 2023
        assert rec["report_received_date"] == "2023-06-15"
        assert rec["component"] == "WHEELS:LUGS/NUTS/BOLTS/STUDS"
        assert rec["num_potentially_affected"] == 5000
        assert rec["park_it"] == 1
        assert rec["park_outside"] == 0

    def test_no_campaign(self):
        item = {"Manufacturer": "Test"}
        rec = _parse_recall_result(item)
        assert rec is None

    def test_fallback_make_model(self):
        item = {
            "NHTSACampaignNumber": "24V001000",
            "Manufacturer": "Ford",
            "ReportReceivedDate": "01/01/2024",
            "Component": "BRAKES",
            "Summary": "Brake issue.",
            "Consequence": "",
            "Remedy": "",
            "Notes": "",
        }
        rec = _parse_recall_result(item, make="Ford", model="F-150", model_year=2024)
        assert rec["make"] == "FORD"
        assert rec["model"] == "F-150"
        assert rec["model_year"] == 2024


class TestNormalizeDate:
    def test_ddmmyyyy(self):
        assert _normalize_date("15/06/2023") == "2023-06-15"

    def test_empty(self):
        assert _normalize_date("") == ""


class TestSafeInt:
    def test_string(self):
        assert _safe_int("5000") == 5000

    def test_none(self):
        assert _safe_int(None) == 0

    def test_empty(self):
        assert _safe_int("") == 0

    def test_int(self):
        assert _safe_int(42) == 42
