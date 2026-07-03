"""Tests for Value Quantifier core functions.

Tests only pure core functions — no IO, no mocks, no network.
"""

import pytest
from shared.models import (
    ActionItem, CarePlan, FinancialImpact, PatientInput, PlanStatus,
    RiskProfile, RiskTier,
)
from features.value_quantifier import (
    quantify_value,
    estimate_annual_er_cost,
    estimate_cost_avoidance,
    estimate_intervention_cost,
    compute_confidence_score,
    ANNUAL_ER_COST_BY_TIER,
    COST_AVOIDANCE_RATE,
)


# ── Fixtures ───────────────────────────────────────────────────────────────

def _make_patient(**kwargs) -> PatientInput:
    defaults = dict(
        patient_id="P001", age=55, zip_code="37208",
        conditions=["diabetes", "hypertension"],
        medications=["metformin", "lisinopril"],
        prior_er_visits=2, is_adherent=False,
    )
    defaults.update(kwargs)
    return PatientInput(**defaults)


def _make_risk_profile(**kwargs) -> RiskProfile:
    defaults = dict(
        patient_id="P001", base_risk_score=20.0, final_risk_score=40.0,
        risk_tier=RiskTier.CRITICAL, primary_risk_factors=["diabetes"],
        applied_multipliers=[],
    )
    defaults.update(kwargs)
    return RiskProfile(**defaults)


def _make_care_plan(action_items=None, **kwargs) -> CarePlan:
    if action_items is None:
        action_items = [
            ActionItem(action="Meal program", category="social",
                       priority="high", target_date_days=7),
            ActionItem(action="Telehealth follow-up", category="monitoring",
                       priority="high", target_date_days=7),
            ActionItem(action="Medication adjustment", category="medication",
                       priority="medium", target_date_days=14),
        ]
    defaults = dict(
        patient_id="P001", reasoning="Test plan",
        action_items=action_items,
        status=PlanStatus.APPROVED,
        triggered_intervention_count=len(action_items),
    )
    defaults.update(kwargs)
    return CarePlan(**defaults)


# ── Annual ER Cost Tests ───────────────────────────────────────────────────

class TestEstimateAnnualErCost:
    def test_low_tier(self):
        assert estimate_annual_er_cost(RiskTier.LOW, 0) == 800.0

    def test_critical_tier(self):
        assert estimate_annual_er_cost(RiskTier.CRITICAL, 0) == 28000.0

    def test_er_visit_adjustment(self):
        """Each prior ER visit adds 20% to base."""
        base = ANNUAL_ER_COST_BY_TIER[RiskTier.HIGH]
        with_visits = estimate_annual_er_cost(RiskTier.HIGH, 2)
        assert with_visits == round(base * 1.4, 2)  # 2 visits = 40% increase

    def test_er_visit_capped_at_5(self):
        """Visits beyond 5 don't add more."""
        five = estimate_annual_er_cost(RiskTier.HIGH, 5)
        ten = estimate_annual_er_cost(RiskTier.HIGH, 10)
        assert five == ten


# ── Cost Avoidance Tests ───────────────────────────────────────────────────

class TestEstimateCostAvoidance:
    def test_zero_interventions(self):
        result = estimate_cost_avoidance(12000.0, RiskTier.HIGH, 0)
        assert result == 0.0

    def test_one_intervention(self):
        """1 intervention = 40% effectiveness × 50% avoidance rate × ER cost."""
        result = estimate_cost_avoidance(12000.0, RiskTier.HIGH, 1)
        # 12000 × 0.50 × 0.40 = 2400
        assert result == 2400.0

    def test_three_interventions(self):
        """3 interventions = 90% effectiveness (0.80 + 0.10) × 50% × 12000."""
        result = estimate_cost_avoidance(12000.0, RiskTier.HIGH, 3)
        # 12000 × 0.50 × 0.90 = 5400
        assert result == 5400.0

    def test_critical_tier_higher_rate(self):
        """Critical tier has 65% avoidance rate vs 50% for high."""
        high = estimate_cost_avoidance(28000.0, RiskTier.HIGH, 3)
        critical = estimate_cost_avoidance(28000.0, RiskTier.CRITICAL, 3)
        assert critical > high


# ── Intervention Cost Tests ────────────────────────────────────────────────

