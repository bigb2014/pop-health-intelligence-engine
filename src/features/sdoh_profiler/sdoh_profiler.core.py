"""SDOH Profiler — Pure functional core.

Translates raw social determinant metrics into normalized 0-1 risk factors.
No IO, no network calls, no database. All functions are deterministic.
"""

from __future__ import annotations

from shared.models import RawSdoHMetrics, SdoHProfile


# ── Normalization Functions ────────────────────────────────────────────────
# Each converts a raw metric (with its native scale) to a 0-1 risk score
# where 1.0 = maximum risk.

def normalize_air_quality(aqi: float) -> float:
    """Convert AQI (0-500) to risk (0-1).
    AQI 0-50 (Good) → 0.0-0.1 risk
    AQI 300+ (Hazardous) → 0.6-1.0 risk
    """
    if aqi <= 0:
        return 0.0
    if aqi >= 300:
        return min(0.6 + (aqi - 300) / 500, 1.0)
    return aqi / 300.0


def normalize_food_access(grocery_score: float) -> float:
    """Convert grocery access score (0=desert, 100=excellent) to risk (0-1).
    Score 0 → risk 1.0 (food desert)
    Score 100 → risk 0.0 (excellent access)
    """
    return max(0.0, 1.0 - (grocery_score / 100.0))


def normalize_housing(instability: float) -> float:
    """Convert housing instability (0=stable, 100=unstable) to risk (0-1)."""
    return min(instability / 100.0, 1.0)


def normalize_transportation(access_score: float) -> float:
    """Convert transportation access (0=no access, 100=excellent) to risk (0-1)."""
    return max(0.0, 1.0 - (access_score / 100.0))


def normalize_crime(crime_per_100k: float) -> float:
    """Convert crime rate per 100k to risk (0-1).
    0 crimes → 0.0 risk
    1500+ per 100k → 1.0 risk (national violent crime rate ~380/100k)
    """
    if crime_per_100k <= 0:
        return 0.0
    return min(crime_per_100k / 1500.0, 1.0)


def normalize_education(education_pct: float) -> float:
    """Convert education attainment % (0-100) to risk (0-1).
    100% have HS diploma → 0.0 risk
    0% have HS diploma → 1.0 risk
    """
    return max(0.0, 1.0 - (education_pct / 100.0))


def compute_overall_risk(
    air_quality_risk: float,
    food_desert_risk: float,
    housing_risk: float,
    transportation_risk: float,
    crime_risk: float,
    education_risk: float,
) -> float:
    """Compute composite SDOH risk using weighted average.

    Weights reflect clinical evidence of health impact:
    - Food access: 25% (strongest direct health link — diabetes, obesity)
    - Housing: 20% (indirect but persistent — chronic stress, exposure)
    - Air quality: 20% (respiratory impact)
    - Transportation: 15% (barrier to care access)
    - Education: 10% (health literacy proxy)
    - Crime: 10% (stress and injury risk)
    """
    weights = {
        "food": 0.25,
        "housing": 0.20,
        "air": 0.20,
        "transport": 0.15,
        "education": 0.10,
        "crime": 0.10,
    }
    weighted_sum = (
        food_desert_risk * weights["food"]
        + housing_risk * weights["housing"]
        + air_quality_risk * weights["air"]
        + transportation_risk * weights["transport"]
        + education_risk * weights["education"]
        + crime_risk * weights["crime"]
    )
    return round(weighted_sum, 4)


# ── Main Entry Point ───────────────────────────────────────────────────────

def build_sdoh_profile(metrics: RawSdoHMetrics) -> SdoHProfile:
    """Transform raw SDOH metrics into a normalized SdoHProfile.

    Args:
        metrics: Raw social determinant data (from Census API, mock, etc.)

    Returns:
        SdoHProfile with all risk factors normalized to 0-1.

    Example:
        >>> from shared.models import RawSdoHMetrics
        >>> metrics = RawSdoHMetrics(
        ...     zip_code="37115", air_quality_index=45,
        ...     grocery_access_score=20, housing_instability_score=60,
        ...     transportation_access_score=30, crime_rate_per_100k=800,
        ...     education_attainment_pct=75,
        ... )
        >>> profile = build_sdoh_profile(metrics)
        >>> profile.food_desert_risk
        0.8
    """
    air_quality_risk = round(normalize_air_quality(metrics.air_quality_index), 4)
    food_desert_risk = round(normalize_food_access(metrics.grocery_access_score), 4)
    housing_risk = round(normalize_housing(metrics.housing_instability_score), 4)
    transportation_risk = round(normalize_transportation(metrics.transportation_access_score), 4)
    crime_risk = round(normalize_crime(metrics.crime_rate_per_100k), 4)
    education_risk = round(normalize_education(metrics.education_attainment_pct), 4)

    overall = compute_overall_risk(
        air_quality_risk,
        food_desert_risk,
        housing_risk,
        transportation_risk,
        crime_risk,
        education_risk,
    )

    return SdoHProfile(
        zip_code=metrics.zip_code,
        air_quality_risk=air_quality_risk,
        food_desert_risk=food_desert_risk,
        housing_risk=housing_risk,
        transportation_risk=transportation_risk,
        crime_risk=crime_risk,
        education_risk=education_risk,
        overall_sdoh_risk=overall,
    )