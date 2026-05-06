from __future__ import annotations

from dataclasses import dataclass

import polars as pl

from .post_dea_molp import DEFAULT_SCENARIOS, solve_post_dea_for_supplier, solutions_to_frames


DEFAULT_PERTURBATION_COLUMNS = [
    "price",
    "late_pct",
    "error_pct",
    "lead_days",
    "quality_score",
]


@dataclass(frozen=True)
class SensitivityConfig:
    delta: float = 0.05
    perturbation_columns: tuple[str, ...] = tuple(DEFAULT_PERTURBATION_COLUMNS)


def _perturb_dataset(df: pl.DataFrame, column: str, delta: float, direction: str) -> pl.DataFrame:
    factor = 1.0 + delta if direction == "plus" else 1.0 - delta
    return df.with_columns((pl.col(column) * factor).alias(column))


def build_weight_sensitivity_summary(target_df: pl.DataFrame) -> pl.DataFrame:
    if target_df.is_empty():
        return pl.DataFrame()

    return (
        target_df.group_by("supplier")
        .agg(
            pl.col("theta").var().fill_null(0.0).alias("robustness_index_weight"),
            pl.col("theta").min().alias("theta_min"),
            pl.col("theta").max().alias("theta_max"),
            (pl.col("target_price").max() - pl.col("target_price").min()).alias("target_price_range"),
            (pl.col("target_late_pct").max() - pl.col("target_late_pct").min()).alias("target_late_range"),
            (pl.col("target_error_pct").max() - pl.col("target_error_pct").min()).alias("target_error_range"),
            (pl.col("target_lead_days").max() - pl.col("target_lead_days").min()).alias("target_lead_range"),
            (pl.col("target_quality_score").max() - pl.col("target_quality_score").min()).alias("target_quality_range"),
            (pl.col("target_purchase").max() - pl.col("target_purchase").min()).alias("target_purchase_range"),
            pl.col("scenario").n_unique().alias("scenario_count"),
        )
        .sort("supplier")
    )


def run_parameter_sensitivity(
    df: pl.DataFrame,
    candidates: list[str],
    rts: str,
    delta: float,
    perturbation_columns: tuple[str, ...],
    peer_suppliers: list[str] | tuple[str, ...],
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    target_runs = []
    peer_runs = []

    for column in perturbation_columns:
        for direction in ("minus", "plus"):
            perturbed = _perturb_dataset(df, column=column, delta=delta, direction=direction)

            solutions = [
                solve_post_dea_for_supplier(
                    df=perturbed,
                    supplier=supplier,
                    scenario_name=scenario_name,
                    weights=weights,
                    peer_suppliers=peer_suppliers,
                    rts=rts,
                )
                for supplier in candidates
                for scenario_name, weights in DEFAULT_SCENARIOS.items()
            ]

            target_df, peer_df, _ = solutions_to_frames(solutions)

            run_metadata = [
                pl.lit(column).alias("perturbed_parameter"),
                pl.lit(direction).alias("perturbation_direction"),
                pl.lit(delta).alias("delta"),
            ]

            if not target_df.is_empty():
                target_runs.append(target_df.with_columns(*run_metadata))

            if not peer_df.is_empty():
                peer_runs.append(peer_df.with_columns(*run_metadata))

    if not target_runs:
        return pl.DataFrame(), pl.DataFrame(), pl.DataFrame()

    run_df = pl.concat(target_runs, how="diagonal_relaxed")

    peer_run_df = (
        pl.concat(peer_runs, how="diagonal_relaxed")
        if peer_runs
        else pl.DataFrame()
    )

    summary_df = (
        run_df.group_by("supplier", "scenario")
        .agg(
            pl.col("theta").var().fill_null(0.0).alias("robustness_index_parameter"),
            pl.col("theta").min().alias("theta_min"),
            pl.col("theta").max().alias("theta_max"),
            (pl.col("target_price").max() - pl.col("target_price").min()).alias("target_price_range"),
            (pl.col("target_late_pct").max() - pl.col("target_late_pct").min()).alias("target_late_range"),
            (pl.col("target_error_pct").max() - pl.col("target_error_pct").min()).alias("target_error_range"),
            (pl.col("target_lead_days").max() - pl.col("target_lead_days").min()).alias("target_lead_range"),
            (pl.col("target_quality_score").max() - pl.col("target_quality_score").min()).alias("target_quality_range"),
            (pl.col("target_purchase").max() - pl.col("target_purchase").min()).alias("target_purchase_range"),
            pl.len().alias("run_count"),
        )
        .sort(["supplier", "scenario"])
    )

    return run_df, summary_df, peer_run_df