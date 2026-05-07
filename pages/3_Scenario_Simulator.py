from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.app_state import require_data
from utils.charts import current_vs_target_radar, scenario_target_bar
from utils.formatting import apply_global_style, scenario_label
from utils.load_data import SCENARIO_LABELS
from utils.optimizer import check_live_optimizer_available, normalise_weights, run_live_molp
from utils.transforms import (
    build_baseline_potential_table,
    build_improvement_table,
    build_scenario_potential_summary,
    build_scenario_potential_table,
    build_scenario_table,
    inefficient_suppliers,
)

st.set_page_config(page_title="Scenario Interpretation", page_icon="⚙️", layout="wide")
apply_global_style()

app_data = require_data()
master_df = app_data["master"]
outputs = app_data["outputs"]
targets_df = outputs.get("molp_targets", pd.DataFrame())
payoff_df = outputs.get("molp_payoff_table", pd.DataFrame())

st.sidebar.header("Scenario controls")
inefficient = inefficient_suppliers(master_df)
live_available, live_message = check_live_optimizer_available()
st.sidebar.caption("Precomputed scenarios are the default. Live MOLP is secondary and only appears when the optimiser stack is available.")

st.title("3. Scenario Interpretation")
st.markdown(
    """
    <div class="guide-box">
    <strong>Purpose.</strong> This page ranks supplier-development potential without changing the optimiser.
    MCDA and DEA remain upstream inputs; MOLP provides scenario-specific targets. Customer service is a strategic overlay, peer weights are benchmark intensities, and purchase is commercial scale/context.
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown(
    """
    <div class="muted-box">
    The MOLP model is solved using normalised deviations so price, delay, error, lead time and quality can be compared fairly despite different units.
    Recommended improvement actions below are reported in original business units for implementation.
    </div>
    """,
    unsafe_allow_html=True,
)

if targets_df.empty:
    st.error("No precomputed MOLP target data is available. Check outputs/team_ccr/molp_targets.csv.")
    st.stop()

baseline = build_baseline_potential_table(master_df, targets_df)
scenario_summary = build_scenario_potential_summary(master_df, targets_df)

st.subheader("Baseline Development Potential")
st.markdown(
    """
    <div class="action-box">
    <b>Baseline definition:</b> among CCR-inefficient suppliers, higher CCR efficiency means smaller frontier gap and therefore stronger baseline development potential.
    This is not a supplier replacement ranking.
    </div>
    """,
    unsafe_allow_html=True,
)

if baseline.empty:
    st.info("No CCR-inefficient suppliers were found.")
else:
    chart_df = baseline.copy()
    chart_df["Frontier gap"] = pd.to_numeric(chart_df["Frontier gap"], errors="coerce")
    frontier_chart = px.bar(
        chart_df.sort_values("Frontier gap", ascending=False),
        x="Frontier gap",
        y="Supplier",
        orientation="h",
        text="Frontier gap",
        hover_data=["CCR efficiency", "Mean theta", "Portfolio status"],
        title="Baseline potential: smaller frontier gap means closer to the efficient frontier",
    )
    frontier_chart.update_traces(texttemplate="%{text:.3f}", textposition="outside", marker_color="#2563eb")
    frontier_chart.update_layout(height=360, margin=dict(l=10, r=25, t=45, b=10), xaxis_title="Frontier gap = 1 - CCR efficiency", yaxis_title="")
    left, right = st.columns([1.0, 1.1], gap="large")
    with left:
        st.plotly_chart(frontier_chart, width="stretch")
    with right:
        display = baseline.copy()
        for col in ["CCR efficiency", "Frontier gap", "Mean theta", "Product quality", "Customer service overlay"]:
            display[col] = pd.to_numeric(display[col], errors="coerce").map(lambda x: "—" if pd.isna(x) else f"{x:.3f}")
        st.dataframe(display, width="stretch", hide_index=True)

st.subheader("Scenario-Specific Potential")
st.markdown(
    """
    <div class="action-box">
    <b>Scenario definition:</b> under each scenario, the most potential suppliers are the CCR-inefficient suppliers with the lowest theta; CCR efficiency is used as the tie-breaker.
    The biggest gap is selected using normalised gap size, then reported in original units.
    </div>
    """,
    unsafe_allow_html=True,
)

story_tab, drill_tab, live_tab, method_tab = st.tabs(
    ["Scenario story", "Selected-supplier drill-down", "Live MOLP", "Method notes"]
)

with story_tab:
    scenario_name = st.selectbox("Scenario to interpret", list(SCENARIO_LABELS.keys()), key="story_scenario")
    selected_scenario = SCENARIO_LABELS[scenario_name]
    selected_label = scenario_label(selected_scenario)
    potential_df = build_scenario_potential_table(master_df, targets_df, selected_scenario)

    if potential_df.empty:
        st.info("No scenario-potential table could be built for this scenario.")
    else:
        lead = potential_df.iloc[0]
        st.markdown(
            f"""
            <div class="action-box">
            <b>{selected_label}: immediate management read-out</b><br>
            Supplier <b>{lead['Supplier']}</b> has the strongest development potential under this scenario
            because it has the lowest theta among CCR-inefficient suppliers
            (<b>{float(lead['Theta']):.3f}</b>) and CCR efficiency of <b>{float(lead['CCR efficiency']):.3f}</b>.
            The first capability gap to discuss is <b>{lead['Biggest improvement gap']}</b>:
            <b>{float(lead['Biggest gap real']):.3f} {lead['Biggest gap unit']}</b>.
            </div>
            """,
            unsafe_allow_html=True,
        )

        top_cards = st.columns(3)
        for idx, (_, row) in enumerate(potential_df.head(3).iterrows()):
            with top_cards[idx]:
                st.markdown(
                    f"""
                    <div class="flow-card">
                    <b>Rank {int(row['Scenario potential rank'])}: Supplier {row['Supplier']}</b><br>
                    <span>Theta: {float(row['Theta']):.3f}</span><br>
                    <span>CCR: {float(row['CCR efficiency']):.3f}</span><br>
                    <span>Focus: {row['Biggest improvement gap']} ({float(row['Biggest gap real']):.3f} {row['Biggest gap unit']})</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        potential_chart_df = potential_df.copy()
        potential_chart_df["Potential label"] = potential_chart_df["Top potential"].map({True: "Top 3 potential", False: "Other development candidate"})
        theta_chart = px.scatter(
            potential_chart_df,
            x="Theta",
            y="CCR efficiency",
            color="Potential label",
            size="Biggest gap normalised",
            text="Supplier",
            hover_data=["Biggest improvement gap", "Biggest gap real", "Biggest gap unit", "Frontier gap"],
            title=f"{selected_label}: potential map, lower theta and higher CCR are better",
        )
        theta_chart.update_traces(textposition="top center")
        theta_chart.update_layout(height=420, margin=dict(l=10, r=20, t=45, b=10))

        norm_cols = {
            "norm_price_improvement": "Price",
            "norm_late_improvement": "Late delivery",
            "norm_error_improvement": "Shipping errors",
            "norm_lead_improvement": "Lead time",
            "norm_quality_gain": "Product quality",
        }
        lead_norm = pd.DataFrame(
            {
                "Criterion": list(norm_cols.values()),
                "Normalised gap": [float(lead[col]) for col in norm_cols],
            }
        )
        gap_chart = px.bar(
            lead_norm.sort_values("Normalised gap", ascending=True),
            x="Normalised gap",
            y="Criterion",
            orientation="h",
            text="Normalised gap",
            title=f"Supplier {lead['Supplier']}: biggest normalised capability gap",
        )
        gap_chart.update_traces(texttemplate="%{text:.2f}", textposition="outside", marker_color="#2563eb")
        gap_chart.update_layout(height=420, margin=dict(l=10, r=20, t=45, b=10), xaxis_title="Normalised gap", yaxis_title="")

        left, right = st.columns([1.05, 0.95], gap="large")
        with left:
            st.plotly_chart(theta_chart, width="stretch")
        with right:
            st.plotly_chart(gap_chart, width="stretch")

        scenario_display = potential_df.copy()
        for col in ["CCR efficiency", "Frontier gap", "Theta", "Biggest gap real", "Biggest gap normalised"]:
            scenario_display[col] = pd.to_numeric(scenario_display[col], errors="coerce").map(lambda x: "—" if pd.isna(x) else f"{x:.3f}")
        st.dataframe(
            scenario_display[
                [
                    "Scenario potential rank",
                    "Supplier",
                    "Theta",
                    "CCR efficiency",
                    "Frontier gap",
                    "Biggest improvement gap",
                    "Biggest gap real",
                    "Biggest gap unit",
                    "Biggest gap normalised",
                    "Top potential",
                ]
            ],
            width="stretch",
            hide_index=True,
        )

    if not scenario_summary.empty:
        st.markdown("#### Four-scenario shortlist")
        summary = scenario_summary.copy()
        for col in ["Theta", "CCR efficiency", "Frontier gap"]:
            summary[col] = pd.to_numeric(summary[col], errors="coerce").map(lambda x: "—" if pd.isna(x) else f"{x:.3f}")
        st.dataframe(summary, width="stretch", hide_index=True)

with drill_tab:
    st.markdown(
        """
        <div class="muted-box">
        Use this tab when a stakeholder asks what exactly changes for one supplier. It filters precomputed MOLP outputs and keeps MCDA/DEA fixed.
        </div>
        """,
        unsafe_allow_html=True,
    )
    if not inefficient:
        st.info("No CCR-inefficient suppliers are available for drill-down.")
    else:
        c1, c2 = st.columns([0.5, 0.5])
        with c1:
            supplier = st.selectbox("Development candidate", inefficient, index=inefficient.index("L") if "L" in inefficient else 0)
        with c2:
            scenario_name = st.selectbox("Precomputed scenario", list(SCENARIO_LABELS.keys()), key="drill_scenario")
            scenario = SCENARIO_LABELS[scenario_name]

        st.markdown(
            f"""
            <div class="action-box">
            <b>Supplier {supplier} under {scenario_label(scenario)}</b><br>
            Read this as a supplier-development target and benchmark discussion, not as replacement or order-allocation advice.
            </div>
            """,
            unsafe_allow_html=True,
        )
        left, right = st.columns([1.0, 1.0], gap="large")
        with left:
            table = build_scenario_table(targets_df, supplier)
            st.dataframe(table, width="stretch", hide_index=True)
        with right:
            improvement = build_improvement_table(master_df, targets_df, supplier, scenario)
            if improvement.empty:
                st.info("No improvement table is available for this supplier/scenario.")
            else:
                shown = improvement[~improvement["Metric"].isin(["Customer Service Overlay", "Purchase"])].copy()
                shown["Improvement %"] = shown["Improvement %"].map(lambda x: "—" if pd.isna(x) else f"{x:.1f}%")
                shown["Normalised room"] = shown["Normalised room"].map(lambda x: "—" if pd.isna(x) else f"{x:.1f}")
                st.dataframe(shown, width="stretch", hide_index=True)

        chart_left, chart_right = st.columns([1.0, 1.0], gap="large")
        with chart_left:
            target_chart = scenario_target_bar(master_df, targets_df, supplier, scenario)
            if target_chart is None:
                st.info("No selected-scenario target chart can be drawn because current-target data is unavailable.")
            else:
                st.plotly_chart(target_chart, width="stretch")
        with chart_right:
            radar = current_vs_target_radar(master_df, targets_df, supplier, scenario)
            if radar is None:
                st.info("No radar can be drawn because current-target data is unavailable.")
            else:
                st.plotly_chart(radar, width="stretch")

with live_tab:
    if not live_available:
        st.info("Live custom MOLP unavailable in this environment. The stakeholder page uses precomputed scenario outputs.")
        st.caption(live_message)
    else:
        st.success(live_message)
        supplier = st.selectbox("Live development candidate", inefficient, key="live_supplier")
        st.caption("Set criterion weights. They are normalised to sum to 1 before solving the post-DEA MOLP model.")
        cols = st.columns(5)
        raw_weights = {
            "price": cols[0].slider("Price", 0.0, 1.0, 0.20, 0.05),
            "late": cols[1].slider("Late delivery", 0.0, 1.0, 0.20, 0.05),
            "error": cols[2].slider("Shipping error", 0.0, 1.0, 0.20, 0.05),
            "lead": cols[3].slider("Lead time", 0.0, 1.0, 0.20, 0.05),
            "quality": cols[4].slider("Product quality", 0.0, 1.0, 0.20, 0.05),
        }
        weights = normalise_weights(raw_weights)
        if st.button("Run live MOLP", type="primary"):
            with st.spinner("Running live post-DEA MOLP..."):
                dea_df = outputs.get("dea_team_ccr_efficiency", pd.DataFrame())
                if dea_df.empty:
                    dea_df = app_data["inputs"].get("dea_efficiency", pd.DataFrame())
                result = run_live_molp(
                    molp_inputs_df=outputs.get("supplier_molp_inputs", pd.DataFrame()),
                    dea_df=dea_df,
                    supplier=supplier,
                    weights=weights,
                )
            if not result.ok:
                st.error(result.message)
            else:
                st.success(result.message)
                st.dataframe(result.targets, width="stretch", hide_index=True)
                st.dataframe(result.peers, width="stretch", hide_index=True)

with method_tab:
    st.markdown(
        """
        - MCDA scores are imported as strategic attractiveness inputs.
        - DEA CCR efficiency is imported as the efficiency diagnosis and benchmark frontier.
        - MOLP provides scenario-specific supplier-development targets.
        - Scenario potential ranks inefficient suppliers by theta, with CCR efficiency as tie-breaker.
        - Biggest gaps are selected using normalised gap size, then reported in original units.
        - Customer service is a strategic overlay, not a MOLP-optimised target in this app.
        - Peer weights are benchmark intensities, not probabilities and not order-allocation shares.
        - Purchase is commercial scale/context, not a direct improvement action.
        """
    )
    if payoff_df.empty:
        st.info("No payoff table available.")
    else:
        st.dataframe(payoff_df, width="stretch", hide_index=True)
