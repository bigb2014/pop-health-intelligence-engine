# Pop-Health Intelligence Engine

## Overview

Strategic middleware layer between Health Systems (Providers) and Employers (Payers).
Fuses clinical EHR data with public SDOH (Social Determinants of Health) data to
identify high-risk patients and generate medically validated, financially quantified
intervention plans.

**Core Value:** Transitions Population Health from *descriptive* (what happened) to
*prescriptive* (what to do and how much it saves).

## Architecture

**Functional Core / Imperative Shell (FCIS) + Ports & Adapters (Hexagonal)**

Every feature is split into:
- **Core** (`.core.py`): Pure, deterministic logic. No IO, no DB, no LLM. 100% testable.
- **Shell** (`.shell.py`): IO glue — API calls, LLM calls, logging.

All external services are abstracted behind ports (interfaces) with swappable adapters.

## Features

| # | Feature | Role | Data Source |
|---|---------|------|------------|
| 1 | SDOH Profiler | Geographic → social risk factors | Census ACS + AirNow + HUD CHAS + CHR Crime |
| 2 | Risk Scoring Engine | Risk tier with interaction multipliers | Pure Core (8 multiplier rules) |
| 3 | Intervention Strategist | LLM care plans + critic validation | Ollama qwen2.5:7b + 5-rule critic |
| 4 | Value Quantifier | Actuarial ROI model | Pure Core (actuarial tables) |

## SDOH Data Sources (6/6 fields covered)

| Field | Provider | Source | API Key? |
|-------|----------|--------|----------|
| `air_quality_index` | AirNowProvider | EPA AirNow API | Free key |
| `education_attainment_pct` | CensusACSProvider | Census ACS 5-Year | Free key |
| `housing_instability_score` | CHASHousingProvider | HUD CHAS API | Free token (HUD) |
| `transportation_access_score` | CensusACSProvider | Census ACS 5-Year | Free key |
| `grocery_access_score` | FoodAccessCrimeProvider | Census poverty proxy / USDA FARA | Free (USDA is CSV download) |
| `crime_rate_per_100k` | FoodAccessCrimeProvider | County Health Rankings (all 95 TN counties) | Free (embedded) |

### Composite Provider Architecture

```
CompositeSdoHProvider (merges 4 sources)
├── Census ACS (primary)     → education, transportation, food proxy, housing baseline
├── AirNow (supplement)       → air_quality_index (real-time AQI)
├── FoodCrime (supplement)    → grocery_access_score, crime_rate_per_100k
└── CHAS (supplement)         → housing_instability_score (HUD official)
```

## Tech Stack

- Python 3.11+ (Docker: 3.12-slim)
- Pydantic v2 (strict typing for PHI/PII safety)
- Streamlit (demo UI with batch CSV upload)
- Ollama (local LLM inference — qwen2.5:7b)
- SQLite (local SDOH database for offline/HIPAA-safe operation)
- Docker Compose (containerized, NetBird-accessible)

## Setup

### 1. Get free API keys

| Key | URL | Used For |
|-----|-----|----------|
| Census API | https://api.census.gov/data/key_signup.html | Education, housing, transportation |
| AirNow API | https://docs.airnowapi.org/airnow/downloads/ | Real-time air quality |
| HUD API | https://www.huduser.gov/hudapi/public/register | ZIP crosswalk + CHAS housing data |

### 2. Create .env file

```bash
cp .env.example .env
# Edit .env and add your API keys
```

### 3. Install Ollama and pull a model

```bash
# Install from https://ollama.com
ollama pull qwen2.5:7b
```

### 4. Run with Docker

```bash
docker compose build
docker compose up -d
```

The app will be available at `http://localhost:8501`.

### 5. (Optional) Bulk download SDOH data for offline use

```bash
python scripts/download_sdoh_data.py --all-nashville
# Then set SDOH_PROVIDER=local_db in .env to use offline database
```

### 6. (Optional) Ingest USDA Food Access Atlas

```bash
# Download Excel from:
# https://www.ers.usda.gov/data-products/food-access-research-atlas/download-the-data/
# Save as: data/FoodAccessResearchAtlasData2019.xlsx
pip install openpyxl
python scripts/ingest_food_access.py
```

## Testing

```bash
PYTHONPATH=src python -m pytest src/ -p no:langsmith -v
```

130 tests covering:
- SDOH normalization (6 dimensions, 18 tests)
- Risk scoring + multipliers (20 tests)
- Critic validation (5 rules, 25 tests)
- Actuarial ROI model (24 tests)
- Provider adapters (Census, AirNow, HUD, FoodCrime, CHAS, LocalDB — 30+ tests)
- Composite 4-source merging (10 tests)
- Historical tracking (SDOH snapshots over time)

## Project Structure

```
pop-health-intelligence-engine/
├── app.py                         # Streamlit UI (single patient + batch CSV)
├── docker-compose.yml             # Container config (env_file: .env)
├── Dockerfile                     # Multi-stage build (Python 3.12-slim)
├── .env.example                    # API key documentation
├── .env                           # Your API keys (gitignored)
├── data/                          # Local SQLite DB + USDA Excel (gitignored)
├── scripts/
│   ├── download_sdoh_data.py       # Bulk download to local DB
│   └── ingest_food_access.py       # USDA Food Atlas → SQLite
└── src/
    ├── main.py                    # CLI entry point
    ├── shared/models.py           # Pydantic data models
    └── features/
        ├── sdoh_profiler/
        │   ├── sdoh_profiler.core.py   # Pure normalization logic
        │   ├── sdoh_profiler.shell.py  # IO shell
        │   ├── base.py                 # SdoHDataProvider port
        │   ├── historical.py           # SDOH snapshot tracking
        │   ├── providers/
        │   │   ├── mock.py             # MockSdoHProvider
        │   │   ├── census.py           # CensusACSProvider
        │   │   ├── airnow.py           # AirNowProvider
        │   │   ├── composite.py        # CompositeSdoHProvider (4-source merge)
        │   │   ├── food_crime.py       # FoodAccessCrimeProvider
        │   │   ├── chas.py            # CHASHousingProvider
        │   │   ├── hud.py             # HUDCrosswalkProvider
        │   │   ├── local_db.py        # LocalDbSdoHProvider
        │   │   └── tn_crime_data.py   # All 95 TN county crime rates
        │   └── test_*.py              # Tests
        ├── risk_scoring/
        ├── intervention_strategist/
        │   ├── intervention_strategist.core.py  # Critic + prompt builder
        │   ├── intervention_strategist.shell.py # LLM pipeline
        │   └── providers/
        │       ├── mock.py             # MockLLMProvider
        │       ├── ollama.py          # OllamaProvider (qwen2.5:7b)
        │       └── llama.py           # LlamaProvider (stub)
        └── value_quantifier/
```

## Docker + Network Access

The container binds to `0.0.0.0:8501` and is accessible via:
- **localhost**: `http://localhost:8501`
- **LAN**: `http://<your-IP>:8501`
- **NetBird**: `http://<netbird-IP>:8501` (VPN mesh network)

Restart policy: `unless-stopped` (survives reboots).
Health check: `http://localhost:8501/_stcore/health`

## Historical Tracking

Every time a patient is analyzed, the SDOH metrics for their ZIP code are
snapshotted to `data/sdoh.db`. Over time, this builds a history that shows
whether interventions are improving social determinants — essential for
proving ROI to payers.

```python
from features.sdoh_profiler.historical import SDOHHistoryTracker

tracker = SDOHHistoryTracker()
history = tracker.get_history("37208", limit=12)
# Returns daily snapshots of SDOH risk factors over time
```

## License

MIT