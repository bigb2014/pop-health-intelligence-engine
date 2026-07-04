"""Tests for CHAS housing affordability adapter."""

import pytest
from unittest.mock import MagicMock, patch

from shared.models import RawSdoHMetrics
from features.sdoh_profiler.base import SdoHDataProvider
from features.sdoh_profiler.providers.chas import CHASHousingProvider
from features.sdoh_profiler.providers.composite import CompositeSdoHProvider


class TestCHASHousingProvider:
    def test_no_token_returns_default_housing(self):
        """Without a HUD token, should return default housing score (40.0)."""
        provider = CHASHousingProvider(api_token="")
        metrics = provider.fetch_metrics("37208")
        assert metrics.housing_instability_score == 40.0  # Default

    def test_unknown_state_returns_default(self):
        """ZIP codes with unknown state prefix should use default."""
        provider = CHASHousingProvider(api_token="fake_token")
        metrics = provider.fetch_metrics("90210")  # CA, not in our map
        # 90 is in the map (maps to CA=06), but with fake token API will fail
        # and return default
        assert metrics.housing_instability_score == 40.0

    def test_other_fields_are_neutral(self):
        """Non-housing fields should be neutral defaults."""
        provider = CHASHousingProvider(api_token="")
        metrics = provider.fetch_metrics("37208")
        assert metrics.air_quality_index == 50
        assert metrics.grocery_access_score == 50
        assert metrics.transportation_access_score == 50
        assert metrics.crime_rate_per_100k == 380
        assert metrics.education_attainment_pct == 80

    def test_compute_housing_instability_with_real_data(self):
        """Test the scoring formula with realistic CHAS values."""
        provider = CHASHousingProvider(api_token="fake")

        # Simulate TN CHAS data
        # A1-A6 (total households): ~1.27M total
        # A7-A12 (cost burdened): ~500K (about 39%)
        # A13-A18 (severely burdened): ~200K (about 16%)
        # B5+B6 (severe problems): ~2.5M total
        chas_data = {
            "A1": 130000, "A2": 200000, "A3": 330000,
            "A4": 157000, "A5": 145000, "A6": 303000,
            # total = 1,265,000
            "A7": 100000, "A8": 80000, "A9": 120000,
            "A10": 90000, "A11": 60000, "A12": 50000,
            # cost burdened = 500,000 (39.5%)
            "A13": 40000, "A14": 35000, "A15": 45000,
            "A16": 40000, "A17": 20000, "A18": 20000,
            # severe burdened = 200,000 (15.8%)
            "B5": 100000, "B6": 200000,
            # severe problems = 300,000 (23.7%)
        }

        score = provider._compute_housing_instability(chas_data)
        # Expected: 0.395*40 + min(0.158*2,1.0)*30 + min(0.237,1.0)*30
        # = 15.8 + 9.5 + 7.1 = 32.4
        assert 25 < score < 45  # In reasonable range
        assert score > 0

    def test_compute_housing_instability_zero_data(self):
        """Empty CHAS data should return default fallback."""
        provider = CHASHousingProvider(api_token="")
        score = provider._compute_housing_instability({})
        assert score == 40.0

    def test_compute_housing_instability_high_burden(self):
        """High cost burden should produce high instability score."""
        provider = CHASHousingProvider(api_token="")

        chas_data = {
            "A1": 100000, "A2": 100000, "A3": 100000,
            "A4": 100000, "A5": 100000, "A6": 100000,
            # total = 600,000
            "A7": 200000, "A8": 200000, "A9": 200000,
            "A10": 200000, "A11": 200000, "A12": 200000,
            # cost burdened = 1.2M (200% — more burdened than total, unrealistic
            # but tests the cap)
            "A13": 100000, "A14": 100000, "A15": 100000,
            "A16": 100000, "A17": 100000, "A18": 100000,
            # severe burdened = 600K (100%)
            "B5": 300000, "B6": 300000,
            # severe problems = 600K (100%)
        }

        score = provider._compute_housing_instability(chas_data)
        # Expected: 1.0*40 + min(2.0,1.0)*30 + min(1.0,1.0)*30 = 40+30+30 = 100
        assert score == 100.0  # Capped at 100

    def test_caching_works(self):
        """CHAS provider should cache state-level data."""
        provider = CHASHousingProvider(api_token="fake")

        # Mock the API response at the urllib level so _query_chas caches it
        mock_response_data = [
            {"A1": "100", "A2": "100", "A3": "100", "A4": "100", "A5": "100", "A6": "100",
             "geoname": "Tennessee", "year": "2018-2022"}
        ]

        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'[{"A1":"100","A2":"100","A3":"100","A4":"100","A5":"100","A6":"100","geoname":"Tennessee","year":"2018-2022"}]'
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp

            # Clear cache
            CHASHousingProvider._cache.clear()

            # First call — should query API and cache
            provider.fetch_metrics("37208")
            assert "47" in CHASHousingProvider._cache

            # Second call — should use cache (urlopen not called again)
            call_count_before = mock_urlopen.call_count
            provider.fetch_metrics("37211")
            assert mock_urlopen.call_count == call_count_before  # No new API call


