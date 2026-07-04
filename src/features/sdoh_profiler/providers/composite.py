"""Composite SDOH provider — merges data from multiple source providers.

No single API covers all SDOH dimensions at ZIP level. This provider
combines Census ACS (education, housing, transportation, poverty-as-food-proxy)
with EPA AirNow (real-time air quality) to produce complete RawSdoHMetrics.

Usage:
    provider = CompositeSdoHProvider(
        primary=CensusACSProvider(api_key="..."),
        supplement=AirNowProvider(api_key="..."),
    )
    metrics = provider.fetch_metrics("37208")
"""

from __future__ import annotations

from shared.models import RawSdoHMetrics
from features.sdoh_profiler.base import SdoHDataProvider


class CompositeSdoHProvider(SdoHDataProvider):
    """Merges SDOH data from a primary source with supplemental sources.

    The primary provider supplies most fields. Each supplemental provider
    fills in specific fields that the primary doesn't cover well.

    Priority: supplements override primary for the fields they provide.
    - AirNow overrides air_quality_index (if it has real data)
    - FoodAccessCrime overrides grocery_access_score and crime_rate_per_100k
    """

    def __init__(
        self,
        primary: SdoHDataProvider,
        supplement: SdoHDataProvider | None = None,
        food_crime: SdoHDataProvider | None = None,
    ):
        self._primary = primary
        self._supplement = supplement
        self._food_crime = food_crime

    def fetch_metrics(self, zip_code: str) -> RawSdoHMetrics:
        """Fetch from primary, then override with supplements' non-default values."""
        # Get primary data (Census ACS: education, housing, transportation, food proxy)
        primary_metrics = self._primary.fetch_metrics(zip_code)

        updates = {}

        # AirNow supplement: override air quality if it has real data
        if self._supplement is not None:
            try:
                supp_metrics = self._supplement.fetch_metrics(zip_code)
                if supp_metrics.air_quality_index != 50.0:
                    updates["air_quality_index"] = supp_metrics.air_quality_index
            except Exception:
                pass

        # Food+Crime supplement: override grocery access and crime rate
        if self._food_crime is not None:
            try:
                fc_metrics = self._food_crime.fetch_metrics(zip_code)
                # Override grocery access if it's not the default (50)
                if fc_metrics.grocery_access_score != 50.0:
                    updates["grocery_access_score"] = fc_metrics.grocery_access_score
                # Override crime rate if it's not the national average (380)
                if fc_metrics.crime_rate_per_100k != 380.0:
                    updates["crime_rate_per_100k"] = fc_metrics.crime_rate_per_100k
            except Exception:
                pass

        if updates:
            return primary_metrics.model_copy(update=updates)
        return primary_metrics