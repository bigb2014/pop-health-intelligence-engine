"""Intervention Strategist feature package.

FCIS structure:
  intervention_strategist.core.py  — pure functions (critic validator, prompt builder, parser)
  intervention_strategist.shell.py — IO shell (calls LLM, delegates to core)
"""

import importlib.util
import os
import sys

_pkg_dir = os.path.dirname(__file__)


def _load_dotted_module(filename: str, modname: str):
    filepath = os.path.join(_pkg_dir, filename)
    if not os.path.exists(filepath):
        return None
    spec = importlib.util.spec_from_file_location(modname, filepath)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    return mod


# 1. Load core first — re-export
core = _load_dotted_module("intervention_strategist.core.py", "features.intervention_strategist.core")
if core is not None:
    validate_care_plan = core.validate_care_plan
    build_llm_prompt = core.build_llm_prompt
    parse_llm_response = core.parse_llm_response
    validate_medication_safety = core.validate_medication_safety
    validate_non_adherence_safety = core.validate_non_adherence_safety
    validate_specialist_referral = core.validate_specialist_referral
    validate_priority_alignment = core.validate_priority_alignment
    validate_plan_completeness = core.validate_plan_completeness

# 2. Load shell lazily
try:
    shell = _load_dotted_module("intervention_strategist.shell.py", "features.intervention_strategist.shell")
    if shell is not None:
        generate_care_plan = shell.generate_care_plan
except Exception:
    pass