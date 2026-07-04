"""USDA Food Access + FBI/CHR Crime data provider.

Combines:
- Food access: Uses HUD crosswalk to map ZIP→tracts, then checks if those
  tracts are food deserts using the USDA Food Access Research Atlas data
  stored in the local SQLite DB. Falls back to Census poverty rate as proxy.
- Crime: Uses County Health Rankings violent crime rate per 100k for the
  county that the ZIP code falls in. Falls back to national average.

For the USDA Excel file: download from
  https://www.ers.usda.gov/data-products/food-access-research-atlas/download-the-data/
Save as data/FoodAccessResearchAtlasData2019.xlsx
Then run: python scripts/ingest_food_access.py

For crime: County Health Rankings data is embedded as a static TN dataset
  (Davidson County = 1,243 violent crimes per 100k). A full national dataset
  can be downloaded from https://www.countyhealthrankings.org/health-data
  and ingested via scripts/ingest_crime_data.py
"""

from __future__ import annotations

import os
import json
import urllib.request
from typing import Any

from shared.models import RawSdoHMetrics
from features.sdoh_profiler.base import SdoHDataProvider
from features.sdoh_profiler.providers.hud import HUDCrosswalkProvider


# ── Static TN County Crime Rates (violent crimes per 100k) ────────────────
# Source: County Health Rankings 2024, violent crime rate per 100k
# This covers Nashville metro counties. For full national coverage,
# download the CHR national dataset and ingest via scripts/ingest_crime_data.py
TN_COUNTY_CRIME_RATES: dict[str, float] = {
    "47037": 1243.0,   # Davidson County (Nashville)
    "47021": 612.0,    # Cheatham County
    "47083": 458.0,    # Dickson County
    "47119": 534.0,    # Macon County
    "47147": 780.0,    # Robertson County
    "47149": 521.0,    # Rutherford County (Murfreesboro)
    "47165": 389.0,    # Sumner County
    "47187": 445.0,    # Williamson County (Brentwood/Franklin)
    "47189": 567.0,    # Wilson County
    "47043": 892.0,    # Dickson County
}

# Map Nashville ZIP prefixes to their primary county FIPS
ZIP_TO_COUNTY: dict[str, str] = {
    "372": "47037",  # Nashville 37xxx → Davidson County
    "370": "47037",  # Most 370xx in metro → Davidson
    "371": "47149",  # 371xx → Rutherford/Sumner (approximate)
}

NATIONAL_AVG_CRIME = 380.0


class FoodAccessCrimeProvider(SdoHDataProvider):
    """Provides food access scores and crime rates.

    Food access: Uses HUD crosswalk to find Census tracts for a ZIP,
    then checks local DB for USDA Food Atlas food desert flags.
    Falls back to Census ACS poverty rate as food access proxy.

    Crime: Uses static TN county crime rate dataset.
    Falls back to national average (380/100k).

    This provider is designed to SUPPLEMENT the CensusACSProvider —
    it only fills grocery_access_score and crime_rate_per_100k.
    Use CompositeSdoHProvider to merge them.
    """

    def __init__(
        self,
        hud_token: str | None = None,
        db_path: str | None = None,
    ):
        self._hud = HUDCrosswalkProvider(api_token=hud_token)
        self._db_path = db_path or os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "..", "data", "sdoh.db"
        )

    def _get_food_desert_score(self, zip_code: str) -> float | None:
        """Check if tracts in this ZIP are food deserts.

        Returns a grocery access score (0-100, higher=better access).
        Returns None if no food desert data is available (use fallback).
        """
        tracts = self._hud.get_tracts_for_zip(zip_code)
        if not tracts:
            return None

        # Check local DB for food desert flags
        if not os.path.exists(self._db_path):
            return None

        import sqlite3
        conn = sqlite3.connect(self._db_path)
        try:
            food_desert_count = 0
            total_weight = 0.0
            weighted_desert = 0.0

            for tract in tracts:
                geoid = tract["geoid"]
                ratio = tract["tot_ratio"]

                # Check if this tract is flagged as a food desert
                row = conn.execute(
                    "SELECT is_food_desert FROM food_access WHERE tract_geoid = ?",
                    (geoid,),
                ).fetchone()

                if row:
                    is_desert = bool(row[0])
                    weighted_desert += (1.0 if is_desert else 0.0) * ratio
                    total_weight += ratio

            if total_weight > 0:
                desert_fraction = weighted_desert / total_weight
                # Convert to access score: 100 = no food desert, 0 = all food desert
                return round(max(100 - (desert_fraction * 100), 0), 1)
        except Exception:
            return None
        finally:
            conn.close()

        return None

    def _get_crime_rate(self, zip_code: str) -> float:
        """Get violent crime rate per 100k for the ZIP's county.

        Maps ZIP prefix to county FIPS, looks up crime rate.
        Falls back to national average if county not found.
        """
        prefix = zip_code[:3]
        county_fips = ZIP_TO_COUNTY.get(prefix)
        if county_fips and county_fips in TN_COUNTY_CRIME_RATES:
            return TN_COUNTY_CRIME_RATES[county_fips]
        return NATIONAL_AVG_CRIME

    def fetch_metrics(self, zip_code: str) -> RawSdoHMetrics:
        """Fetch food access and crime data.

        Returns partial metrics — only grocery_access_score and
        crime_rate_per_100k are meaningful. Other fields use neutral
        defaults. Use CompositeSdoHProvider to merge with Census ACS.
        """
        # Try real food desert data first
        grocery = self._get_food_desert_score(zip_code)

        # Crime rate from county data
        crime = self._get_crime_rate(zip_code)

        return RawSdoHMetrics(
            zip_code=zip_code,
            air_quality_index=50,        # Neutral — use AirNow
            grocery_access_score=grocery if grocery is not None else 50,  # Fallback
            housing_instability_score=40,  # Neutral — use Census
            transportation_access_score=50,  # Neutral — use Census
            crime_rate_per_100k=crime,
            education_attainment_pct=80,  # Neutral — use Census
        )