class TestEstimateInterventionCost:
    def test_social_intervention_cost(self):
        plan = _make_care_plan(action_items=[
            ActionItem(action="Meal program", category="social",
                       priority="high", target_date_days=7),
        ])
        cost = estimate_intervention_cost(plan)
        assert cost == 1500.0

    def test_multiple_categories(self):
        plan = _make_care_plan(action_items=[
            ActionItem(action="Meal program", category="social",
                       priority="high", target_date_days=7),
            ActionItem(action="Metformin adjustment", category="medication",
                       priority="medium", target_date_days=14),
            ActionItem(action="Exercise plan", category="lifestyle",
                       priority="low", target_date_days=30),
        ])
        cost = estimate_intervention_cost(plan)
        assert cost == 1500.0 + 300.0 + 500.0  # 2300.0


# ── Confidence Score Tests ─────────────────────────────────────────────────

class TestComputeConfidenceScore:
    def test_base_confidence_low_tier(self):
        score = compute_confidence_score(RiskTier.LOW, 0, True, 0)
        assert score == 0.60

    def test_base_confidence_critical_tier(self):
        score = compute_confidence_score(RiskTier.CRITICAL, 0, True, 0)
        assert score == 0.85

    def test_intervention_boost(self):
        base = compute_confidence_score(RiskTier.HIGH, 0, True, 0)
        with_boost = compute_confidence_score(RiskTier.HIGH, 4, True, 0)
        assert with_boost > base

    def test_non_adherence_penalty(self):
        adherent = compute_confidence_score(RiskTier.HIGH, 2, True, 1)
        non_adherent = compute_confidence_score(RiskTier.HIGH, 2, False, 1)
        assert adherent > non_adherent
        assert adherent - non_adherent == pytest.approx(0.10, abs=0.01)

    def test_er_visit_penalty(self):
        no_visits = compute_confidence_score(RiskTier.HIGH, 2, True, 0)
        with_visits = compute_confidence_score(RiskTier.HIGH, 2, True, 3)
        assert no_visits > with_visits

    def test_confidence_capped_below_1(self):
        """Confidence should never exceed max."""
        score = compute_confidence_score(RiskTier.CRITICAL, 10, True, 0)
        assert score <= 0.95

    def test_confidence_never_negative(self):
        score = compute_confidence_score(RiskTier.LOW, 0, False, 10)
        assert score >= 0.0


# ── Full quantify_value Integration Tests ──────────────────────────────────

class TestQuantifyValue:
    def test_returns_financial_impact(self):
        patient = _make_patient()
        risk = _make_risk_profile()
        plan = _make_care_plan()
        result = quantify_value(patient, risk, plan)
        assert isinstance(result, FinancialImpact)
        assert result.patient_id == "P001"

    def test_vetoed_plan_zero_savings(self):
        patient = _make_patient()
        risk = _make_risk_profile()
        plan = _make_care_plan(status=PlanStatus.VETOED, veto_reason="Test veto")
        result = quantify_value(patient, risk, plan)
        assert result.estimated_cost_avoidance == 0.0
        assert result.intervention_cost == 0.0
        assert result.net_savings == 0.0
        assert result.confidence_score == 0.0

    def test_critical_patient_positive_roi(self):
        """Critical patient with interventions should have positive net savings."""
        patient = _make_patient()
        risk = _make_risk_profile(risk_tier=RiskTier.CRITICAL)
        plan = _make_care_plan()
        result = quantify_value(patient, risk, plan)
        assert result.net_savings > 0
        assert result.roi_ratio > 0

    def test_low_risk_patient_smaller_savings(self):
        """Low risk patient should have smaller absolute savings."""
        patient = _make_patient(prior_er_visits=0, is_adherent=True)
        risk = _make_risk_profile(risk_tier=RiskTier.LOW, final_risk_score=5.0)
        plan = _make_care_plan()
        critical_patient = _make_patient()
        critical_risk = _make_risk_profile(risk_tier=RiskTier.CRITICAL)
        critical_plan = _make_care_plan()

        low_result = quantify_value(patient, risk, plan)
        critical_result = quantify_value(critical_patient, critical_risk, critical_plan)
        assert critical_result.estimated_cost_avoidance > low_result.estimated_cost_avoidance

    def test_roi_ratio_calculated(self):
        patient = _make_patient()
        risk = _make_risk_profile()
        plan = _make_care_plan()
        result = quantify_value(patient, risk, plan)
        if result.intervention_cost > 0:
            expected_roi = round(result.net_savings / result.intervention_cost, 2)
            assert result.roi_ratio == expected_roi

    def test_all_fields_populated(self):
        patient = _make_patient()
        risk = _make_risk_profile()
        plan = _make_care_plan()
        result = quantify_value(patient, risk, plan)
        assert result.estimated_annual_er_cost > 0
        assert result.estimated_cost_avoidance >= 0
        assert result.intervention_cost >= 0
        assert isinstance(result.net_savings, float)
        assert 0 <= result.confidence_score <= 1
        assert isinstance(result.roi_ratio, float)