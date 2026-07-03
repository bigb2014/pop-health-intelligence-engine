"""Tests for Intervention Strategist core functions.

Tests only pure core functions — the critic, prompt builder, and parser.
No IO, no mocks, no network, no LLM calls.
"""

import json
import pytest
from shared.models import (
    ActionItem, CarePlan, PatientInput, PlanStatus, RiskProfile, RiskTier, SdoHProfile,
)
from features.intervention_strategist import (
    validate_care_plan,
    build_llm_prompt,
    parse_llm_response,
    validate_medication_safety,
    validate_non_adherence_safety,
    validate_specialist_referral,
    validate_priority_alignment,
    validate_plan_completeness,
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
        risk_tier=RiskTier.CRITICAL, primary_risk_factors=["diabetes", "food desert"],
        applied_multipliers=[],
    )
    defaults.update(kwargs)
    return RiskProfile(**defaults)


def _make_action_item(**kwargs) -> ActionItem:
    defaults = dict(
        action="Test action", category="monitoring",
        priority="medium", target_date_days=7,
    )
    defaults.update(kwargs)
    return ActionItem(**defaults)


def _make_care_plan(action_items: list[ActionItem], **kwargs) -> CarePlan:
    defaults = dict(
        patient_id="P001", reasoning="Test reasoning",
        action_items=action_items,
        status=PlanStatus.NEEDS_REVISION,
        triggered_intervention_count=len(action_items),
    )
    defaults.update(kwargs)
    return CarePlan(**defaults)


# ── Critic: Medication Safety Tests ────────────────────────────────────────

class TestValidateMedicationSafety:
    def test_safe_medication_passes(self):
        patient = _make_patient(medications=["metformin"])
        items = [_make_action_item(
            action="Continue metformin 500mg twice daily",
            category="medication",
        )]
        assert validate_medication_safety(items, patient) is None

    def test_contraindicated_medication_flagged(self):
        patient = _make_patient(medications=["warfarin"])
        items = [_make_action_item(
            action="Start daily aspirin 81mg for cardiovascular protection",
            category="medication",
        )]
        result = validate_medication_safety(items, patient)
        assert result is not None
        assert "CONTRAINDICATION" in result

    def test_dangerous_dosage_flagged(self):
        patient = _make_patient(medications=["metformin"])
        items = [_make_action_item(
            action="Increase metformin to 3000mg daily",
            category="medication",
        )]
        result = validate_medication_safety(items, patient)
        assert result is not None
        assert "DOSAGE EXCEEDED" in result

    def test_safe_dosage_passes(self):
        patient = _make_patient(medications=["metformin"])
        items = [_make_action_item(
            action="Continue metformin 2000mg daily",
            category="medication",
        )]
        assert validate_medication_safety(items, patient) is None


# ── Critic: Non-Adherence Tests ────────────────────────────────────────────

class TestValidateNonAdherence:
    def test_too_many_meds_for_non_adherent(self):
        patient = _make_patient(is_adherent=False)
        items = [
            _make_action_item(action="Start metformin", category="medication"),
            _make_action_item(action="Start lisinopril", category="medication"),
            _make_action_item(action="Start atorvastatin", category="medication"),
        ]
        result = validate_non_adherence_safety(items, patient)
        assert result is not None
        assert "NON-ADHERENCE" in result

    def test_two_meds_ok_for_non_adherent(self):
        patient = _make_patient(is_adherent=False)
        items = [
            _make_action_item(action="Start metformin", category="medication"),
            _make_action_item(action="Start lisinopril", category="medication"),
        ]
        assert validate_non_adherence_safety(items, patient) is None

    def test_adherent_patient_no_restriction(self):
        patient = _make_patient(is_adherent=True)
        items = [
            _make_action_item(action="Start metformin", category="medication"),
            _make_action_item(action="Start lisinopril", category="medication"),
            _make_action_item(action="Start atorvastatin", category="medication"),
            _make_action_item(action="Start amlodipine", category="medication"),
        ]
        assert validate_non_adherence_safety(items, patient) is None


# ── Critic: Specialist Referral Tests ──────────────────────────────────────

class TestValidateSpecialistReferral:
    def test_missing_specialist_flagged(self):
        patient = _make_patient(conditions=["heart_disease"])
        items = [_make_action_item(action="Continue current medications", category="monitoring")]
        result = validate_specialist_referral(items, patient)
        assert result is not None
        assert "MISSING SPECIALIST" in result
        assert "cardiologist" in result

    def test_specialist_referral_present_passes(self):
        patient = _make_patient(conditions=["heart_disease"])
        items = [_make_action_item(
            action="Refer to cardiologist for echocardiogram",
            category="monitoring",
        )]
        assert validate_specialist_referral(items, patient) is None

    def test_no_specialist_condition_passes(self):
        patient = _make_patient(conditions=["diabetes"])
        items = [_make_action_item(action="Continue metformin", category="medication")]
        assert validate_specialist_referral(items, patient) is None


# ── Critic: Priority Alignment Tests ───────────────────────────────────────

