"""EPA AirNow air quality data provider.

Fetches real-time air quality index (AQI) by ZIP code from the EPA AirNow API.
This adapter supplements the Census ACS provider with actual air quality data.

API docs: https://docs.airnowapi.org/
Free key: https://docs.airnowapi.org/airnow/downloads/
"""

from __future__ import annotations

import os
import urllib.request
import json
from typing import Any

from shared.models import RawSdoHMetrics
from features.sdoh_profiler.base import SdoHDataProvider


class AirNowProvider(SdoHDataProvider):
    """Live adapter for EPA AirNow air quality data by ZIP code.

    Requires a free AirNow API key. Get one at:
    https://docs.airnowapi.org/airnow/downloads/

    This provider ONLY fetches air quality. It must be combined with
    another provider (like CensusACSProvider) for the other SDOH dimensions.
    Use CompositeSdoHProvider to merge them.
    """

    BASE_URL = "https://www.airnowapi.org/aq/observation/zipCode/current/"

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or os.environ.get("AIRNOW_API_KEY", "")

    def fetch_air_quality(self, zip_code: str) -> float | None:
        """Fetch current AQI for a ZIP code.

        Returns the AQI value or None if unavailable.
        """
        if not self._api_key:
            return None

        url = (
            f"{self.BASE_URL}?format=application/json"
            f"&zipCode={zip_code}&distance=25"
            f"&API_KEY={self._api_key}"
        )
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "PopHealthEngine/0.1"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())

            if not data or not isinstance(data, list):
                return None

            # Return the highest AQI from the observations (multiple pollutants)
            aqi_values = [obs.get("AQI") for obs in data if obs.get("AQI")]
            return max(aqi_values) if aqi_values else None
        except Exception:
            return None

    def fetch_metrics(self, zip_code: str) -> RawSdoHMetrics:
        """Fetch air quality and return partial metrics.

        NOTE: This returns ONLY air quality data. All other fields are
        set to neutral defaults. Use CompositeSdoHProvider to merge with
        a Census ACS provider for complete SDOH data.
        """
        aqi = self.fetch_air_quality(zip_code)
        aqi_value = aqi if aqi is not None else 50.0

        return RawSdoHMetrics(
            zip_code=zip_code,
            air_quality_index=aqi_value,
            grocery_access_score=50,        # Neutral default
            housing_instability_score=40,   # Neutral default
            transportation_access_score=50,  # Neutral default
            crime_rate_per_100k=380,         # National average
            education_attainment_pct=80,     # National average
        )