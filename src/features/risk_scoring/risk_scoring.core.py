"""Risk Scoring Engine — Pure functional core.

The "Brain" that determines a patient's risk tier.
Uses interaction-based multipliers (the "secret sauce"):
  Diabetes + Food Desert ≠ additive — the interaction amplifies risk.

No IO, no network calls, no database. All functions are deterministic.
"""

from __future__ import annotations

from shared.models import (
    PatientInput,
    RiskProfile,
    RiskMultiplier,
    RiskTier,
    SdoHProfile,
)


# ── Condition Base Risk Weights ────────────────────────────────────────────
# Each condition carries an intrinsic risk weight (0-10 scale).

CONDITION_WEIGHTS: dict[str, float] = {
    "diabetes": 6.0,
    "hypertension": 4.5,
    "copd": 5.5,
    "asthma": 3.5,
    "heart_disease": 7.0,
    "chronic_kidney_disease": 6.5,
    "obesity": 3.0,
    "depression": 3.5,
    "anxiety": 2.5,
    "substance_abuse": 5.0,
    "cancer": 8.0,
    "stroke_history": 8.5,
}

DEFAULT_CONDITION_WEIGHT = 2.0  # Unknown conditions get a conservative default


# ── ER Visit Risk Contribution ─────────────────────────────────────────────

def er_visit_risk(prior_er_visits: int) -> float:
    """Convert prior ER visits to risk score.

    0 visits → 0.0
    1 visit → 1.5
    2 visits → 3.0
    3+ visits → 4.5 (capped)
    """
    if prior_er_visits <= 0:
        return 0.0
    return min(prior_er_visits * 1.5, 4.5)


# ── Non-Adherence Risk ─────────────────────────────────────────────────────

NON_ADHERENCE_PENALTY = 2.0


# ── SDOH Risk Contribution ─────────────────────────────────────────────────

def sdoh_risk_contribution(profile: SdoHProfile) -> float:
    """Convert SDOH profile to risk score contribution (0-10 scale).

    The overall SDOH risk (0-1) is scaled to a 0-10 contribution,
    with food desert and housing risks weighted more heavily.
    """
    base = profile.overall_sdoh_risk * 10.0
    return round(base, 2)


# ── Interaction Multipliers (The "Secret Sauce") ───────────────────────────
# When specific conditions co-occur with SDOH risk factors, the risk
# is NOT additive — it's multiplicative. This captures emergent risk.

MULTIPLIER_RULES: list[dict] = [
    {
        "condition": "diabetes",
        "sdoh_factor": "food_desert_risk",
        "threshold": 0.5,
        "multiplier": 1.8,
        "description": "Diabetes + Food Desert: Inability to access fresh food amplifies diabetic risk.",
    },
    {
        "condition": "diabetes",
        "sdoh_factor": "transportation_risk",
        "threshold": 0.5,
        "multiplier": 1.4,
        "description": "Diabetes + Transportation Barrier: Cannot reach regular care/pharmacy.",
    },
    {
        "condition": "hypertension",
        "sdoh_factor": "housing_risk",
        "threshold": 0.5,
        "multiplier": 1.5,
        "description": "Hypertension + Housing Instability: Chronic stress elevates blood pressure.",
    },
    {
        "condition": "copd",
        "sdoh_factor": "air_quality_risk",
        "threshold": 0.3,
        "multiplier": 1.7,
        "description": "COPD + Poor Air Quality: Respiratory conditions worsened by environmental exposure.",
    },
    {
        "condition": "asthma",
        "sdoh_factor": "air_quality_risk",
        "threshold": 0.3,
        "multiplier": 1.6,
        "description": "Asthma + Poor Air Quality: Environmental trigger amplifies airway inflammation.",
    },
    {
        "condition": "heart_disease",
        "sdoh_factor": "food_desert_risk",
        "threshold": 0.5,
        "multiplier": 1.5,
        "description": "Heart Disease + Food Desert: Dietary restrictions impossible without fresh food access.",
    },
    {
        "condition": "depression",
        "sdoh_factor": "housing_risk",
        "threshold": 0.5,
        "multiplier": 1.4,
        "description": "Depression + Housing Instability: Instability worsens mental health outcomes.",
    },
    {
        "condition": "hypertension",
        "sdoh_factor": "food_desert_risk",
        "threshold": 0.5,
        "multiplier": 1.3,
        "description": "Hypertension + Food Desert: Sodium-heavy processed food access worsens BP.",
    },
]


def find_applicable_multipliers(
    conditions: list[str],
    sdoh_profile: SdoHProfile,
) -> list[RiskMultiplier]:
    """Find all interaction multipliers that apply to this patient.

    Checks each multiplier rule: if the patient has the condition AND
    the relevant SDOH risk factor exceeds the threshold, the multiplier applies.

    Args:
        conditions: Patient's active diagnoses
        sdoh_profile: Normalized SDOH risk factors

    Returns:
        List of applicable RiskMultiplier objects.
    """
    conditions_lower = [c.lower().replace(" ", "_") for c in conditions]
    applicable: list[RiskMultiplier] = []

    for rule in MULTIPLIER_RULES:
        if rule["condition"] not in conditions_lower:
            continue

        sdoh_value = getattr(sdoh_profile, rule["sdoh_factor"], 0.0)
        if sdoh_value >= rule["threshold"]:
            applicable.append(
                RiskMultiplier(
                    condition_a=rule["condition"],
                    condition_b=rule["sdoh_factor"],
                    multiplier=rule["multiplier"],
                    description=rule["description"],
                )
            )

    return applicable


