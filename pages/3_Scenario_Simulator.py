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
    build_balanced_base_case_table,
    build_improvement_table,
    build_scenario_interpretation_table,
    build_scenario_table,
    build_supplier_burden_table,
    inefficient_suppliers,
    SCENARIO_WEIGHTS,
)

st.set_page_config(page_title="Scenario Interpretation", page_icon="⚙️", layout="wide")
apply_global_style()

app_data = require_data()
master_df = app_data["master"]
outputs = app_data["outputs"]
targets_df = outputs.get("molp_targets", pd.DataFrame())
payoff_df = outputs.get("molp_payoff_table", pd.DataFrame())
peer_weights_df = outputs.get("molp_peer_weights", pd.DataFrame())

st.sidebar.header("Scenario controls")
inefficient = inefficient_suppliers(master_df)
live_available, live_message = check_live_optimizer_available()
st.sidebar.caption("Precomputed scenarios are the default. Live MOLP is optional and only appears when the optimiser stack is available.")

st.title("3. Scenario Interpretation")
st.markdown(
    """
    <div class="guide-box">
    <strong>Purpose.</strong> This page translates precomputed MOLP scenarios into supplier-development priorities.
    MCDA and DEA remain upstream inputs; MOLP provides scenario-specific targets. Customer service is a strategic overlay, peer weights are benchmark intensities, and purchase is commercial scale/context.
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="muted-box">
    <b>Scenario meanings:</b>
    <span class="badge badge-blue">Balanced</span> neutral compromise baseline
    <span class="badge badge-grey">Cost-led</span> emphasises unit-price improvement
    <span class="badge badge-amber">Delivery-led</span> emphasises late delivery, errors, and lead time
    <span class="badge badge-green">Quality-led</span> emphasises product-quality gain.
    </div>
    """,
    unsafe_allow_html=True,
)

if targets_df.empty:
    st.error("No precomputed MOLP target data is available. Check outputs/team_ccr/molp_targets.csv.")
    st.stop()

base_case = build_balanced_base_case_table(master_df, targets_df, peer_weights_df)
scenario_summary = build_scenario_interpretation_table(master_df, targets_df, peer_weights_df)

st.subheader("Base Case: Balanced Supplier-Development Needs")
st.markdown(
    """
    <div class="action-box">
    <b>Question answered:</b> among all CCR-inefficient suppliers under the Balanced scenario, what should each supplier improve, and by how much?
    These are development needs and capability gaps, not replacement labels.
    </div>
    """,
    unsafe_allow_html=True,
)

if base_case.empty:
    st.info("No CCR-inefficient suppliers with Balanced MOLP targets were found.")
else:
    display = base_case.copy()
    numeric_formats = {
        "Price improvement": "{:.3f}",
        "Late-delivery improvement": "{:.3f}",
        "Shipping-error improvement": "{:.3f}",
        "Lead-time improvement": "{:.3f}",
        "Product-quality gain": "{:.3f}",
        "Weighted normalised burden": "{:.2f}",
        "Theta": "{:.3f}",
    }
    for col, fmt in numeric_formats.items():
        if col in display.columns:
            display[col] = pd.to_numeric(display[col], errors="coerce").map(lambda x, f=fmt: "—" if pd.isna(x) else f.format(x))
    st.dataframe(display, width="stretch", hide_index=True)
    st.caption("Purchase is excluded from this action table because it is commercial scale/context, not a direct supplier-controlled improvement action.")

st.subheader("Scenario Interpretation Across Inefficient Suppliers")
st.markdown(
    """
    <div class="action-box">
    <b>Question answered:</b> choose a predefined scenario and quickly see which inefficient supplier carries the largest weighted normalised improvement burden, which criterion drives it, and what management should do next.
    </div>
    """,
    unsafe_allow_html=True,
)

if scenario_summary.empty:
    st.info("No scenario interpretation table could be built from the precomputed targets.")
