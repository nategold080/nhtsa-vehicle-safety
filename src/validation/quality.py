"""Quality scoring for NHTSA records."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class QualityScore:
    score: float
    components: dict[str, float]


# Weights for complaint quality scoring
COMPLAINT_WEIGHTS = {
    "has_odi_number": 0.15,
    "has_make_model": 0.20,
    "has_model_year": 0.10,
    "has_date": 0.10,
    "has_component": 0.15,
    "has_summary": 0.15,
    "has_manufacturer": 0.10,
    "has_vin": 0.05,
}

# Weights for recall quality scoring
RECALL_WEIGHTS = {
    "has_campaign_number": 0.15,
    "has_make_model": 0.15,
    "has_model_year": 0.10,
    "has_date": 0.10,
    "has_component": 0.15,
    "has_summary": 0.10,
    "has_consequence": 0.10,
    "has_remedy": 0.10,
    "has_manufacturer": 0.05,
}

# Weights for investigation quality scoring
INVESTIGATION_WEIGHTS = {
    "has_investigation_number": 0.20,
    "has_type": 0.10,
    "has_status": 0.10,
    "has_date": 0.15,
    "has_subject": 0.20,
    "has_description": 0.15,
    "has_make": 0.10,
}

MIN_THRESHOLD = 0.40


def score_complaint(rec: dict) -> QualityScore:
    """Score a complaint record for quality."""
    components = {
        "has_odi_number": 1.0 if rec.get("odi_number") else 0.0,
        "has_make_model": 1.0 if rec.get("make") and rec.get("model") else 0.0,
        "has_model_year": 1.0 if rec.get("model_year", 0) > 1900 else 0.0,
        "has_date": 1.0 if rec.get("date_complaint_filed") else 0.0,
        "has_component": 1.0 if rec.get("components") else 0.0,
        "has_summary": 1.0 if len(rec.get("summary", "")) > 10 else 0.0,
        "has_manufacturer": 1.0 if rec.get("manufacturer") else 0.0,
        "has_vin": 1.0 if rec.get("vin_prefix") else 0.0,
    }

    score = sum(
        COMPLAINT_WEIGHTS[k] * v for k, v in components.items()
    )
    return QualityScore(score=round(score, 3), components=components)


def score_recall(rec: dict) -> QualityScore:
    """Score a recall record for quality."""
    components = {
        "has_campaign_number": 1.0 if rec.get("campaign_number") else 0.0,
        "has_make_model": 1.0 if rec.get("make") and rec.get("model") else 0.0,
        "has_model_year": 1.0 if rec.get("model_year", 0) > 1900 else 0.0,
        "has_date": 1.0 if rec.get("report_received_date") else 0.0,
        "has_component": 1.0 if rec.get("component") else 0.0,
        "has_summary": 1.0 if len(rec.get("summary", "")) > 10 else 0.0,
        "has_consequence": 1.0 if len(rec.get("consequence", "")) > 10 else 0.0,
        "has_remedy": 1.0 if len(rec.get("remedy", "")) > 10 else 0.0,
        "has_manufacturer": 1.0 if rec.get("manufacturer") else 0.0,
    }

    score = sum(
        RECALL_WEIGHTS[k] * v for k, v in components.items()
    )
    return QualityScore(score=round(score, 3), components=components)


def score_investigation(rec: dict) -> QualityScore:
    """Score an investigation record for quality."""
    components = {
        "has_investigation_number": 1.0 if rec.get("investigation_number") else 0.0,
        "has_type": 1.0 if rec.get("investigation_type") else 0.0,
        "has_status": 1.0 if rec.get("status") else 0.0,
        "has_date": 1.0 if rec.get("open_date") else 0.0,
        "has_subject": 1.0 if len(rec.get("subject", "")) > 5 else 0.0,
        "has_description": 1.0 if len(rec.get("description", "")) > 10 else 0.0,
        "has_make": 1.0 if rec.get("make") else 0.0,
    }

    score = sum(
        INVESTIGATION_WEIGHTS[k] * v for k, v in components.items()
    )
    return QualityScore(score=round(score, 3), components=components)
