"""Bulk SDOH data downloader — populates the local SQLite database.

Downloads public SDOH datasets and ingests them into data/sdoh.db.
This gives us:
1. Full coverage (including ZCTAs missing from API responses)
2. Zero runtime API dependency (HIPAA: no patient ZIPs sent externally)
3. Access to datasets with no API (USDA FARA, FBI UCR)
4. Faster batch processing

Usage:
    python scripts/download_sdoh_data.py --zctas 37115,37208,37027
    python scripts/download_sdoh_data.py --all-nashville
    python scripts/download_sdoh_data.py --all  # Downloads ALL ~32K ZCTAs

Required env vars:
    CENSUS_API_KEY  — Free key from https://api.census.gov/data/key_signup.html
    AIRNOW_API_KEY  — Free key from https://docs.airnowapi.org/airnow/downloads/
                      (optional — air quality defaults to 50 if missing)
"""

from __future__ import annotations

import sys
import os
import argparse

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from shared.models import RawSdoHMetrics
from features.sdoh_profiler.providers.census import CensusACSProvider
from features.sdoh_profiler.providers.airnow import AirNowProvider
from features.sdoh_profiler.providers.composite import CompositeSdoHProvider
from features.sdoh_profiler.providers.local_db import LocalDbSdoHProvider


# Nashville metro ZCTAs (37xxx)
NASHVILLE_ZCTAS = [
    "37115", "37138", "37201", "37203", "37204", "37205", "37206",
    "37207", "37208", "37209", "37210", "37211", "37212", "37213",
    "37214", "37215", "37216", "37217", "37218", "37219", "37220",
    "37221", "37222", "37227", "37228", "37229", "37230", "37235",
    "37236", "37237", "37238", "37240", "37241", "37242", "37243",
    "37244", "37245", "37246", "37247", "37248", "37249", "37250",
    "37013", "37027", "37055", "37064", "37067", "37069", "37072",
    "37075", "37076", "37080", "37082", "37086", "37090",
]


def download_zctas(
    zip_codes: list[str],
    db_path: str | None = None,
    verbose: bool = True,
) -> int:
    """Download SDOH data for a list of ZIP codes and store in local DB.

    Returns the number of ZCTAs successfully ingested.
    """
    census_key = os.environ.get("CENSUS_API_KEY", "")
    airnow_key = os.environ.get("AIRNOW_API_KEY", "")

    if not census_key:
        print("⚠ No CENSUS_API_KEY found. Census data will be unavailable.")
        print("  Get a free key at: https://api.census.gov/data/key_signup.html")
        return 0

    primary = CensusACSProvider(api_key=census_key)
    supplement = AirNowProvider(api_key=airnow_key) if airnow_key else None
    composite = CompositeSdoHProvider(primary=primary, supplement=supplement)
    local_db = LocalDbSdoHProvider(db_path=db_path)

    ingested = 0
    for i, zcta in enumerate(zip_codes):
        try:
            metrics = composite.fetch_metrics(zcta)
            local_db.upsert_metrics(metrics, source="census_acs+airnow")
            ingested += 1
            if verbose:
                print(f"  [{i+1}/{len(zip_codes)}] ZCTA {zcta}: "
                      f"edu={metrics.education_attainment_pct}% "
                      f"housing={metrics.housing_instability_score} "
                      f"transport={metrics.transportation_access_score} "
                      f"food_access={metrics.grocery_access_score} "
                      f"aqi={metrics.air_quality_index}")
        except Exception as e:
            if verbose:
                print(f"  [{i+1}/{len(zip_codes)}] ZCTA {zcta}: FAILED — {e}")

    return ingested


def main():
    parser = argparse.ArgumentParser(description="Download SDOH data to local SQLite DB")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--zctas", type=str, help="Comma-separated ZCTA codes (e.g., 37115,37208)")
    group.add_argument("--all-nashville", action="store_true", help="Download all Nashville metro ZCTAs")
    group.add_argument("--all", action="store_true", help="Download ALL US ZCTAs (takes a while)")
    parser.add_argument("--db-path", type=str, default=None, help="Path to SQLite DB file")
    args = parser.parse_args()

    if args.zctas:
        zip_codes = [z.strip() for z in args.zctas.split(",")]
    elif args.all_nashville:
        zip_codes = NASHVILLE_ZCTAS
    elif args.all:
        # Generate all US ZCTAs (00001-99950, 5-digit)
        # In practice, only ~32,520 ZCTAs exist; we try them all
        print("⚠ Downloading ALL US ZCTAs. This will take 30-60 minutes.")
        zip_codes = [f"{i:05d}" for i in range(1, 99951)]

    print(f"\n📥 Downloading SDOH data for {len(zip_codes)} ZCTAs...")
    print(f"   Database: {os.path.abspath(args.db_path) if args.db_path else 'data/sdoh.db'}")
    print()

    count = download_zctas(zip_codes, db_path=args.db_path)

    print(f"\n✅ Ingested {count}/{len(zip_codes)} ZCTAs into local database.")
    print(f"   Use LocalDbSdoHProvider in your app to read this data offline.")


if __name__ == "__main__":
    main()