"""Intervention Strategist — Imperative shell.

Flat, procedural IO code. Calls the LLM provider, parses response,
runs the critic, and returns the validated care plan. No business logic here.
"""

from __future__ import annotations

from shared.models import CarePlan, PatientInput, RiskProfile
from features.intervention_strategist.base import LLMProvider
from features.intervention_strategist.core import (
    build_llm_prompt,
    parse_llm_response,
    validate_care_plan,
)


def generate_care_plan(
    patient: PatientInput,
    risk_profile: RiskProfile,
    llm_provider: LLMProvider,
) -> CarePlan:
    """Full care plan generation pipeline: prompt → LLM → parse → critic.

    Args:
        patient: Clinical input from EHR
        risk_profile: Risk assessment from the Risk Scoring Engine
        llm_provider: An LLMProvider adapter

    Returns:
        Validated CarePlan (status APPROVED or VETOED by the critic).
    """
    # Pure: build the prompt
    prompt = build_llm_prompt(patient, risk_profile)

    # IO: call the LLM
    raw_response = llm_provider.generate(prompt)

    # Pure: parse the response
    care_plan = parse_llm_response(raw_response, patient.patient_id)

    # Pure: run the critic (deterministic validation)
    validated_plan = validate_care_plan(care_plan, patient, risk_profile)

    return validated_plan