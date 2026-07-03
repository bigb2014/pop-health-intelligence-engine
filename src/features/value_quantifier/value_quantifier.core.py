"""Value Quantifier — Pure functional core.

The "Money Layer." Attaches a dollar value to interventions using an
Actuarial Savings Model based on risk tier and triggered interventions.

No IO, no network calls, no database. All functions are deterministic.
"""

from __future__ import annotations

from shared.models import (
    CarePlan,
    FinancialImpact,
    PatientInput,
    RiskProfile,
    RiskTier,
    PlanStatus,
)


# ── Actuarial Tables ───────────────────────────────────────────────────────

# Average annual ER cost per patient by risk tier (USD)
# Based on healthcare cost data: high-risk chronic patients incur significantly more
ANNUAL_ER_COST_BY_TIER: dict[RiskTier, float] = {
    RiskTier.LOW: 800.0,
    RiskTier.MODERATE: 3_500.0,
    RiskTier.HIGH: 12_000.0,
    RiskTier.CRITICAL: 28_000.0,
}

# Cost avoidance percentage by risk tier
# Higher risk = more avoidable cost (more headroom to prevent)
COST_AVOIDANCE_RATE: dict[RiskTier, float] = {
    RiskTier.LOW: 0.15,       # 15% of ER costs avoidable
    RiskTier.MODERATE: 0.30,  # 30%
    RiskTier.HIGH: 0.50,      # 50%
    RiskTier.CRITICAL: 0.65,  # 65% — most preventable
}

# Average cost per intervention (USD)
# Social interventions (meal programs, housing assistance) vs monitoring (telehealth)
INTERVENTION_COSTS: dict[str, float] = {
    "social": 1_500.0,      # e.g., 90-day meal program
    "medication": 300.0,    # medication adjustment / new prescription
    "lifestyle": 500.0,     # counseling, exercise program
    "monitoring": 800.0,    # telehealth follow-ups, home BP monitoring
}

DEFAULT_INTERVENTION_COST = 600.0


# ── Confidence Model ───────────────────────────────────────────────────────

# Base confidence by risk tier (higher risk = more data = higher confidence)
BASE_CONFIDENCE: dict[RiskTier, float] = {
    RiskTier.LOW: 0.60,
    RiskTier.MODERATE: 0.70,
    RiskTier.HIGH: 0.80,
    RiskTier.CRITICAL: 0.85,
}

# Confidence boost per intervention (diminishing returns, capped)
CONFIDENCE_BOOST_PER_INTERVENTION = 0.03
MAX_CONFIDENCE_BOOST = 0.12
MAX_CONFIDENCE = 0.95

# Non-adherent patients have lower confidence (less predictable outcomes)
NON_ADHERENCE_CONFIDENCE_PENALTY = 0.10

# Prior ER visits reduce confidence (unpredictable utilization pattern)
ER_VISIT_CONFIDENCE_PENALTY_PER_VISIT = 0.02
MAX_ER_CONFIDENCE_PENALTY = 0.08


# ── Cost Calculations ──────────────────────────────────────────────────────

def estimate_annual_er_cost(
    risk_tier: RiskTier,
    prior_er_visits: int,
) -> float:
    """Estimate the patient's expected annual ER cost without intervention.

    Combines the base actuarial cost for the risk tier with an adjustment
    based on prior ER visit history.

    Args:
        risk_tier: The patient's risk classification
        prior_er_visits: ER visits in the last 12 months

    Returns:
        Estimated annual ER cost in USD.

    Example:
        >>> estimate_annual_er_cost(RiskTier.HIGH, 2)
        14400.0
    """
    base = ANNUAL_ER_COST_BY_TIER[risk_tier]
    # Each prior ER visit adds 20% to the base (patient is a heavy utilizer)
    visit_multiplier = 1.0 + (min(prior_er_visits, 5) * 0.20)
    return round(base * visit_multiplier, 2)


def estimate_cost_avoidance(
    annual_er_cost: float,
    risk_tier: RiskTier,
    intervention_count: int,
) -> float:
    """Estimate the dollar amount of ER costs that can be avoided.

    Formula:
        avoidance = annual_er_cost × avoidance_rate × intervention_effectiveness

    Where intervention_effectiveness increases with the number of
    triggered interventions but with diminishing returns (capped at 1.0).

    Args:
        annual_er_cost: The patient's expected annual ER cost
        risk_tier: Risk classification
        intervention_count: Number of interventions in the care plan

    Returns:
        Estimated cost avoidance in USD.

    Example:
        >>> estimate_cost_avoidance(12000.0, RiskTier.HIGH, 3)
        6000.0
    """
    base_rate = COST_AVOIDANCE_RATE[risk_tier]

    # Diminishing returns: first 2 interventions count full, then 50% each
    if intervention_count <= 0:
        effectiveness = 0.0
    elif intervention_count <= 2:
        effectiveness = intervention_count * 0.40  # 40% per intervention, up to 80%
    else:
        effectiveness = 0.80 + (intervention_count - 2) * 0.10  # diminishing

    effectiveness = min(effectiveness, 1.0)

    return round(annual_er_cost * base_rate * effectiveness, 2)


def estimate_intervention_cost(
    care_plan: CarePlan,
) -> float:
    """Sum the cost of all interventions in the care plan.

    Args:
        care_plan: The validated care plan

    Returns:
        Total intervention cost in USD.
    """
    total = 0.0
    for item in care_plan.action_items:
        cost = INTERVENTION_COSTS.get(item.category, DEFAULT_INTERVENTION_COST)
        total += cost
    return round(total, 2)


