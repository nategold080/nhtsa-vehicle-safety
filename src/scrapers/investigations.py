"""Download and parse NHTSA investigation data."""

from __future__ import annotations

import csv
import io
import json
import re
import time
import zipfile
from pathlib import Path

import httpx

FLAT_FILE_URL = "https://static.nhtsa.gov/odi/ffdd/inv/FLAT_INV.zip"
API_URL = "https://api.nhtsa.gov/investigations"
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "raw"
CACHE_FILE = CACHE_DIR / "FLAT_INV.txt"

HEADERS = {
    "User-Agent": "DataFactory/1.0 (NHTSA-Vehicle-Safety; research; nathanmauricegoldberg@gmail.com)",
}


def download_investigations_flat_file(force: bool = False) -> Path:
    """Download the NHTSA investigations flat file."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if CACHE_FILE.exists() and not force:
        return CACHE_FILE

    zip_path = CACHE_DIR / "FLAT_INV.zip"
    with httpx.Client(timeout=300, headers=HEADERS, follow_redirects=True) as client:
        with client.stream("GET", FLAT_FILE_URL) as response:
            response.raise_for_status()
            with open(zip_path, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                    f.write(chunk)

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        txt_name = next((n for n in names if n.endswith(".txt")), names[0])
        zf.extract(txt_name, CACHE_DIR)
        extracted = CACHE_DIR / txt_name
        if extracted != CACHE_FILE:
            extracted.rename(CACHE_FILE)

    zip_path.unlink(missing_ok=True)
    return CACHE_FILE


def parse_investigations_flat_file(file_path: Path | None = None) -> list[dict]:
    """Parse investigations flat file into records."""
    path = file_path or CACHE_FILE
    if not path.exists():
        raise FileNotFoundError(f"Flat file not found: {path}. Run download first.")

    records = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f, delimiter="\t")
        for row in reader:
            if len(row) < 10:
                continue

            inv_num = row[0].strip()
            if not inv_num:
                continue

            # Actual NHTSA flat file columns:
            # 0: investigation_number
            # 1: make
            # 2: model
            # 3: model_year
            # 4: components
            # 5: manufacturer
            # 6: open_date (YYYYMMDD)
            # 7: close_date (YYYYMMDD)
            # 8: related_campaign_number (often empty)
            # 9: subject
            # 10: description
            model_year = _safe_int(row[3]) if len(row) > 3 else 0

            # Determine investigation type from prefix: PE=Preliminary Evaluation,
            # EA=Engineering Analysis, AQ=Audit Query, DP=Defect Petition, etc.
            inv_type = ""
            if inv_num[:2] in ("PE", "EA", "AQ", "DP", "RQ", "RD", "CI"):
                inv_type = inv_num[:2]

            rec = {
                "investigation_number": inv_num,
                "nhtsa_id": "",
                "make": row[1].strip().upper() if len(row) > 1 else "",
                "model": row[2].strip().upper() if len(row) > 2 else "",
                "model_year_start": model_year,
                "model_year_end": model_year,
                "investigation_type": inv_type,
                "status": "Closed" if (len(row) > 7 and row[7].strip()) else "Open",
                "open_date": _normalize_date(row[6]) if len(row) > 6 else "",
                "close_date": _normalize_date(row[7]) if len(row) > 7 else "",
                "subject": row[9].strip() if len(row) > 9 else "",
                "description": row[10].strip()[:5000] if len(row) > 10 else "",
                "num_complaints": 0,
                "num_vehicles": 0,
                "components": row[4].strip() if len(row) > 4 else "",
            }
            records.append(rec)

    return records


def fetch_investigations_api(
    make: str = "",
    model: str = "",
    client: httpx.Client | None = None,
) -> list[dict]:
    """Fetch investigations from the NHTSA API."""
    params = {}
    if make:
        params["make"] = make
    if model:
        params["model"] = model

    _client = client or httpx.Client(timeout=30, headers=HEADERS)
    try:
        r = _client.get(API_URL, params=params)
        r.raise_for_status()
        data = r.json()
    finally:
        if client is None:
            _client.close()

    results = []
    for item in data.get("results", []):
        rec = _parse_api_investigation(item)
        if rec:
            results.append(rec)

    return results


def _parse_api_investigation(item: dict) -> dict | None:
    """Parse an API investigation result."""
    inv_num = item.get("investigationNumber", "")
    if not inv_num:
        return None

    # Extract make/model/year from subject if available
    subject = item.get("subject", "")
    description = item.get("description", "")
    # Strip HTML from description
    description = re.sub(r"<[^>]+>", " ", description)
    description = re.sub(r"\s+", " ", description).strip()

    return {
        "investigation_number": inv_num,
        "nhtsa_id": str(item.get("nhtsaId", "")),
        "make": "",  # Not directly in API result
        "model": "",
        "model_year_start": item.get("issueYear", 0) or 0,
        "model_year_end": 0,
        "investigation_type": item.get("investigationType", ""),
        "status": item.get("status", ""),
        "open_date": item.get("openDate", ""),
        "close_date": item.get("latestActivityDate", ""),
        "subject": subject,
        "description": description[:5000],  # Cap at 5K chars
        "num_complaints": 0,
        "num_vehicles": 0,
        "components": "",
    }


def _safe_int(val: str) -> int:
    val = val.strip() if isinstance(val, str) else str(val)
    try:
        return int(float(val)) if val else 0
    except (ValueError, TypeError):
        return 0


def _normalize_date(val: str) -> str:
    val = val.strip()
    if len(val) == 8 and val.isdigit():
        return f"{val[:4]}-{val[4:6]}-{val[6:8]}"
    return val
