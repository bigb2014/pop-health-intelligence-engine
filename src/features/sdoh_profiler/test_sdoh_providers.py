"""Tests for new SDOH provider adapters.

Tests for CensusACSProvider, AirNowProvider, CompositeSdoHProvider,
and LocalDbSdoHProvider. These test the pure logic (normalization,
merging, DB operations) without requiring live API keys.
"""

import pytest
import os
import tempfile
from unittest.mock import MagicMock, patch

from shared.models import RawSdoHMetrics
from features.sdoh_profiler.base import SdoHDataProvider
from features.sdoh_profiler.providers.census import CensusACSProvider
from features.sdoh_profiler.providers.airnow import AirNowProvider
from features.sdoh_profiler.providers.composite import CompositeSdoHProvider
from features.sdoh_profiler.providers.local_db import LocalDbSdoHProvider


# ── Census ACS Provider Tests ────────────────────────────────────────────

class TestCensusACSProvider:
    def test_no_key_returns_fallback(self):
        """Without an API key, should return national-average fallback."""
        provider = CensusACSProvider(api_key="")
        # _query_zcta returns empty dict without a key (API redirects)
        with patch.object(provider, '_query_zcta', return_value={}):
            metrics = provider.fetch_metrics("37208")
            assert metrics.zip_code == "37208"
            assert metrics.education_attainment_pct == 80  # National avg
            assert metrics.air_quality_index == 50

    def test_with_mock_data_normalizes_correctly(self):
        """Test normalization with mocked ACS API response."""
        provider = CensusACSProvider(api_key="fake_key")

        mock_acs_data = {
            "B15003_017E": "15000",  # 15K with HS diploma
            "B15003_001E": "20000",  # 20K total 25+
            "B25070_007E": "1000",   # cost burdened
            "B25070_008E": "500",
            "B25070_009E": "300",
            "B25070_010E": "200",
            "B25070_001E": "10000",  # total housing
            "B25014_005E": "100",    # overcrowded
            "B25014_006E": "50",
            "B25014_007E": "25",
            "B25014_001E": "10000",
            "B25003_003E": "6000",   # renter occupied
            "B25003_001E": "10000",  # total housing units
            "B25044_003E": "2000",   # no vehicle
            "B25044_001E": "10000",  # total vehicles
            "B17001_002E": "5000",   # below poverty
            "B17001_001E": "20000",  # total poverty
            "B01003_001E": "25000",  # total pop
        }

        with patch.object(provider, '_query_zcta', return_value=mock_acs_data):
            metrics = provider.fetch_metrics("37208")
            assert metrics.zip_code == "37208"
            assert metrics.education_attainment_pct == 75.0  # 15000/20000 * 100
            assert metrics.transportation_access_score < 100  # Some have no vehicle
            assert metrics.grocery_access_score < 100  # Some poverty

    def test_fallback_metrics_structure(self):
        provider = CensusACSProvider(api_key="")
        metrics = provider._fallback_metrics("99999")
        assert metrics.zip_code == "99999"
        assert 0 <= metrics.air_quality_index <= 500
        assert 0 <= metrics.grocery_access_score <= 100
        assert 0 <= metrics.housing_instability_score <= 100
        assert 0 <= metrics.transportation_access_score <= 100
        assert metrics.crime_rate_per_100k > 0


# ── AirNow Provider Tests ─────────────────────────────────────────────────

class TestAirNowProvider:
    def test_no_key_returns_default_aqi(self):
        """Without API key, should return default AQI of 50."""
        provider = AirNowProvider(api_key="")
        assert provider.fetch_air_quality("37208") is None

    def test_fetch_metrics_returns_defaults(self):
        """fetch_metrics should return partial metrics with default non-air fields."""
        provider = AirNowProvider(api_key="")
        metrics = provider.fetch_metrics("37208")
        assert metrics.zip_code == "37208"
        assert metrics.air_quality_index == 50.0  # Default
        assert metrics.grocery_access_score == 50  # Neutral default

    def test_with_mock_air_quality(self):
        """Test with mocked AirNow API response."""
        provider = AirNowProvider(api_key="fake_key")

        mock_response = [
            {"AQI": 72, "ParameterName": "PM2.5", "Category": {"Number": 2}},
            {"AQI": 45, "ParameterName": "Ozone", "Category": {"Number": 1}},
        ]

        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'[{"AQI": 72, "ParameterName": "PM2.5"}, {"AQI": 45, "ParameterName": "Ozone"}]'
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp

            aqi = provider.fetch_air_quality("37208")
            assert aqi == 72  # Should return the highest AQI


# ── Composite Provider Tests ──────────────────────────────────────────────

