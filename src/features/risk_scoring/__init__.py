"""Risk Scoring Engine feature package.

FCIS structure:
  risk_scoring.core.py  — pure functions (risk computation, multipliers, tiering)
  risk_scoring.shell.py — IO shell (fetches SDOH, delegates to core)
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
core = _load_dotted_module("risk_scoring.core.py", "features.risk_scoring.core")
if core is not None:
    compute_risk_profile = core.compute_risk_profile
    find_applicable_multipliers = core.find_applicable_multipliers
    classify_risk_tier = core.classify_risk_tier
    identify_primary_risk_factors = core.identify_primary_risk_factors
    er_visit_risk = core.er_visit_risk
    sdoh_risk_contribution = core.sdoh_risk_contribution
    CONDITION_WEIGHTS = core.CONDITION_WEIGHTS
    MULTIPLIER_RULES = core.MULTIPLIER_RULES

# 2. Load shell lazily
try:
    shell = _load_dotted_module("risk_scoring.shell.py", "features.risk_scoring.shell")
    if shell is not None:
        assess_patient_risk = shell.assess_patient_risk
except Exception:
    pass