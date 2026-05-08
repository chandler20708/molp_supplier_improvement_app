from __future__ import annotations

import streamlit as st

from utils.app_state import require_data
from utils.charts import portfolio_matrix_3d
from utils.formatting import apply_global_style, render_plotly_chart

st.set_page_config(page_title="Portfolio Overview", page_icon="📊", layout="wide")
apply_global_style()

app_data = require_data()
master_df = app_data["master"]

st.sidebar.header("Portfolio controls")
dea_filter = st.sidebar.selectbox("DEA status", ["All", "CCR-efficient", "Needs development"])
tier_filter = st.sidebar.multiselect(
    "Recommendation tier",
    master_df[["recommendation_order", "recommendation_tier"]]
    .drop_duplicates()
    .sort_values("recommendation_order")["recommendation_tier"]
    .tolist(),
    default=master_df[["recommendation_order", "recommendation_tier"]]
    .drop_duplicates()
    .sort_values("recommendation_order")["recommendation_tier"]
    .tolist(),
)
st.sidebar.caption("This page is diagnostic. It does not need a scenario selector because no MOLP target is shown here.")

view_df = master_df.copy()
if dea_filter != "All":
    view_df = view_df[view_df["dea_status"] == dea_filter]
if tier_filter:
    view_df = view_df[view_df["recommendation_tier"].isin(tier_filter)]

st.title("1. Portfolio Overview")
st.markdown(
    """
    <div class="guide-box">
      <strong>Use this page as the evidence view.</strong> The recommendation tier is the management conclusion.
      The analytical status, DEA efficiency, product quality and customer service columns explain the evidence behind it.
    </div>
    """,
    unsafe_allow_html=True,
)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Suppliers", len(master_df))
c2.metric("CCR-efficient", int((master_df["ccr_efficiency"] >= 0.999).sum()))
c3.metric("Needs development", int((master_df["ccr_efficiency"] < 0.999).sum()))
c4.metric("Preferred suppliers", "H, B, A")

st.subheader("Action table")
action_cols = [
    "supplier",
    "recommendation_tier",
    "recommended_action",
    "management_note",
    "portfolio_status",
    "ccr_efficiency",
    "product_quality_score",
    "customer_service_score",
]
action_table = view_df[[c for c in action_cols if c in view_df.columns]].rename(
    columns={
        "supplier": "Supplier",
        "recommendation_tier": "Recommendation tier",
        "recommended_action": "Action",
        "management_note": "Why / caveat",
        "portfolio_status": "Analytical status",
        "ccr_efficiency": "CCR efficiency",
        "product_quality_score": "PQ score",
        "customer_service_score": "CS score",
    }
)
st.dataframe(action_table, width="stretch", hide_index=True)

left, right = st.columns([1.25, 1.0], gap="large")
with left:
    st.subheader("Evidence matrix — 3D")
    st.markdown(
        """
        <div class="action-box">
        <b>3D reading guide:</b> right = higher DEA CCR efficiency; up = stronger product quality; depth = stronger customer service.
        Use CCR efficiency as an operational diagnosis, not as proof of supplier desirability.
        </div>
        """,
        unsafe_allow_html=True,
    )
    render_plotly_chart(portfolio_matrix_3d(view_df), key="portfolio_matrix")
    st.caption("Black reference lines mark the zero axes. Faint floor labels show supplier projections onto the DEA–PQ plane, making the 3D position easier to read.")

with right:
    st.subheader("Recommendation legend")
    st.markdown(
        """
        <div class="status-legend">
          <div class="legend-item"><span class="badge badge-green">Preferred strategic</span><br>Retain and deepen partnership.</div>
          <div class="legend-item"><span class="badge badge-grey">Operational benchmark</span><br>Use as a reference, not the strategic standard.</div>
          <div class="legend-item"><span class="badge badge-blue">Primary development</span><br>Create the first supplier-development plan.</div>
          <div class="legend-item"><span class="badge badge-amber">Conditional development</span><br>Develop only with review gates.</div>
          <div class="legend-item"><span class="badge badge-red">Lower priority</span><br>Monitor, renegotiate or use selectively.</div>
        </div>
        <div class="decision-box">
        <b>Next management action:</b> open Supplier C in the Supplier Deep Dive page and translate its late-delivery MOLP target into a joint supplier-development plan.
        </div>
        """,
        unsafe_allow_html=True,
    )
    table_cols = [
        "supplier", "product_quality_score", "customer_service_score", "ccr_efficiency",
        "avg_unit_price", "late_delivery_pct", "shipping_error_pct", "lead_time_days",
        "total_purchase", "recommendation_tier", "portfolio_status",
    ]
    table = view_df[[c for c in table_cols if c in view_df.columns]].rename(
        columns={
            "supplier": "Supplier",
            "product_quality_score": "PQ score",
            "customer_service_score": "CS score",
            "ccr_efficiency": "CCR efficiency",
            "avg_unit_price": "Avg price",
            "late_delivery_pct": "Late %",
            "shipping_error_pct": "Error %",
            "lead_time_days": "Lead days",
            "total_purchase": "Purchase",
            "recommendation_tier": "Recommendation tier",
            "portfolio_status": "Analytical status",
        }
    )
    st.dataframe(table, width="stretch", hide_index=True)

st.markdown(
    """
    <div class="muted-box">
    Method note: product quality and customer service are kept separate because collapsing them into one MCDA average can hide suppliers that are strong on one stakeholder dimension but weak on the other.
    </div>
    """,
    unsafe_allow_html=True,
)
