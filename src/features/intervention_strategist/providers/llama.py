"""Llama-3 LLM provider — local inference via Ollama.

Calls a local Llama-3 model through Ollama for care plan generation.
Requires Ollama running with a Llama-3 model pulled.
"""

from __future__ import annotations

import os

from features.intervention_strategist.base import LLMProvider


class LlamaProvider(LLMProvider):
    """Live adapter for local Llama-3 via Ollama.

    NOTE: This is a stub. In production, this would call
    `ollama.chat(model='llama3', messages=[...])` or the Ollama HTTP API.
    """

    def __init__(self, model: str = "llama3", host: str = "http://localhost:11434"):
        self._model = model
        self._host = host

    def generate(self, prompt: str) -> str:
        # IO: would call Ollama API here
        raise NotImplementedError(
            "LlamaProvider requires Ollama to be running. "
            f"Install Ollama, pull {self._model}, and implement generate()."
        )