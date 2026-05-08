from __future__ import annotations

import pandas as pd
import streamlit as st


PLOTLY_CONFIG = {"displaylogo": False, "responsive": True}


def apply_global_style() -> None:
    st.markdown(
        """
        <style>
        .block-container {padding-top: 1.15rem; padding-bottom: 2rem;}
        div[data-testid="stMetric"] {
            background-color: #fbfbfb;
            border: 1px solid #dddddd;
            padding: 0.80rem;
            border-radius: 0.70rem;
        }
        div[data-testid="stMetricLabel"] {font-size: 0.78rem; color: #555;}
        div[data-testid="stMetricValue"] {font-size: 1.35rem; font-weight: 700;}
        .hero-box {
            background: linear-gradient(90deg, #f2f6ff, #fafafa);
            border: 1px solid #d6e2ff;
            border-radius: 14px;
            padding: 1.05rem 1.20rem;
            margin: 0.75rem 0 1rem 0;
        }
        .hero-title {font-size: 1.25rem; font-weight: 750; color: #1d3557; margin-bottom: 0.2rem;}
        .hero-subtitle {font-size: 0.94rem; color: #334155;}
        .flow-card {
            min-height: 106px;
            background: #ffffff;
            border: 1px solid #dddddd;
            border-radius: 12px;
            padding: 0.95rem;
            box-shadow: 0 1px 2px rgba(0,0,0,0.04);
            margin-bottom: 0.7rem;
        }
        .flow-card b {font-size: 1.0rem; color: #1f2937;}
        .flow-card span {font-size: 0.86rem; color: #4b5563;}
        .guide-box {
            background: #f8fafc;
            border-left: 5px solid #2563eb;
            border-radius: 10px;
            padding: 0.85rem 1rem;
            margin: 0.6rem 0 1rem 0;
            color: #1f2937;
        }
        .guide-box strong {color: #1d4ed8;}
        .decision-box {
            background: #f0fdf4;
            border-left: 5px solid #16a34a;
            border-radius: 10px;
            padding: 0.85rem 1rem;
            margin: 0.6rem 0 1rem 0;
        }
        .warning-box {
            background: #fff7ed;
            border-left: 5px solid #ea580c;
            border-radius: 10px;
            padding: 0.85rem 1rem;
            margin: 0.6rem 0 1rem 0;
        }
        .action-box {
            background: #eff6ff;
            border-left: 6px solid #2563eb;
            border-radius: 10px;
            padding: 1rem 1.1rem;
            margin: 0.7rem 0 1rem 0;
            color: #172554;
        }
        .action-box b {font-size: 1.08rem;}
        .status-legend {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.45rem;
            margin: 0.5rem 0 1rem 0;
        }
        .legend-item {
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 0.55rem 0.65rem;
            background: #ffffff;
            font-size: 0.88rem;
        }
        .badge {
            display: inline-block;
            border-radius: 999px;
            padding: 0.25rem 0.55rem;
            margin: 0.15rem 0.25rem 0.15rem 0;
            font-size: 0.82rem;
            font-weight: 750;
        }
        .badge-green {background: #dcfce7; color: #166534;}
        .badge-amber {background: #fef3c7; color: #92400e;}
        .badge-red {background: #fee2e2; color: #991b1b;}
        .badge-blue {background: #dbeafe; color: #1e40af;}
        .badge-grey {background: #f1f5f9; color: #475569;}
        .badge-purple {background: #ede9fe; color: #5b21b6;}
        .muted-box {
            background: #fafafa;
            border: 1px solid #e5e7eb;
            border-radius: 10px;
            padding: 0.80rem 0.95rem;
            margin: 0.5rem 0;
            color: #4b5563;
            font-size: 0.92rem;
        }
        .section-label {
            font-weight: 750;
            font-size: 0.98rem;
            color: #111827;
            margin-top: 0.4rem;
            margin-bottom: 0.3rem;
        }
        .priority-high {background-color: #fee2e2; color: #991b1b; font-weight: 700;}
        .priority-medium {background-color: #fef3c7; color: #92400e; font-weight: 700;}
        .priority-low {background-color: #dcfce7; color: #166534; font-weight: 700;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def format_number(value, decimals: int = 3) -> str:
    if pd.isna(value):
        return "—"
    try:
        return f"{float(value):,.{decimals}f}"
    except Exception:
        return str(value)


def format_money(value, decimals: int = 2) -> str:
    if pd.isna(value):
        return "—"
    return f"${float(value):,.{decimals}f}"


def format_pct(value, decimals: int = 1) -> str:
    if pd.isna(value):
        return "—"
    return f"{float(value):.{decimals}f}%"


def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def render_download_button(label: str, df: pd.DataFrame, file_name: str) -> None:
    st.download_button(
        label=label,
        data=dataframe_to_csv_bytes(df),
        file_name=file_name,
        mime="text/csv",
        disabled=df.empty,
    )


def scenario_label(scenario: str) -> str:
    mapping = {
        "balanced_improvement": "Balanced",
        "cost_led_development": "Cost-led",
        "delivery_reliability_led": "Delivery-led",
        "product_quality_led": "Quality-led",
        "custom_live": "Custom live",
    }
    return mapping.get(scenario, str(scenario).replace("_", " ").title())


def render_plotly_chart(fig, *, key: str | None = None) -> None:
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG, key=key)