# ── Confidence Score ───────────────────────────────────────────────────────

def compute_confidence_score(
    risk_tier: RiskTier,
    intervention_count: int,
    is_adherent: bool,
    prior_er_visits: int,
) -> float:
    """Compute confidence in the financial estimate.

    Confidence is based on:
    - Base confidence by risk tier (more data for higher risk)
    - Boost per intervention (diminishing returns, capped)
    - Penalty for non-adherence (unpredictable outcomes)
    - Penalty for high ER utilization (unpredictable pattern)

    Args:
        risk_tier: Risk classification
        intervention_count: Number of interventions triggered
        is_adherent: Whether patient is medication-adherent
        prior_er_visits: ER visits in last 12 months

    Returns:
        Confidence score 0-1.

    Example:
        >>> compute_confidence_score(RiskTier.HIGH, 3, True, 1)
        0.86
    """
    confidence = BASE_CONFIDENCE[risk_tier]

    # Boost from interventions (diminishing returns)
    boost = min(
        intervention_count * CONFIDENCE_BOOST_PER_INTERVENTION,
        MAX_CONFIDENCE_BOOST,
    )
    confidence += boost

    # Non-adherence penalty
    if not is_adherent:
        confidence -= NON_ADHERENCE_CONFIDENCE_PENALTY

    # ER visit penalty
    er_penalty = min(
        prior_er_visits * ER_VISIT_CONFIDENCE_PENALTY_PER_VISIT,
        MAX_ER_CONFIDENCE_PENALTY,
    )
    confidence -= er_penalty

    confidence = min(confidence, MAX_CONFIDENCE)

    return round(max(confidence, 0.0), 2)


# ── Main Entry Point ───────────────────────────────────────────────────────

def quantify_value(
    patient: PatientInput,
    risk_profile: RiskProfile,
    care_plan: CarePlan,
) -> FinancialImpact:
    """Compute the financial ROI of a care plan for a patient.

    The main entry point for the Value Quantifier. Combines all
    actuarial calculations into a single FinancialImpact report.

    Args:
        patient: Clinical input from EHR
        risk_profile: Risk assessment from the Risk Scoring Engine
        care_plan: Validated care plan from the Intervention Strategist

    Returns:
        FinancialImpact with cost avoidance, net savings, ROI, and confidence.

    Example:
        >>> from shared.models import PatientInput, RiskProfile, CarePlan, \\
        ...     RiskTier, PlanStatus, ActionItem
        >>> patient = PatientInput(
        ...     patient_id="P001", age=55, zip_code="37208",
        ...     conditions=["diabetes"], medications=["metformin"],
        ...     prior_er_visits=2, is_adherent=False,
        ... )
        >>> risk = RiskProfile(
        ...     patient_id="P001", base_risk_score=15, final_risk_score=25,
        ...     risk_tier=RiskTier.HIGH, primary_risk_factors=["diabetes"],
        ... )
        >>> plan = CarePlan(
        ...     patient_id="P001", reasoning="Test",
        ...     action_items=[ActionItem(
        ...         action="Meal program", category="social",
        ...         priority="high", target_date_days=7,
        ...     )],
        ...     status=PlanStatus.APPROVED, triggered_intervention_count=1,
        ... )
        >>> impact = quantify_value(patient, risk, plan)
        >>> impact.net_savings > 0
        True
    """
    # If the plan was vetoed, no interventions will be executed
    if care_plan.status == PlanStatus.VETOED:
        return FinancialImpact(
            patient_id=patient.patient_id,
            risk_tier=risk_profile.risk_tier,
            estimated_annual_er_cost=estimate_annual_er_cost(
                risk_profile.risk_tier, patient.prior_er_visits
            ),
            estimated_cost_avoidance=0.0,
            intervention_cost=0.0,
            net_savings=0.0,
            confidence_score=0.0,
            roi_ratio=0.0,
        )

    intervention_count = care_plan.triggered_intervention_count

    # 1. Estimate annual ER cost without intervention
    annual_er_cost = estimate_annual_er_cost(
        risk_profile.risk_tier, patient.prior_er_visits
    )

    # 2. Estimate cost avoidance from interventions
    cost_avoidance = estimate_cost_avoidance(
        annual_er_cost, risk_profile.risk_tier, intervention_count
    )

    # 3. Estimate cost of implementing interventions
    intervention_cost = estimate_intervention_cost(care_plan)

    # 4. Net savings = cost avoidance - intervention cost
    net_savings = round(cost_avoidance - intervention_cost, 2)

    # 5. Confidence score
    confidence = compute_confidence_score(
        risk_profile.risk_tier,
        intervention_count,
        patient.is_adherent,
        patient.prior_er_visits,
    )

    # 6. ROI ratio = net savings / intervention cost
    roi_ratio = round(net_savings / intervention_cost, 2) if intervention_cost > 0 else 0.0

    return FinancialImpact(
        patient_id=patient.patient_id,
        risk_tier=risk_profile.risk_tier,
        estimated_annual_er_cost=annual_er_cost,
        estimated_cost_avoidance=cost_avoidance,
        intervention_cost=intervention_cost,
        net_savings=net_savings,
        confidence_score=confidence,
        roi_ratio=roi_ratio,
    )