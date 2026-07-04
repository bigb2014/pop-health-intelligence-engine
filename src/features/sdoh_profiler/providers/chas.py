"""HUD CHAS Housing Affordability provider.

Uses the HUD CHAS (Comprehensive Housing Affordability Strategy) API to
get housing cost burden and severe housing problem data. This is more
clinically validated than the Census ACS housing cost burden proxy because:
- CHAS uses HUD's standard definitions of cost burden (>30% income) and
  severe cost burden (>50% income)
- CHAS breaks down by income bracket (AMI) which enables targeted interventions
- CHAS data is specifically designed for housing planning, not general census

API: https://www.huduser.gov/hudapi/public/chas
Token: Same HUD API token used for USPS crosswalk

CHAS Table 1 (A fields): Households by income and housing cost burden
  A1-A6:   Total households (by income bracket, no housing problems)
  A7-A12:  Cost burdened households (>30% income on housing)
  A13-A18: Severely cost burdened households (>50% income on housing)

CHAS Table 2 (B fields): Severe housing problems by tenure and income
  B1: Renter, low-income (<=80% AMI), severe problems
  B2: Renter, higher-income (>80% AMI), severe problems
  B3: Owner, low-income, severe problems
  B4: Owner, higher-income, severe problems
  B5: Total low-income, severe problems
  B6: Total higher-income, severe problems

We use: cost burden rate + severe problem rate to compute
housing_instability_score (0-100, higher = more instability).
"""

from __future__ import annotations

import os
import json
import urllib.request

from shared.models import RawSdoHMetrics
from features.sdoh_profiler.base import SdoHDataProvider


class CHASHousingProvider(SdoHDataProvider):
    """Live adapter for HUD CHAS housing affordability data.

    Provides housing_instability_score based on HUD's official cost burden
    and severe housing problem data. More accurate than the Census ACS proxy.

    This is a SUPPLEMENT provider — it only fills housing_instability_score.
    Use CompositeSdoHProvider to merge with Census ACS for other fields.

    Args:
        api_token: HUD API token (same as USPS crosswalk)
    """

    BASE_URL = "https://www.huduser.gov/hudapi/public/chas"

    # Map ZIP prefix to state FIPS for CHAS queries
    # CHAS state-level data is the most granular available via the API
    # (county and tract level queries return empty for many areas)
    ZIP_TO_STATE: dict[str, str] = {
        "37": "47",  # Tennessee
        "36": "36",  # New York
        "90": "06",  # California
        "60": "17",  # Illinois
        "19": "25",  # Massachusetts
        "75": "48",  # Texas
        "30": "13",  # Georgia
        "98": "53",  # Washington
        "80": "08",  # Colorado
        "33": "12",  # Florida
    }

    # Cache: state FIPS → CHAS data (avoid repeated API calls)
    _cache: dict[str, dict] = {}

    def __init__(self, api_token: str | None = None):
        self._token = api_token or os.environ.get("HUD_API_TOKEN", "")

    def _query_chas(self, state_fips: str) -> dict:
        """Fetch CHAS data for a state. Caches results."""
        if state_fips in self._cache:
            return self._cache[state_fips]

        if not self._token:
            return {}

        url = f"{self.BASE_URL}?type=2&stateId={state_fips}"
        headers = {
            "Authorization": "Bearer " + self._token,
            "User-Agent": "PopHealth/0.1",
        }

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode()
                if not raw:
                    return {}
                data = json.loads(raw)
                if isinstance(data, list) and data:
                    record = data[0]
                    self._cache[state_fips] = record
                    return record
        except Exception:
            return {}

        return {}

    def _compute_housing_instability(self, chas_data: dict) -> float:
        """Compute housing instability score (0-100) from CHAS data.

        Formula based on HUD cost burden definitions:
        - Cost burdened rate: % of households paying >30% income on housing
        - Severe cost burdened rate: % paying >50% income
        - Severe housing problem rate: % with severe physical/affordability issues

        Score = weighted combination:
          cost_burden_rate * 40 + severe_burden_rate * 2 * 30 + severe_problem_rate * 30
        Capped at 100.
        """
        def safe_float(v) -> float:
            try:
                return float(v) if v is not None else 0.0
            except (ValueError, TypeError):
                return 0.0

        # Table 1 (A fields): cost burden data
        # A1-A6 are total households by income bracket (no problems)
        # A7-A12 are cost burdened (>30% income on housing)
        # A13-A18 are severely cost burdened (>50% income on housing)
        total_households = sum(safe_float(chas_data.get(f"A{i}", 0)) for i in range(1, 7))
        cost_burdened = sum(safe_float(chas_data.get(f"A{i}", 0)) for i in range(7, 13))
        severe_burdened = sum(safe_float(chas_data.get(f"A{i}", 0)) for i in range(13, 19))

        # Table 2 (B fields): severe housing problems
        # B5 = total low-income severe problems, B6 = total higher-income
        severe_problems_low = safe_float(chas_data.get("B5", 0))
        severe_problems_high = safe_float(chas_data.get("B6", 0))
        severe_problems_total = severe_problems_low + severe_problems_high

        if total_households <= 0:
            return 40.0  # National average fallback

        cost_burden_rate = cost_burdened / total_households
        severe_burden_rate = severe_burdened / total_households
        severe_problem_rate = severe_problems_total / total_households

        # Weighted score (0-100)
        # Cost burden is the primary indicator (40% weight)
        # Severe burden adds more risk (30% weight, doubled because >50% is extreme)
        # Severe housing problems (structural/physical) add 30% weight
        score = (
            cost_burden_rate * 40
            + min(severe_burden_rate * 2, 1.0) * 30
            + min(severe_problem_rate, 1.0) * 30
        )

        return round(min(max(score, 0.0), 100.0), 1)

    def fetch_metrics(self, zip_code: str) -> RawSdoHMetrics:
        """Fetch CHAS housing data and return partial metrics.

        Only housing_instability_score is meaningful. All other fields
        use neutral defaults — use CompositeSdoHProvider to merge.
        """
        # Map ZIP to state FIPS
        zip_prefix = zip_code[:2]
        state_fips = self.ZIP_TO_STATE.get(zip_prefix)

        housing_score = 40.0  # Default fallback
        if state_fips and self._token:
            chas_data = self._query_chas(state_fips)
            if chas_data:
                housing_score = self._compute_housing_instability(chas_data)

        return RawSdoHMetrics(
            zip_code=zip_code,
            air_quality_index=50,           # Neutral — use AirNow
            grocery_access_score=50,         # Neutral — use FoodAccessCrime
            housing_instability_score=housing_score,  # CHAS data
            transportation_access_score=50,  # Neutral — use Census
            crime_rate_per_100k=380,         # Neutral — use FoodAccessCrime
            education_attainment_pct=80,     # Neutral — use Census
        )