class TestCompositeSdoHProvider:
    def test_primary_only_works(self):
        """Composite with no supplement should return primary data."""
        primary = MagicMock(spec=SdoHDataProvider)
        primary.fetch_metrics.return_value = RawSdoHMetrics(
            zip_code="37208", air_quality_index=50, grocery_access_score=30,
            housing_instability_score=60, transportation_access_score=40,
            crime_rate_per_100k=800, education_attainment_pct=75,
        )
        composite = CompositeSdoHProvider(primary=primary, supplement=None)
        metrics = composite.fetch_metrics("37208")
        assert metrics.air_quality_index == 50
        assert metrics.grocery_access_score == 30

    def test_supplement_overrides_air_quality(self):
        """AirNow should override Census default AQI when it has real data."""
        primary = MagicMock(spec=SdoHDataProvider)
        primary.fetch_metrics.return_value = RawSdoHMetrics(
            zip_code="37208", air_quality_index=50, grocery_access_score=30,
            housing_instability_score=60, transportation_access_score=40,
            crime_rate_per_100k=800, education_attainment_pct=75,
        )
        supplement = MagicMock(spec=SdoHDataProvider)
        supplement.fetch_metrics.return_value = RawSdoHMetrics(
            zip_code="37208", air_quality_index=85, grocery_access_score=50,
            housing_instability_score=40, transportation_access_score=50,
            crime_rate_per_100k=380, education_attainment_pct=80,
        )
        composite = CompositeSdoHProvider(primary=primary, supplement=supplement)
        metrics = composite.fetch_metrics("37208")
        assert metrics.air_quality_index == 85  # Overridden by supplement
        assert metrics.grocery_access_score == 30  # From primary (not overridden)
        assert metrics.education_attainment_pct == 75  # From primary

    def test_supplement_failure_falls_back_to_primary(self):
        """If supplement raises an exception, should still return primary data."""
        primary = MagicMock(spec=SdoHDataProvider)
        primary.fetch_metrics.return_value = RawSdoHMetrics(
            zip_code="37208", air_quality_index=50, grocery_access_score=30,
            housing_instability_score=60, transportation_access_score=40,
            crime_rate_per_100k=800, education_attainment_pct=75,
        )
        supplement = MagicMock(spec=SdoHDataProvider)
        supplement.fetch_metrics.side_effect = Exception("API down")

        composite = CompositeSdoHProvider(primary=primary, supplement=supplement)
        metrics = composite.fetch_metrics("37208")
        assert metrics.air_quality_index == 50  # Primary default
        assert metrics.grocery_access_score == 30  # Primary


# ── Local DB Provider Tests ───────────────────────────────────────────────

class TestLocalDbSdoHProvider:
    def test_missing_db_raises_filenotfound(self):
        provider = LocalDbSdoHProvider(db_path="/nonexistent/path/sdoh.db")
        with pytest.raises(FileNotFoundError):
            provider.fetch_metrics("37208")

    def test_upsert_and_fetch_roundtrip(self):
        """Should be able to insert metrics and read them back."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            provider = LocalDbSdoHProvider(db_path=db_path)

            # Insert test data
            test_metrics = RawSdoHMetrics(
                zip_code="37208", air_quality_index=65, grocery_access_score=15,
                housing_instability_score=70, transportation_access_score=25,
                crime_rate_per_100k=1200, education_attainment_pct=60,
            )
            provider.upsert_metrics(test_metrics, source="test")

            # Read it back
            metrics = provider.fetch_metrics("37208")
            assert metrics.zip_code == "37208"
            assert metrics.air_quality_index == 65
            assert metrics.grocery_access_score == 15
            assert metrics.housing_instability_score == 70
            assert metrics.transportation_access_score == 25
            assert metrics.crime_rate_per_100k == 1200
            assert metrics.education_attainment_pct == 60
        finally:
            os.unlink(db_path)

    def test_missing_zip_returns_fallback(self):
        """If ZIP code isn't in DB, should return national averages."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            provider = LocalDbSdoHProvider(db_path=db_path)

            # Insert one ZIP
            test_metrics = RawSdoHMetrics(
                zip_code="37208", air_quality_index=65, grocery_access_score=15,
                housing_instability_score=70, transportation_access_score=25,
                crime_rate_per_100k=1200, education_attainment_pct=60,
            )
            provider.upsert_metrics(test_metrics, source="test")

            # Query a different ZIP that doesn't exist
            metrics = provider.fetch_metrics("99999")
            assert metrics.zip_code == "99999"
            assert metrics.air_quality_index == 50  # National avg
            assert metrics.education_attainment_pct == 80  # National avg
        finally:
            os.unlink(db_path)

    def test_upsert_updates_existing(self):
        """Upserting the same ZIP should update, not duplicate."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            provider = LocalDbSdoHProvider(db_path=db_path)

            # Insert
            provider.upsert_metrics(RawSdoHMetrics(
                zip_code="37208", air_quality_index=40, grocery_access_score=50,
                housing_instability_score=30, transportation_access_score=60,
                crime_rate_per_100k=400, education_attainment_pct=85,
            ))

            # Update with different values
            provider.upsert_metrics(RawSdoHMetrics(
                zip_code="37208", air_quality_index=75, grocery_access_score=10,
                housing_instability_score=80, transportation_access_score=20,
                crime_rate_per_100k=1500, education_attainment_pct=55,
            ))

            # Should have the updated values
            metrics = provider.fetch_metrics("37208")
            assert metrics.air_quality_index == 75
            assert metrics.grocery_access_score == 10
            assert metrics.education_attainment_pct == 55
        finally:
            os.unlink(db_path)