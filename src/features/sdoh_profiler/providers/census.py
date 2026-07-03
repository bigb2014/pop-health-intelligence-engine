"""Census Bureau SDOH data provider — live API adapter.

Fetches real SDOH metrics from Census / CDC APIs.
Requires API key set in environment variable CENSUS_API_KEY.
"""

from __future__ import annotations

import os

from shared.models import RawSdoHMetrics
from features.sdoh_profiler.base import SdoHDataProvider


class CensusBureauProvider(SdoHDataProvider):
    """Live adapter for Census Bureau / CDC SDOH data.

    NOTE: This is a stub implementation. In production, this would call
    the Census API (api.census.gov) and EPA AirNow API.
    """

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or os.environ.get("CENSUS_API_KEY", "")

    def fetch_metrics(self, zip_code: str) -> RawSdoHMetrics:
        # IO: would make real API calls here
        raise NotImplementedError(
            "CensusBureauProvider requires implementation with live API calls. "
            "Set CENSUS_API_KEY and implement fetch_metrics with Census API calls."
        )