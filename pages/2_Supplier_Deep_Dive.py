from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.app_state import require_data, scenario_selector, supplier_selector
from utils.charts import current_vs_target_radar, peer_weights_bar
from utils.formatting import apply_global_style, format_money, format_number, format_pct, scenario_label
from utils.recommendations import generate_recommendation_summary
from utils.transforms import build_improvement_table, get_selected_target

st.set_page_config(page_title="Supplier Deep Dive", page_icon="🔍", layout="wide")
apply_global_style()

app_data = require_data()
master_df = app_data["master"]
outputs = app_data["outputs"]
targets_df = outputs.get("molp_targets", pd.DataFrame())
peer_weights_df = outputs.get("molp_peer_weights", pd.DataFrame())

st.sidebar.header("Supplier controls")
supplier = supplier_selector(master_df)
scenario = scenario_selector()
st.sidebar.caption("This page uses both controls: supplier changes the diagnosis; scenario changes the MOLP target.")

st.title("2. Supplier Deep Dive")
current_rows = master_df[master_df["supplier"] == supplier]
if current_rows.empty:
    st.error("Selected supplier not found.")
    st.stop()
current = current_rows.iloc[0]
target = get_selected_target(targets_df, supplier, scenario)
recommendation = generate_recommendation_summary(current, target, peer_weights_df, supplier, scenario)
is_ccr_efficient = pd.notna(current.get("ccr_efficiency")) and float(current.get("ccr_efficiency")) >= 0.999

st.markdown(
    f"""
    <div class="guide-box">
      <strong>Selected supplier: {supplier}</strong> · Scenario: <b>{scenario_label(scenario)}</b><br>
      Read left-to-right: current position → MOLP target → benchmark peers → recommended action.
    </div>
    """,
    unsafe_allow_html=True,
)

h1, h2, h3, h4 = st.columns([1.3, 1.1, 1.1, 1.1])
h1.metric("Portfolio status", current.get("portfolio_status", "—"))
h2.metric("CCR efficiency", format_number(current.get("ccr_efficiency"), 3))
h3.metric("Product quality", format_number(current.get("product_quality_score"), 3))
h4.metric("Customer service", format_number(current.get("customer_service_score"), 3))

