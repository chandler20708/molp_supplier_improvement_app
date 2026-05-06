from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional

import pandas as pd


SCENARIO_LABELS = {
    "Balanced": "balanced_improvement",
    "Cost-led": "cost_led_development",
    "Delivery-led": "delivery_reliability_led",
    "Quality-led": "product_quality_led",
}
SCENARIO_DISPLAY = {value: key for key, value in SCENARIO_LABELS.items()}

PRIMARY_INPUT_FILES = {
    "product_quality": "product_quality_scores.csv",
    "customer_service": "customer_service_scores.csv",
    "operational_inputs": "supplier_operational_inputs.csv",
    "dea_efficiency": "dea_ccr_efficiency.csv",
}

OUTPUT_FILES = {
    "supplier_molp_inputs": "supplier_molp_inputs.csv",
    "dea_team_ccr_efficiency": "dea_team_ccr_efficiency.csv",
    "dea_team_candidates": "dea_team_candidates.csv",
    "molp_targets": "molp_targets.csv",
    "molp_peer_weights": "molp_peer_weights.csv",
    "molp_payoff_table": "molp_payoff_table.csv",
    "sensitivity_weight_summary": "sensitivity_weight_summary.csv",
    "sensitivity_parameter_summary": "sensitivity_parameter_summary.csv",
    "sensitivity_parameter_runs": "sensitivity_parameter_runs.csv",
    "sensitivity_parameter_peer_weights": "sensitivity_parameter_peer_weights.csv",
}

REQUIRED_COLUMNS = {
    "product_quality": {"supplier", "quality_score"},
    "customer_service": {"supplier", "service_score"},
    "operational_inputs": {"supplier", "price", "late_pct", "error_pct", "lead_days", "purchase"},
    "dea_efficiency": {"supplier", "CCR_Efficiency"},
    "supplier_molp_inputs": {"supplier", "price", "late_pct", "error_pct", "lead_days", "quality_score", "purchase"},
    "dea_team_ccr_efficiency": {"supplier", "CCR_Efficiency"},
    "molp_targets": {
        "supplier", "scenario", "theta", "target_price", "target_late_pct",
        "target_error_pct", "target_lead_days", "target_quality_score", "target_purchase",
    },
    "molp_peer_weights": {"supplier", "scenario", "peer_supplier", "lambda_value"},
}


@dataclass(frozen=True)
class AppPaths:
    root_dir: Path
    data_dir: Path
    output_dir: Path


def resolve_paths(root_dir: str | Path = ".", output_subdir: str = "outputs/team_ccr") -> AppPaths:
    root = Path(root_dir).resolve()
    data_dir = root / "data"
    output_dir = root / output_subdir
    if not data_dir.exists() and any((root / name).exists() for name in PRIMARY_INPUT_FILES.values()):
        data_dir = root
    if not output_dir.exists() and any((root / name).exists() for name in OUTPUT_FILES.values()):
        output_dir = root
    return AppPaths(root, data_dir, output_dir)


