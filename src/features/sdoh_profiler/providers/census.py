"""Census ACS 5-Year SDOH data provider.

Fetches education, housing, transportation, and poverty data from the
Census ACS 5-Year API at ZCTA (ZIP Code Tabulation Area) level.

API docs: https://www.census.gov/data/developers/data-sets/acs-5year.html
Free key: https://api.census.gov/data/key_signup.html
"""

from __future__ import annotations

import os
import urllib.request
import json
from typing import Any

from shared.models import RawSdoHMetrics
from features.sdoh_profiler.base import SdoHDataProvider

# ── ACS Variable Codes ────────────────────────────────────────────────────
# Education: % adults 25+ with HS diploma
EDU_HS = "B15003_017E"       # Population 25+ with regular HS diploma
EDU_TOTAL = "B15003_001E"    # Population 25+ total

# Housing: cost burden (>30% income on housing) + overcrowding + renters
HOUSING_COST_BURDEN = [
    "B25070_007E",  # 30-34.9% of income on housing
    "B25070_008E",  # 35-39.9%
    "B25070_009E",  # 40-49.9%
    "B25070_010E",  # 50%+
]
HOUSING_TOTAL = "B25070_001E"
HOUSING_OVERCROWD = ["B25014_005E", "B25014_006E", "B25014_007E"]
HOUSING_OVERCROWD_TOTAL = "B25014_001E"
RENTER_OCCUPIED = "B25003_003E"
HOUSING_UNITS_TOTAL = "B25003_001E"

# Transportation: % households with no vehicle
NO_VEHICLE = "B25044_003E"
VEHICLE_TOTAL = "B25044_001E"

# Poverty: % below poverty level
POVERTY = "B17001_002E"
POVERTY_TOTAL = "B17001_001E"

# Population
TOTAL_POP = "B01003_001E"

# All variables we need in one request
ALL_VARS = [
    EDU_HS, EDU_TOTAL,
    *HOUSING_COST_BURDEN, HOUSING_TOTAL,
    *HOUSING_OVERCROWD, HOUSING_OVERCROWD_TOTAL,
    RENTER_OCCUPIED, HOUSING_UNITS_TOTAL,
    NO_VEHICLE, VEHICLE_TOTAL,
    POVERTY, POVERTY_TOTAL,
    TOTAL_POP,
]


class CensusACSProvider(SdoHDataProvider):
    """Live adapter for Census ACS 5-Year SDOH data at ZCTA level.

    Requires a free Census API key. Get one at:
    https://api.census.gov/data/key_signup.html
    """

    BASE_URL = "https://api.census.gov/data/2023/acs/acs5"

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or os.environ.get("CENSUS_API_KEY", "")

    def _query_zcta(self, zip_code: str) -> dict[str, str]:
        """Fetch ACS variables for a single ZCTA.

        Returns a dict mapping variable code → estimate value.
        Returns empty dict if the ZCTA is not found, the API errors,
        or the key is rate-limited (Census returns HTML instead of JSON).
        """
        var_str = ",".join(["NAME"] + ALL_VARS)
        url = (
            f"{self.BASE_URL}?get={var_str}"
            f"&for=zip%20code%20tabulation%20area:{zip_code}"
        )
        if self._api_key:
            url += f"&key={self._api_key}"

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "PopHealthEngine/0.1"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode()
                if not raw or raw.strip() == "":
                    return {}
                # Census returns an HTML "Invalid Key" page when rate-limited
                if "<html" in raw.lower() or "<title" in raw.lower():
                    return {}
                data = json.loads(raw)
        except Exception:
            return {}

        if not isinstance(data, list) or len(data) < 2:
            return {}

        headers = data[0]
        values = data[1]
        return {h: v for h, v in zip(headers, values)}

    def fetch_metrics(self, zip_code: str) -> RawSdoHMetrics:
        """Fetch and normalize ACS data into RawSdoHMetrics.

        Maps ACS estimates to our SDOH model:
        - Education: % with HS diploma → education_attainment_pct
        - Housing: cost burden % + overcrowding % + renter % → housing_instability_score
        - Transportation: % no vehicle → transportation_access_score (inverted)
        - Poverty: % below poverty → used as proxy for food access (food desert correlation)
        - Crime: not available from Census → defaults to national average
        - Air quality: not available from Census → defaults to moderate
        """
        data = self._query_zcta(zip_code)

        if not data:
            # Fallback to national averages if ZCTA not found
            return self._fallback_metrics(zip_code)

        def pct(numerator: str, denominator: str) -> float:
            try:
                n = float(data.get(numerator, "0"))
                d = float(data.get(denominator, "1"))
                return round((n / d) * 100, 1) if d > 0 else 0.0
            except (ValueError, ZeroDivisionError):
                return 0.0

        # Education: % adults 25+ with HS diploma
        edu_pct = pct(EDU_HS, EDU_TOTAL)

        # Housing instability: composite of cost burden + overcrowding + renter rate
        cost_burden_sum = sum(
            float(data.get(v, "0") or "0") for v in HOUSING_COST_BURDEN
        )
        cost_burden_pct = (cost_burden_sum / max(float(data.get(HOUSING_TOTAL, "1") or "1"), 1)) * 100
        overcrowd_sum = sum(
            float(data.get(v, "0") or "0") for v in HOUSING_OVERCROWD
        )
        overcrowd_pct = (overcrowd_sum / max(float(data.get(HOUSING_OVERCROWD_TOTAL, "1") or "1"), 1)) * 100
        renter_pct = pct(RENTER_OCCUPIED, HOUSING_UNITS_TOTAL)
        # Composite housing instability (0-100): weighted average
        housing_instability = round(min((cost_burden_pct * 0.5) + (overcrowd_pct * 3) + (renter_pct * 0.2), 100), 1)

        # Transportation: % households with no vehicle → invert to access score
        no_vehicle_pct = pct(NO_VEHICLE, VEHICLE_TOTAL)
        transportation_access = round(max(100 - (no_vehicle_pct * 5), 0), 1)  # Scale: 20% no vehicle → 0 access

        # Poverty as food access proxy (high poverty → low grocery access)
        poverty_pct = pct(POVERTY, POVERTY_TOTAL)
        grocery_access = round(max(100 - (poverty_pct * 4), 0), 1)  # Scale: 25% poverty → 0 access

        # Crime and air quality: not available from Census
        # Use national average defaults (crime ~380/100k, AQI ~50)
        crime_rate = 380.0
        air_quality = 50.0

        return RawSdoHMetrics(
            zip_code=zip_code,
            air_quality_index=air_quality,
            grocery_access_score=grocery_access,
            housing_instability_score=housing_instability,
            transportation_access_score=transportation_access,
            crime_rate_per_100k=crime_rate,
            education_attainment_pct=edu_pct,
        )

    def _fallback_metrics(self, zip_code: str) -> RawSdoHMetrics:
        """Return national-average metrics when ZCTA data is unavailable."""
        return RawSdoHMetrics(
            zip_code=zip_code,
            air_quality_index=50,
            grocery_access_score=50,
            housing_instability_score=40,
            transportation_access_score=50,
            crime_rate_per_100k=380,
            education_attainment_pct=80,
        )