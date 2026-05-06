from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from .transforms import SCENARIO_NAMES, build_current_target_long


def portfolio_matrix_3d(master_df: pd.DataFrame) -> go.Figure:
    if master_df.empty:
        return go.Figure()
    df = master_df.copy()
    fig = px.scatter_3d(
        df,
        x="ccr_efficiency",
        y="product_quality_score",
        z="customer_service_score",
        text="supplier",
        color="portfolio_status",
        hover_data={
            "supplier": True,
            "ccr_efficiency": ":.3f",
            "product_quality_score": ":.3f",
            "customer_service_score": ":.3f",
            "avg_unit_price": ":.2f" if "avg_unit_price" in df.columns else False,
            "late_delivery_pct": ":.1f" if "late_delivery_pct" in df.columns else False,
            "portfolio_status": True,
        },
    )
    palette = {
        "Strategic partner": "#15803d",
        "Development candidate": "#d97706",
        "Selective development": "#f59e0b",
        "Tactical efficient": "#64748b",
        "Deprioritise / renegotiate": "#dc2626",
    }
    for trace in fig.data:
        if trace.name in palette:
            trace.marker.color = palette[trace.name]
    fig.update_traces(marker=dict(size=8, line=dict(width=1.2, color="#222")), textposition="top center")

    # Floor projections make the 3D position readable.
    projection = df.copy()
    projection["customer_service_score"] = 0
    fig.add_trace(
        go.Scatter3d(
            x=projection["ccr_efficiency"],
            y=projection["product_quality_score"],
            z=projection["customer_service_score"],
            mode="markers+text",
            text=projection["supplier"],
            marker=dict(size=4, color="rgba(60,60,60,0.25)"),
            textfont=dict(color="rgba(60,60,60,0.45)", size=9),
            name="floor projection",
            hoverinfo="skip",
            showlegend=False,
        )
    )

    # Explicit zero/reference axes.
    axis_style = dict(color="#111", width=6)
    fig.add_trace(go.Scatter3d(x=[0, 1.05], y=[0, 0], z=[0, 0], mode="lines", line=axis_style, name="DEA zero axis", hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter3d(x=[0, 0], y=[0, 1.05], z=[0, 0], mode="lines", line=axis_style, name="PQ zero axis", hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter3d(x=[0, 0], y=[0, 0], z=[0, 1.05], mode="lines", line=axis_style, name="CS zero axis", hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter3d(x=[0], y=[0], z=[0], mode="markers+text", text=["origin"], marker=dict(size=4, color="#111"), name="origin", hoverinfo="skip", showlegend=False))

    fig.update_layout(
        height=590,
        margin=dict(l=0, r=0, t=30, b=0),
        legend_title="Portfolio status",
        scene=dict(
            xaxis=dict(title="DEA CCR efficiency", range=[0, 1.05], showbackground=True, backgroundcolor="rgb(248,248,248)", zeroline=True),
            yaxis=dict(title="Product quality score", range=[0, 1.05], showbackground=True, backgroundcolor="rgb(248,248,248)", zeroline=True),
            zaxis=dict(title="Customer service score", range=[0, 1.05], showbackground=True, backgroundcolor="rgb(248,248,248)", zeroline=True),
            camera=dict(eye=dict(x=1.75, y=1.35, z=1.2)),
        ),
    )
    return fig


def current_vs_target_radar(master_df: pd.DataFrame, targets_df: pd.DataFrame, supplier: str, scenario: str) -> go.Figure | None:
    long_df = build_current_target_long(master_df, targets_df, supplier, scenario)
    if long_df.empty:
        return None
    required = {"Metric", "Score", "Current raw", "Target raw", "Current score", "Target score", "Direction", "Method role", "State"}
    if missing := required.difference(long_df.columns):
        raise ValueError(f"Radar chart data is missing required columns: {sorted(missing)}")
    fig = go.Figure()
    metric_order = ["Price", "Late Delivery", "Shipping Error", "Lead Time", "Product Quality", "Customer Service Overlay", "Purchase"]
    for state, group in long_df.groupby("State"):
        group = group.set_index("Metric").reindex(metric_order).reset_index()
        group = group.dropna(subset=["Metric"])
        if group.empty:
            continue
        values = group["Score"].fillna(0).tolist()
        metrics = group["Metric"].tolist()
        hover = [
            (
                f"<b>{m}</b><br>{role}<br>Raw current: {cr:.3g}<br>Raw target/context: {tr:.3g}"
                f"<br>Normalised current: {cs:.1f}/100<br>Normalised target/context: {ts:.1f}/100<br>{direction}"
            )
            for m, role, cr, tr, cs, ts, direction in zip(
                group["Metric"],
                group["Method role"],
                group["Current raw"],
                group["Target raw"],
                group["Current score"].fillna(0),
                group["Target score"].fillna(0),
                group["Direction"],
            )
        ]
        fig.add_trace(
            go.Scatterpolar(
                r=values + [values[0]],
                theta=metrics + [metrics[0]],
                fill="toself",
                name=state,
                customdata=hover + [hover[0]],
                hovertemplate="%{customdata}<extra></extra>",
            )
        )
    fig.update_layout(
        height=470,
        margin=dict(l=25, r=25, t=30, b=25),
        polar=dict(radialaxis=dict(visible=True, range=[0, 100], tickfont=dict(size=10))),
        legend_title="",
    )
    return fig if fig.data else None


def current_vs_target_bar(master_df: pd.DataFrame, targets_df: pd.DataFrame, supplier: str, scenario: str) -> go.Figure | None:
    long_df = build_current_target_long(master_df, targets_df, supplier, scenario)
    if long_df.empty:
        return None
    fig = px.bar(long_df, x="Metric", y="Score", color="State", barmode="group", hover_data=["Current raw", "Target raw", "Direction"])
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=30, b=10), yaxis_title="Normalised score, higher is better", xaxis_title="", legend_title="")
    return fig


def peer_weights_bar(peer_weights_df: pd.DataFrame, supplier: str, scenario: str) -> go.Figure:
    if peer_weights_df is None or peer_weights_df.empty:
        return go.Figure()
    df = peer_weights_df[(peer_weights_df["supplier"] == supplier) & (peer_weights_df["scenario"] == scenario)].copy()
    if df.empty:
        return go.Figure()
    df = df.sort_values("lambda_value", ascending=False)
    fig = px.bar(df, x="peer_supplier", y="lambda_value", text="lambda_value")
    fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
    fig.update_layout(height=300, margin=dict(l=10, r=10, t=25, b=10), xaxis_title="Benchmark peer", yaxis_title="Lambda weight", showlegend=False, yaxis_range=[0, max(1.0, df["lambda_value"].max() * 1.15)])
    return fig


def theta_by_scenario(targets_df: pd.DataFrame, supplier: str) -> go.Figure:
    if targets_df is None or targets_df.empty:
        return go.Figure()
    df = targets_df[targets_df["supplier"] == supplier].copy()
    if df.empty:
        return go.Figure()
    df["Scenario"] = df["scenario"].map(SCENARIO_NAMES).fillna(df["scenario"])
    fig = px.bar(df, x="Scenario", y="theta", text="theta")
    fig.update_traces(texttemplate="%{text:.3f}", textposition="outside")
    fig.update_layout(height=330, margin=dict(l=10, r=10, t=25, b=10), xaxis_title="", yaxis_title="Theta / deviation score", showlegend=False)
    return fig


def scenario_target_bar(master_df: pd.DataFrame, targets_df: pd.DataFrame, supplier: str, scenario: str) -> go.Figure | None:
    return current_vs_target_bar(master_df, targets_df, supplier, scenario)


def target_range_box(param_runs_df: pd.DataFrame, supplier: str, scenario: str) -> go.Figure:
    if param_runs_df is None or param_runs_df.empty:
        return go.Figure()
    df = param_runs_df[(param_runs_df["supplier"] == supplier) & (param_runs_df["scenario"] == scenario)].copy()
    if df.empty:
        return go.Figure()
    metric_cols = {
        "target_price": "Price",
        "target_late_pct": "Late Delivery",
        "target_error_pct": "Shipping Error",
        "target_lead_days": "Lead Time",
        "target_quality_score": "Product Quality",
        "target_purchase": "Purchase",
    }
    existing = [c for c in metric_cols if c in df.columns]
    long = df[existing].rename(columns=metric_cols).melt(var_name="Metric", value_name="Target")
    fig = px.box(long, x="Metric", y="Target", points="all")
    fig.update_layout(height=360, margin=dict(l=10, r=10, t=25, b=10), xaxis_title="", yaxis_title="Target value")
    return fig


def parameter_impact_bar(param_runs_df: pd.DataFrame, supplier: str, scenario: str) -> go.Figure:
    if param_runs_df is None or param_runs_df.empty or "perturbed_parameter" not in param_runs_df.columns:
        return go.Figure()
    df = param_runs_df[(param_runs_df["supplier"] == supplier) & (param_runs_df["scenario"] == scenario)].copy()
    if df.empty:
        return go.Figure()
    impact = df.groupby("perturbed_parameter", as_index=False)["theta"].agg(lambda x: x.max() - x.min())
    impact = impact.rename(columns={"theta": "theta_range"}).sort_values("theta_range", ascending=True)
    fig = px.bar(impact, x="theta_range", y="perturbed_parameter", orientation="h", text="theta_range")
    fig.update_traces(texttemplate="%{text:.3f}", textposition="outside")
    fig.update_layout(height=360, margin=dict(l=10, r=10, t=25, b=10), xaxis_title="Theta range", yaxis_title="Perturbed parameter", showlegend=False)
    return fig