# ── Risk Tier Classification ───────────────────────────────────────────────

def classify_risk_tier(final_score: float) -> RiskTier:
    """Map final risk score to a risk tier.

    Score ranges (after multipliers):
      0-10  → Low
      10-20 → Moderate
      20-35 → High
      35+   → Critical
    """
    if final_score < 10:
        return RiskTier.LOW
    elif final_score < 20:
        return RiskTier.MODERATE
    elif final_score < 30:
        return RiskTier.HIGH
    else:
        return RiskTier.CRITICAL


# ── Primary Risk Factor Identification ─────────────────────────────────────

def identify_primary_risk_factors(
    conditions: list[str],
    sdoh_profile: SdoHProfile,
    applied_multipliers: list[RiskMultiplier],
) -> list[str]:
    """Identify the top risk factors driving the patient's risk score.

    Returns a list of human-readable risk factor descriptions,
    prioritized by severity.
    """
    factors: list[tuple[float, str]] = []

    # Condition-based factors
    conditions_lower = [c.lower().replace(" ", "_") for c in conditions]
    for cond in conditions_lower:
        weight = CONDITION_WEIGHTS.get(cond, DEFAULT_CONDITION_WEIGHT)
        factors.append((weight, f"Active condition: {cond.replace('_', ' ')}"))

    # SDOH factors (only if significant)
    sdoh_factors = {
        "food_desert_risk": "Food desert / poor grocery access",
        "housing_risk": "Housing instability",
        "air_quality_risk": "Poor air quality exposure",
        "transportation_risk": "Transportation barrier to care",
        "crime_risk": "High crime environment",
        "education_risk": "Low health literacy (education proxy)",
    }

    for field, label in sdoh_factors.items():
        value = getattr(sdoh_profile, field, 0.0)
        if value >= 0.5:
            factors.append((value * 5, label))

    # Multiplier interactions are always high priority
    for m in applied_multipliers:
        factors.append((10.0, m.description))

    # Sort by weight descending, return top descriptions
    factors.sort(key=lambda x: x[0], reverse=True)
    return [label for _, label in factors[:5]]


# ── Main Entry Point ───────────────────────────────────────────────────────

def compute_risk_profile(
    patient: PatientInput,
    sdoh_profile: SdoHProfile,
) -> RiskProfile:
    """Compute a complete risk profile for a patient.

    Combines clinical conditions, SDOH factors, ER history, and adherence
    into a final risk score with interaction multipliers applied.

    Args:
        patient: Clinical input from EHR
        sdoh_profile: Normalized SDOH risk factors

    Returns:
        RiskProfile with base score, applied multipliers, final score, and tier.

    Example:
        >>> from shared.models import PatientInput, SdoHProfile
        >>> patient = PatientInput(
        ...     patient_id="P001", age=55, zip_code="37208",
        ...     conditions=["diabetes", "hypertension"],
        ...     prior_er_visits=2, is_adherent=False,
        ... )
        >>> sdoh = SdoHProfile(
        ...     zip_code="37208", air_quality_risk=0.18,
        ...     food_desert_risk=0.9, housing_risk=0.75,
        ...     transportation_risk=0.75, crime_risk=0.8,
        ...     education_risk=0.4, overall_sdoh_risk=0.65,
        ... )
        >>> profile = compute_risk_profile(patient, sdoh)
        >>> profile.risk_tier
        <RiskTier.CRITICAL: 'critical'>
    """
    # 1. Base risk: sum of condition weights
    conditions_lower = [c.lower().replace(" ", "_") for c in patient.conditions]
    base_score = sum(
        CONDITION_WEIGHTS.get(c, DEFAULT_CONDITION_WEIGHT)
        for c in conditions_lower
    )

    # 2. Add ER visit risk
    base_score += er_visit_risk(patient.prior_er_visits)

    # 3. Add non-adherence penalty
    if not patient.is_adherent:
        base_score += NON_ADHERENCE_PENALTY

    # 4. Add SDOH risk contribution
    base_score += sdoh_risk_contribution(sdoh_profile)

    base_score = round(base_score, 2)

    # 5. Find applicable interaction multipliers
    multipliers = find_applicable_multipliers(patient.conditions, sdoh_profile)

    # 6. Apply multipliers sequentially (compounding)
    final_score = base_score
    for m in multipliers:
        # Multiplier applies to the portion of risk related to that condition
        condition_weight = CONDITION_WEIGHTS.get(
            m.condition_a.lower().replace(" ", "_"), DEFAULT_CONDITION_WEIGHT
        )
        amplified = condition_weight * (m.multiplier - 1.0)
        final_score += amplified

    final_score = round(final_score, 2)

    # 7. Classify risk tier
    risk_tier = classify_risk_tier(final_score)

    # 8. Identify primary risk factors
    primary_factors = identify_primary_risk_factors(
        patient.conditions, sdoh_profile, multipliers
    )

    return RiskProfile(
        patient_id=patient.patient_id,
        base_risk_score=base_score,
        applied_multipliers=multipliers,
        final_risk_score=final_score,
        risk_tier=risk_tier,
        primary_risk_factors=primary_factors,
        sdoh_profile=sdoh_profile,
    )