class TestValidatePriorityAlignment:
    def test_critical_patient_needs_high_priority(self):
        profile = _make_risk_profile(risk_tier=RiskTier.CRITICAL)
        items = [_make_action_item(priority="medium")]
        result = validate_priority_alignment(items, profile)
        assert result is not None
        assert "PRIORITY MISMATCH" in result

    def test_critical_patient_has_high_priority_passes(self):
        profile = _make_risk_profile(risk_tier=RiskTier.CRITICAL)
        items = [
            _make_action_item(priority="high"),
            _make_action_item(priority="medium"),
        ]
        assert validate_priority_alignment(items, profile) is None

    def test_low_risk_no_priority_requirement(self):
        profile = _make_risk_profile(risk_tier=RiskTier.LOW)
        items = [_make_action_item(priority="low")]
        assert validate_priority_alignment(items, profile) is None


# ── Critic: Completeness Tests ─────────────────────────────────────────────

class TestValidateCompleteness:
    def test_empty_plan_flagged(self):
        assert validate_plan_completeness([]) is not None

    def test_non_empty_plan_passes(self):
        assert validate_plan_completeness([_make_action_item()]) is None


# ── Full Critic Integration Tests ──────────────────────────────────────────

class TestValidateCarePlan:
    def test_valid_plan_approved(self):
        patient = _make_patient(conditions=["diabetes"], medications=["metformin"])
        profile = _make_risk_profile(risk_tier=RiskTier.HIGH, final_risk_score=22.0)
        items = [
            _make_action_item(
                action="Enroll in medically tailored meal program",
                category="social", priority="high",
            ),
            _make_action_item(
                action="Continue metformin 500mg twice daily",
                category="medication", priority="medium",
            ),
        ]
        plan = _make_care_plan(items)
        result = validate_care_plan(plan, patient, profile)
        assert result.status == PlanStatus.APPROVED
        assert result.veto_reason is None

    def test_dangerous_dosage_vetoed(self):
        patient = _make_patient(conditions=["diabetes"], medications=["metformin"])
        profile = _make_risk_profile(risk_tier=RiskTier.CRITICAL)
        items = [
            _make_action_item(
                action="Prescribe metformin 3000mg daily",
                category="medication", priority="high",
            ),
        ]
        plan = _make_care_plan(items)
        result = validate_care_plan(plan, patient, profile)
        assert result.status == PlanStatus.VETOED
        assert "DOSAGE EXCEEDED" in result.veto_reason

    def test_empty_plan_vetoed(self):
        patient = _make_patient()
        profile = _make_risk_profile()
        plan = _make_care_plan([])
        result = validate_care_plan(plan, patient, profile)
        assert result.status == PlanStatus.VETOED
        assert "EMPTY" in result.veto_reason


# ── Prompt Builder Tests ───────────────────────────────────────────────────

class TestBuildLlmPrompt:
    def test_prompt_contains_patient_info(self):
        patient = _make_patient(patient_id="P123", age=62)
        profile = _make_risk_profile()
        prompt = build_llm_prompt(patient, profile)
        assert "P123" in prompt
        assert "62" in prompt

    def test_prompt_contains_risk_tier(self):
        patient = _make_patient()
        profile = _make_risk_profile(risk_tier=RiskTier.CRITICAL)
        prompt = build_llm_prompt(patient, profile)
        assert "critical" in prompt.lower()

    def test_prompt_contains_conditions(self):
        patient = _make_patient(conditions=["diabetes", "hypertension"])
        profile = _make_risk_profile()
        prompt = build_llm_prompt(patient, profile)
        assert "diabetes" in prompt
        assert "hypertension" in prompt

    def test_prompt_contains_multiplier_descriptions(self):
        from shared.models import RiskMultiplier
        patient = _make_patient()
        profile = _make_risk_profile(
            applied_multipliers=[RiskMultiplier(
                condition_a="diabetes", condition_b="food_desert_risk",
                multiplier=1.8, description="Diabetes + Food Desert amplifies risk.",
            )]
        )
        prompt = build_llm_prompt(patient, profile)
        assert "Diabetes + Food Desert" in prompt


# ── LLM Response Parser Tests ──────────────────────────────────────────────

class TestParseLlmResponse:
    def test_valid_json_parsed(self):
        response = json.dumps({
            "reasoning": "Patient needs lifestyle intervention.",
            "action_items": [
                {"action": "Diet counseling", "category": "lifestyle",
                 "priority": "medium", "target_date_days": 14},
                {"action": "Exercise plan", "category": "lifestyle",
                 "priority": "low", "target_date_days": 30},
            ],
        })
        plan = parse_llm_response(response, "P001")
        assert plan.patient_id == "P001"
        assert plan.reasoning == "Patient needs lifestyle intervention."
        assert len(plan.action_items) == 2
        assert plan.triggered_intervention_count == 2

    def test_invalid_json_vetoed(self):
        plan = parse_llm_response("not valid json", "P001")
        assert plan.status == PlanStatus.VETOED
        assert "parser" in (plan.veto_reason or "")

    def test_missing_action_items_handled(self):
        response = json.dumps({"reasoning": "No actions needed."})
        plan = parse_llm_response(response, "P001")
        assert len(plan.action_items) == 0
        assert plan.triggered_intervention_count == 0