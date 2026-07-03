"""SDOH Profiler feature package.

FCIS structure:
  sdoh_profiler.core.py  — pure functions (normalization + profile building)
  sdoh_profiler.shell.py — IO shell (fetches via provider, delegates to core)

Files use dotted names per FCIS convention. Loaded via importlib.
Core is loaded first and re-exported so shell can import from the package.
Shell is loaded lazily (may fail if deps are missing — tests don't need it).
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


# 1. Load core first — re-export so shell can import from the package
core = _load_dotted_module("sdoh_profiler.core.py", "features.sdoh_profiler.core")
if core is not None:
    build_sdoh_profile = core.build_sdoh_profile
    normalize_air_quality = core.normalize_air_quality
    normalize_food_access = core.normalize_food_access
    normalize_housing = core.normalize_housing
    normalize_transportation = core.normalize_transportation
    normalize_crime = core.normalize_crime
    normalize_education = core.normalize_education
    compute_overall_risk = core.compute_overall_risk

# 2. Load shell lazily — may fail if deps are missing (tests don't need it)
try:
    shell = _load_dotted_module("sdoh_profiler.shell.py", "features.sdoh_profiler.shell")
    if shell is not None:
        get_sdoh_profile = shell.get_sdoh_profile
except Exception:
    pass