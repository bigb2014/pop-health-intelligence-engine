# Pop-Health Intelligence Engine

## Overview

Strategic middleware layer between Health Systems (Providers) and Employers (Payers).
Fuses clinical EHR data with public SDOH (Social Determinants of Health) data to
identify high-risk patients and generate medically validated, financially quantified
intervention plans.

**Core Value:** Transitions Population Health from *descriptive* (what happened) to
*prescriptive* (what to do and how much it saves).

## Architecture

**Functional Core / Imperative Shell (FCIS) + Ports & Adapters (Hexagonal)**

Every feature is split into:
- **Core** (`.core.py`): Pure, deterministic logic. No IO, no DB, no LLM. 100% testable.
- **Shell** (`.shell.py`): IO glue — API calls, LLM calls, logging.

All external services are abstracted behind ports (interfaces) with swappable adapters.

## Features

| # | Feature | Role |
|---|---------|------|
| 1 | SDOH Profiler | Translates geographic data → social risk factors |
| 2 | Risk Scoring Engine | Risk tier determination with interaction multipliers |
| 3 | Intervention Strategist | LLM-generated care plans with critic validation |
| 4 | Value Quantifier | Actuarial ROI model for interventions |

## Tech Stack

- Python 3.11+
- Pydantic (strict typing for PHI/PII safety)
- Streamlit (demo UI)

## Setup

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Testing

```bash
PYTHONPATH=src python -m pytest src/ -p no:langsmith -v
```

## Project Structure

```
pop-health-intelligence-engine/
├── app.py                        # Streamlit UI
├── pyproject.toml
├── requirements.txt
├── .env.example
├── SPEC.md                       # Architecture decisions
└── src/
    ├── __init__.py
    ├── main.py                   # Programmatic entry point
    ├── shared/
    │   ├── __init__.py
    │   └── models.py             # Pydantic data models
    └── features/
        ├── __init__.py
        ├── sdoh_profiler/
        │   ├── __init__.py
        │   ├── sdoh_profiler.core.py
        │   ├── sdoh_profiler.shell.py
        │   ├── base.py           # Port (abstract interface)
        │   ├── providers/        # Adapters
        │   │   ├── __init__.py
        │   │   ├── mock.py
        │   │   └── census.py
        │   └── test_sdoh_profiler.py
        ├── risk_scoring/
        │   ├── __init__.py
        │   ├── risk_scoring.core.py
        │   ├── risk_scoring.shell.py
        │   └── test_risk_scoring.py
        ├── intervention_strategist/
        │   ├── __init__.py
        │   ├── intervention_strategist.core.py
        │   ├── intervention_strategist.shell.py
        │   ├── base.py           # LLM Port
        │   ├── providers/
        │   │   ├── __init__.py
        │   │   ├── mock.py
        │   │   └── llama.py
        │   └── test_intervention_strategist.py
        └── value_quantifier/
            ├── __init__.py
            ├── value_quantifier.core.py
            ├── value_quantifier.shell.py
            └── test_value_quantifier.py
```