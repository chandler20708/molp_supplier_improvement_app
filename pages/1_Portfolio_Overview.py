from __future__ import annotations

import streamlit as st

from utils.app_state import require_data
from utils.charts import portfolio_matrix_3d
from utils.formatting import apply_global_style, format_number

st.set_page_config(page_title="Portfolio Overview", page_icon="📊", layout="wide")
apply_global_style()

app_data = require_data()
master_df = app_data["master"]

st.sidebar.header("Portfolio controls")
dea_filter = st.sidebar.selectbox("DEA status", ["All", "CCR-efficient", "Needs development"])
status_filter = st.sidebar.multiselect(
    "Portfolio status",
    sorted(master_df["portfolio_status"].dropna().unique().tolist()),
    default=sorted(master_df["portfolio_status"].dropna().unique().tolist()),
)
st.sidebar.caption("This page is diagnostic. It does not need a scenario selector because no MOLP target is shown here.")

view_df = master_df.copy()
if dea_filter != "All":
    view_df = view_df[view_df["dea_status"] == dea_filter]
if status_filter:
    view_df = view_df[view_df["portfolio_status"].isin(status_filter)]

st.title("1. Portfolio Overview")
st.markdown(
    """
    <div class="guide-box">
      <strong>Use this page first.</strong> It separates three ideas that should not be collapsed: <b>DEA efficiency</b>, <b>product quality</b>, and <b>customer service</b>.
      The 3D matrix is the portfolio diagnosis; the table is the audit trail.
    </div>
    """,
    unsafe_allow_html=True,
)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Suppliers", len(master_df))
c2.metric("CCR-efficient", int((master_df["ccr_efficiency"] >= 0.999).sum()))
c3.metric("Needs development", int((master_df["ccr_efficiency"] < 0.999).sum()))
worst = master_df.sort_values("ccr_efficiency").head(3)["supplier"].tolist()
c4.metric("Lowest CCR", ", ".join(worst))

left, right = st.columns([1.25, 1.0], gap="large")
with left:
    st.subheader("Supplier Portfolio Matrix — 3D")
    st.markdown(
        """
        <div class="action-box">
        <b>3D reading guide:</b> right = higher DEA CCR efficiency; up = stronger product quality; depth = stronger customer service.
        Use CCR efficiency as an operational diagnosis, not as proof of supplier desirability.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.plotly_chart(portfolio_matrix_3d(view_df), width="stretch")
    st.caption("Black reference lines mark the zero axes. Faint floor labels show supplier projections onto the DEA–PQ plane, making the 3D position easier to read.")

with right:
    st.subheader("Portfolio action legend")
    st.markdown(
        """
        <div class="status-legend">
          <div class="legend-item"><span class="badge badge-green">Strategic partner</span><br>Retain and deepen partnership.</div>
          <div class="legend-item"><span class="badge badge-amber">Development candidate</span><br>Create supplier-development plan.</div>
          <div class="legend-item"><span class="badge badge-grey">Tactical efficient</span><br>Use selectively; monitor strategic weakness.</div>
          <div class="legend-item"><span class="badge badge-red">Deprioritise / renegotiate</span><br>Reduce dependency or renegotiate.</div>
        </div>
        <div class="decision-box">
        <b>Next management action:</b> select a development candidate in the Supplier Deep Dive page and translate its MOLP target into a joint capability-improvement plan.
        </div>
        """,
        unsafe_allow_html=True,
    )
    table_cols = [
        "supplier", "product_quality_score", "customer_service_score", "ccr_efficiency",
        "avg_unit_price", "late_delivery_pct", "shipping_error_pct", "lead_time_days",
        "total_purchase", "portfolio_status",
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
            "portfolio_status": "Status",
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
