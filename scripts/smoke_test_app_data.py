from __future__ import annotations

import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = APP_DIR
sys.path.insert(0, str(APP_DIR))

from utils.load_data import load_app_data  # noqa: E402
from utils.transforms import (  # noqa: E402
    build_baseline_potential_table,
    build_current_target_long,
    build_current_target_wide,
    build_scenario_potential_summary,
    build_scenario_potential_table,
)


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    raise SystemExit(1)


def main() -> None:
    app_data = load_app_data(PROJECT_ROOT)
    master = app_data["master"]
    targets = app_data["outputs"].get("molp_targets")

    if len(master["supplier"].dropna().unique()) != 12:
        fail(f"expected 12 suppliers, found {len(master['supplier'].dropna().unique())}")
    required_target_columns = {"supplier", "scenario", "theta", "target_price", "target_late_pct", "target_error_pct", "target_lead_days", "target_quality_score", "target_purchase"}
    missing = required_target_columns.difference(targets.columns)
    if missing:
        fail(f"molp_targets.csv missing columns {sorted(missing)}")

    inefficient = master[pd_to_numeric(master["ccr_efficiency"]) < 0.999]["supplier"].astype(str).tolist()
    if not inefficient:
        fail("no CCR-inefficient suppliers found")
    supplier = "L" if "L" in inefficient else inefficient[0]
    scenario = "balanced_improvement"
    target_rows = targets[(targets["supplier"] == supplier) & (targets["scenario"] == scenario)]
    if target_rows.empty:
        fail(f"no target rows for inefficient supplier {supplier} under {scenario}")

    wide = build_current_target_wide(master, targets, supplier, scenario)
    long = build_current_target_long(master, targets, supplier, scenario)
    if wide.empty or len(wide) < 6:
        fail(f"wide chart data is empty or incomplete for supplier {supplier}")
    if long.empty or set(long["State"]) != {"Current", "Target"}:
        fail(f"long chart data is empty or has wrong states for supplier {supplier}")

    radar_metrics = {"Price", "Late Delivery", "Shipping Error", "Lead Time", "Product Quality", "Customer Service Overlay", "Purchase"}
    if not radar_metrics.issubset(set(long["Metric"])):
        fail(f"radar metric data is incomplete for supplier {supplier}")
    if long["Score"].isna().all():
        fail(f"radar scores are all missing for supplier {supplier}")
    target_rows_for_chart = long[long["State"].isin(["Current", "Target"])]
    if target_rows_for_chart.empty or target_rows_for_chart["Score"].isna().all():
        fail(f"selected scenario target chart data is empty for supplier {supplier}")

    efficient = master[pd_to_numeric(master["ccr_efficiency"]) >= 0.999]["supplier"].astype(str).tolist()
    if not efficient:
        fail("no CCR-efficient benchmark suppliers found")

    baseline = build_baseline_potential_table(master, targets)
    if baseline.empty or "Baseline potential rank" not in baseline.columns:
        fail("baseline potential table is empty or incomplete")
    scenario_table = build_scenario_potential_table(master, targets, "balanced_improvement")
    if scenario_table.empty or "Scenario potential rank" not in scenario_table.columns:
        fail("scenario potential table is empty or incomplete")
    required_potential = {"MOLP target distance", "Bottleneck gap", "Bottleneck criterion", "norm_price_gap", "norm_late_gap", "norm_error_gap", "norm_lead_gap", "norm_quality_gap"}
    if missing_potential := required_potential.difference(scenario_table.columns):
        fail(f"scenario potential table missing columns {sorted(missing_potential)}")
    distances = pd_to_numeric(scenario_table["MOLP target distance"]).tolist()
    if distances != sorted(distances):
        fail("scenario potential table is not ranked by ascending MOLP target distance")
    scenario_summary = build_scenario_potential_summary(master, targets)
    if len(scenario_summary) != 4:
        fail(f"expected 4 scenario potential summary rows, found {len(scenario_summary)}")
    required_summary = {"Top potential supplier", "MOLP target distance", "Bottleneck criterion", "Managerial interpretation"}
    if missing_summary := required_summary.difference(scenario_summary.columns):
        fail(f"scenario potential summary missing columns {sorted(missing_summary)}")

    print(
        "PASS: app data has 12 suppliers, required target columns, non-empty inefficient-supplier targets, "
        "non-empty radar data, non-empty selected-scenario target chart data, and potential interpretation tables."
    )


def pd_to_numeric(series):
    import pandas as pd

    return pd.to_numeric(series, errors="coerce")


if __name__ == "__main__":
    main()
