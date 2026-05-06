from __future__ import annotations

import pandas as pd

SCENARIO_DISPLAY_ORDER = [
    "balanced_improvement",
    "cost_led_development",
    "delivery_reliability_led",
    "product_quality_led",
]

SCENARIO_NAMES = {
    "balanced_improvement": "Balanced",
    "cost_led_development": "Cost-led",
    "delivery_reliability_led": "Delivery-led",
    "product_quality_led": "Quality-led",
    "custom_live": "Custom live",
}

LOWER_IS_BETTER = {
    "Price": ("avg_unit_price", "target_price"),
    "Late Delivery": ("late_delivery_pct", "target_late_pct"),
    "Shipping Error": ("shipping_error_pct", "target_error_pct"),
    "Lead Time": ("lead_time_days", "target_lead_days"),
}
HIGHER_IS_BETTER = {
    "Product Quality": ("product_quality_score", "target_quality_score"),
    "Customer Service Overlay": ("customer_service_score", None),
    "Purchase": ("total_purchase", "target_purchase"),
}


def normalise_higher_is_better(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    mn = values.min(skipna=True)
    mx = values.max(skipna=True)
    if pd.isna(mn) or pd.isna(mx) or mx == mn:
        return pd.Series([50.0] * len(values), index=values.index)
    return 100 * (values - mn) / (mx - mn)


def normalise_lower_is_better(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    mn = values.min(skipna=True)
    mx = values.max(skipna=True)
    if pd.isna(mn) or pd.isna(mx) or mx == mn:
        return pd.Series([50.0] * len(values), index=values.index)
    return 100 * (mx - values) / (mx - mn)


def get_selected_target(targets_df: pd.DataFrame, supplier: str, scenario: str) -> pd.Series | None:
    if targets_df is None or targets_df.empty:
        return None
    rows = targets_df[(targets_df["supplier"] == supplier) & (targets_df["scenario"] == scenario)]
    if rows.empty:
        return None
    return rows.iloc[0]


def _target_value(current: pd.Series, target: pd.Series | None, current_col: str, target_col: str | None):
    if target is None or target_col is None:
        return current.get(current_col)
    return target.get(target_col)


def build_current_target_wide(master_df: pd.DataFrame, targets_df: pd.DataFrame, supplier: str, scenario: str) -> pd.DataFrame:
    rows = master_df[master_df["supplier"] == supplier]
    if rows.empty:
        return pd.DataFrame()
    current = rows.iloc[0]
    target = get_selected_target(targets_df, supplier, scenario)

    records = []
    for metric, (current_col, target_col) in LOWER_IS_BETTER.items():
        records.append({
            "Metric": metric,
            "Direction": "Lower is better",
            "Current raw": current.get(current_col),
            "Target raw": _target_value(current, target, current_col, target_col),
            "Method role": "MOLP criterion",
        })
    for metric, (current_col, target_col) in HIGHER_IS_BETTER.items():
        records.append({
            "Metric": metric,
            "Direction": "Higher is better",
            "Current raw": current.get(current_col),
            "Target raw": _target_value(current, target, current_col, target_col),
            "Method role": "Strategic overlay; not MOLP-optimised" if target_col is None else (
                "Commercial scale/context; not a supplier-controlled action" if metric == "Purchase" else "MOLP criterion"
            ),
        })
    raw = pd.DataFrame(records)
    raw["Current raw"] = pd.to_numeric(raw["Current raw"], errors="coerce")
    raw["Target raw"] = pd.to_numeric(raw["Target raw"], errors="coerce")

    current_scores = []
    target_scores = []
    for _, row in raw.iterrows():
        metric = row["Metric"]
        if metric in LOWER_IS_BETTER:
            current_col, target_col = LOWER_IS_BETTER[metric]
            reference = pd.concat(
                [
                    pd.to_numeric(master_df.get(current_col, pd.Series(dtype=float)), errors="coerce"),
                    pd.to_numeric(targets_df.get(target_col, pd.Series(dtype=float)) if targets_df is not None else pd.Series(dtype=float), errors="coerce"),
                    pd.Series([row["Current raw"], row["Target raw"]]),
                ],
                ignore_index=True,
            )
            scores = normalise_lower_is_better(pd.concat([reference, pd.Series([row["Current raw"], row["Target raw"]])], ignore_index=True)).tail(2).reset_index(drop=True)
        else:
            current_col, target_col = HIGHER_IS_BETTER[metric]
            reference = pd.concat(
                [
                    pd.to_numeric(master_df.get(current_col, pd.Series(dtype=float)), errors="coerce"),
                    pd.to_numeric(targets_df.get(target_col, pd.Series(dtype=float)) if (targets_df is not None and target_col is not None) else pd.Series(dtype=float), errors="coerce"),
                    pd.Series([row["Current raw"], row["Target raw"]]),
                ],
                ignore_index=True,
            )
            scores = normalise_higher_is_better(pd.concat([reference, pd.Series([row["Current raw"], row["Target raw"]])], ignore_index=True)).tail(2).reset_index(drop=True)
        current_scores.append(scores.iloc[0])
        target_scores.append(scores.iloc[1])
    raw["Current score"] = current_scores
    raw["Target score"] = target_scores
    raw["Room to improve"] = raw["Target score"] - raw["Current score"]
    return raw


def build_current_target_long(master_df: pd.DataFrame, targets_df: pd.DataFrame, supplier: str, scenario: str) -> pd.DataFrame:
    wide = build_current_target_wide(master_df, targets_df, supplier, scenario)
    if wide.empty:
        return wide
    long = wide.melt(
        id_vars=["Metric", "Direction", "Current raw", "Target raw", "Room to improve", "Method role"],
        value_vars=["Current score", "Target score"],
        var_name="State",
        value_name="Score",
    )
    long["State"] = long["State"].str.replace(" score", "", regex=False)
    long = long.merge(
        wide[["Metric", "Current score", "Target score"]],
        on="Metric",
        how="left",
        validate="many_to_one",
    )
    return long


def build_improvement_table(master_df: pd.DataFrame, targets_df: pd.DataFrame, supplier: str, scenario: str) -> pd.DataFrame:
    wide = build_current_target_wide(master_df, targets_df, supplier, scenario)
    if wide.empty:
        return wide
    rows = []
    for _, r in wide.iterrows():
        current = r["Current raw"]
        target = r["Target raw"]
        if pd.isna(current) or pd.isna(target) or current == 0:
            pct = None
        elif r["Direction"] == "Lower is better":
            pct = 100 * (current - target) / current
        else:
            pct = 100 * (target - current) / current
        room = r["Room to improve"]
        if pd.isna(room) or room < 1:
            priority = "Low"
        elif room >= 45:
            priority = "High"
        elif room >= 20:
            priority = "Medium"
        else:
            priority = "Low"
        rows.append({
            "Metric": r["Metric"],
            "Current": current,
            "Target": target,
            "Improvement %": pct,
            "Normalised room": room,
            "Priority": priority,
            "Direction": r["Direction"],
        })
    return pd.DataFrame(rows)


def build_scenario_table(targets_df: pd.DataFrame, supplier: str) -> pd.DataFrame:
    if targets_df is None or targets_df.empty:
        return pd.DataFrame()
    rows = targets_df[targets_df["supplier"] == supplier].copy()
    if rows.empty:
        return pd.DataFrame()
    rows["scenario_label"] = rows["scenario"].map(SCENARIO_NAMES).fillna(rows["scenario"])
    rows["scenario_sort"] = pd.Categorical(rows["scenario"], categories=SCENARIO_DISPLAY_ORDER, ordered=True)
    rows = rows.sort_values("scenario_sort")
    metric_map = {
        "target_price": "Price",
        "target_late_pct": "Late Delivery",
        "target_error_pct": "Shipping Error",
        "target_lead_days": "Lead Time",
        "target_quality_score": "Product Quality",
        "target_purchase": "Purchase",
        "theta": "Theta",
    }
    table = rows[["scenario_label", *[c for c in metric_map if c in rows.columns]]].rename(columns=metric_map)
    return table.set_index("scenario_label").T.reset_index().rename(columns={"index": "Metric"})


def filter_by_supplier_scenario(df: pd.DataFrame, supplier: str | None = None, scenario: str | None = None) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    if supplier and "supplier" in out.columns:
        out = out[out["supplier"] == supplier]
    if scenario and "scenario" in out.columns:
        out = out[out["scenario"] == scenario]
    return out.reset_index(drop=True)