st.markdown(
    f"""
    <div class="action-box">
    <b>{recommendation['primary_action']}</b><br>
    {recommendation['secondary_action']}
    </div>
    """,
    unsafe_allow_html=True,
)
if is_ccr_efficient:
    st.markdown(
        """
        <div class="muted-box">
        <b>CCR-efficient benchmark supplier:</b> this supplier is already on the CCR frontier in the imported DEA diagnosis.
        The MOLP target should be read as a monitoring or benchmark case, not as the same development plan used for CCR-inefficient suppliers.
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown('<div class="section-label">Observed baseline grouped for stakeholder reading</div>', unsafe_allow_html=True)
g1, g2, g3 = st.columns(3, gap="large")
with g1:
    st.markdown("**Strategic attractiveness**")
    st.metric("Product quality", format_number(current.get("product_quality_score"), 3))
    st.metric("Customer service overlay", format_number(current.get("customer_service_score"), 3))
with g2:
    st.markdown("**Operational risk**")
    st.metric("Late delivery", format_pct(current.get("late_delivery_pct")))
    st.metric("Shipping errors", format_pct(current.get("shipping_error_pct")))
    st.metric("Lead time", f"{format_number(current.get('lead_time_days'), 1)} days")
with g3:
    st.markdown("**Commercial / efficiency**")
    st.metric("Average unit price", format_money(current.get("avg_unit_price")))
    st.metric("Total purchase", format_money(current.get("total_purchase")))
    st.metric("CCR efficiency", format_number(current.get("ccr_efficiency"), 3))

st.markdown('<div class="section-label">MOLP target under selected scenario</div>', unsafe_allow_html=True)
if target is None:
    st.warning("No MOLP target exists for this supplier/scenario. Check molp_targets.csv.")
else:
    target_cols = st.columns(6)
    target_cols[0].metric("Target price", format_money(target.get("target_price")))
    target_cols[1].metric("Target late", format_pct(target.get("target_late_pct")))
    target_cols[2].metric("Target errors", format_pct(target.get("target_error_pct")))
    target_cols[3].metric("Target lead", f"{format_number(target.get('target_lead_days'), 1)} days")
    target_cols[4].metric("Target PQ", format_number(target.get("target_quality_score"), 3))
    target_cols[5].metric("Theta", format_number(target.get("theta"), 3))

left, right = st.columns([1.2, 1.0], gap="large")
with left:
    st.subheader("Current vs target radar")
    radar = current_vs_target_radar(master_df, targets_df, supplier, scenario)
    if radar is None:
        st.info("No radar chart can be drawn for the selected supplier/scenario because the required current-target data is unavailable.")
    else:
        st.plotly_chart(radar, width="stretch")
    st.caption("Radar values are normalised to 0-100. Higher is always better, even for price, late delivery, shipping errors, and lead time.")
    st.caption("Customer service is a strategic overlay in this app. It is shown for relationship interpretation, not as a MOLP-optimised target.")

with right:
    st.subheader("Room to improve")
    improvement = build_improvement_table(master_df, targets_df, supplier, scenario)
    if improvement.empty:
        st.info("No improvement table available.")
    else:
        top_priorities = improvement[improvement["Metric"] != "Purchase"].sort_values("Normalised room", ascending=False).head(2)
        if not top_priorities.empty:
            badges = "".join(
                f"<span class='badge badge-blue'>{row['Metric']}: {row['Normalised room']:.1f} room</span>"
                for _, row in top_priorities.iterrows()
                if pd.notna(row["Normalised room"]) and row["Normalised room"] > 0
            )
            if badges:
                st.markdown(f"<div class='muted-box'><b>Top two improvement priorities</b><br>{badges}</div>", unsafe_allow_html=True)
        display = improvement.copy()
        display["Improvement %"] = display["Improvement %"].map(lambda x: "—" if pd.isna(x) else f"{x:.1f}%")
        display["Normalised room"] = display["Normalised room"].map(lambda x: "—" if pd.isna(x) else f"{x:.1f}")
        def priority_style(v):
            return "background-color: #fee2e2; color: #991b1b; font-weight: 700" if v == "High" else (
                "background-color: #fef3c7; color: #92400e; font-weight: 700" if v == "Medium" else (
                    "background-color: #dcfce7; color: #166534; font-weight: 700" if v == "Low" else ""
                )
            )

        styled = display.style
        if hasattr(styled, "map"):
            styled = styled.map(priority_style, subset=["Priority"])
        else:
            styled = styled.applymap(priority_style, subset=["Priority"])
        st.dataframe(styled, width="stretch", hide_index=True)

peer_col, rec_col = st.columns([0.95, 1.05], gap="large")
with peer_col:
    st.subheader("Benchmark peer weights")
    st.plotly_chart(peer_weights_bar(peer_weights_df, supplier, scenario), width="stretch")
    peers = peer_weights_df[(peer_weights_df["supplier"] == supplier) & (peer_weights_df["scenario"] == scenario)].copy() if not peer_weights_df.empty else pd.DataFrame()
    if not peers.empty:
        peers = peers.sort_values("lambda_value", ascending=False).rename(columns={"peer_supplier": "Peer", "lambda_value": "Weight"})
        st.dataframe(peers[["Peer", "Weight"]], width="stretch", hide_index=True)
    else:
        st.info("No peer weights available for this supplier/scenario.")

with rec_col:
    st.subheader("Recommended action")
    st.markdown("<div class='decision-box'>", unsafe_allow_html=True)
    for label, rec in recommendation.items():
        st.markdown(f"- **{label.replace('_', ' ').title()}:** {rec}")
    st.markdown("</div>", unsafe_allow_html=True)
    st.caption("Theta is a weighted normalised deviation score, not DEA efficiency. Peer weights are composite benchmark weights, not probabilities or order-allocation shares.")
