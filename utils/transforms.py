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

SCENARIO_WEIGHTS = {
    "balanced_improvement": {
        "Price": 0.20,
        "Late Delivery": 0.20,
        "Shipping Error": 0.20,
        "Lead Time": 0.20,
        "Product Quality": 0.20,
    },
    "cost_led_development": {
        "Price": 0.35,
        "Late Delivery": 0.15,
        "Shipping Error": 0.15,
        "Lead Time": 0.10,
        "Product Quality": 0.25,
    },
    "delivery_reliability_led": {
        "Price": 0.10,
        "Late Delivery": 0.30,
        "Shipping Error": 0.25,
        "Lead Time": 0.25,
        "Product Quality": 0.10,
    },
    "product_quality_led": {
        "Price": 0.10,
        "Late Delivery": 0.15,
        "Shipping Error": 0.10,
        "Lead Time": 0.15,
        "Product Quality": 0.50,
    },
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


def inefficient_suppliers(master_df: pd.DataFrame) -> list[str]:
    if master_df is None or master_df.empty or "ccr_efficiency" not in master_df.columns:
        return []
    rows = master_df[pd.to_numeric(master_df["ccr_efficiency"], errors="coerce") < 0.999]
    return sorted(rows["supplier"].dropna().astype(str).unique().tolist())


def _dominant_peer(peer_weights_df: pd.DataFrame, supplier: str, scenario: str) -> str:
    if peer_weights_df is None or peer_weights_df.empty:
        return "No peer weights"
    peers = peer_weights_df[(peer_weights_df["supplier"] == supplier) & (peer_weights_df["scenario"] == scenario)].copy()
    if peers.empty:
        return "No peer weights"
    peers = peers.sort_values("lambda_value", ascending=False)
    top = peers.iloc[0]
    return f"{top['peer_supplier']} ({float(top['lambda_value']):.2f})"


def _top_priority_from_improvement(improvement: pd.DataFrame, scenario: str) -> tuple[str, float]:
    if improvement.empty:
        return "No target movement", 0.0
    weights = SCENARIO_WEIGHTS.get(scenario, {})
    rows = improvement[improvement["Metric"].isin(weights)].copy()
    if rows.empty:
        return "No target movement", 0.0
    rows["Weighted room"] = rows["Metric"].map(weights).fillna(0.0) * pd.to_numeric(rows["Normalised room"], errors="coerce").clip(lower=0).fillna(0.0)
    top = rows.sort_values("Weighted room", ascending=False).iloc[0]
    if float(top["Weighted room"]) <= 0:
        return "Monitor current capability", 0.0
    return str(top["Metric"]), float(top["Weighted room"])


def build_balanced_base_case_table(master_df: pd.DataFrame, targets_df: pd.DataFrame, peer_weights_df: pd.DataFrame) -> pd.DataFrame:
    scenario = "balanced_improvement"
    rows: list[dict[str, object]] = []
    for supplier in inefficient_suppliers(master_df):
        target = get_selected_target(targets_df, supplier, scenario)
        if target is None:
            continue
        improvement = build_improvement_table(master_df, targets_df, supplier, scenario)
        top_priority, weighted_room = _top_priority_from_improvement(improvement, scenario)
        rows.append(
            {
                "Supplier": supplier,
                "Development need": top_priority,
                "Price improvement": target.get("price_improvement"),
                "Late-delivery improvement": target.get("late_improvement"),
                "Shipping-error improvement": target.get("error_improvement"),
                "Lead-time improvement": target.get("lead_improvement"),
                "Product-quality gain": target.get("quality_gain"),
                "Weighted normalised burden": weighted_room,
                "Theta": target.get("theta"),
                "Leading benchmark peer": _dominant_peer(peer_weights_df, supplier, scenario),
            }
        )
    return pd.DataFrame(rows).sort_values("Weighted normalised burden", ascending=False).reset_index(drop=True)


def _managerial_interpretation(supplier: str, scenario: str, criterion: str) -> str:
    scenario_name = SCENARIO_NAMES.get(scenario, scenario)
    if criterion == "Price":
        priority = "cost competitiveness pathway"
    elif criterion in {"Late Delivery", "Shipping Error", "Lead Time"}:
        priority = "delivery-reliability capability gap"
    elif criterion == "Product Quality":
        priority = "product-quality capability gap"
    else:
        priority = "broad capability gap"
    return (
        f"Under the {scenario_name} scenario, Supplier {supplier} has the largest development burden; "
        f"start with the {priority} and use benchmark peers for process learning."
    )


def build_supplier_burden_table(master_df: pd.DataFrame, targets_df: pd.DataFrame, peer_weights_df: pd.DataFrame, scenario: str) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for supplier in inefficient_suppliers(master_df):
        improvement = build_improvement_table(master_df, targets_df, supplier, scenario)
        if improvement.empty:
            continue
        weights = SCENARIO_WEIGHTS.get(scenario, {})
        criteria = improvement[improvement["Metric"].isin(weights)].copy()
        if criteria.empty:
            continue
        criteria["Weighted room"] = criteria["Metric"].map(weights).fillna(0.0) * pd.to_numeric(criteria["Normalised room"], errors="coerce").clip(lower=0).fillna(0.0)
        top = criteria.sort_values("Weighted room", ascending=False).iloc[0]
        rows.append(
            {
                "Supplier": supplier,
                "Weighted normalised improvement burden": float(criteria["Weighted room"].sum()),
                "Driving criterion": str(top["Metric"]),
                "Driving-criterion contribution": float(top["Weighted room"]),
                "Leading benchmark peer": _dominant_peer(peer_weights_df, supplier, scenario),
                "Managerial interpretation": _managerial_interpretation(supplier, scenario, str(top["Metric"])),
            }
        )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("Weighted normalised improvement burden", ascending=False).reset_index(drop=True)


def build_scenario_interpretation_table(master_df: pd.DataFrame, targets_df: pd.DataFrame, peer_weights_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for scenario in SCENARIO_DISPLAY_ORDER:
        supplier_rows = build_supplier_burden_table(master_df, targets_df, peer_weights_df, scenario)
        if supplier_rows.empty:
            continue
        selected = supplier_rows.iloc[0]
        rows.append(
            {
                "Scenario": SCENARIO_NAMES.get(scenario, scenario),
                "Supplier with largest burden": selected["Supplier"],
                "Weighted normalised improvement burden": selected["Weighted normalised improvement burden"],
                "Driving criterion": selected["Driving criterion"],
                "Driving-criterion contribution": selected["Driving-criterion contribution"],
                "Leading benchmark peer": selected["Leading benchmark peer"],
                "Managerial interpretation": selected["Managerial interpretation"],
            }
        )
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
