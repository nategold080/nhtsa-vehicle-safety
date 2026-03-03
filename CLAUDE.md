# NHTSA Vehicle Safety Defect Tracker

## Project Overview
Cross-linked database of NHTSA vehicle owner complaints, defect investigations, and recall campaigns. Traces the full defect lifecycle: complaint clusters → investigation triggers → recall outcomes. All data from public NHTSA sources.

## Data Sources

| Source | Type | Records | URL |
|--------|------|---------|-----|
| NHTSA Complaints Flat File | Bulk ZIP/TSV | 500K+ (2015+) | static.nhtsa.gov/odi/ffdd/cmpl/ |
| NHTSA Investigations Flat File | Bulk ZIP/TSV | 5K+ unique | static.nhtsa.gov/odi/ffdd/inv/ |
| NHTSA Recalls API | JSON API | 2K+ campaigns | api.nhtsa.gov/recalls/ |
| NHTSA Products API | JSON API | Make/model index | api.nhtsa.gov/products/ |

## Technical Standards
- Python 3.12+, SQLite WAL, Click CLI, Streamlit + Plotly
- Zero LLM dependency (rule-based extraction and cross-linking)
- Quality scoring on every record (weighted 0.0-1.0)
- Rate limit: 5 req/sec to NHTSA APIs, polite User-Agent
- Cache all raw data locally
- Dark theme dashboard: primaryColor="#0984E3", backgroundColor="#0E1117"
- Footer: "Built by Nathan Goldberg" + contact info

## Cross-Linking Strategy
1. **Complaints → Recalls**: Match by normalized make/model/year + component prefix overlap
2. **Complaints → Investigations**: Match by make/model with year-in-range check
3. **Recalls → Investigations**: Match by make/model/year range

## Quality Scoring
### Complaints
- has_odi_number (0.15), has_make_model (0.20), has_model_year (0.10)
- has_date (0.10), has_component (0.15), has_summary (0.15)
- has_manufacturer (0.10), has_vin (0.05)

### Recalls
- has_campaign_number (0.15), has_make_model (0.15), has_model_year (0.10)
- has_date (0.10), has_component (0.15), has_summary (0.10)
- has_consequence (0.10), has_remedy (0.10), has_manufacturer (0.05)

## SQLite Schema
- **complaints** — odi_number (PK), manufacturer, make, model, model_year, crash, fire, injuries, deaths, incident/filed dates, components, summary, VIN prefix
- **recalls** — campaign_number (PK), manufacturer, make, model, model_year, date, component, summary, consequence, remedy, affected count, park_it flags
- **investigations** — investigation_number (PK), make, model, year_start, year_end, type (PE/EA/AQ/DP), status, dates, subject, description, components
- **cross_links** — source_type+id → target_type+id, link_method, confidence
- **vehicles** — deduplicated make/model pairs with normalized names

## Dashboard Sections (8)
1. Overview — KPI cards, top makes, top components
2. Complaint Explorer — Search/filter by make/model/crash/fire
3. Recall Tracker — Park It alerts, affected vehicles
4. Investigation Monitor — Status/type breakdown
5. Vehicle Deep Dive — Per-vehicle complaints + recalls + investigations
6. Safety Trends — Monthly complaint/crash/fire volumes
7. Component Analysis — Component ranking, death rate analysis
8. Data Quality — Per-table quality metrics, cross-link coverage

## Target Audiences
- Lemon law firms, product liability attorneys
- Insurance companies (Verisk, LexisNexis Risk Solutions)
- Fleet management companies
- Auto industry research/media
- Consumer safety advocates

## CLI Commands
```bash
python -m src.cli download     # Download flat files
python -m src.cli recalls      # Fetch recalls from API
python -m src.cli pipeline     # Full pipeline
python -m src.cli stats        # Show statistics
python -m src.cli export       # Export all formats
python -m src.cli dashboard    # Launch Streamlit
```
