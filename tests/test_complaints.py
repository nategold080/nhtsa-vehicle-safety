"""Tests for complaints parser."""

import io
import tempfile
from pathlib import Path

import pytest

from src.scrapers.complaints import (
    parse_complaints_flat_file,
    _safe_int,
    _normalize_date,
    _normalize_api_date,
)


class TestSafeInt:
    def test_valid(self):
        assert _safe_int("42") == 42

    def test_float_string(self):
        assert _safe_int("3.0") == 3

    def test_empty(self):
        assert _safe_int("") == 0

    def test_whitespace(self):
        assert _safe_int("  ") == 0

    def test_invalid(self):
        assert _safe_int("abc") == 0


class TestNormalizeDate:
    def test_yyyymmdd(self):
        assert _normalize_date("20240315") == "2024-03-15"

    def test_short(self):
        assert _normalize_date("2024") == "2024"

    def test_empty(self):
        assert _normalize_date("") == ""


class TestNormalizeApiDate:
    def test_standard(self):
        assert _normalize_api_date("03/14/2024") == "2024-03-14"

    def test_single_digit(self):
        assert _normalize_api_date("1/5/2024") == "2024-01-05"

    def test_empty(self):
        assert _normalize_api_date("") == ""


class TestParseFlat:
    def test_parse_basic(self, tmp_path):
        """Test parsing a minimal flat file."""
        lines = [
            # CMPLID ODI MFR MAKE MODEL YEAR CRASH FAILDATE FIRE INJ DEATH DATEA LDATE CDESCR CITY STATE VIN PRODTYPE SUMMARY
            "11111111\t11111111\tToyota Motor\tTOYOTA\tCAMRY\t2023\tN\t20240101\tN\t0\t0\t20240115\t20240115\tENGINE\tANYCITY\tCA\t4T1K1234\tV\tEngine stalled while driving.\tN\tN",
            "22222222\t22222222\tFord Motor\tFORD\tF-150\t2022\tY\t20230601\tN\t2\t0\t20230610\t20230610\tBRAKES\tDALLAS\tTX\t1FTFW1E5\tV\tBrakes failed on highway.\tY\tN",
            "33333333\t33333333\tTesla Inc\tTESLA\tMODEL 3\t2024\tN\t20240301\tY\t0\t0\t20240310\t20240310\tELECTRICAL SYSTEM\tLA\tCA\t5YJ3E1EA\tV\tBattery fire.\tN\tN",
        ]
        flat_file = tmp_path / "test.txt"
        flat_file.write_text("\n".join(lines))

        records = parse_complaints_flat_file(flat_file, min_year=2020)
        assert len(records) == 3
        assert records[0]["odi_number"] == 11111111
        assert records[0]["make"] == "TOYOTA"
        assert records[0]["model"] == "CAMRY"
        assert records[0]["model_year"] == 2023
        assert records[0]["crash"] == 0
        assert records[0]["fire"] == 0
        assert records[0]["date_of_incident"] == "2024-01-01"
        assert records[0]["components"] == "ENGINE"

    def test_min_year_filter(self, tmp_path):
        """Test that min_year filter works."""
        lines = [
            "11111111\t11111111\tTest\tFORD\tFOCUS\t2010\tN\t20100101\tN\t0\t0\t20100101\t20100101\tENGINE\tNY\tNY\tABC\tV\tTest\tN\tN",
            "22222222\t22222222\tTest\tFORD\tFOCUS\t2020\tN\t20200101\tN\t0\t0\t20200101\t20200101\tENGINE\tNY\tNY\tABC\tV\tTest\tN\tN",
        ]
        flat_file = tmp_path / "test.txt"
        flat_file.write_text("\n".join(lines))

        records = parse_complaints_flat_file(flat_file, min_year=2015)
        assert len(records) == 1
        assert records[0]["model_year"] == 2020

    def test_max_records(self, tmp_path):
        """Test max_records limit."""
        lines = [
            f"{i}\t{i}\tTest\tFORD\tFOCUS\t2023\tN\t20230101\tN\t0\t0\t20230101\t20230101\tENGINE\tNY\tNY\tABC\tV\tTest\tN\tN"
            for i in range(100000, 100010)
        ]
        flat_file = tmp_path / "test.txt"
        flat_file.write_text("\n".join(lines))

        records = parse_complaints_flat_file(flat_file, min_year=2020, max_records=3)
        assert len(records) == 3

    def test_crash_fire_flags(self, tmp_path):
        lines = [
            "11111111\t11111111\tTest\tFORD\tF-150\t2023\tY\t20230601\tY\t2\t1\t20230610\t20230610\tBRAKES\tNY\tNY\tABC\tV\tCrash and fire.\tY\tY",
        ]
        flat_file = tmp_path / "test.txt"
        flat_file.write_text("\n".join(lines))

        records = parse_complaints_flat_file(flat_file, min_year=2020)
        assert records[0]["crash"] == 1
        assert records[0]["fire"] == 1
        assert records[0]["num_injuries"] == 2
        assert records[0]["num_deaths"] == 1

    def test_skip_short_rows(self, tmp_path):
        """Rows with < 19 columns should be skipped."""
        lines = [
            "11111111\t11111111\tTest",
            "22222222\t22222222\tTest\tFORD\tFOCUS\t2023\tN\t20230101\tN\t0\t0\t20230101\t20230101\tENGINE\tNY\tNY\tABC\tV\tTest\tN\tN",
        ]
        flat_file = tmp_path / "test.txt"
        flat_file.write_text("\n".join(lines))

        records = parse_complaints_flat_file(flat_file, min_year=2020)
        assert len(records) == 1
        assert records[0]["odi_number"] == 22222222
        assert records[0]["make"] == "FORD"
