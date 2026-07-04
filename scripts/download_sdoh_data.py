"""Bulk download all SDOH data for Nashville metro ZCTAs.

Downloads Census ACS + AirNow + CHAS + crime data for all Nashville ZIP codes
and stores in data/sdoh.db for offline/HIPAA-safe operation.

Usage:
    python scripts/download_sdoh_data.py --all-nashville

Requires:
    CENSUS_API_KEY, AIRNOW_API_KEY, HUD_API_TOKEN in .env or environment
"""
import sys, os, time, sqlite3, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from shared.models import RawSdoHMetrics
from features.sdoh_profiler.providers.census import CensusACSProvider
from features.sdoh_profiler.providers.airnow import AirNowProvider
from features.sdoh_profiler.providers.food_crime import FoodAccessCrimeProvider
from features.sdoh_profiler.providers.chas import CHASHousingProvider
from features.sdoh_profiler.providers.composite import CompositeSdoHProvider
from features.sdoh_profiler.providers.local_db import LocalDbSdoHProvider

NASHVILLE_ZCTAS = [
    "37115", "37138", "37201", "37203", "37204", "37205", "37206",
    "37207", "37208", "37209", "37210", "37211", "37212", "37213",
    "37214", "37215", "37216", "37217", "37218", "37219", "37220",
    "37221", "37227", "37228", "37229", "37230", "37235",
    "37236", "37237", "37238", "37240", "37241", "37242", "37243",
    "37244", "37245", "37246", "37247", "37248", "37249", "37250",
    "37013", "37027", "37055", "37064", "37067", "37069", "37072",
    "37075", "37076", "37080", "37082", "37086", "37090",
]

def main():
    census_key = os.environ.get("CENSUS_API_KEY", "")
    airnow_key = os.environ.get("AIRNOW_API_KEY", "")
    hud_token = os.environ.get("HUD_API_TOKEN", "")

    if not census_key:
        print("ERROR: CENSUS_API_KEY not set. Put it in .env or export it.")
        sys.exit(1)

    # Build composite provider with all sources
    primary = CensusACSProvider(api_key=census_key)
    airnow = AirNowProvider(api_key=airnow_key) if airnow_key else None
    food_crime = FoodAccessCrimeProvider(hud_token=hud_token) if hud_token else None
    chas = CHASHousingProvider(api_token=hud_token) if hud_token else None
    composite = CompositeSdoHProvider(
        primary=primary, supplement=airnow,
        food_crime=food_crime, chas=chas,
    )

    # Local DB for storage
    project_root = os.path.join(os.path.dirname(__file__), "..")
    db_path = os.path.abspath(os.path.join(project_root, "data", "sdoh.db"))
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    local_db = LocalDbSdoHProvider(db_path=db_path)

    print(f"\nDownloading SDOH data for {len(NASHVILLE_ZCTAS)} Nashville ZCTAs...")
    print(f"Database: {db_path}")
    print()

    ingested = 0
    failed = 0
    for i, zcta in enumerate(NASHVILLE_ZCTAS):
        try:
            metrics = composite.fetch_metrics(zcta)
            local_db.upsert_metrics(metrics, source="census+airnow+foodcrime+chas")
            ingested += 1
            print(f"  [{i+1:2d}/{len(NASHVILLE_ZCTAS)}] {zcta}: "
                  f"edu={metrics.education_attainment_pct:.0f}% "
                  f"house={metrics.housing_instability_score:.0f} "
                  f"transit={metrics.transportation_access_score:.0f} "
                  f"food={metrics.grocery_access_score:.0f} "
                  f"aqi={metrics.air_quality_index:.0f} "
                  f"crime={metrics.crime_rate_per_100k:.0f}")
        except Exception as e:
            failed += 1
            print(f"  [{i+1:2d}/{len(NASHVILLE_ZCTAS)}] {zcta}: FAILED - {str(e)[:60]}")
        time.sleep(1.5)  # Rate limit courtesy for Census API

    print(f"\nDone: {ingested} ingested, {failed} failed.")
    print(f"Database: {db_path}")

    # Also create a food_access table for USDA data (empty, ready for ingestion)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS food_access (
                tract_geoid TEXT PRIMARY KEY,
                is_food_desert INTEGER,
                low_income INTEGER,
                low_access_1mi INTEGER,
                low_access_10mi INTEGER,
                low_access_halfmi INTEGER,
                source TEXT,
                updated_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sdoh_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zip_code TEXT,
                overall_risk REAL,
                air_quality_index REAL,
                grocery_access_score REAL,
                housing_instability_score REAL,
                transportation_access_score REAL,
                crime_rate_per_100k REAL,
                education_attainment_pct REAL,
                snapshot_date TEXT,
                source TEXT
            )
        """)
        conn.commit()
        print("Created food_access and sdoh_history tables.")
    finally:
        conn.close()

if __name__ == "__main__":
    main()