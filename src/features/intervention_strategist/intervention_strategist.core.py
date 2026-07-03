"""Intervention Strategist — Pure functional core.

Contains the "Critic" — a deterministic, rule-based validator that
scans LLM-generated care plans for safety violations before approval.

Also contains the prompt builder for the LLM, which is pure string construction.

No IO, no network calls, no LLM calls. All functions are deterministic.
"""

from __future__ import annotations

import json
from typing import Any

from shared.models import (
    ActionItem,
    CarePlan,
    PatientInput,
    PlanStatus,
    RiskProfile,
)


# ── Safety Rules (The Critic) ──────────────────────────────────────────────
# Each rule is a pure function: (parsed_plan, patient, risk_profile) -> violation | None

# Contraindicated medication combinations
CONTRAINDICATED_MEDS: dict[str, list[str]] = {
    "metformin": ["contrast_dye", "severe_kidney_disease"],
    "lisinopril": ["potassium_supplements", "aliskiren"],
    "warfarin": ["aspirin", "ibuprofen", "naproxen", "ginkgo_biloba"],
    "fluoxetine": ["maoi", "selegiline", "tramadol"],
    "insulin": ["prednisone"],  # requires dose adjustment, flag for review
}

# Maximum safe dosage per day (mg) for common medications
MAX_SAFE_DOSAGE: dict[str, float] = {
    "metformin": 2550.0,
    "lisinopril": 40.0,
    "atorvastatin": 80.0,
    "amlodipine": 10.0,
    "metoprolol": 400.0,
    "glipizide": 20.0,
    "insulin": 100.0,  # units
}

# Conditions that require specialist referral
SPECIALIST_REQUIRED: dict[str, str] = {
    "cancer": "oncologist",
    "chronic_kidney_disease": "nephrologist",
    "stroke_history": "neurologist",
    "heart_disease": "cardiologist",
    "copd": "pulmonologist",
}


def validate_medication_safety(
    action_items: list[ActionItem],
    patient: PatientInput,
) -> str | None:
    """Check for contraindicated medications and dangerous dosages.

    Returns a violation description if found, None if safe.
    """
    for item in action_items:
        if item.category != "medication":
            continue

        action_lower = item.action.lower()

        # Check for contraindicated combinations
        for current_med in patient.medications:
            current_lower = current_med.lower().replace(" ", "_")
            contraindicated = CONTRAINDICATED_MEDS.get(current_lower, [])
            for contra in contraindicated:
                if contra in action_lower:
                    return (
                        f"CONTRAINDICATION: Plan suggests '{contra}' which is "
                        f"contraindicated with patient's current medication '{current_med}'."
                    )

        # Check dosage limits
        for med, max_dose in MAX_SAFE_DOSAGE.items():
            if med in action_lower:
                # Extract dosage number from the action text
                import re
                dose_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:mg|units|mcg)", action_lower)
                if dose_match:
                    dose = float(dose_match.group(1))
                    if dose > max_dose:
                        return (
                            f"DOSAGE EXCEEDED: {med} dose of {dose} exceeds "
                            f"maximum safe daily dose of {max_dose}."
                        )

    return None


def validate_non_adherence_safety(
    action_items: list[ActionItem],
    patient: PatientInput,
) -> str | None:
    """Veto plans that prescribe complex medication regimens to non-adherent patients.

    Non-adherent patients need simplified regimens, not more medications.
    """
    if not patient.is_adherent:
        med_count = sum(1 for item in action_items if item.category == "medication")
        if med_count > 2:
            return (
                f"NON-ADHERENCE RISK: Plan prescribes {med_count} medications to a "
                f"non-adherent patient. Simplify regimen to ≤2 medications."
            )
    return None


def validate_specialist_referral(
    action_items: list[ActionItem],
    patient: PatientInput,
) -> str | None:
    """Ensure conditions requiring specialist care include a referral action."""
    conditions_lower = [c.lower().replace(" ", "_") for c in patient.conditions]
    for cond in conditions_lower:
        specialist = SPECIALIST_REQUIRED.get(cond)
        if specialist:
            has_referral = any(
                "referral" in item.action.lower() or specialist in item.action.lower()
                for item in action_items
            )
            if not has_referral:
                return (
                    f"MISSING SPECIALIST: Patient has '{cond.replace('_', ' ')}' "
                    f"which requires referral to {specialist}."
                )
    return None


def validate_priority_alignment(
    action_items: list[ActionItem],
    risk_profile: RiskProfile,
) -> str | None:
    """Ensure high-risk patients have at least one high-priority action item."""
    from shared.models import RiskTier

    if risk_profile.risk_tier in (RiskTier.HIGH, RiskTier.CRITICAL):
        has_high_priority = any(
            item.priority == "high" for item in action_items
        )
        if not has_high_priority:
            return (
                f"PRIORITY MISMATCH: {risk_profile.risk_tier.value} risk patient "
                f"has no high-priority action items."
            )
    return None


