"""Pop-Health Intelligence Engine — Streamlit Demo App.

CEO-level demo: input patient data → see SDOH risk, risk tier, care plan, and ROI.
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
from features.sdoh_profiler.shell import get_sdoh_profile
from features.risk_scoring.core import compute_risk_profile
from features.intervention_strategist.providers.mock import MockLLMProvider
from features.intervention_strategist.shell import generate_care_plan
from features.value_quantifier.core import quantify_value


# Select SDOH provider based on environment variable
_sdoh_provider_mode = os.environ.get("SDOH_PROVIDER", "mock")
_census_key = os.environ.get("CENSUS_API_KEY", "")
_airnow_key = os.environ.get("AIRNOW_API_KEY", "")

if _sdoh_provider_mode == "composite" and _census_key:
    _sdoh_provider = CompositeSdoHProvider(
        primary=CensusACSProvider(api_key=_census_key),
        supplement=AirNowProvider(api_key=_airnow_key) if _airnow_key else None,
    )
elif _sdoh_provider_mode == "census" and _census_key:
    _sdoh_provider = CensusACSProvider(api_key=_census_key)
else:
    _sdoh_provider = MockSdoHProvider()

_sdoh_data_source = "Mock" if _sdoh_provider_mode == "mock" else f"Live ({_sdoh_provider_mode})"


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
zip_code = st.sidebar.selectbox(
    "ZIP Code",
    options=["37115", "37208", "37027"],
    format_func=lambda z: {
        "37115": "37115 — Madison, TN",
        "37208": "37208 — North Nashville",
        "37027": "37027 — Brentwood, TN",
    }.get(z, z),
)
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

# ── Main Content ───────────────────────────────────────────────────────────

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

    sdoh_provider = _sdoh_provider
    llm_provider = MockLLMProvider()

    # Pipeline
    with st.spinner("Analyzing SDOH factors..."):
        sdoh_profile = get_sdoh_profile(patient.zip_code, sdoh_provider)

    with st.spinner("Computing risk score..."):
        risk_profile = compute_risk_profile(patient, sdoh_profile)

    with st.spinner("Generating care plan (LLM + Critic)..."):
        care_plan = generate_care_plan(patient, risk_profile, llm_provider)

    with st.spinner("Quantifying financial impact..."):
        financial_impact = quantify_value(patient, risk_profile, care_plan)

    # ── Results Dashboard ───────────────────────────────────────────────────

    # Risk tier banner
    tier_colors = {
        "low": "green",
        "moderate": "blue",
        "high": "orange",
        "critical": "red",
    }
    tier_color = tier_colors.get(risk_profile.risk_tier.value, "gray")
    st.markdown(
        f"### Risk Tier: :{tier_color}[{risk_profile.risk_tier.value.upper()}] "
        f"(Score: {risk_profile.final_risk_score})"
    )
    st.caption(f"📊 SDOH Data Source: {_sdoh_data_source}")

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

    # Architecture overview
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