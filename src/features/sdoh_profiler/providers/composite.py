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

    Priority: supplement overrides primary for the fields it provides
    (e.g., AirNow's air_quality_index overrides Census's default of 50).
    """

    def __init__(
        self,
        primary: SdoHDataProvider,
        supplement: SdoHDataProvider | None = None,
    ):
        self._primary = primary
        self._supplement = supplement

    def fetch_metrics(self, zip_code: str) -> RawSdoHMetrics:
        """Fetch from primary, then override with supplement's non-default values.

        The supplement's air_quality_index overrides the primary's if the
        supplement returns a non-default value (i.e., it actually got real data).
        """
        # Get primary data (Census ACS: education, housing, transportation, food proxy)
        primary_metrics = self._primary.fetch_metrics(zip_code)

        if self._supplement is None:
            return primary_metrics

        # Get supplemental data (AirNow: real-time air quality)
        try:
            supp_metrics = self._supplement.fetch_metrics(zip_code)

            # Override air quality if supplement has real data (not the default 50.0)
            # AirNow returns actual AQI; if it's different from the default, use it
            if supp_metrics.air_quality_index != 50.0:
                return primary_metrics.model_copy(update={
                    "air_quality_index": supp_metrics.air_quality_index,
                })
        except Exception:
            # If supplement fails, just use primary data
            pass

        return primary_metrics