def validate_plan_completeness(action_items: list[ActionItem]) -> str | None:
    """Ensure the plan has at least one action item."""
    if len(action_items) == 0:
        return "EMPTY PLAN: Care plan contains no action items."
    return None


# ── The Critic ─────────────────────────────────────────────────────────────

def validate_care_plan(
    care_plan: CarePlan,
    patient: PatientInput,
    risk_profile: RiskProfile,
) -> CarePlan:
    """Run all safety validators on an LLM-generated care plan.

    The Critic: if any validator returns a violation, the plan is VETOED.
    This is deterministic, rule-based, and independent of the LLM.

    Args:
        care_plan: The care plan to validate (from LLM)
        patient: The patient the plan is for
        risk_profile: The patient's risk assessment

    Returns:
        The care plan with status updated to APPROVED or VETOED.
    """
    validators = [
        ("completeness", lambda: validate_plan_completeness(care_plan.action_items)),
        ("medication_safety", lambda: validate_medication_safety(care_plan.action_items, patient)),
        ("non_adherence", lambda: validate_non_adherence_safety(care_plan.action_items, patient)),
        ("specialist_referral", lambda: validate_specialist_referral(care_plan.action_items, patient)),
        ("priority_alignment", lambda: validate_priority_alignment(care_plan.action_items, risk_profile)),
    ]

    for name, validator in validators:
        violation = validator()
        if violation is not None:
            return care_plan.model_copy(
                update={
                    "status": PlanStatus.VETOED,
                    "veto_reason": f"[{name}] {violation}",
                }
            )

    return care_plan.model_copy(update={"status": PlanStatus.APPROVED})


# ── Prompt Builder (Pure) ──────────────────────────────────────────────────

def build_llm_prompt(patient: PatientInput, risk_profile: RiskProfile) -> str:
    """Build the prompt for the LLM to generate a care plan.

    Pure function: just string construction, no IO.
    """
    conditions_str = ", ".join(patient.conditions) if patient.conditions else "None"
    medications_str = ", ".join(patient.medications) if patient.medications else "None"
    factors_str = "; ".join(risk_profile.primary_risk_factors) if risk_profile.primary_risk_factors else "None"

    multiplier_descriptions = ""
    if risk_profile.applied_multipliers:
        multiplier_descriptions = "\n".join(
            f"  - {m.description}" for m in risk_profile.applied_multipliers
        )

    prompt = f"""You are a clinical care plan strategist. Generate a prescriptive care plan.

PATIENT PROFILE:
- ID: {patient.patient_id}
- Age: {patient.age}
- ZIP: {patient.zip_code}
- Conditions: {conditions_str}
- Current Medications: {medications_str}
- Prior ER Visits (12mo): {patient.prior_er_visits}
- Medication Adherent: {"Yes" if patient.is_adherent else "No"}

RISK ASSESSMENT:
- Risk Tier: {risk_profile.risk_tier.value}
- Base Risk Score: {risk_profile.base_risk_score}
- Final Risk Score: {risk_profile.final_risk_score}
- Primary Risk Factors: {factors_str}

RISK MULTIPLIERS (Interaction Effects):
{multiplier_descriptions if multiplier_descriptions else "  None identified"}

INSTRUCTIONS:
1. Generate 2-5 action items addressing the primary risk factors.
2. Each action item must have a category, priority, and target date.
3. Consider medication adherence status when prescribing.
4. Include social interventions (not just medications) when SDOH risks are present.
5. For high/critical risk patients, include at least one high-priority action.

Return JSON:
{{
  "reasoning": "Clinical reasoning for the plan...",
  "action_items": [
    {{
      "action": "Description of intervention",
      "category": "medication|social|lifestyle|monitoring",
      "priority": "high|medium|low",
      "target_date_days": 7
    }}
  ]
}}
"""
    return prompt


# ── LLM Response Parser (Pure) ─────────────────────────────────────────────

def parse_llm_response(
    raw_response: str,
    patient_id: str,
) -> CarePlan:
    """Parse the LLM's JSON response into a CarePlan object.

    Pure function: string → structured data. No IO.
    Handles malformed JSON gracefully.
    """
    try:
        data: dict[str, Any] = json.loads(raw_response)
    except json.JSONDecodeError:
        # If JSON fails, return a vetoed plan with the raw text
        return CarePlan(
            patient_id=patient_id,
            reasoning="FAILED TO PARSE LLM RESPONSE",
            action_items=[],
            status=PlanStatus.VETOED,
            veto_reason="[parser] LLM response was not valid JSON.",
            triggered_intervention_count=0,
        )

    action_items = []
    for item_data in data.get("action_items", []):
        try:
            action_items.append(
                ActionItem(
                    action=item_data["action"],
                    category=item_data["category"],
                    priority=item_data["priority"],
                    target_date_days=item_data["target_date_days"],
                )
            )
        except (KeyError, TypeError):
            continue

    return CarePlan(
        patient_id=patient_id,
        reasoning=data.get("reasoning", "No reasoning provided."),
        action_items=action_items,
        status=PlanStatus.NEEDS_REVISION,  # Will be set by critic
        triggered_intervention_count=len(action_items),
    )