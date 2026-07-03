"""SDOH Profiler — Port (abstract interface).

Defines the contract for fetching raw SDOH metrics.
Adapters in providers/ implement this interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from shared.models import RawSdoHMetrics


class SdoHDataProvider(ABC):
    """Port: Abstract interface for SDOH data sources.

    Implementations:
    - providers.mock.MockSdoHProvider  — deterministic test data
    - providers.census.CensusBureauProvider — live Census/CDC API
    """

    @abstractmethod
    def fetch_metrics(self, zip_code: str) -> RawSdoHMetrics:
        """Fetch raw SDOH metrics for a ZIP code.

        Args:
            zip_code: 5-digit ZIP code

        Returns:
            RawSdoHMetrics with all social determinant fields populated.
        """
        ...