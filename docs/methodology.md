# NHTSA Vehicle Safety Defect Tracker — Methodology

**Author:** Nathan Goldberg | nathanmauricegoldberg@gmail.com
**Date:** March 2026
**Version:** 1.0

## Overview

This document describes the methodology for building a cross-linked database of NHTSA vehicle safety data spanning complaints, investigations, and recalls. The project enables analysis of the full defect lifecycle: from consumer complaint patterns to investigation triggers to recall outcomes.

## Data Sources

### Primary Source: NHTSA Complaints Flat File
- **Source:** National Highway Traffic Safety Administration (NHTSA), Office of Defects Investigation (ODI)
- **File:** FLAT_CMPL.zip (~341 MB compressed, tab-delimited text)
- **Coverage:** Vehicle owner complaints from 1949 to present, updated daily
- **Fields:** ODI number, manufacturer, make, model, model year, crash/fire flags, injuries, deaths, incident/filing dates, VIN, component category, free-text summary
- **Filtering:** Records are filtered to model year 2015+ for relevance

### Secondary Source: NHTSA Investigations Flat File
- **Source:** NHTSA ODI
- **File:** FLAT_INV.zip (tab-delimited text)
- **Coverage:** All ODI investigations (Preliminary Evaluations, Engineering Analyses, Audit Queries, Defect Petitions)
- **Fields:** Investigation number, make, model, model year, component, manufacturer, open/close dates, subject, full description

### Tertiary Source: NHTSA Recalls API
- **Source:** NHTSA Vehicle Safety API (api.nhtsa.gov)
- **Coverage:** All recall campaigns, searchable by make/model/year or campaign number
- **Fields:** Campaign number, manufacturer, make, model, model year, report date, component, summary, consequence, remedy, affected unit count, Park It advisory
- **Access method:** JSON REST API via Products API (make/model index) + Recalls API (per vehicle)

## Extraction Pipeline

### Step 1: Data Download
- Download FLAT_CMPL.zip (complaints) and FLAT_INV.zip (investigations) from NHTSA static files
- Both are ZIP-compressed tab-delimited text files
- Files cached locally to prevent re-downloading

### Step 2: Complaint Parsing
- Parse tab-delimited file with 21 columns per NHTSA documentation
- Filter to model year >= 2015 (configurable)
- Normalize dates from YYYYMMDD to ISO format
- Normalize crash/fire flags from Y/N to boolean
- Deduplicate by ODI number (primary key)

### Step 3: Investigation Parsing
- Parse tab-delimited file with 11 columns
- Extract investigation type from number prefix (PE, EA, AQ, DP)
- Infer status from close_date presence
- Deduplicate by investigation number

### Step 4: Recall Fetching
- Use NHTSA Products API to enumerate models with recalls for each make/year combination
- Fetch recall details per vehicle via Recalls API
- Deduplicate by campaign number (one recall may cover multiple models)
- Rate limit: 5 requests/second with identified User-Agent

### Step 5: Vehicle Normalization
- Normalize make names via alias mapping (e.g., "CHEVY" → "CHEVROLET", "VW" → "VOLKSWAGEN")
- Strip manufacturer suffixes ("Motor Company", "Inc.", "LLC")
- Create deduplicated vehicle make/model registry

### Step 6: Cross-Linking
Three cross-linking strategies connect records across datasets:

**Complaints → Recalls:** Match by normalized make + model + model_year. Component overlap checked using prefix matching (e.g., complaint "WHEELS" matches recall "WHEELS:LUGS/NUTS/BOLTS/STUDS"). Confidence: 0.9 (component match) or 0.6 (make/model/year only).

**Complaints → Investigations:** Match by normalized make + model with year-in-range check (complaint model_year between investigation year_start and year_end). Confidence: 0.7 (model match) or 0.5 (make-only match).

**Recalls → Investigations:** Match by normalized make + model + year range overlap. Confidence: 0.8.

### Step 7: Quality Scoring
Each record scored 0.0-1.0 with type-specific component weights. Minimum threshold: 0.40. Components include: identifier presence, make/model completeness, date availability, summary text length, component categorization.

### Step 8: Storage
- SQLite database with WAL mode for concurrent read access
- Tables: complaints, recalls, investigations, cross_links, vehicles
- Indexed by make/model/year, components, dates

## Limitations

1. **Complaint volume bias:** Makes with larger market share naturally have more complaints. Per-capita rates should be used for comparison.
2. **Self-reported data:** Complaints are consumer-submitted and unverified. Crash/fire flags rely on consumer reports.
3. **Investigation coverage:** Only NHTSA-initiated investigations are included. Manufacturer-initiated recalls without prior NHTSA investigation are captured via the recalls dataset.
4. **Flat file format:** NHTSA flat files have minimal documentation. Column assignments verified by manual inspection of data patterns.
5. **Recall deduplication:** One recall campaign may cover many makes/models. We store one record per campaign-make-model combination.

## Quality Assurance

- All extraction is rule-based (zero LLM dependency)
- Automated test suite with 88 tests covering parsers, normalization, quality scoring, database, cross-linking, exports, and pipeline integration
- Cross-link confidence scores tracked per link
- Quality scoring with component-level breakdown

## Output Format

Available exports: CSV, JSON, Excel (styled), Markdown summary, SQLite database, Streamlit dashboard (8 sections).

## Reproducibility

```bash
python -m src.cli pipeline --min-year 2015
```
