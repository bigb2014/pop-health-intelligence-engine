"""Value Quantifier feature package.

FCIS structure:
  value_quantifier.core.py  — pure functions (actuarial model, confidence, ROI)
  value_quantifier.shell.py — IO shell (delegates to core, may log externally)
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
core = _load_dotted_module("value_quantifier.core.py", "features.value_quantifier.core")
if core is not None:
    quantify_value = core.quantify_value
    estimate_annual_er_cost = core.estimate_annual_er_cost
    estimate_cost_avoidance = core.estimate_cost_avoidance
    estimate_intervention_cost = core.estimate_intervention_cost
    compute_confidence_score = core.compute_confidence_score
    ANNUAL_ER_COST_BY_TIER = core.ANNUAL_ER_COST_BY_TIER
    COST_AVOIDANCE_RATE = core.COST_AVOIDANCE_RATE
    INTERVENTION_COSTS = core.INTERVENTION_COSTS

# 2. Load shell lazily
try:
    shell = _load_dotted_module("value_quantifier.shell.py", "features.value_quantifier.shell")
    if shell is not None:
        calculate_roi = shell.calculate_roi
except Exception:
    pass