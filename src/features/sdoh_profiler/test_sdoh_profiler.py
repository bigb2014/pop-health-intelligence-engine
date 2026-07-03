"""Tests for SDOH Profiler core functions.

Tests only pure core functions — no IO, no mocks, no network.
"""

import pytest
from shared.models import RawSdoHMetrics
from features.sdoh_profiler import (
    build_sdoh_profile,
    normalize_air_quality,
    normalize_food_access,
    normalize_housing,
    normalize_transportation,
    normalize_crime,
    normalize_education,
    compute_overall_risk,
)


# ── Normalization Tests ────────────────────────────────────────────────────

class TestNormalizeAirQuality:
    def test_good_air(self):
        assert normalize_air_quality(0) == 0.0
        assert normalize_air_quality(50) == pytest.approx(0.1667, abs=0.01)

    def test_hazardous(self):
        assert normalize_air_quality(300) == 0.6
        assert normalize_air_quality(500) == 1.0

    def test_zero(self):
        assert normalize_air_quality(0) == 0.0


class TestNormalizeFoodAccess:
    def test_food_desert(self):
        """Score 0 = full food desert → risk 1.0"""
        assert normalize_food_access(0) == 1.0

    def test_excellent_access(self):
        """Score 100 = excellent → risk 0.0"""
        assert normalize_food_access(100) == 0.0

    def test_midpoint(self):
        assert normalize_food_access(50) == 0.5


class TestNormalizeHousing:
    def test_stable(self):
        assert normalize_housing(0) == 0.0

    def test_unstable(self):
        assert normalize_housing(100) == 1.0

    def test_midpoint(self):
        assert normalize_housing(50) == 0.5


class TestNormalizeTransportation:
    def test_no_access(self):
        assert normalize_transportation(0) == 1.0

    def test_excellent(self):
        assert normalize_transportation(100) == 0.0


class TestNormalizeCrime:
    def test_no_crime(self):
        assert normalize_crime(0) == 0.0

    def test_high_crime(self):
        assert normalize_crime(1500) == 1.0
        assert normalize_crime(2000) == 1.0  # capped

    def test_moderate(self):
        assert normalize_crime(750) == 0.5


class TestNormalizeEducation:
    def test_full_education(self):
        assert normalize_education(100) == 0.0

    def test_no_education(self):
        assert normalize_education(0) == 1.0


# ── Composite Risk Tests ───────────────────────────────────────────────────

class TestComputeOverallRisk:
    def test_all_zero_risk(self):
        result = compute_overall_risk(0, 0, 0, 0, 0, 0)
        assert result == 0.0

    def test_all_max_risk(self):
        result = compute_overall_risk(1, 1, 1, 1, 1, 1)
        assert result == 1.0

    def test_food_has_highest_weight(self):
        """Food access carries 25% weight — highest."""
        food_only = compute_overall_risk(0, 1.0, 0, 0, 0, 0)
        crime_only = compute_overall_risk(0, 0, 0, 0, 1.0, 0)
        assert food_only > crime_only
        assert food_only == 0.25
        assert crime_only == 0.10


# ── Integration: build_sdoh_profile ────────────────────────────────────────

class TestBuildSdohProfile:
    def _make_metrics(self, **kwargs) -> RawSdoHMetrics:
        defaults = dict(
            zip_code="37115",
            air_quality_index=45,
            grocery_access_score=20,
            housing_instability_score=60,
            transportation_access_score=30,
            crime_rate_per_100k=800,
            education_attainment_pct=75,
        )
        defaults.update(kwargs)
        return RawSdoHMetrics(**defaults)

    def test_returns_profile_with_correct_zip(self):
        metrics = self._make_metrics(zip_code="37208")
        profile = build_sdoh_profile(metrics)
        assert profile.zip_code == "37208"

    def test_food_desert_risk_correct(self):
        metrics = self._make_metrics(grocery_access_score=20)
        profile = build_sdoh_profile(metrics)
        assert profile.food_desert_risk == 0.8

    def test_overall_risk_in_range(self):
        metrics = self._make_metrics()
        profile = build_sdoh_profile(metrics)
        assert 0.0 <= profile.overall_sdoh_risk <= 1.0

    def test_low_risk_zip(self):
        """Brentwood-like area should have low overall risk."""
        metrics = self._make_metrics(
            air_quality_index=30, grocery_access_score=90,
            housing_instability_score=15, transportation_access_score=85,
            crime_rate_per_100k=100, education_attainment_pct=95,
        )
        profile = build_sdoh_profile(metrics)
        assert profile.overall_sdoh_risk < 0.2

    def test_high_risk_zip(self):
        """North Nashville-like area should have high overall risk."""
        metrics = self._make_metrics(
            air_quality_index=55, grocery_access_score=10,
            housing_instability_score=75, transportation_access_score=25,
            crime_rate_per_100k=1200, education_attainment_pct=60,
        )
        profile = build_sdoh_profile(metrics)
        assert profile.overall_sdoh_risk > 0.5

    def test_all_fields_populated(self):
        metrics = self._make_metrics()
        profile = build_sdoh_profile(metrics)
        assert profile.air_quality_risk is not None
        assert profile.food_desert_risk is not None
        assert profile.housing_risk is not None
        assert profile.transportation_risk is not None
        assert profile.crime_risk is not None
        assert profile.education_risk is not None
        assert profile.overall_sdoh_risk is not None