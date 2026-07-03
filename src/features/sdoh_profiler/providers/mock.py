"""Mock SDOH data provider — deterministic test data.

Returns realistic but fixed SDOH metrics for any ZIP code.
Useful for development, demos, and testing without API calls.
"""

from __future__ import annotations

from shared.models import RawSdoHMetrics
from features.sdoh_profiler.base import SdoHDataProvider


# Predefined profiles for known ZIPs (Nashville metro area examples)
_MOCK_DATA: dict[str, RawSdoHMetrics] = {
    "37115": RawSdoHMetrics(  # Madison, TN — moderate risk
        zip_code="37115",
        air_quality_index=45,
        grocery_access_score=20,
        housing_instability_score=60,
        transportation_access_score=30,
        crime_rate_per_100k=800,
        education_attainment_pct=75,
    ),
    "37208": RawSdoHMetrics(  # North Nashville — high risk
        zip_code="37208",
        air_quality_index=55,
        grocery_access_score=10,
        housing_instability_score=75,
        transportation_access_score=25,
        crime_rate_per_100k=1200,
        education_attainment_pct=60,
    ),
    "37027": RawSdoHMetrics(  # Brentwood, TN — low risk
        zip_code="37027",
        air_quality_index=30,
        grocery_access_score=90,
        housing_instability_score=15,
        transportation_access_score=85,
        crime_rate_per_100k=100,
        education_attainment_pct=95,
    ),
}

# Default fallback for unknown ZIPs
_DEFAULT_METRICS = RawSdoHMetrics(
    zip_code="00000",
    air_quality_index=50,
    grocery_access_score=50,
    housing_instability_score=40,
    transportation_access_score=50,
    crime_rate_per_100k=500,
    education_attainment_pct=80,
)


class MockSdoHProvider(SdoHDataProvider):
    """Deterministic mock provider for development and testing."""

    def fetch_metrics(self, zip_code: str) -> RawSdoHMetrics:
        data = _MOCK_DATA.get(zip_code, _DEFAULT_METRICS)
        # Return a copy with the requested zip_code
        return data.model_copy(update={"zip_code": zip_code})