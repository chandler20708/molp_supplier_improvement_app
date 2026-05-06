from __future__ import annotations

import argparse
from pathlib import Path

import polars as pl

from .data import load_dea_team_table, load_molp_inputs
from .post_dea_molp import DEFAULT_SCENARIOS, solve_post_dea_for_supplier, solutions_to_frames
from .sensitivity import DEFAULT_PERTURBATION_COLUMNS, build_weight_sensitivity_summary, run_parameter_sensitivity


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the coursework-aligned supplier improvement MOLP workflow."
    )
    parser.add_argument(
        "--rts",
        choices=["CCR", "CRS", "VRS"],
        default="CCR",
        help="Returns-to-scale assumption used in DEA and post-DEA MOLP.",
    )
    parser.add_argument(
        "--supplier",
        help="Optional supplier ID to solve only for one supplier.",
    )
    parser.add_argument(
        "--supplier-data",
        default=None,
        help="Optional path to the MOLP input CSV with supplier, price, late_pct, error_pct, lead_days, quality_score, purchase.",
    )
    parser.add_argument(
        "--dea-table",
        default=None,
        help="Optional path to an external DEA CSV with columns Supplier and CCR_Efficiency.",
    )
    parser.add_argument(
        "--efficiency-threshold",
        type=float,
        default=1.0,
        help="Suppliers with CCR_Efficiency below this threshold are selected for post-DEA MOLP.",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/team_ccr",
        help="Directory for CSV exports.",
    )
    parser.add_argument(
        "--inefficient-only",
        action="store_true",
        help="Only run the post-DEA MOLP for suppliers below the efficiency threshold. By default all suppliers are analysed.",
    )
    parser.add_argument(
        "--sensitivity-delta",
        type=float,
        default=0.05,
        help="Relative perturbation size used for parameter sensitivity, e.g. 0.05 for +/-5%%.",
    )
    parser.add_argument(
        "--skip-sensitivity",
        action="store_true",
        help="Skip the sensitivity-analysis exports.",
    )
    parser.add_argument(
        "--efficiency-tolerance",
        type=float,
        default=1e-6,
        help="Tolerance for classifying suppliers as CCR-efficient.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    dataset = load_molp_inputs(args.supplier_data)
    dea_team = load_dea_team_table(args.dea_table)
    efficient_cutoff = args.efficiency_threshold - args.efficiency_tolerance

    efficient_peers = (
        dea_team
        .filter(pl.col("CCR_Efficiency") >= efficient_cutoff)
        .get_column("Supplier")
        .cast(pl.Utf8)
        .to_list()
    )

    if not efficient_peers:
        parser.error("No CCR-efficient peer suppliers found. Check the DEA table or efficiency threshold.")
    candidate_dea = (
        dea_team.filter(pl.col("CCR_Efficiency") < efficient_cutoff)
        if args.inefficient_only
        else dea_team
    )
    candidates = candidate_dea["Supplier"].to_list()

    if args.supplier:
        if args.supplier not in dataset["supplier"].to_list():
            parser.error(f"Unknown supplier '{args.supplier}'.")
        candidates = [args.supplier]

    solutions = [
        solve_post_dea_for_supplier(
            df=dataset,
            supplier=supplier,
            scenario_name=scenario_name,
            weights=weights,
            peer_suppliers=efficient_peers,
            rts=args.rts,
        )
        for supplier in candidates
        for scenario_name, weights in DEFAULT_SCENARIOS.items()
    ]

    target_df, peer_df, payoff_df = solutions_to_frames(solutions)
    target_df = target_df.join(
        dea_team.rename({"Supplier": "supplier", "CCR_Efficiency": "ccr_efficiency"}),
        on="supplier",
        how="left",
    )

    dataset.write_csv(output_dir / "supplier_molp_inputs.csv")
    dea_team.write_csv(output_dir / "dea_team_ccr_efficiency.csv")
    candidate_dea.write_csv(output_dir / "dea_team_candidates.csv")
    target_df.write_csv(output_dir / "molp_targets.csv")
    peer_df.write_csv(output_dir / "molp_peer_weights.csv")
    payoff_df.write_csv(output_dir / "molp_payoff_table.csv")

    if not args.skip_sensitivity:
        weight_summary_df = build_weight_sensitivity_summary(target_df)
        parameter_runs_df, parameter_summary_df, peer_run_df = run_parameter_sensitivity(
            df=dataset,
            candidates=candidates,
            rts=args.rts,
            delta=args.sensitivity_delta,
            perturbation_columns=tuple(DEFAULT_PERTURBATION_COLUMNS),
            peer_suppliers=efficient_peers,
        )
        weight_summary_df.write_csv(output_dir / "sensitivity_weight_summary.csv")
        parameter_runs_df.write_csv(output_dir / "sensitivity_parameter_runs.csv")
        parameter_summary_df.write_csv(output_dir / "sensitivity_parameter_summary.csv")
        peer_run_df.write_csv(output_dir / "sensitivity_parameter_peer_weights.csv")
    print(f"Wrote outputs to {output_dir}")
    print("Candidate suppliers:", ", ".join(candidates) if candidates else "none")
    print("CCR-efficient peer suppliers:", ", ".join(efficient_peers))
    print("DEA team candidate counts:")
    print(
        dea_team.with_columns(
            pl.when(pl.col("CCR_Efficiency") < args.efficiency_threshold)
            .then(pl.lit("selected"))
            .otherwise(pl.lit("not_selected"))
            .alias("candidate_status")
        )
        .group_by("candidate_status")
        .len()
        .sort("candidate_status")
    )
    if not args.skip_sensitivity:
        print(f"Sensitivity delta: +/-{args.sensitivity_delta:.2%}")
    return 0
