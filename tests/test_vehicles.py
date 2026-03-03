"""Tests for vehicle normalization."""

import pytest

from src.normalization.vehicles import (
    normalize_make,
    normalize_model,
    make_model_key,
)


class TestNormalizeMake:
    def test_standard(self):
        assert normalize_make("Toyota") == "TOYOTA"

    def test_alias(self):
        assert normalize_make("CHEVY") == "CHEVROLET"

    def test_vw(self):
        assert normalize_make("VW") == "VOLKSWAGEN"

    def test_mercedes(self):
        assert normalize_make("MERCEDES BENZ") == "MERCEDES-BENZ"

    def test_strip_suffix(self):
        assert normalize_make("Toyota Motor Corporation") == "TOYOTA"

    def test_ford_motor(self):
        assert normalize_make("Ford Motor Company") == "FORD"

    def test_tesla_inc(self):
        assert normalize_make("Tesla, Inc.") == "TESLA"

    def test_unknown(self):
        assert normalize_make("Rivian") == "RIVIAN"

    def test_case_insensitive(self):
        assert normalize_make("ford") == "FORD"


class TestNormalizeModel:
    def test_standard(self):
        assert normalize_model("Camry") == "CAMRY"

    def test_strip_year_range(self):
        assert normalize_model("F-150 (2020-2023)") == "F-150"

    def test_whitespace(self):
        assert normalize_model("  Model 3  ") == "MODEL 3"


class TestMakeModelKey:
    def test_standard(self):
        assert make_model_key("Toyota", "Camry") == "TOYOTA|CAMRY"

    def test_normalized(self):
        assert make_model_key("CHEVY", "SILVERADO 1500") == "CHEVROLET|SILVERADO 1500"