class TestCompositeWithCHAS:
    def test_chas_overrides_housing(self):
        """CHAS should override housing_instability_score from primary."""
        primary = MagicMock(spec=SdoHDataProvider)
        primary.fetch_metrics.return_value = RawSdoHMetrics(
            zip_code="37208", air_quality_index=50, grocery_access_score=30,
            housing_instability_score=55, transportation_access_score=40,
            crime_rate_per_100k=380, education_attainment_pct=75,
        )
        chas = MagicMock(spec=SdoHDataProvider)
        chas.fetch_metrics.return_value = RawSdoHMetrics(
            zip_code="37208", air_quality_index=50, grocery_access_score=50,
            housing_instability_score=72.5, transportation_access_score=50,
            crime_rate_per_100k=380, education_attainment_pct=80,
        )
        composite = CompositeSdoHProvider(
            primary=primary, supplement=None, food_crime=None, chas=chas,
        )
        metrics = composite.fetch_metrics("37208")
        assert metrics.housing_instability_score == 72.5  # Overridden by CHAS
        assert metrics.grocery_access_score == 30  # From primary (not overridden)
        assert metrics.education_attainment_pct == 75  # From primary

    def test_chas_default_does_not_override(self):
        """If CHAS returns default (40.0), should NOT override primary."""
        primary = MagicMock(spec=SdoHDataProvider)
        primary.fetch_metrics.return_value = RawSdoHMetrics(
            zip_code="37208", air_quality_index=50, grocery_access_score=30,
            housing_instability_score=55, transportation_access_score=40,
            crime_rate_per_100k=380, education_attainment_pct=75,
        )
        chas = MagicMock(spec=SdoHDataProvider)
        chas.fetch_metrics.return_value = RawSdoHMetrics(
            zip_code="37208", air_quality_index=50, grocery_access_score=50,
            housing_instability_score=40.0,  # Default — should NOT override
            transportation_access_score=50,
            crime_rate_per_100k=380, education_attainment_pct=80,
        )
        composite = CompositeSdoHProvider(
            primary=primary, chas=chas,
        )
        metrics = composite.fetch_metrics("37208")
        assert metrics.housing_instability_score == 55  # From primary (CHAS default didn't override)

    def test_all_four_sources_merged(self):
        """Census + AirNow + FoodCrime + CHAS all contribute their fields."""
        primary = MagicMock(spec=SdoHDataProvider)
        primary.fetch_metrics.return_value = RawSdoHMetrics(
            zip_code="37208", air_quality_index=50, grocery_access_score=30,
            housing_instability_score=55, transportation_access_score=40,
            crime_rate_per_100k=380, education_attainment_pct=75,
        )
        airnow = MagicMock(spec=SdoHDataProvider)
        airnow.fetch_metrics.return_value = RawSdoHMetrics(
            zip_code="37208", air_quality_index=72, grocery_access_score=50,
            housing_instability_score=40, transportation_access_score=50,
            crime_rate_per_100k=380, education_attainment_pct=80,
        )
        food_crime = MagicMock(spec=SdoHDataProvider)
        food_crime.fetch_metrics.return_value = RawSdoHMetrics(
            zip_code="37208", air_quality_index=50, grocery_access_score=10,
            housing_instability_score=40, transportation_access_score=50,
            crime_rate_per_100k=1243, education_attainment_pct=80,
        )
        chas = MagicMock(spec=SdoHDataProvider)
        chas.fetch_metrics.return_value = RawSdoHMetrics(
            zip_code="37208", air_quality_index=50, grocery_access_score=50,
            housing_instability_score=68.5, transportation_access_score=50,
            crime_rate_per_100k=380, education_attainment_pct=80,
        )
        composite = CompositeSdoHProvider(
            primary=primary, supplement=airnow, food_crime=food_crime, chas=chas,
        )
        metrics = composite.fetch_metrics("37208")
        assert metrics.air_quality_index == 72       # From AirNow
        assert metrics.grocery_access_score == 10     # From FoodCrime
        assert metrics.crime_rate_per_100k == 1243   # From FoodCrime
        assert metrics.housing_instability_score == 68.5  # From CHAS
        assert metrics.education_attainment_pct == 75  # From Census
        assert metrics.transportation_access_score == 40  # From Census