"""Ollama LLM provider — local inference for care plan generation.

Calls a local Ollama model to generate prescriptive care plans.
The critic (in the core) validates the output before it's accepted.

Ollama must be running with a model pulled. Tested with qwen2.5:7b.

Ollama API: POST http://localhost:11434/api/chat
Docs: https://ollama.com/library
"""

from __future__ import annotations

import os
import json
import urllib.request

from features.intervention_strategist.base import LLMProvider


class OllamaProvider(LLMProvider):
    """Live adapter for local LLM inference via Ollama.

    Generates care plans using a local model. The critic validates
    every response — if the LLM hallucinates a dangerous dosage,
    the critic vetoes it.

    Args:
        model: Ollama model name (default: qwen2.5:7b)
        host: Ollama API host (default: http://localhost:11434)
        temperature: Sampling temperature (lower = more deterministic)
        max_tokens: Max response length
    """

    def __init__(
        self,
        model: str = "qwen2.5:7b",
        host: str = "http://localhost:11434",
        temperature: float = 0.3,
    ):
        self._model = model
        self._host = host
        self._temperature = temperature

    def generate(self, prompt: str) -> str:
        """Generate a care plan from the prompt via Ollama chat API.

        Returns:
            JSON string with 'reasoning' and 'action_items' fields.
            Falls back to a minimal valid JSON if the model output
            can't be parsed (the critic will catch safety issues).
        """
        payload = json.dumps({
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a clinical care plan strategist. "
                        "Generate prescriptive care plans as JSON. "
                        "Always respond with valid JSON containing "
                        "'reasoning' (string) and 'action_items' (array of objects "
                        "with 'action', 'category', 'priority', 'target_date_days'). "
                        "Categories: medication, social, lifestyle, monitoring. "
                        "Priority: high, medium, low. "
                        "Do NOT include markdown formatting or explanation outside JSON."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "format": "json",
            "options": {
                "temperature": self._temperature,
                "num_predict": 2048,
            },
        }).encode()

        url = f"{self._host}/api/chat"
        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json"},
        )

        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode())

        content = data.get("message", {}).get("content", "")

        # The model should return valid JSON thanks to format="json"
        # But let's be defensive — extract JSON if there's any wrapper
        content = content.strip()

        # If it's already valid JSON, return as-is
        try:
            json.loads(content)
            return content
        except json.JSONDecodeError:
            pass

        # Try to extract JSON from a code block or mixed text
        import re
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            candidate = json_match.group(0)
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                pass

        # Last resort: wrap in a minimal structure — the critic will veto if needed
        return json.dumps({
            "reasoning": content[:500] if content else "No reasoning provided.",
            "action_items": [],
        })