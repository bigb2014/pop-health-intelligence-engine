"""Mock LLM provider — deterministic care plan generation.

Returns a realistic care plan as JSON without calling any LLM.
Useful for development, demos, and testing the critic pattern.
"""

from __future__ import annotations

import json

from features.intervention_strategist.base import LLMProvider


# Predefined care plan templates for different risk tiers
_MOCK_PLANS: dict[str, str] = {
    "critical": json.dumps({
        "reasoning": "Patient presents with critical risk due to diabetes compounded by food desert conditions and non-adherence. Immediate intervention required to prevent ER visit.",
        "action_items": [
            {
                "action": "Enroll patient in medically tailored meal delivery program (e.g., Meals on Wheels) for 90 days",
                "category": "social",
                "priority": "high",
                "target_date_days": 7,
            },
            {
                "action": "Refer to community health worker for medication adherence coaching and home visit",
                "category": "monitoring",
                "priority": "high",
                "target_date_days": 3,
            },
            {
                "action": "Switch metformin to extended-release formulation to simplify regimen",
                "category": "medication",
                "priority": "medium",
                "target_date_days": 14,
            },
            {
                "action": "Schedule telehealth follow-up with primary care within 7 days",
                "category": "monitoring",
                "priority": "high",
                "target_date_days": 7,
            },
        ],
    }),
    "high": json.dumps({
        "reasoning": "Patient at high risk due to hypertension and housing instability. Stress-related BP elevation requires multi-pronged approach.",
        "action_items": [
            {
                "action": "Refer to housing stabilization program and social worker",
                "category": "social",
                "priority": "high",
                "target_date_days": 7,
            },
            {
                "action": "Increase lisinopril to 20mg daily (from 10mg) with home BP monitoring",
                "category": "medication",
                "priority": "high",
                "target_date_days": 14,
            },
            {
                "action": "Enroll in stress management program",
                "category": "lifestyle",
                "priority": "medium",
                "target_date_days": 30,
            },
        ],
    }),
    "moderate": json.dumps({
        "reasoning": "Patient at moderate risk. Focus on preventive lifestyle interventions and regular monitoring.",
        "action_items": [
            {
                "action": "Refer to nutrition counseling for diabetic diet education",
                "category": "lifestyle",
                "priority": "medium",
                "target_date_days": 14,
            },
            {
                "action": "Schedule quarterly HbA1c monitoring",
                "category": "monitoring",
                "priority": "medium",
                "target_date_days": 90,
            },
        ],
    }),
    "low": json.dumps({
        "reasoning": "Patient at low risk. Maintain current regimen with routine follow-up.",
        "action_items": [
            {
                "action": "Continue current medications and lifestyle",
                "category": "monitoring",
                "priority": "low",
                "target_date_days": 180,
            },
        ],
    }),
    # Dangerous plan — used to test the critic veto
    "dangerous_dose": json.dumps({
        "reasoning": "Increasing metformin dosage.",
        "action_items": [
            {
                "action": "Prescribe metformin 3000mg daily",
                "category": "medication",
                "priority": "high",
                "target_date_days": 1,
            },
        ],
    }),
}


class MockLLMProvider(LLMProvider):
    """Deterministic mock LLM for development and testing."""

    def __init__(self, plan_key: str = "auto"):
        """
        Args:
            plan_key: Which plan to return. "auto" picks based on the
                      risk tier keyword found in the prompt.
        """
        self._plan_key = plan_key

    def generate(self, prompt: str) -> str:
        if self._plan_key != "auto":
            return _MOCK_PLANS.get(self._plan_key, _MOCK_PLANS["moderate"])

        # Auto-select based on risk tier in prompt
        prompt_lower = prompt.lower()
        if "critical" in prompt_lower:
            return _MOCK_PLANS["critical"]
        elif "high" in prompt_lower:
            return _MOCK_PLANS["high"]
        elif "moderate" in prompt_lower:
            return _MOCK_PLANS["moderate"]
        else:
            return _MOCK_PLANS["low"]