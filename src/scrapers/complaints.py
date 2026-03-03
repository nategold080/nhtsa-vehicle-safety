"""Download and parse NHTSA complaints flat file."""

from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path

import httpx

FLAT_FILE_URL = "https://static.nhtsa.gov/odi/ffdd/cmpl/FLAT_CMPL.zip"
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "raw"
CACHE_FILE = CACHE_DIR / "FLAT_CMPL.txt"

HEADERS = {
    "User-Agent": "DataFactory/1.0 (NHTSA-Vehicle-Safety; research; nathanmauricegoldberg@gmail.com)",
}

# Column indices for the tab-delimited flat file (per NHTSA documentation)
# The flat file has these columns in order:
FLAT_COLUMNS = [
    "CMPLID",       # 0 - Complaint ODI number
    "ODESSION",      # 1 - ODI number (duplicate)
    "MFR_NAME",      # 2 - Manufacturer name
    "MAKETXT",       # 3 - Make
    "MODELTXT",      # 4 - Model
    "YEARTXT",       # 5 - Model year
    "CRASH",         # 6 - Crash (Y/N)
    "FAILDATE",      # 7 - Date of failure
    "FIRE",          # 8 - Fire (Y/N)
    "INJURED",       # 9 - Number injured
    "DEATHS",        # 10 - Number of deaths
    "DATEA",         # 11 - Date complaint filed
    "LDATE",         # 12 - Date record last modified
    "CDESCR",        # 13 - Component description
    "CITY",          # 14 - City
    "STATE",         # 15 - State
    "VIN",           # 16 - VIN
    "PROD_TYPE",     # 17 - Product type (V=vehicle, T=tire, E=equipment, C=child seat)
    "STXT",          # 18 - Summary text
    "MEDICAL_ATTN",  # 19 - Medical attention (Y/N)
    "VEHICLES_TOWED_YN",  # 20 - Vehicle towed (Y/N)
]


def download_complaints_flat_file(force: bool = False) -> Path:
    """Download the NHTSA complaints flat file.

    Returns path to the extracted text file.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if CACHE_FILE.exists() and not force:
        return CACHE_FILE

    zip_path = CACHE_DIR / "FLAT_CMPL.zip"

    with httpx.Client(timeout=600, headers=HEADERS, follow_redirects=True) as client:
        with client.stream("GET", FLAT_FILE_URL) as response:
            response.raise_for_status()
            with open(zip_path, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                    f.write(chunk)

    # Extract
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        txt_name = next((n for n in names if n.endswith(".txt")), names[0])
        zf.extract(txt_name, CACHE_DIR)
        extracted = CACHE_DIR / txt_name
        if extracted != CACHE_FILE:
            extracted.rename(CACHE_FILE)

    zip_path.unlink(missing_ok=True)
    return CACHE_FILE


def parse_complaints_flat_file(
    file_path: Path | None = None,
    min_year: int = 2015,
    max_records: int | None = None,
) -> list[dict]:
    """Parse the flat file into structured records.

    Args:
        file_path: Path to the flat file (default: cached file).
        min_year: Only include complaints for model years >= this.
        max_records: Stop after this many records (for testing).
    """
    path = file_path or CACHE_FILE
    if not path.exists():
        raise FileNotFoundError(f"Flat file not found: {path}. Run download first.")

    records = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f, delimiter="\t")
        for row in reader:
            if len(row) < 19:
                continue

            try:
                year = int(row[5]) if row[5].strip() else 0
            except ValueError:
                continue

            if year < min_year:
                continue

            odi = row[0].strip()
            if not odi or not odi.isdigit():
                continue

            rec = {
                "odi_number": int(odi),
                "manufacturer": row[2].strip(),
                "make": row[3].strip().upper(),
                "model": row[4].strip().upper(),
                "model_year": year,
                "crash": 1 if row[6].strip().upper() == "Y" else 0,
                "fire": 1 if row[8].strip().upper() == "Y" else 0,
                "num_injuries": _safe_int(row[9]),
                "num_deaths": _safe_int(row[10]),
                "date_of_incident": _normalize_date(row[7]),
                "date_complaint_filed": _normalize_date(row[11]),
                "components": row[13].strip(),
                "summary": row[18].strip() if len(row) > 18 else "",
                "vin_prefix": row[16].strip()[:11] if len(row) > 16 and row[16].strip() else "",
            }
            records.append(rec)

            if max_records and len(records) >= max_records:
                break

    return records


def fetch_complaints_api(
    make: str,
    model: str,
    model_year: int,
    client: httpx.Client | None = None,
) -> list[dict]:
    """Fetch complaints for a specific vehicle from the API."""
    url = "https://api.nhtsa.gov/complaints/complaintsByVehicle"
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
        rec = {
            "odi_number": item.get("odiNumber", 0),
            "manufacturer": item.get("manufacturer", ""),
            "make": make.upper(),
            "model": model.upper(),
            "model_year": model_year,
            "crash": 1 if item.get("crash") else 0,
            "fire": 1 if item.get("fire") else 0,
            "num_injuries": item.get("numberOfInjuries", 0) or 0,
            "num_deaths": item.get("numberOfDeaths", 0) or 0,
            "date_of_incident": _normalize_api_date(item.get("dateOfIncident", "")),
            "date_complaint_filed": _normalize_api_date(item.get("dateComplaintFiled", "")),
            "components": item.get("components", ""),
            "summary": item.get("summary", ""),
            "vin_prefix": (item.get("vin") or "")[:11],
        }
        results.append(rec)

    return results


def _safe_int(val: str) -> int:
    """Safely convert a string to int."""
    val = val.strip()
    if not val:
        return 0
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return 0


def _normalize_date(val: str) -> str:
    """Normalize flat file date (YYYYMMDD) to YYYY-MM-DD."""
    val = val.strip()
    if len(val) == 8 and val.isdigit():
        return f"{val[:4]}-{val[4:6]}-{val[6:8]}"
    return val


def _normalize_api_date(val: str) -> str:
    """Normalize API date (MM/DD/YYYY) to YYYY-MM-DD."""
    if not val:
        return ""
    parts = val.split("/")
    if len(parts) == 3:
        return f"{parts[2]}-{parts[0].zfill(2)}-{parts[1].zfill(2)}"
    return val
