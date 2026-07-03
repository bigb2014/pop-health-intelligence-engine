"""Pop-Health Intelligence Engine — Programmatic entry point.

Runs the full pipeline: SDOH Profile → Risk Score → Care Plan → Financial ROI.
Uses mock providers by default for zero-dependency demonstration.
"""

from __future__ import annotations

import sys
import os

# Ensure src/ is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from shared.models import PatientInput
from features.sdoh_profiler.providers.mock import MockSdoHProvider
from features.sdoh_profiler.shell import get_sdoh_profile
from features.risk_scoring.core import compute_risk_profile
from features.intervention_strategist.providers.mock import MockLLMProvider
from features.intervention_strategist.shell import generate_care_plan
from features.value_quantifier.core import quantify_value


def run_pipeline(patient: PatientInput) -> dict:
    """Run the full intelligence pipeline for a single patient.

    Args:
        patient: Clinical input from EHR

    Returns:
        Dict with all pipeline outputs: sdoh, risk, care_plan, financial.
    """
    sdoh_provider = MockSdoHProvider()
    llm_provider = MockLLMProvider()

    # 1. SDOH Profile
    sdoh_profile = get_sdoh_profile(patient.zip_code, sdoh_provider)

    # 2. Risk Scoring
    risk_profile = compute_risk_profile(patient, sdoh_profile)

    # 3. Intervention Strategist (LLM + Critic)
    care_plan = generate_care_plan(patient, risk_profile, llm_provider)

    # 4. Value Quantifier
    financial_impact = quantify_value(patient, risk_profile, care_plan)

    return {
        "patient": patient,
        "sdoh_profile": sdoh_profile,
        "risk_profile": risk_profile,
        "care_plan": care_plan,
        "financial_impact": financial_impact,
    }


if __name__ == "__main__":
    # Demo: critical patient in North Nashville
    patient = PatientInput(
        patient_id="DEMO-001",
        age=55,
        zip_code="37208",
        conditions=["diabetes", "hypertension"],
        medications=["metformin", "lisinopril"],
        prior_er_visits=3,
        is_adherent=False,
    )

    results = run_pipeline(patient)

    print("=" * 60)
    print("POP-HEALTH INTELLIGENCE ENGINE — DEMO RUN")
    print("=" * 60)

    print(f"\nPatient: {patient.patient_id}")
    print(f"  Age: {patient.age}, ZIP: {patient.zip_code}")
    print(f"  Conditions: {', '.join(patient.conditions)}")
    print(f"  Prior ER Visits: {patient.prior_er_visits}")
    print(f"  Adherent: {patient.is_adherent}")

    sdoh = results["sdoh_profile"]
    print(f"\n📊 SDOH Profile (ZIP {sdoh.zip_code}):")
    print(f"  Food Desert Risk:    {sdoh.food_desert_risk:.1%}")
    print(f"  Housing Risk:        {sdoh.housing_risk:.1%}")
    print(f"  Air Quality Risk:    {sdoh.air_quality_risk:.1%}")
    print(f"  Overall SDOH Risk:   {sdoh.overall_sdoh_risk:.1%}")

    risk = results["risk_profile"]
    print(f"\n🧠 Risk Assessment:")
    print(f"  Base Score:          {risk.base_risk_score}")
    print(f"  Final Score:         {risk.final_risk_score}")
    print(f"  Risk Tier:           {risk.risk_tier.value.upper()}")
    print(f"  Multipliers Applied: {len(risk.applied_multipliers)}")
    for m in risk.applied_multipliers:
        print(f"    → {m.description}")
    print(f"  Primary Factors:")
    for f in risk.primary_risk_factors:
        print(f"    • {f}")

    plan = results["care_plan"]
    print(f"\n📋 Care Plan ({plan.status.value.upper()}):")
    print(f"  Reasoning: {plan.reasoning[:100]}...")
    if plan.veto_reason:
        print(f"  ⚠ VETO REASON: {plan.veto_reason}")
    print(f"  Action Items ({plan.triggered_intervention_count}):")
    for i, item in enumerate(plan.action_items, 1):
        print(f"    {i}. [{item.priority.upper()}] {item.action}")
        print(f"       Category: {item.category} | Target: {item.target_date_days} days")

    fin = results["financial_impact"]
    print(f"\n💰 Financial Impact:")
    print(f"  Annual ER Cost:      ${fin.estimated_annual_er_cost:,.2f}")
    print(f"  Cost Avoidance:      ${fin.estimated_cost_avoidance:,.2f}")
    print(f"  Intervention Cost:   ${fin.intervention_cost:,.2f}")
    print(f"  Net Savings:         ${fin.net_savings:,.2f}")
    print(f"  ROI Ratio:           {fin.roi_ratio:.2f}x")
    print(f"  Confidence:          {fin.confidence_score:.0%}")

    print("\n" + "=" * 60)