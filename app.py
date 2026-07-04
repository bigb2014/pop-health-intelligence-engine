"""Pop-Health Intelligence Engine — Streamlit Demo App.

CEO-level demo: input patient data → see SDOH risk, risk tier, care plan, and ROI.
Supports single patient analysis and batch CSV upload.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import streamlit as st
from shared.models import PatientInput
from features.sdoh_profiler.providers.mock import MockSdoHProvider
from features.sdoh_profiler.providers.census import CensusACSProvider
from features.sdoh_profiler.providers.airnow import AirNowProvider
from features.sdoh_profiler.providers.composite import CompositeSdoHProvider
from features.sdoh_profiler.providers.food_crime import FoodAccessCrimeProvider
from features.sdoh_profiler.providers.chas import CHASHousingProvider
from features.sdoh_profiler.historical import SDOHHistoryTracker
from features.sdoh_profiler.shell import get_sdoh_profile
from features.risk_scoring.core import compute_risk_profile
from features.intervention_strategist.providers.mock import MockLLMProvider
from features.intervention_strategist.providers.ollama import OllamaProvider
from features.intervention_strategist.shell import generate_care_plan
from features.value_quantifier.core import quantify_value


# Select SDOH provider based on environment variable
_sdoh_provider_mode = os.environ.get("SDOH_PROVIDER", "mock")
_census_key = os.environ.get("CENSUS_API_KEY", "")
_airnow_key = os.environ.get("AIRNOW_API_KEY", "")

if _sdoh_provider_mode == "composite" and _census_key:
    _hud_token = os.environ.get("HUD_API_TOKEN", "")
    _food_crime = FoodAccessCrimeProvider(hud_token=_hud_token) if _hud_token else None
    _chas = CHASHousingProvider(api_token=_hud_token) if _hud_token else None
    _sdoh_provider = CompositeSdoHProvider(
        primary=CensusACSProvider(api_key=_census_key),
        supplement=AirNowProvider(api_key=_airnow_key) if _airnow_key else None,
        food_crime=_food_crime,
        chas=_chas,
    )
elif _sdoh_provider_mode == "census" and _census_key:
    _sdoh_provider = CensusACSProvider(api_key=_census_key)
else:
    _sdoh_provider = MockSdoHProvider()

_sdoh_data_source = "Mock" if _sdoh_provider_mode == "mock" else f"Live ({_sdoh_provider_mode})"

# Select LLM provider based on environment variable
_llm_provider_mode = os.environ.get("LLM_PROVIDER", "mock")
_ollama_model = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")
_ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

if _llm_provider_mode == "ollama":
    _llm_provider = OllamaProvider(model=_ollama_model, host=_ollama_host)
    _llm_data_source = f"Ollama ({_ollama_model})"
else:
    _llm_provider = MockLLMProvider()
    _llm_data_source = "Mock LLM"


st.set_page_config(
    page_title="Pop-Health Intelligence Engine",
    page_icon="🧠",
    layout="wide",
)

st.title("🧠 Pop-Health Intelligence Engine")
st.markdown("*Transitioning Population Health from Descriptive to Prescriptive*")
st.divider()

# ── Sidebar: Patient Input ─────────────────────────────────────────────────

st.sidebar.header("Patient Input (EHR Data)")

patient_id = st.sidebar.text_input("Patient ID", value="DEMO-001")
age = st.sidebar.slider("Age", 18, 100, 55)

# ZIP code: dropdown for common Nashville areas + free-text for any ZIP
_zip_labels = {
    "37115": "37115 — Madison",
    "37208": "37208 — North Nashville",
    "37027": "37027 — Brentwood",
    "37211": "37211 — South Nashville",
    "37205": "37205 — West Nashville",
    "37201": "37201 — Downtown",
    "37207": "37207 — East Nashville",
    "37209": "37209 — Midtown",
    "37214": "37214 — Donelson",
    "37215": "37215 — Green Hills",
    "37216": "37216 — Inglewood",
    "37217": "37217 — Airport area",
    "37218": "37218 — Bordeaux",
    "37221": "37221 — Bellevue",
    "37013": "37013 — Antioch",
    "37055": "37055 — Dickson",
    "37067": "37067 — Franklin",
    "37076": "37076 — Hermitage",
    "37167": "37167 — Smyrna",
    "37128": "37128 — Murfreesboro",
    "__custom__": "✏️ Type a custom ZIP...",
}
_zip_choice = st.sidebar.selectbox("ZIP Code", options=list(_zip_labels.keys()),
                                    format_func=lambda z: _zip_labels.get(z, z))
if _zip_choice == "__custom__":
    zip_code = st.sidebar.text_input("Custom ZIP", value="37208", max_chars=5)
else:
    zip_code = _zip_choice
conditions = st.sidebar.multiselect(
    "Active Conditions",
    options=["diabetes", "hypertension", "copd", "asthma", "heart_disease",
             "chronic_kidney_disease", "obesity", "depression", "anxiety",
             "substance_abuse", "cancer", "stroke_history"],
    default=["diabetes", "hypertension"],
)
medications = st.sidebar.multiselect(
    "Current Medications",
    options=["metformin", "lisinopril", "atorvastatin", "amlodipine",
             "metoprolol", "glipizide", "insulin", "warfarin", "fluoxetine"],
    default=["metformin", "lisinopril"],
)
prior_er_visits = st.sidebar.slider("Prior ER Visits (12mo)", 0, 10, 3)
is_adherent = st.sidebar.checkbox("Medication Adherent", value=False)

run = st.sidebar.button("🚀 Run Analysis", type="primary")

# ── Tabs ────────────────────────────────────────────────────────────────────
tab_single, tab_batch = st.tabs(["Single Patient", "Batch (CSV Upload)"])

# ── Single Patient Tab ──────────────────────────────────────────────────────

with tab_single:
    if run:
        patient = PatientInput(
            patient_id=patient_id,
            age=age,
            zip_code=zip_code,
            conditions=conditions,
            medications=medications,
            prior_er_visits=prior_er_visits,
            is_adherent=is_adherent,
        )

        llm_provider = _llm_provider

        # Pipeline
        with st.spinner("Analyzing SDOH factors..."):
            sdoh_profile = get_sdoh_profile(patient.zip_code, _sdoh_provider)

        with st.spinner("Computing risk score..."):
            risk_profile = compute_risk_profile(patient, sdoh_profile)

        with st.spinner(f"Generating care plan via {_llm_data_source}..."):
            care_plan = generate_care_plan(patient, risk_profile, llm_provider)

        with st.spinner("Quantifying financial impact..."):
            financial_impact = quantify_value(patient, risk_profile, care_plan)

        # Save SDOH snapshot for historical tracking
        try:
            _history_tracker = SDOHHistoryTracker()
            _history_tracker.snapshot(patient.zip_code, {
                "overall_risk": sdoh_profile.overall_sdoh_risk,
                "air_quality_index": _sdoh_provider.fetch_metrics(patient.zip_code).air_quality_index
                    if _sdoh_provider_mode != "mock" else 50,
                "grocery_access_score": sdoh_profile.food_desert_risk * 100
                    if hasattr(sdoh_profile, "food_desert_risk") else 50,
                "housing_instability_score": sdoh_profile.housing_risk * 100
                    if hasattr(sdoh_profile, "housing_risk") else 40,
                "transportation_access_score": sdoh_profile.transportation_risk * 100
                    if hasattr(sdoh_profile, "transportation_risk") else 50,
                "crime_rate_per_100k": 380,
                "education_attainment_pct": 80,
            }, source=_sdoh_provider_mode)
        except Exception:
            pass  # Historical tracking is non-critical

        # Risk tier banner
        tier_colors = {
            "low": "green", "moderate": "blue",
            "high": "orange", "critical": "red",
        }
        tier_color = tier_colors.get(risk_profile.risk_tier.value, "gray")
        st.markdown(
            f"### Risk Tier: :{tier_color}[{risk_profile.risk_tier.value.upper()}] "
            f"(Score: {risk_profile.final_risk_score})"
        )
        st.caption(f"📊 SDOH Data Source: {_sdoh_data_source} | 🤖 LLM: {_llm_data_source}")

        # Four columns for the four features
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.subheader("📊 SDOH Profile")
            st.metric("Overall SDOH Risk", f"{sdoh_profile.overall_sdoh_risk:.1%}")
            st.metric("Food Desert Risk", f"{sdoh_profile.food_desert_risk:.1%}")
            st.metric("Housing Risk", f"{sdoh_profile.housing_risk:.1%}")
            st.metric("Air Quality Risk", f"{sdoh_profile.air_quality_risk:.1%}")

        with col2:
            st.subheader("🧠 Risk Scoring")
            st.metric("Base Score", f"{risk_profile.base_risk_score}")
            st.metric("Final Score", f"{risk_profile.final_risk_score}")
            st.metric("Multipliers", f"{len(risk_profile.applied_multipliers)}")
            if risk_profile.applied_multipliers:
                with st.expander("Multiplier Details"):
                    for m in risk_profile.applied_multipliers:
                        st.write(f"**{m.multiplier}x** — {m.description}")

        with col3:
            st.subheader("📋 Care Plan")
            status_emoji = "✅" if care_plan.status.value == "approved" else "⚠"
            st.metric("Status", f"{status_emoji} {care_plan.status.value}")
            st.metric("Actions", care_plan.triggered_intervention_count)
            if care_plan.veto_reason:
                st.error(f"**Vetoed:** {care_plan.veto_reason}")
            with st.expander("Action Items"):
                for i, item in enumerate(care_plan.action_items, 1):
                    st.write(f"{i}. **[{item.priority.upper()}]** {item.action}")
                    st.write(f"   _{item.category}_ | Target: {item.target_date_days} days")

        with col4:
            st.subheader("💰 Financial Impact")
            st.metric("Annual ER Cost", f"${financial_impact.estimated_annual_er_cost:,.0f}")
            st.metric("Cost Avoidance", f"${financial_impact.estimated_cost_avoidance:,.0f}")
            st.metric("Net Savings", f"${financial_impact.net_savings:,.0f}")
            st.metric("ROI Ratio", f"{financial_impact.roi_ratio:.1f}x")
            st.metric("Confidence", f"{financial_impact.confidence_score:.0%}")

        # Primary risk factors
        st.divider()
        st.subheader("🎯 Primary Risk Factors")
        for factor in risk_profile.primary_risk_factors:
            st.write(f"• {factor}")

        # Care plan reasoning
        if care_plan.reasoning:
            st.subheader("📝 Clinical Reasoning")
            st.write(care_plan.reasoning)

    else:
        st.info("👈 Enter patient data in the sidebar and click **Run Analysis** to see the full pipeline.")
        st.divider()
        st.subheader("Architecture")
        st.markdown("""
        **Functional Core / Imperative Shell (FCIS) + Ports & Adapters**

        | Feature | Role | Pattern |
        |---------|------|---------|
        | SDOH Profiler | Geographic → social risk factors | Port + Adapter |
        | Risk Scoring Engine | Risk tier with interaction multipliers | Pure Core |
        | Intervention Strategist | LLM care plans + critic validation | LLM Port + Critic |
        | Value Quantifier | Actuarial ROI model | Pure Core |
        """)


# ── Batch CSV Tab ──────────────────────────────────────────────────────────

with tab_batch:
    st.subheader("📋 Batch Patient Analysis")
    st.markdown("""
    Upload a CSV file with patient data. The engine will run the full pipeline
    (SDOH → Risk → Care Plan → ROI) for each patient and display a summary table.

    **Required CSV columns:** `patient_id, age, zip_code, conditions, medications, prior_er_visits, is_adherent`

    *Conditions and medications are pipe-separated (e.g., `diabetes|hypertension`)*
    """)

    # Download template button
    template_csv = "patient_id,age,zip_code,conditions,medications,prior_er_visits,is_adherent\nP001,55,37208,diabetes|hypertension,metformin|lisinopril,3,false\nP002,62,37027,diabetes,metformin,1,true\nP003,48,37115,hypertension|obesity,lisinopril|atorvastatin,0,true\n"
    st.download_button("📥 Download CSV Template", template_csv, file_name="patient_template.csv", mime="text/csv")

    uploaded = st.file_uploader("Upload patient CSV", type=["csv"])

    if uploaded is not None:
        import csv
        import io

        try:
            content = uploaded.read().decode("utf-8")
            reader = csv.DictReader(io.StringIO(content))
            rows = list(reader)
        except Exception as e:
            st.error(f"Error reading CSV: {e}")
            rows = []

        if rows:
            st.write(f"**{len(rows)} patients loaded.** Running pipeline...")

            results = []
            progress = st.progress(0)

            for i, row in enumerate(rows):
                try:
                    p = PatientInput(
                        patient_id=row.get("patient_id", f"P{i:03d}"),
                        age=int(row.get("age", 50)),
                        zip_code=str(row.get("zip_code", "37208"))[:5],
                        conditions=row.get("conditions", "").split("|") if row.get("conditions") else [],
                        medications=row.get("medications", "").split("|") if row.get("medications") else [],
                        prior_er_visits=int(row.get("prior_er_visits", 0)),
                        is_adherent=row.get("is_adherent", "true").lower().strip() == "true",
                    )

                    sdoh = get_sdoh_profile(p.zip_code, _sdoh_provider)
                    risk = compute_risk_profile(p, sdoh)
                    plan = generate_care_plan(p, risk, _llm_provider)
                    impact = quantify_value(p, risk, plan)

                    results.append({
                        "Patient ID": p.patient_id,
                        "ZIP": p.zip_code,
                        "Age": p.age,
                        "Conditions": ", ".join(p.conditions),
                        "Risk Tier": risk.risk_tier.value.upper(),
                        "Risk Score": round(risk.final_risk_score, 1),
                        "Multipliers": len(risk.applied_multipliers),
                        "Care Plan": plan.status.value,
                        "Net Savings": f"${impact.net_savings:,.0f}",
                        "ROI": f"{impact.roi_ratio:.1f}x",
                        "Confidence": f"{impact.confidence_score:.0%}",
                    })
                except Exception as e:
                    results.append({
                        "Patient ID": row.get("patient_id", "?"),
                        "ZIP": row.get("zip_code", "?"),
                        "Age": row.get("age", "?"),
                        "Conditions": "ERROR",
                        "Risk Tier": "—",
                        "Risk Score": "—",
                        "Multipliers": "—",
                        "Care Plan": f"Error: {e}",
                        "Net Savings": "—",
                        "ROI": "—",
                        "Confidence": "—",
                    })

                progress.progress((i + 1) / len(rows))

            # Display results table
            st.dataframe(results, use_container_width=True, hide_index=True)

            # Summary metrics
            st.divider()
            st.subheader("📊 Batch Summary")
            valid = [r for r in results if r["Risk Tier"] != "—"]
            if valid:
                tiers = [r["Risk Tier"] for r in valid]
                total_savings = sum(
                    float(r["Net Savings"].replace("$", "").replace(",", ""))
                    for r in valid if r["Net Savings"] != "—"
                )
                col_a, col_b, col_c, col_d = st.columns(4)
                col_a.metric("Patients Processed", len(results))
                col_b.metric("Critical/High", sum(1 for t in tiers if t in ("CRITICAL", "HIGH")))
                col_c.metric("Total Net Savings", f"${total_savings:,.0f}")
                col_d.metric("Approved Plans", sum(1 for r in valid if r["Care Plan"] == "approved"))

            # Download results
            st.divider()
            result_csv = io.StringIO()
            writer = csv.DictWriter(result_csv, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)
            st.download_button("📥 Download Results CSV", result_csv.getvalue(),
                               file_name="patient_results.csv", mime="text/csv")