from __future__ import annotations

from pathlib import Path

import streamlit as st

from .load_data import load_app_data, SCENARIO_LABELS
from .recommendation_tiers import add_recommendation_columns

ROOT_DIR = "."
OUTPUT_SUBDIR = "outputs/team_ccr"


@st.cache_data(show_spinner=False)
def cached_load_app_data(root_dir: str = ROOT_DIR, output_subdir: str = OUTPUT_SUBDIR) -> dict:
    return load_app_data(root_dir=Path(root_dir), output_subdir=output_subdir)


def require_data() -> dict:
    app_data = cached_load_app_data()
    if app_data["master"].empty:
        st.error(
            "No supplier data could be loaded. Run the app from the project root, or place the required CSV files beside app.py for testing."
        )
        st.stop()
    app_data = dict(app_data)
    master = app_data["master"].copy()
    if "supplier" in master.columns:
        missing_recommendation_cols = {
            "recommendation_tier",
            "management_note",
            "recommended_action",
            "recommendation_order",
            "supplier_recommendation_order",
        }.difference(master.columns)
        if missing_recommendation_cols:
            master = add_recommendation_columns(master)
        if "supplier_recommendation_order" in master.columns:
            master = master.sort_values(["supplier_recommendation_order", "supplier"]).reset_index(drop=True)
        app_data["master"] = master
    diagnostics = app_data.get("diagnostics", [])
    if diagnostics:
        with st.expander("Data validation messages", expanded=True):
            st.warning("Some expected app inputs are missing columns or files. Pages may be incomplete until these are fixed.")
            for message in diagnostics:
                st.markdown(f"- {message}")
    return app_data


def supplier_selector(master_df, label: str = "Supplier", default: str | None = None) -> str:
    suppliers = sorted(master_df["supplier"].dropna().astype(str).unique().tolist())
    if not suppliers:
        return ""
    index = suppliers.index(default) if default in suppliers else 0
    return st.sidebar.selectbox(label, suppliers, index=index)


def scenario_selector(label: str = "Scenario") -> str:
    chosen = st.sidebar.selectbox(label, list(SCENARIO_LABELS.keys()))
    return SCENARIO_LABELS[chosen]
