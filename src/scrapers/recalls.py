"""Download and parse NHTSA recall data via API."""

from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "raw" / "recalls"
HEADERS = {
    "User-Agent": "DataFactory/1.0 (NHTSA-Vehicle-Safety; research; nathanmauricegoldberg@gmail.com)",
}
DELAY = 0.2  # 5 req/sec


def fetch_recalls_for_vehicle(
    make: str,
    model: str,
    model_year: int,
    client: httpx.Client | None = None,
) -> list[dict]:
    """Fetch recall campaigns for a specific vehicle."""
    url = "https://api.nhtsa.gov/recalls/recallsByVehicle"
    params = {"make": make, "model": model, "modelYear": str(model_year)}

    _client = client or httpx.Client(timeout=30, headers=HEADERS)
    try:
        r = _client.get(url, params=params)
        r.raise_for_status()
        data = r.json()
    finally:
        if client is None:
            _client.close()

    results = []
    for item in data.get("results", []):
        rec = _parse_recall_result(item, make, model, model_year)
        if rec:
            results.append(rec)

    return results


def fetch_recall_by_campaign(
    campaign_number: str,
    client: httpx.Client | None = None,
) -> list[dict]:
    """Fetch recall details by campaign number."""
    url = "https://api.nhtsa.gov/recalls/campaignNumber"
    params = {"campaignNumber": campaign_number}

    _client = client or httpx.Client(timeout=30, headers=HEADERS)
    try:
        r = _client.get(url, params=params)
        r.raise_for_status()
        data = r.json()
    finally:
        if client is None:
            _client.close()

    results = []
    for item in data.get("results", []):
        rec = _parse_recall_result(item)
        if rec:
            results.append(rec)

    return results


def fetch_recalls_bulk(
    makes: list[str],
    model_years: list[int],
    progress_callback=None,
) -> list[dict]:
    """Fetch recalls for multiple makes and years.

    Iterates: for each make, get models with recalls via products API,
    then fetch recalls per model.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    all_recalls = {}
    total = len(makes) * len(model_years)
    processed = 0

    with httpx.Client(timeout=30, headers=HEADERS, follow_redirects=True) as client:
        for make in makes:
            for year in model_years:
                processed += 1
                cache_file = CACHE_DIR / f"recalls_{make}_{year}.json"

                if cache_file.exists():
                    with open(cache_file) as f:
                        cached = json.load(f)
                    for rec in cached:
                        all_recalls[rec["campaign_number"]] = rec
                    if progress_callback:
                        progress_callback(processed, total, f"{make} {year} (cached)")
                    continue

                # Get models with recalls for this make/year
                try:
                    models_r = client.get(
                        "https://api.nhtsa.gov/products/vehicle/models",
                        params={"modelYear": str(year), "make": make, "issueType": "r"},
                    )
                    models_r.raise_for_status()
                    models_data = models_r.json()
                    models = list({m["model"] for m in models_data.get("results", [])})
                except Exception:
                    models = []

                time.sleep(DELAY)

                year_recalls = []
                for model in models:
                    try:
                        recalls = fetch_recalls_for_vehicle(make, model, year, client)
                        for rec in recalls:
                            if rec["campaign_number"] not in all_recalls:
                                all_recalls[rec["campaign_number"]] = rec
                                year_recalls.append(rec)
                    except Exception:
                        pass
                    time.sleep(DELAY)

                # Cache
                with open(cache_file, "w") as f:
                    json.dump(year_recalls, f)

                if progress_callback:
                    progress_callback(processed, total, f"{make} {year}: {len(year_recalls)} recalls")

    return list(all_recalls.values())


def _parse_recall_result(
    item: dict,
    make: str = "",
    model: str = "",
    model_year: int = 0,
) -> dict | None:
    """Parse a single recall API result into a record."""
    campaign = item.get("NHTSACampaignNumber", "")
    if not campaign:
        return None

    # Try to get year from item or fallback
    year = model_year
    if not year:
        try:
            year = int(item.get("ModelYear", 0))
        except (ValueError, TypeError):
            year = 0

    return {
        "campaign_number": campaign,
        "manufacturer": item.get("Manufacturer", ""),
        "make": (item.get("Make") or make).upper(),
        "model": (item.get("Model") or model).upper(),
        "model_year": year,
        "report_received_date": _normalize_date(item.get("ReportReceivedDate", "")),
        "component": item.get("Component", ""),
        "summary": item.get("Summary", ""),
        "consequence": item.get("Consequence", ""),
        "remedy": item.get("Remedy", ""),
        "notes": item.get("Notes", ""),
        "num_potentially_affected": _safe_int(item.get("PotentialNumberofUnitsAffected", 0)),
        "park_it": 1 if item.get("parkIt") else 0,
        "park_outside": 1 if item.get("parkOutSide") else 0,
    }


def _normalize_date(val: str) -> str:
    """Normalize API date (DD/MM/YYYY) to YYYY-MM-DD."""
    if not val:
        return ""
    parts = val.split("/")
    if len(parts) == 3:
        return f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
    return val


def _safe_int(val) -> int:
    """Safely convert to int."""
    try:
        return int(val) if val else 0
    except (ValueError, TypeError):
        return 0
