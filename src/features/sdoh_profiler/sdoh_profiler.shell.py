"""SDOH Profiler — Imperative shell.

Flat, procedural IO code. Fetches raw metrics via a provider adapter,
then delegates to the pure core for normalization. No business logic here.
"""

from __future__ import annotations

from shared.models import SdoHProfile
from features.sdoh_profiler.base import SdoHDataProvider
from features.sdoh_profiler.core import build_sdoh_profile


def get_sdoh_profile(zip_code: str, provider: SdoHDataProvider) -> SdoHProfile:
    """Fetch raw SDOH data from provider and build normalized profile.

    Args:
        zip_code: 5-digit ZIP code
        provider: An SdoHDataProvider adapter (mock, census, etc.)

    Returns:
        Normalized SdoHProfile with 0-1 risk factors.
    """
    # IO: fetch from external source
    raw_metrics = provider.fetch_metrics(zip_code)

    # Pure: delegate to core for transformation
    return build_sdoh_profile(raw_metrics)