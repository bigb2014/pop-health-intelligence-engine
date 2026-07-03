"""Intervention Strategist — LLM Port (abstract interface).

Defines the contract for LLM-based care plan generation.
Adapters in providers/ implement this interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Port: Abstract interface for LLM providers.

    Implementations:
    - providers.mock.MockLLMProvider  — deterministic test plans
    - providers.llama.LlamaProvider   — local Llama-3 via Ollama
    """

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Generate a care plan from the prompt.

        Args:
            prompt: The structured prompt from build_llm_prompt()

        Returns:
            JSON string with 'reasoning' and 'action_items' fields.
        """
        ...