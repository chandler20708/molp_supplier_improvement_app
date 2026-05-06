from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from .load_data import resolve_paths, standardise_supplier_key, validate_required_columns


@dataclass
class LiveOptimisationResult:
    ok: bool
    message: str
    targets: pd.DataFrame
    peers: pd.DataFrame
    payoff: pd.DataFrame


def normalise_weights(weights: dict[str, float]) -> dict[str, float]:
    clean = {k: max(0.0, float(v)) for k, v in weights.items()}
    total = sum(clean.values())
    if total <= 0:
        return {k: 1.0 / len(clean) for k in clean}
    return {k: v / total for k, v in clean.items()}


def check_live_optimizer_available() -> tuple[bool, str]:
    """Check the optional live optimisation stack without solving the model."""
    try:
        import polars  # noqa: F401
    except Exception as exc:  # pragma: no cover - optional dependency
        return False, f"Live custom MOLP unavailable: polars could not be imported ({exc})."
    try:
        import gurobipy  # noqa: F401
    except Exception as exc:  # pragma: no cover - optional dependency
        return False, f"Live custom MOLP unavailable: gurobipy could not be imported ({exc})."
    try:
        from risk_supplier_improvement import post_dea_molp
    except Exception as exc:  # pragma: no cover - optional dependency
        return False, f"Live custom MOLP unavailable: risk_supplier_improvement could not be imported ({exc})."
    for function_name in ("solve_post_dea_for_supplier", "solutions_to_frames"):
        if not callable(getattr(post_dea_molp, function_name, None)):
            return False, f"Live custom MOLP unavailable: missing {function_name}()."

    paths = resolve_paths(".")
    molp_path = paths.output_dir / "supplier_molp_inputs.csv"
    dea_path = paths.output_dir / "dea_team_ccr_efficiency.csv"
    if not dea_path.exists():
        dea_path = paths.data_dir / "dea_ccr_efficiency.csv"
    if not molp_path.exists():
        return False, f"Live custom MOLP unavailable: missing {molp_path}."
    if not dea_path.exists():
        return False, "Live custom MOLP unavailable: missing DEA efficiency table."
    try:
        molp_df = standardise_supplier_key(pd.read_csv(molp_path, nrows=3))
        dea_df = standardise_supplier_key(pd.read_csv(dea_path, nrows=3))
    except Exception as exc:
        return False, f"Live custom MOLP unavailable: required CSVs could not be read ({exc})."
    molp_errors = validate_required_columns(
        molp_df,
        {"supplier", "price", "late_pct", "error_pct", "lead_days", "quality_score", "purchase"},
        "supplier_molp_inputs",
    )
    dea_errors = validate_required_columns(dea_df, {"supplier", "CCR_Efficiency"}, "DEA efficiency")
    if molp_errors or dea_errors:
        return False, "Live custom MOLP unavailable: " + " ".join(molp_errors + dea_errors)
    return True, "Live custom MOLP available. Slider weights will re-solve the post-DEA MOLP model."


def run_live_molp(
    molp_inputs_df: pd.DataFrame,
    dea_df: pd.DataFrame,
    supplier: str,
    weights: dict[str, float],
    efficiency_threshold: float = 1.0,
    rts: str = "CCR",
) -> LiveOptimisationResult:
    """Run the original post-DEA MOLP optimiser for one supplier.

    This is optional. It requires polars, gurobipy, the local
    risk_supplier_improvement package, and a valid Gurobi licence.
    """
    try:
        import polars as pl
        from risk_supplier_improvement.post_dea_molp import solve_post_dea_for_supplier, solutions_to_frames
    except Exception as exc:  # pragma: no cover - depends on local optional stack
        return LiveOptimisationResult(False, f"Live optimiser unavailable: {exc}", pd.DataFrame(), pd.DataFrame(), pd.DataFrame())

    if molp_inputs_df is None or molp_inputs_df.empty:
        return LiveOptimisationResult(False, "Live optimiser needs supplier_molp_inputs.csv.", pd.DataFrame(), pd.DataFrame(), pd.DataFrame())
    if dea_df is None or dea_df.empty:
        return LiveOptimisationResult(False, "Live optimiser needs dea_team_ccr_efficiency.csv or dea_ccr_efficiency.csv.", pd.DataFrame(), pd.DataFrame(), pd.DataFrame())

    try:
        dea = dea_df.copy()
        if "Supplier" in dea.columns and "supplier" not in dea.columns:
            dea = dea.rename(columns={"Supplier": "supplier"})
        if "CCR_Efficiency" in dea.columns and "ccr_efficiency" not in dea.columns:
            dea = dea.rename(columns={"CCR_Efficiency": "ccr_efficiency"})
        peer_suppliers = dea.loc[dea["ccr_efficiency"] >= efficiency_threshold - 1e-6, "supplier"].astype(str).str.upper().tolist()
        if not peer_suppliers:
            return LiveOptimisationResult(False, "No CCR-efficient peers found. Check the DEA table and threshold.", pd.DataFrame(), pd.DataFrame(), pd.DataFrame())

        df = molp_inputs_df.copy()
        if "supplier" in df.columns:
            df["supplier"] = df["supplier"].astype(str).str.upper()
        solution = solve_post_dea_for_supplier(
            df=pl.from_pandas(df),
            supplier=str(supplier).upper(),
            scenario_name="custom_live",
            weights=normalise_weights(weights),
            peer_suppliers=peer_suppliers,
            rts=rts,
        )
        target_pl, peer_pl, payoff_pl = solutions_to_frames([solution])
        return LiveOptimisationResult(True, "Live MOLP run completed.", target_pl.to_pandas(), peer_pl.to_pandas(), payoff_pl.to_pandas())
    except Exception as exc:  # pragma: no cover - depends on Gurobi runtime
        return LiveOptimisationResult(False, f"Live optimiser failed: {exc}", pd.DataFrame(), pd.DataFrame(), pd.DataFrame())
