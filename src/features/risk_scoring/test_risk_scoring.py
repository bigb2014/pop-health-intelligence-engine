"""Tests for Risk Scoring Engine core functions.

Tests only pure core functions — no IO, no mocks, no network.
"""

import pytest
from shared.models import PatientInput, SdoHProfile, RiskTier
from features.risk_scoring import (
    compute_risk_profile,
    find_applicable_multipliers,
    classify_risk_tier,
    er_visit_risk,
    sdoh_risk_contribution,
    identify_primary_risk_factors,
    CONDITION_WEIGHTS,
)


# ── Fixtures ───────────────────────────────────────────────────────────────

def _make_sdoh(**kwargs) -> SdoHProfile:
    defaults = dict(
        zip_code="37208",
        air_quality_risk=0.18,
        food_desert_risk=0.9,
        housing_risk=0.75,
        transportation_risk=0.75,
        crime_risk=0.8,
        education_risk=0.4,
        overall_sdoh_risk=0.65,
    )
    defaults.update(kwargs)
    return SdoHProfile(**defaults)


def _make_patient(**kwargs) -> PatientInput:
    defaults = dict(
        patient_id="P001",
        age=55,
        zip_code="37208",
        conditions=["diabetes", "hypertension"],
        medications=["metformin", "lisinopril"],
        prior_er_visits=2,
        is_adherent=False,
    )
    defaults.update(kwargs)
    return PatientInput(**defaults)


# ── ER Visit Risk Tests ────────────────────────────────────────────────────

class TestErVisitRisk:
    def test_zero_visits(self):
        assert er_visit_risk(0) == 0.0

    def test_one_visit(self):
        assert er_visit_risk(1) == 1.5

    def test_three_visits(self):
        assert er_visit_risk(3) == 4.5

    def test_capped_at_five_visits(self):
        assert er_visit_risk(5) == 4.5


# ── Risk Tier Classification Tests ─────────────────────────────────────────

class TestClassifyRiskTier:
    def test_low(self):
        assert classify_risk_tier(5) == RiskTier.LOW

    def test_moderate(self):
        assert classify_risk_tier(15) == RiskTier.MODERATE

    def test_high(self):
        assert classify_risk_tier(25) == RiskTier.HIGH

    def test_critical(self):
        assert classify_risk_tier(40) == RiskTier.CRITICAL

    def test_boundary_low_moderate(self):
        assert classify_risk_tier(10) == RiskTier.MODERATE

    def test_boundary_moderate_high(self):
        assert classify_risk_tier(20) == RiskTier.HIGH

    def test_boundary_high_critical(self):
        assert classify_risk_tier(30) == RiskTier.CRITICAL


# ── Multiplier Tests (The "Secret Sauce") ──────────────────────────────────

class TestFindApplicableMultipliers:
    def test_diabetes_food_desert_triggers(self):
        """Diabetes + food_desert_risk >= 0.5 should trigger multiplier."""
        sdoh = _make_sdoh(food_desert_risk=0.9)
        multipliers = find_applicable_multipliers(["diabetes"], sdoh)
        diabetes_multipliers = [m for m in multipliers if m.condition_a == "diabetes"]
        assert len(diabetes_multipliers) >= 1
        assert any("food_desert" in m.condition_b for m in diabetes_multipliers)

    def test_diabetes_food_desert_below_threshold(self):
        """Diabetes + food_desert_risk < 0.5 should NOT trigger multiplier."""
        sdoh = _make_sdoh(food_desert_risk=0.3)
        multipliers = find_applicable_multipliers(["diabetes"], sdoh)
        food_desert = [m for m in multipliers if "food_desert" in m.condition_b]
        assert len(food_desert) == 0

    def test_copd_air_quality_triggers(self):
        sdoh = _make_sdoh(air_quality_risk=0.35)
        multipliers = find_applicable_multipliers(["copd"], sdoh)
        assert any(m.condition_a == "copd" for m in multipliers)

    def test_no_conditions_no_multipliers(self):
        sdoh = _make_sdoh()
        multipliers = find_applicable_multipliers([], sdoh)
        assert len(multipliers) == 0

    def test_multiple_conditions_multiple_multipliers(self):
        """Diabetes + hypertension in a high-risk area → multiple multipliers."""
        sdoh = _make_sdoh()
        multipliers = find_applicable_multipliers(
            ["diabetes", "hypertension"], sdoh
        )
        assert len(multipliers) >= 3  # diabetes+food, diabetes+transport, hypertension+housing, hypertension+food