else:
    scenario_tab, drill_tab, live_tab, method_tab = st.tabs(
        ["Scenario story", "Selected-supplier drill-down", "Live MOLP", "Method notes"]
    )

    with scenario_tab:
        scenario_name = st.selectbox("Scenario to interpret", list(SCENARIO_LABELS.keys()), key="story_scenario")
        selected_scenario = SCENARIO_LABELS[scenario_name]
        selected_label = scenario_label(selected_scenario)
        burden_df = build_supplier_burden_table(master_df, targets_df, peer_weights_df, selected_scenario)

        if burden_df.empty:
            st.info("No supplier burden table could be built for this scenario.")
        else:
            lead = burden_df.iloc[0]
            st.markdown(
                f"""
                <div class="action-box">
                <b>{selected_label}: immediate management read-out</b><br>
                Supplier <b>{lead['Supplier']}</b> carries the largest weighted normalised development burden
                (<b>{float(lead['Weighted normalised improvement burden']):.2f}</b>).
                The main improvement priority is <b>{lead['Driving criterion']}</b>.
                Use benchmark peer <b>{lead['Leading benchmark peer']}</b> as a process-learning reference.
                <br><br>{lead['Managerial interpretation']}
                </div>
                """,
                unsafe_allow_html=True,
            )

            chart_df = burden_df.copy()
            chart_df["Weighted normalised improvement burden"] = pd.to_numeric(
                chart_df["Weighted normalised improvement burden"], errors="coerce"
            )
            burden_chart = px.bar(
                chart_df.sort_values("Weighted normalised improvement burden", ascending=True),
                x="Weighted normalised improvement burden",
                y="Supplier",
                color="Driving criterion",
                orientation="h",
                text="Weighted normalised improvement burden",
                hover_data=["Driving criterion", "Leading benchmark peer"],
                title=f"{selected_label}: development burden by supplier",
            )
            burden_chart.update_traces(texttemplate="%{text:.2f}", textposition="outside")
            burden_chart.update_layout(height=390, margin=dict(l=10, r=20, t=45, b=10), xaxis_title="Weighted normalised improvement burden", yaxis_title="")

            criterion_df = build_improvement_table(master_df, targets_df, str(lead["Supplier"]), selected_scenario)
            weights = SCENARIO_WEIGHTS.get(selected_scenario, {})
            criterion_df = criterion_df[criterion_df["Metric"].isin(weights)].copy()
            criterion_df["Scenario weight"] = criterion_df["Metric"].map(weights).fillna(0.0)
            criterion_df["Weighted contribution"] = criterion_df["Scenario weight"] * pd.to_numeric(
                criterion_df["Normalised room"], errors="coerce"
            ).clip(lower=0).fillna(0.0)
            criterion_chart = px.bar(
                criterion_df.sort_values("Weighted contribution", ascending=True),
                x="Weighted contribution",
                y="Metric",
                orientation="h",
                text="Weighted contribution",
                title=f"Supplier {lead['Supplier']}: what drives the burden",
                hover_data=["Scenario weight", "Normalised room", "Direction"],
            )
            criterion_chart.update_traces(texttemplate="%{text:.2f}", textposition="outside", marker_color="#2563eb")
            criterion_chart.update_layout(height=390, margin=dict(l=10, r=20, t=45, b=10), xaxis_title="Weighted contribution", yaxis_title="")

            left, right = st.columns([1.1, 0.9], gap="large")
            with left:
                st.plotly_chart(burden_chart, width="stretch")
            with right:
                st.plotly_chart(criterion_chart, width="stretch")

            scenario_display = burden_df.copy()
            for col in ["Weighted normalised improvement burden", "Driving-criterion contribution"]:
                scenario_display[col] = pd.to_numeric(scenario_display[col], errors="coerce").map(lambda x: "—" if pd.isna(x) else f"{x:.2f}")
            st.dataframe(scenario_display, width="stretch", hide_index=True)

        st.sidebar.markdown("#### Four-scenario summary")
        cards = st.sidebar.columns(4)
        for idx, row in scenario_summary.iterrows():
            with cards[idx % 4]:
                st.sidebar.markdown(
                    f"""
                    <div class="flow-card">
                    <b>{row['Scenario']}</b><br>
                    <span class="badge badge-blue">Supplier {row['Supplier with largest burden']}</span><br>
                    <span>Development burden: {float(row['Weighted normalised improvement burden']):.2f}</span><br>
                    <span>Priority: {row['Driving criterion']}</span><br>
                    <span>Benchmark peer: {row['Leading benchmark peer']}</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    with drill_tab:
        st.markdown(
            """
            <div class="muted-box">
            Use this tab when a stakeholder asks, "what exactly changes for this supplier?" It filters precomputed MOLP outputs and keeps MCDA/DEA fixed.
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
            - Customer service is a strategic overlay, not a MOLP-optimised target in this app.
            - Peer weights are benchmark intensities, not probabilities and not order-allocation shares.
            - Purchase is commercial scale/context, not a direct improvement action.
            """
        )
        if payoff_df.empty:
            st.info("No payoff table available.")
        else:
            st.dataframe(payoff_df, width="stretch", hide_index=True)

