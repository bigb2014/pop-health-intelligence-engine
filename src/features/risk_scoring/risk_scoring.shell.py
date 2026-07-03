"""Risk Scoring Engine — Imperative shell.

Flat, procedural IO code. Fetches SDOH profile via the SDOH Profiler shell,
then delegates to the pure core for risk computation. No business logic here.
"""

from __future__ import annotations

from shared.models import PatientInput, RiskProfile, SdoHProfile
from features.sdoh_profiler.base import SdoHDataProvider
from features.sdoh_profiler.core import build_sdoh_profile
from features.risk_scoring.core import compute_risk_profile
from features.sdoh_profiler.shell import get_sdoh_profile


def assess_patient_risk(
    patient: PatientInput,
    sdoh_provider: SdoHDataProvider,
) -> RiskProfile:
    """Full risk assessment pipeline: fetch SDOH data → compute risk.

    Args:
        patient: Clinical input from EHR
        sdoh_provider: An SdoHDataProvider adapter

    Returns:
        Complete RiskProfile with multipliers and tier.
    """
    # IO: fetch SDOH data via provider
    sdoh_profile = get_sdoh_profile(patient.zip_code, sdoh_provider)

    # Pure: compute risk
    return compute_risk_profile(patient, sdoh_profile)