# ── Full Risk Profile Computation Tests ────────────────────────────────────

class TestComputeRiskProfile:
    def test_returns_profile_with_patient_id(self):
        patient = _make_patient()
        sdoh = _make_sdoh()
        profile = compute_risk_profile(patient, sdoh)
        assert profile.patient_id == "P001"

    def test_base_score_includes_conditions(self):
        patient = _make_patient(conditions=["diabetes"], prior_er_visits=0, is_adherent=True)
        sdoh = _make_sdoh(overall_sdoh_risk=0.0, food_desert_risk=0.0,
                          housing_risk=0.0, transportation_risk=0.0,
                          crime_risk=0.0, education_risk=0.0, air_quality_risk=0.0)
        profile = compute_risk_profile(patient, sdoh)
        # diabetes weight = 6.0, no ER, no SDOH, adherent
        assert profile.base_risk_score == 6.0

    def test_non_adherence_adds_penalty(self):
        patient_adherent = _make_patient(
            conditions=["diabetes"], prior_er_visits=0, is_adherent=True
        )
        patient_non_adherent = _make_patient(
            conditions=["diabetes"], prior_er_visits=0, is_adherent=False
        )
        sdoh = _make_sdoh(overall_sdoh_risk=0.0, food_desert_risk=0.0,
                          housing_risk=0.0, transportation_risk=0.0,
                          crime_risk=0.0, education_risk=0.0, air_quality_risk=0.0)
        profile_a = compute_risk_profile(patient_adherent, sdoh)
        profile_n = compute_risk_profile(patient_non_adherent, sdoh)
        assert profile_n.base_risk_score > profile_a.base_risk_score
        assert profile_n.base_risk_score == profile_a.base_risk_score + 2.0

    def test_multiplier_amplifies_score(self):
        """Diabetes + food desert should produce higher score than diabetes alone."""
        patient = _make_patient(conditions=["diabetes"], prior_er_visits=0, is_adherent=True)
        sdoh_no_food_desert = _make_sdoh(
            food_desert_risk=0.0, transportation_risk=0.0,
            housing_risk=0.0, overall_sdoh_risk=0.0,
            air_quality_risk=0.0, crime_risk=0.0, education_risk=0.0,
        )
        sdoh_food_desert = _make_sdoh(
            food_desert_risk=0.9, transportation_risk=0.0,
            housing_risk=0.0, overall_sdoh_risk=0.225,  # 0.9 * 0.25 weight
            air_quality_risk=0.0, crime_risk=0.0, education_risk=0.0,
        )
        profile_no = compute_risk_profile(patient, sdoh_no_food_desert)
        profile_yes = compute_risk_profile(patient, sdoh_food_desert)
        assert profile_yes.final_risk_score > profile_no.final_risk_score
        assert len(profile_yes.applied_multipliers) > 0
        assert len(profile_no.applied_multipliers) == 0

    def test_critical_risk_scenario(self):
        """Diabetic, non-adherent, in food desert, prior ER visits → critical."""
        patient = _make_patient(
            conditions=["diabetes", "hypertension"],
            prior_er_visits=3,
            is_adherent=False,
        )
        sdoh = _make_sdoh()
        profile = compute_risk_profile(patient, sdoh)
        assert profile.risk_tier == RiskTier.CRITICAL
        assert profile.final_risk_score >= 30

    def test_low_risk_scenario(self):
        """Healthy patient in good area → low risk."""
        patient = _make_patient(
            conditions=[],
            prior_er_visits=0,
            is_adherent=True,
        )
        sdoh = _make_sdoh(
            air_quality_risk=0.1, food_desert_risk=0.1,
            housing_risk=0.1, transportation_risk=0.1,
            crime_risk=0.1, education_risk=0.1,
            overall_sdoh_risk=0.1,
        )
        profile = compute_risk_profile(patient, sdoh)
        assert profile.risk_tier == RiskTier.LOW

    def test_primary_risk_factors_populated(self):
        patient = _make_patient()
        sdoh = _make_sdoh()
        profile = compute_risk_profile(patient, sdoh)
        assert len(profile.primary_risk_factors) > 0
        assert any("diabetes" in f.lower() for f in profile.primary_risk_factors)

    def test_sdoh_profile_attached(self):
        patient = _make_patient()
        sdoh = _make_sdoh()
        profile = compute_risk_profile(patient, sdoh)
        assert profile.sdoh_profile is not None
        assert profile.sdoh_profile.zip_code == sdoh.zip_code