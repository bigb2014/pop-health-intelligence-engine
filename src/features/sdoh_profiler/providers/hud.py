"""HUD ZIP-to-Tract crosswalk provider.

Uses the HUD USPS ZIP Code Crosswalk API to map ZIP codes to Census tracts.
This is needed because USDA Food Access Atlas data is at census-tract level,
and we need to aggregate it up to ZIP level.

API: https://www.huduser.gov/hudapi/public/usps
Token: Free registration at https://www.huduser.gov/hudapi/public/register
"""

from __future__ import annotations

import os
import json
import urllib.request
from typing import Any

from features.sdoh_profiler.base import SdoHDataProvider
from shared.models import RawSdoHMetrics


class HUDCrosswalkProvider:
    """Fetches ZIP-to-Census-tract crosswalk data from HUD API.

    This is NOT an SdoHDataProvider — it's a utility provider used by
    other adapters (like USDAFoodAccessProvider) to map tract-level data
    to ZIP level.
    """

    BASE_URL = "https://www.huduser.gov/hudapi/public/usps"

    def __init__(self, api_token: str | None = None):
        self._token = api_token or os.environ.get("HUD_API_TOKEN", "")

    def get_tracts_for_zip(self, zip_code: str, quarter: int = 1, year: int = 2026) -> list[dict]:
        """Get all Census tracts that intersect a ZIP code.

        Returns a list of dicts with:
        - geoid: Census tract FIPS code (11 digits)
        - res_ratio: fraction of residential addresses in this tract
        - bus_ratio: fraction of business addresses
        - tot_ratio: fraction of total addresses
        """
        if not self._token:
            return []

        url = f"{self.BASE_URL}?type=1&query={zip_code}&year={year}&quarter={quarter}"
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {self._token}",
            "User-Agent": "PopHealthEngine/0.1",
        })

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())

            results = data.get("data", {}).get("results", [])
            return [
                {
                    "geoid": r.get("geoid", ""),
                    "res_ratio": float(r.get("res_ratio", 0)),
                    "bus_ratio": float(r.get("bus_ratio", 0)),
                    "tot_ratio": float(r.get("tot_ratio", 0)),
                }
                for r in results
            ]
        except Exception:
            return []