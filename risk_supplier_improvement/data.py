from __future__ import annotations

from pathlib import Path

import polars as pl


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    return project_root() / "data"


def default_dea_table_path() -> Path:
    return data_dir() / "dea_ccr_efficiency.csv"


def default_molp_input_path() -> Path:
    return data_dir() / "supplier_molp_inputs.csv"


def default_operational_input_path() -> Path:
    return data_dir() / "supplier_operational_inputs.csv"


def default_quality_scores_path() -> Path:
    return data_dir() / "product_quality_scores.csv"


def default_service_scores_path() -> Path:
    return data_dir() / "customer_service_scores.csv"


def load_dea_team_table(path: str | Path | None = None) -> pl.DataFrame:
    csv_path = Path(path) if path is not None else default_dea_table_path()
    df = pl.read_csv(csv_path)
    required = {"Supplier", "CCR_Efficiency"}
    if not required.issubset(set(df.columns)):
        missing = sorted(required.difference(set(df.columns)))
        raise ValueError(f"DEA team table is missing columns: {missing}")
    return df.sort("CCR_Efficiency", descending=True)

def _read_and_validate(path: Path, required: set[str], label: str) -> pl.DataFrame:
    df = pl.read_csv(path)
    if not required.issubset(set(df.columns)):
        missing = sorted(required.difference(set(df.columns)))
        raise ValueError(f"{label} is missing columns: {missing}")
    return df


def load_molp_inputs(path: str | Path | None = None) -> pl.DataFrame:
    if path is not None:
        csv_path = Path(path)
        df = pl.read_csv(csv_path)
    else:
        operational = _read_and_validate(
            default_operational_input_path(),
            {"supplier", "price", "late_pct", "error_pct", "lead_days", "purchase"},
            "Operational input table",
        )
        quality = _read_and_validate(
            default_quality_scores_path(),
            {"supplier", "quality_score"},
            "Product quality score table",
        )
        df = operational.join(quality, on="supplier", how="left")

    required = {
        "supplier",
        "price",
        "late_pct",
        "error_pct",
        "lead_days",
        "quality_score",
        "purchase",
    }
    if not required.issubset(set(df.columns)):
        missing = sorted(required.difference(set(df.columns)))
        raise ValueError(f"MOLP input table is missing columns: {missing}")
    return df.sort("supplier")