def standardise_supplier_key(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    if "Supplier" in out.columns and "supplier" not in out.columns:
        out = out.rename(columns={"Supplier": "supplier"})
    if "supplier" in out.columns:
        out["supplier"] = out["supplier"].astype(str).str.strip().str.upper()
    return out


def _read_csv_if_exists(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return standardise_supplier_key(pd.read_csv(path))


def validate_required_columns(df: pd.DataFrame, required_columns: Iterable[str], table_name: str) -> list[str]:
    if df is None or df.empty:
        return [f"{table_name}: file is missing or empty."]
    missing = sorted(set(required_columns).difference(df.columns))
    if missing:
        return [f"{table_name}: missing required columns {missing}."]
    return []


def validate_app_data(app_data: dict) -> list[str]:
    diagnostics: list[str] = []
    inputs = app_data.get("inputs", {})
    outputs = app_data.get("outputs", {})
    for key, required in REQUIRED_COLUMNS.items():
        source = inputs if key in PRIMARY_INPUT_FILES else outputs
        diagnostics.extend(validate_required_columns(source.get(key, pd.DataFrame()), required, key))
    master = app_data.get("master", pd.DataFrame())
    master_required = {
        "supplier", "product_quality_score", "customer_service_score", "ccr_efficiency",
        "avg_unit_price", "late_delivery_pct", "shipping_error_pct", "lead_time_days",
        "total_purchase", "portfolio_status",
    }
    diagnostics.extend(validate_required_columns(master, master_required, "supplier master"))
    return diagnostics


def load_inputs(paths: AppPaths) -> Dict[str, pd.DataFrame]:
    return {key: _read_csv_if_exists(paths.data_dir / name) for key, name in PRIMARY_INPUT_FILES.items()}


def load_outputs(paths: AppPaths) -> Dict[str, pd.DataFrame]:
    return {key: _read_csv_if_exists(paths.output_dir / name) for key, name in OUTPUT_FILES.items()}


def _safe_merge(left: pd.DataFrame, right: pd.DataFrame, on: str = "supplier") -> pd.DataFrame:
    if right.empty or on not in right.columns:
        return left.copy()
    if left.empty:
        return right.copy()
    return left.merge(right, on=on, how="left")


def _coalesce_columns(df: pd.DataFrame, target: str, candidates: Iterable[str]) -> pd.DataFrame:
    out = df.copy()
    existing = [c for c in candidates if c in out.columns]
    if target not in out.columns and existing:
        out[target] = out[existing[0]]
    for c in existing:
        if c != target:
            out[target] = out[target].combine_first(out[c])
    return out


def classify_portfolio_status(
    pq_score: Optional[float],
    cs_score: Optional[float],
    ccr_efficiency: Optional[float],
    pq_threshold: float,
    cs_threshold: float,
) -> str:
    high_pq = pd.notna(pq_score) and pq_score >= pq_threshold
    high_cs = pd.notna(cs_score) and cs_score >= cs_threshold
    high_dea = pd.notna(ccr_efficiency) and ccr_efficiency >= 0.999
    high_mcda = high_pq and high_cs
    mixed_mcda = high_pq or high_cs
    if high_mcda and high_dea:
        return "Strategic partner"
    if high_mcda and not high_dea:
        return "Development candidate"
    if mixed_mcda and not high_dea:
        return "Selective development"
    if not mixed_mcda and high_dea:
        return "Tactical efficient"
    return "Deprioritise / renegotiate"


def build_supplier_master(inputs: Dict[str, pd.DataFrame], outputs: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    pq = inputs.get("product_quality", pd.DataFrame()).rename(
        columns={
            "quality_score": "product_quality_score",
            "Product Quality Score": "product_quality_score",
            "PQ score": "product_quality_score",
        }
    )
    cs = inputs.get("customer_service", pd.DataFrame()).rename(
        columns={
            "service_score": "customer_service_score",
            "Customer Service Score": "customer_service_score",
            "CS score": "customer_service_score",
        }
    )
    ops = inputs.get("operational_inputs", pd.DataFrame()).rename(
        columns={
            "price": "avg_unit_price",
            "average_unit_price": "avg_unit_price",
            "late_pct": "late_delivery_pct",
            "error_pct": "shipping_error_pct",
            "lead_days": "lead_time_days",
            "purchase": "total_purchase",
        }
    )
    dea = inputs.get("dea_efficiency", pd.DataFrame()).rename(columns={"CCR_Efficiency": "ccr_efficiency"})

    molp_inputs = outputs.get("supplier_molp_inputs", pd.DataFrame()).rename(
        columns={
            "price": "avg_unit_price",
            "late_pct": "late_delivery_pct",
            "error_pct": "shipping_error_pct",
            "lead_days": "lead_time_days",
            "purchase": "total_purchase",
            "quality_score": "product_quality_score",
        }
    )
    dea_out = outputs.get("dea_team_ccr_efficiency", pd.DataFrame()).rename(columns={"CCR_Efficiency": "ccr_efficiency"})

    master = pd.DataFrame()
    for frame in [pq, cs, ops, dea]:
        if not frame.empty:
            master = _safe_merge(master, frame)
    if master.empty and not molp_inputs.empty:
        master = molp_inputs.copy()
    elif not molp_inputs.empty:
        master = _safe_merge(master, molp_inputs)
    if "ccr_efficiency" not in master.columns and not dea_out.empty:
        master = _safe_merge(master, dea_out)

    if master.empty:
        return master

    aliases = {
        "product_quality_score": ["product_quality_score", "quality_score", "product_quality_score_x", "product_quality_score_y", "quality_score_x", "quality_score_y"],
        "customer_service_score": ["customer_service_score", "service_score", "customer_service_score_x", "customer_service_score_y", "service_score_x", "service_score_y"],
        "avg_unit_price": ["avg_unit_price", "price", "avg_unit_price_x", "avg_unit_price_y", "price_x", "price_y"],
        "late_delivery_pct": ["late_delivery_pct", "late_pct", "late_delivery_pct_x", "late_delivery_pct_y", "late_pct_x", "late_pct_y"],
        "shipping_error_pct": ["shipping_error_pct", "error_pct", "shipping_error_pct_x", "shipping_error_pct_y", "error_pct_x", "error_pct_y"],
        "lead_time_days": ["lead_time_days", "lead_days", "lead_time_days_x", "lead_time_days_y", "lead_days_x", "lead_days_y"],
        "total_purchase": ["total_purchase", "purchase", "total_purchase_x", "total_purchase_y", "purchase_x", "purchase_y"],
        "ccr_efficiency": ["ccr_efficiency", "CCR_Efficiency", "ccr_efficiency_x", "ccr_efficiency_y", "CCR_Efficiency_x", "CCR_Efficiency_y"],
    }
    for target, candidates in aliases.items():
        master = _coalesce_columns(master, target, candidates)

    numeric_cols = list(aliases)
    for col in numeric_cols:
        if col in master.columns:
            master[col] = pd.to_numeric(master[col], errors="coerce")

    master["mcda_score"] = master[["product_quality_score", "customer_service_score"]].mean(axis=1, skipna=True)
    master["dea_status"] = master["ccr_efficiency"].apply(lambda x: "CCR-efficient" if pd.notna(x) and x >= 0.999 else "Needs development")

    pq_threshold = master["product_quality_score"].median(skipna=True)
    cs_threshold = master["customer_service_score"].median(skipna=True)
    master["portfolio_status"] = master.apply(
        lambda row: classify_portfolio_status(
            row.get("product_quality_score"), row.get("customer_service_score"), row.get("ccr_efficiency"), pq_threshold, cs_threshold
        ),
        axis=1,
    )
    return master.sort_values("supplier").reset_index(drop=True)


def load_app_data(root_dir: str | Path = ".", output_subdir: str = "outputs/team_ccr") -> dict:
    paths = resolve_paths(root_dir, output_subdir)
    inputs = load_inputs(paths)
    outputs = load_outputs(paths)
    master = build_supplier_master(inputs, outputs)
    app_data = {"paths": paths, "inputs": inputs, "outputs": outputs, "master": master}
    app_data["diagnostics"] = validate_app_data(app_data)
    return app_data
