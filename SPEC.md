# SPEC — Architecture Decisions

## Pattern: Functional Core / Imperative Shell (FCIS)

**Decision:** Every feature splits into `.core.py` (pure functions, no IO) and `.shell.py` (flat procedural IO).

**Rationale:** The "medical math" (risk scoring, SDOH mapping, actuarial calculations, plan validation) must be 100% deterministic and audit-ready. By isolating it from IO, we can test every calculation without mocks, ensuring HIPAA compliance traceability.

## Pattern: Ports & Adapters (Hexagonal)

**Decision:** External services (SDOH data sources, LLM providers) are abstracted behind abstract base classes (`base.py`) with concrete adapters in `providers/`.

**Rationale:** Prevents vendor lock-in. Switch from Mock → Census Bureau API or Llama-3 → proprietary medical model by changing one adapter file. Business logic never touches external APIs directly.

## Data Models: Pydantic v2

**Decision:** All data transfer objects are Pydantic `BaseModel` with strict typing.

**Rationale:** PHI/PII safety requires strict validation at every boundary. Pydantic's validation + serialization gives us audit trails and prevents malformed data from entering the clinical pipeline.

## Risk Multipliers

**Decision:** Risk scoring uses interaction-based multipliers, not additive risk.

**Rationale:** Diabetes + Food Desert ≠ Diabetes + Food Desert (additive). The interaction itself creates emergent risk. Multipliers capture this: `diabetes_risk * food_desert_multiplier = critical_risk`.

## Critic Pattern for LLM Output

**Decision:** A pure-logic validator scans LLM-generated care plans before acceptance.

**Rationale:** LLMs hallucinate. In a clinical context, a hallucinated dosage or contraindicated drug is dangerous. The critic is deterministic, rule-based, and can veto any plan that violates safety constraints.

## Actuarial Savings Model

**Decision:** Value quantification uses a tier-based actuarial table with confidence scoring.

**Rationale:** ROI claims must be defensible. The model maps risk tiers to historical cost-avoidance data with explicit confidence intervals, not arbitrary estimates.