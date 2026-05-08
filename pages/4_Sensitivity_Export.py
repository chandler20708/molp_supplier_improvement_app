from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.app_state import require_data, scenario_selector, supplier_selector
from utils.charts import parameter_impact_bar, target_range_box
from utils.formatting import apply_global_style, render_download_button, render_plotly_chart, scenario_label
from utils.transforms import filter_by_supplier_scenario

st.set_page_config(page_title="Sensitivity & Export", page_icon="📤", layout="wide")
apply_global_style()


def robustness_verdict(weight_row: pd.DataFrame, parameter_row: pd.DataFrame, peer_rows: pd.DataFrame) -> tuple[str, str]:
    theta_range = None
    if not weight_row.empty:
        theta_min = weight_row.iloc[0].get("theta_min")
        theta_max = weight_row.iloc[0].get("theta_max")
        if pd.notna(theta_min) and pd.notna(theta_max):
            theta_range = float(theta_max) - float(theta_min)
    parameter_index = None
    if not parameter_row.empty and pd.notna(parameter_row.iloc[0].get("robustness_index_parameter")):
        parameter_index = float(parameter_row.iloc[0].get("robustness_index_parameter"))
    peer_count = int(peer_rows["peer_supplier"].nunique()) if peer_rows is not None and not peer_rows.empty and "peer_supplier" in peer_rows.columns else 0

    if theta_range is None and parameter_index is None:
        return "Data-sensitive", "Sensitivity outputs are incomplete, so report the target with explicit data-availability caveats."
    if (theta_range is not None and theta_range <= 0.035) and (parameter_index is None or parameter_index <= 0.00025):
        return "Robust", "The target changes little across available weight and parameter checks."
    if (theta_range is not None and theta_range <= 0.055) and peer_count <= 4:
        return "Moderately sensitive", "The recommendation is usable, but management should report the scenario assumptions and benchmark peers."
    if theta_range is not None and theta_range > 0.055:
        return "Preference-sensitive", "The target moves materially when weights change, so stakeholder preference elicitation matters."
    return "Data-sensitive", "Parameter or peer checks drive the caution; inspect the tables before presenting a firm action."

app_data = require_data()
master_df = app_data["master"]
outputs = app_data["outputs"]

st.sidebar.header("Sensitivity controls")
supplier = supplier_selector(master_df)
scenario = scenario_selector()
st.sidebar.caption("Controls filter sensitivity and export tables only.")

st.title("4. Sensitivity & Export")
st.markdown(
    f"""
    <div class="guide-box">
    <strong>Robustness check.</strong> Supplier <b>{supplier}</b>, scenario <b>{scenario_label(scenario)}</b>. Use this page to decide whether the target is stable enough to report.
    </div>
    """,
    unsafe_allow_html=True,
)

targets_df = outputs.get("molp_targets", pd.DataFrame())
peer_weights_df = outputs.get("molp_peer_weights", pd.DataFrame())
weight_sens_df = outputs.get("sensitivity_weight_summary", pd.DataFrame())
param_sens_df = outputs.get("sensitivity_parameter_summary", pd.DataFrame())
param_runs_df = outputs.get("sensitivity_parameter_runs", pd.DataFrame())
peer_sens_df = outputs.get("sensitivity_parameter_peer_weights", pd.DataFrame())

# KPI cards
wrow = weight_sens_df[weight_sens_df["supplier"] == supplier] if not weight_sens_df.empty and "supplier" in weight_sens_df.columns else pd.DataFrame()
prow = param_sens_df[(param_sens_df["supplier"] == supplier) & (param_sens_df["scenario"] == scenario)] if not param_sens_df.empty and "scenario" in param_sens_df.columns else pd.DataFrame()
peer_filtered_for_verdict = peer_sens_df[(peer_sens_df["supplier"] == supplier) & (peer_sens_df["scenario"] == scenario)].copy() if not peer_sens_df.empty and "scenario" in peer_sens_df.columns else pd.DataFrame()
verdict, verdict_reason = robustness_verdict(wrow, prow, peer_filtered_for_verdict)

badge_class = {
    "Robust": "badge-green",
    "Moderately sensitive": "badge-amber",
    "Preference-sensitive": "badge-red",
    "Data-sensitive": "badge-red",
}.get(verdict, "badge-grey")
st.markdown(
    f"""
    <div class="action-box">
    <span class="badge {badge_class}">{verdict}</span>
    <b>Can we trust this target?</b><br>
    {verdict_reason} A robust target can be used as a firmer supplier-development direction; a sensitive target should be framed as conditional on scenario assumptions.
    </div>
    """,
    unsafe_allow_html=True,
)

c1, c2, c3, c4 = st.columns(4)
if not wrow.empty:
    c1.metric("Weight robustness", f"{float(wrow.iloc[0].get('robustness_index_weight', 0)):.4f}")
    c2.metric("Theta range", f"{float(wrow.iloc[0].get('theta_min', 0)):.3f}–{float(wrow.iloc[0].get('theta_max', 0)):.3f}")
else:
    c1.metric("Weight robustness", "—")
    c2.metric("Theta range", "—")
if not prow.empty:
    c3.metric("Parameter robustness", f"{float(prow.iloc[0].get('robustness_index_parameter', 0)):.4f}")
    c4.metric("Perturbation runs", f"{int(prow.iloc[0].get('run_count', 0))}")
else:
    c3.metric("Parameter robustness", "—")
    c4.metric("Perturbation runs", "—")

left, right = st.columns([1.05, 0.95], gap="large")
with left:
    st.subheader("Target range across parameter runs")
    render_plotly_chart(target_range_box(param_runs_df, supplier, scenario), key=f"target_range_{supplier}_{scenario}")
with right:
    st.subheader("Parameter impact on theta")
    render_plotly_chart(parameter_impact_bar(param_runs_df, supplier, scenario), key=f"parameter_impact_{supplier}_{scenario}")

st.subheader("Peer stability")
if peer_sens_df.empty:
    st.info("No peer sensitivity output available.")
else:
    peer_filtered = peer_filtered_for_verdict
    if peer_filtered.empty:
        st.info("No peer sensitivity rows for the selected supplier/scenario.")
    else:
        summary = peer_filtered.groupby("peer_supplier", as_index=False).agg(
            selection_count=("lambda_value", "count"),
            avg_weight=("lambda_value", "mean"),
            min_weight=("lambda_value", "min"),
            max_weight=("lambda_value", "max"),
        ).sort_values("selection_count", ascending=False)
        st.dataframe(summary, width="stretch", hide_index=True)

st.divider()
st.subheader("Export filtered outputs")
st.markdown(
    """
    <div class="muted-box">
    Download tables filtered to the current supplier and scenario. These files are suitable for appendix checks, team review, or report asset generation.
    </div>
    """,
    unsafe_allow_html=True,
)

d1, d2, d3, d4 = st.columns(4)
with d1:
    render_download_button("Targets CSV", filter_by_supplier_scenario(targets_df, supplier, scenario), f"targets_{supplier}_{scenario}.csv")
with d2:
    render_download_button("Peer weights CSV", filter_by_supplier_scenario(peer_weights_df, supplier, scenario), f"peer_weights_{supplier}_{scenario}.csv")
with d3:
    render_download_button("Parameter runs CSV", filter_by_supplier_scenario(param_runs_df, supplier, scenario), f"parameter_runs_{supplier}_{scenario}.csv")
with d4:
    render_download_button("Parameter peers CSV", filter_by_supplier_scenario(peer_sens_df, supplier, scenario), f"parameter_peers_{supplier}_{scenario}.csv")
