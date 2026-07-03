"""Value Quantifier — Imperative shell.

Flat, procedural IO code. Delegates to the pure core for all financial
calculations. May log results to an external system. No business logic here.
"""

from __future__ import annotations

from shared.models import CarePlan, FinancialImpact, PatientInput, RiskProfile
from features.value_quantifier.core import quantify_value


def calculate_roi(
    patient: PatientInput,
    risk_profile: RiskProfile,
    care_plan: CarePlan,
) -> FinancialImpact:
    """Calculate the financial ROI of a patient's care plan.

    Args:
        patient: Clinical input from EHR
        risk_profile: Risk assessment from the Risk Scoring Engine
        care_plan: Validated care plan from the Intervention Strategist

    Returns:
        FinancialImpact with cost avoidance, net savings, and ROI.
    """
    # Pure: all calculations are in the core
    return quantify_value(patient, risk_profile, care_plan)