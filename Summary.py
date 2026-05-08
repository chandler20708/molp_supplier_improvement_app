from __future__ import annotations

import streamlit as st

from utils.app_state import require_data
from utils.formatting import apply_global_style

st.set_page_config(
    page_title="Decision Summary",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_global_style()
app_data = require_data()
master_df = app_data["master"]

st.title("Supplier Decision Summary")
st.caption("Stakeholder-facing recommendation from MCDA quality/service evidence, DEA efficiency diagnosis and MOLP development potential.")

st.markdown(
    """
    <div class="hero-box">
      <div class="hero-title">Overall recommendation: prefer H, B and A; develop C first.</div>
      <div class="hero-subtitle">Use G and I as operational benchmarks, develop F/K/D only conditionally, and keep E/J/L as lower-priority suppliers for monitoring, renegotiation or selective use.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.markdown('<div class="flow-card"><b>Preferred strategic suppliers</b><br><span>H as premium supplier; B and A as scalable sourcing partners.</span></div>', unsafe_allow_html=True)
with col2:
    st.markdown('<div class="flow-card"><b>Operational benchmarks</b><br><span>G and I are DEA-efficient, but weaker as strategic quality-service standards.</span></div>', unsafe_allow_html=True)
with col3:
    st.markdown('<div class="flow-card"><b>Primary development</b><br><span>C has the strongest feasible development potential; start with late delivery.</span></div>', unsafe_allow_html=True)
with col4:
    st.markdown('<div class="flow-card"><b>Conditional development</b><br><span>F, K and D need targeted improvement conditions before investment.</span></div>', unsafe_allow_html=True)
with col5:
    st.markdown('<div class="flow-card"><b>Lower priority</b><br><span>E, J and L should be monitored, renegotiated or used selectively.</span></div>', unsafe_allow_html=True)

st.divider()

st.subheader("What to do")
summary_cols = [
    "supplier",
    "recommendation_tier",
    "recommended_action",
    "management_note",
    "product_quality_score",
    "customer_service_score",
    "ccr_efficiency",
]
display = master_df[[c for c in summary_cols if c in master_df.columns]].copy()
display = display.rename(
    columns={
        "supplier": "Supplier",
        "recommendation_tier": "Recommendation tier",
        "recommended_action": "Action",
        "management_note": "Management note",
        "product_quality_score": "PQ",
        "customer_service_score": "CS",
        "ccr_efficiency": "CCR",
    }
)
for col in ["PQ", "CS", "CCR"]:
    if col in display.columns:
        display[col] = display[col].map(lambda x: "—" if x != x else f"{float(x):.3f}")
st.dataframe(display, width="stretch", hide_index=True)

st.markdown(
    """
    <div class="decision-box">
    <b>How to use the app:</b> start from this recommendation, use Portfolio Overview as the evidence view,
    use Supplier Deep Dive to explain one supplier's targets and peers, and use Scenario Interpretation to test how development priorities change by scenario.
    </div>
    """,
    unsafe_allow_html=True,
)
