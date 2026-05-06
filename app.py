from __future__ import annotations

import streamlit as st

from utils.formatting import apply_global_style

st.set_page_config(
    page_title="Supplier Improvement Cockpit",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_global_style()

st.title("Supplier Improvement Cockpit")
st.caption("Post-DEA MOLP decision-support dashboard for supplier development.")

st.markdown(
    """
    <div class="hero-box">
      <div class="hero-title">Use the pages on the left to move from diagnosis to action.</div>
      <div class="hero-subtitle">MCDA and DEA are imported as upstream evidence. MOLP targets and peer weights are used to guide scenario-specific supplier improvement.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown('<div class="flow-card"><b>1. Portfolio Overview</b><br><span>Classify suppliers using DEA efficiency, product quality, and customer service.</span></div>', unsafe_allow_html=True)
with col2:
    st.markdown('<div class="flow-card"><b>2. Supplier Deep Dive</b><br><span>Inspect the selected supplier’s baseline, MOLP target, and benchmark peers.</span></div>', unsafe_allow_html=True)
with col3:
    st.markdown('<div class="flow-card"><b>3. Scenario Simulator</b><br><span>Compare predefined scenarios or test live custom weights if Gurobi is available.</span></div>', unsafe_allow_html=True)
with col4:
    st.markdown('<div class="flow-card"><b>4. Sensitivity & Export</b><br><span>Check robustness and download filtered outputs for reporting.</span></div>', unsafe_allow_html=True)

st.divider()

st.subheader("Expected project structure")
st.code(
    """.
├── data/
│   ├── product_quality_scores.csv
│   ├── customer_service_scores.csv
│   ├── supplier_operational_inputs.csv
│   └── dea_ccr_efficiency.csv
├── outputs/team_ccr/
│   ├── supplier_molp_inputs.csv
│   ├── dea_team_ccr_efficiency.csv
│   ├── molp_targets.csv
│   ├── molp_peer_weights.csv
│   ├── molp_payoff_table.csv
│   └── sensitivity_*.csv
├── app.py
├── pages/
└── utils/""",
    language="text",
)

st.info(
    "The dashboard will also work in a flat testing folder if the CSVs are placed beside app.py. "
    "For the final project, keep the normal data/ and outputs/team_ccr/ folders."
)
