from __future__ import annotations

import html
import math
import shutil
import subprocess
from pathlib import Path

import polars as pl


BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BASE_DIR / "outputs" / "team_ccr"
ASSET_DIR = BASE_DIR / "doc" / "report2" / "assets"

SCENARIO_LABELS = {
    "balanced_improvement": "Balanced",
    "cost_led_development": "Cost-led",
    "delivery_reliability_led": "Delivery-led",
    "product_quality_led": "Quality-led",
}

IMPROVEMENT_COLS = [
    "price_improvement",
    "late_improvement",
    "error_improvement",
    "lead_improvement",
    "quality_gain",
]

IMPROVEMENT_LABELS = {
    "price_improvement": "Price",
    "late_improvement": "Late delivery",
    "error_improvement": "Shipping errors",
    "lead_improvement": "Lead time",
    "quality_gain": "Product quality",
}

REAL_UNIT_LABELS = {
    "price_improvement": "$",
    "late_improvement": "pp",
    "error_improvement": "pp",
    "lead_improvement": "days",
    "quality_gain": "score",
}

NORM_COLS = [
    "norm_price_improvement",
    "norm_late_improvement",
    "norm_error_improvement",
    "norm_lead_improvement",
    "norm_quality_gain",
]

RADAR_LABELS = ["Price", "Late", "Error", "Lead", "Quality"]
INEFF_THRESHOLD = 0.999999


def load_outputs() -> tuple[pl.DataFrame, pl.DataFrame]:
    targets = pl.read_csv(OUTPUT_DIR / "molp_targets.csv")
    eff = pl.read_csv(OUTPUT_DIR / "dea_team_ccr_efficiency.csv").rename(
        {"Supplier": "supplier", "CCR_Efficiency": "ccr_efficiency"}
    )
    if "ccr_efficiency" not in targets.columns:
        targets = targets.join(eff, on="supplier", how="left")
    return targets, eff


def inefficient_supplier_list(eff: pl.DataFrame, threshold: float = INEFF_THRESHOLD) -> list[str]:
    return (
        eff.filter(pl.col("ccr_efficiency") < threshold)
        .sort("ccr_efficiency", descending=True)
        .get_column("supplier")
        .to_list()
    )


def _safe_norm(value: float, denom: float) -> float:
    if abs(denom) <= 1e-12:
        return 0.0
    return max(0.0, value / denom)


def add_baseline_potential_fields(targets: pl.DataFrame) -> pl.DataFrame:
    ineff = targets.filter(pl.col("ccr_efficiency") < INEFF_THRESHOLD)
    return (
        ineff.group_by("supplier")
        .agg(
            pl.mean("theta").alias("mean_theta"),
            pl.first("ccr_efficiency").alias("ccr_efficiency"),
        )
        .with_columns((1.0 - pl.col("ccr_efficiency")).alias("frontier_gap"))
        .sort(["ccr_efficiency", "mean_theta", "supplier"], descending=[True, False, False])
        .with_row_index("baseline_potential_rank", offset=1)
    )


def build_scenario_potential_table(targets: pl.DataFrame, top_n: int = 3) -> pl.DataFrame:
    ineff = targets.filter(pl.col("ccr_efficiency") < INEFF_THRESHOLD)
    out_rows: list[dict[str, object]] = []

    for scenario in SCENARIO_LABELS:
        scenario_df = ineff.filter(pl.col("scenario") == scenario)
        if scenario_df.height == 0:
            continue

        rows = scenario_df.to_dicts()
        col_max: dict[str, float] = {}
        for col in IMPROVEMENT_COLS:
            max_val = max(float(row.get(col, 0.0) or 0.0) for row in rows)
            col_max[col] = max_val if max_val > 0 else 1.0

        enriched_rows = []
        for row in rows:
            norm_gaps = {
                col: _safe_norm(float(row.get(col, 0.0) or 0.0), col_max[col])
                for col in IMPROVEMENT_COLS
            }
            biggest_gap_col = max(norm_gaps, key=norm_gaps.get)
            enriched = dict(row)
            enriched["biggest_gap_criterion"] = IMPROVEMENT_LABELS[biggest_gap_col]
            enriched["biggest_gap_column"] = biggest_gap_col
            enriched["biggest_gap_real"] = float(row.get(biggest_gap_col, 0.0) or 0.0)
            enriched["biggest_gap_unit"] = REAL_UNIT_LABELS[biggest_gap_col]
            enriched["biggest_gap_normalised"] = norm_gaps[biggest_gap_col]
            enriched["_norm_gaps"] = norm_gaps
            enriched_rows.append(enriched)

        enriched_rows.sort(key=lambda r: (float(r["theta"]), -float(r["ccr_efficiency"]), str(r["supplier"])))

        for rank, row in enumerate(enriched_rows, start=1):
            out_rows.append(
                {
                    "scenario": scenario,
                    "scenario_label": SCENARIO_LABELS[scenario],
                    "scenario_potential_rank": rank,
                    "supplier": row["supplier"],
                    "ccr_efficiency": float(row["ccr_efficiency"]),
                    "frontier_gap": 1.0 - float(row["ccr_efficiency"]),
                    "theta": float(row["theta"]),
                    "is_top_potential": rank <= top_n,
                    "biggest_gap_criterion": row["biggest_gap_criterion"],
                    "biggest_gap_column": row["biggest_gap_column"],
                    "biggest_gap_real": row["biggest_gap_real"],
                    "biggest_gap_unit": row["biggest_gap_unit"],
                    "biggest_gap_normalised": row["biggest_gap_normalised"],
                    "price_improvement": float(row.get("price_improvement", 0.0) or 0.0),
                    "late_improvement": float(row.get("late_improvement", 0.0) or 0.0),
                    "error_improvement": float(row.get("error_improvement", 0.0) or 0.0),
                    "lead_improvement": float(row.get("lead_improvement", 0.0) or 0.0),
                    "quality_gain": float(row.get("quality_gain", 0.0) or 0.0),
                    "norm_price_improvement": row["_norm_gaps"]["price_improvement"],
                    "norm_late_improvement": row["_norm_gaps"]["late_improvement"],
                    "norm_error_improvement": row["_norm_gaps"]["error_improvement"],
                    "norm_lead_improvement": row["_norm_gaps"]["lead_improvement"],
                    "norm_quality_gain": row["_norm_gaps"]["quality_gain"],
                }
            )

    return pl.DataFrame(out_rows)


def build_radar_source_table(scenario_potential_df: pl.DataFrame, baseline_df: pl.DataFrame | None = None) -> pl.DataFrame:
    radar = scenario_potential_df.select(
        [
            "scenario",
            "scenario_label",
            "scenario_potential_rank",
            "supplier",
            "is_top_potential",
            "ccr_efficiency",
            "frontier_gap",
            "theta",
            "biggest_gap_criterion",
            "biggest_gap_column",
            "biggest_gap_real",
            "biggest_gap_unit",
            "price_improvement",
            "late_improvement",
            "error_improvement",
            "lead_improvement",
            "quality_gain",
            *NORM_COLS,
        ]
    )
    if baseline_df is not None and baseline_df.height > 0:
        radar = radar.join(
            baseline_df.select(["supplier", "baseline_potential_rank", "mean_theta"]),
            on="supplier",
            how="left",
        )
    return radar


def write_business_summary_markdown(
    baseline_df: pl.DataFrame,
    scenario_df: pl.DataFrame,
    path: Path,
    top_n: int = 3,
) -> None:
    lines = [
        "# MOLP potential summary",
        "",
        "The optimisation is solved using normalised deviations to ensure comparability across criteria, but recommended improvement actions are reported in original business units for interpretability and implementation.",
        "",
        "## Baseline development potential",
        "",
        "Potential is defined as closeness to the efficient frontier among inefficient suppliers. Suppliers are ranked by CCR efficiency (descending), with mean theta shown as supporting information.",
        "",
    ]

    for row in baseline_df.sort("baseline_potential_rank").to_dicts():
        lines.append(
            f"- Rank {row['baseline_potential_rank']}: Supplier {row['supplier']} "
            f"(CCR={row['ccr_efficiency']:.3f}, frontier gap={row['frontier_gap']:.3f}, "
            f"mean theta={row['mean_theta']:.3f})"
        )

    lines.extend(
        [
            "",
            "## Scenario-specific shortlist",
            "",
            f"For each scenario, the top {top_n} suppliers are ranked by theta (ascending), with CCR efficiency used as a tie-breaker.",
            "",
        ]
    )

    for scenario in SCENARIO_LABELS:
        subset = (
            scenario_df.filter((pl.col("scenario") == scenario) & (pl.col("scenario_potential_rank") <= top_n))
            .sort("scenario_potential_rank")
        )
        if subset.height == 0:
            continue
        lines.append(f"### {SCENARIO_LABELS[scenario]}")
        for row in subset.to_dicts():
            lines.append(
                f"- Rank {row['scenario_potential_rank']}: Supplier {row['supplier']} "
                f"(theta={row['theta']:.3f}, CCR={row['ccr_efficiency']:.3f}) — "
                f"main improvement focus: {row['biggest_gap_criterion']} "
                f"({row['biggest_gap_real']:.3f} {row['biggest_gap_unit']})"
            )
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def _svg_escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def _radar_points(values: list[float], cx: float, cy: float, radius: float) -> list[tuple[float, float]]:
    points = []
    count = len(values)
    for i, value in enumerate(values):
        angle = -math.pi / 2 + (2 * math.pi * i / count)
        r = radius * max(0.0, min(1.0, value))
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return points


def _polygon(points: list[tuple[float, float]]) -> str:
    return " ".join(f"{x:.2f},{y:.2f}" for x, y in points)


def _write_svg_radar_grid(parts: list[str], cx: float, cy: float, radius: float) -> None:
    for scale in [0.25, 0.5, 0.75, 1.0]:
        pts = _radar_points([scale] * 5, cx, cy, radius)
        parts.append(f'<polygon points="{_polygon(pts)}" fill="none" stroke="#d9e2ec" stroke-width="1"/>')
    label_points = _radar_points([1.12] * 5, cx, cy, radius)
    axis_points = _radar_points([1.0] * 5, cx, cy, radius)
    for (x, y), (lx, ly), label in zip(axis_points, label_points, RADAR_LABELS):
        parts.append(f'<line x1="{cx:.2f}" y1="{cy:.2f}" x2="{x:.2f}" y2="{y:.2f}" stroke="#e5e7eb" stroke-width="1"/>')
        parts.append(
            f'<text x="{lx:.2f}" y="{ly:.2f}" font-family="Arial, Helvetica, sans-serif" font-size="10" '
            f'fill="#475569" text-anchor="middle" dominant-baseline="middle">{_svg_escape(label)}</text>'
        )


def _render_radar_svg(
    rows: list[dict[str, object]],
    output_path: Path,
    title: str,
    rank_key: str,
    highlight_top_n: int | None,
) -> None:
    if not rows:
        return
    cols = 3
    cell_w, cell_h = 310, 285
    margin_top = 62
    nrows = math.ceil(len(rows) / cols)
    width = cols * cell_w
    height = margin_top + nrows * cell_h + 20
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{width / 2:.2f}" y="30" font-family="Arial, Helvetica, sans-serif" font-size="20" '
        f'font-weight="700" fill="#102a43" text-anchor="middle">{_svg_escape(title)}</text>',
    ]

    for idx, row in enumerate(rows):
        col = idx % cols
        grid_row = idx // cols
        x0 = col * cell_w
        y0 = margin_top + grid_row * cell_h
        cx = x0 + cell_w / 2
        cy = y0 + 120
        radius = 70
        rank = int(row.get(rank_key) or 999)
        highlighted = highlight_top_n is not None and rank <= highlight_top_n
        stroke = "#1d4ed8" if highlighted else "#64748b"
        fill = "#60a5fa" if highlighted else "#cbd5e1"
        opacity = "0.32" if highlighted else "0.14"
        width_px = "2.4" if highlighted else "1.3"

        _write_svg_radar_grid(parts, cx, cy, radius)
        values = [float(row[col_name] or 0.0) for col_name in NORM_COLS]
        pts = _radar_points(values, cx, cy, radius)
        parts.append(f'<polygon points="{_polygon(pts)}" fill="{fill}" fill-opacity="{opacity}" stroke="{stroke}" stroke-width="{width_px}"/>')

        supplier = row["supplier"]
        title_text = f"Supplier {supplier} | rank {rank}"
        subtitle = f"CCR={float(row['ccr_efficiency']):.3f}, theta={float(row['theta']):.3f}"
        gap = f"{row['biggest_gap_criterion']}: {float(row['biggest_gap_real']):.3f} {row['biggest_gap_unit']}"
        parts.append(
            f'<text x="{cx:.2f}" y="{y0 + 226:.2f}" font-family="Arial, Helvetica, sans-serif" font-size="13" '
            f'font-weight="700" fill="#102a43" text-anchor="middle">{_svg_escape(title_text)}</text>'
        )
        parts.append(
            f'<text x="{cx:.2f}" y="{y0 + 245:.2f}" font-family="Arial, Helvetica, sans-serif" font-size="11" '
            f'fill="#475569" text-anchor="middle">{_svg_escape(subtitle)}</text>'
        )
        parts.append(
            f'<text x="{cx:.2f}" y="{y0 + 263:.2f}" font-family="Arial, Helvetica, sans-serif" font-size="11" '
            f'fill="#475569" text-anchor="middle">{_svg_escape(gap)}</text>'
        )

    parts.append("</svg>")
    output_path.write_text("\n".join(parts), encoding="utf-8")
    _svg_to_png(output_path)


def _svg_to_png(svg_path: Path) -> None:
    converter = shutil.which("rsvg-convert")
    if not converter:
        return
    subprocess.run([converter, str(svg_path), "-o", str(svg_path.with_suffix(".png"))], check=True)


def write_radar_assets(radar_df: pl.DataFrame, top_n: int = 3) -> None:
    balanced = radar_df.filter(pl.col("scenario") == "balanced_improvement").sort("baseline_potential_rank")
    _render_radar_svg(
        balanced.to_dicts(),
        ASSET_DIR / "report_baseline_potential_radar.svg",
        "Baseline potential: Balanced-scenario improvement shapes",
        rank_key="baseline_potential_rank",
        highlight_top_n=top_n,
    )
    _render_radar_svg(
        balanced.to_dicts(),
        ASSET_DIR / "appendix_baseline_potential_radar_all.svg",
        "Appendix: baseline potential radar, all inefficient suppliers",
        rank_key="baseline_potential_rank",
        highlight_top_n=None,
    )

    for scenario, label in SCENARIO_LABELS.items():
        scenario_rows = radar_df.filter(pl.col("scenario") == scenario).sort("scenario_potential_rank")
        top_rows = scenario_rows.filter(pl.col("scenario_potential_rank") <= top_n)
        _render_radar_svg(
            top_rows.to_dicts(),
            ASSET_DIR / f"report_scenario_top_potential_{scenario}.svg",
            f"{label}: top potential suppliers",
            rank_key="scenario_potential_rank",
            highlight_top_n=top_n,
        )
        _render_radar_svg(
            scenario_rows.to_dicts(),
            ASSET_DIR / f"appendix_scenario_potential_{scenario}_all.svg",
            f"Appendix: {label} scenario, all inefficient suppliers",
            rank_key="scenario_potential_rank",
            highlight_top_n=None,
        )


def main(generate_plots: bool = True, top_n: int = 3) -> int:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    targets, _eff = load_outputs()
    baseline_df = add_baseline_potential_fields(targets)
    scenario_df = build_scenario_potential_table(targets, top_n=top_n)
    radar_df = build_radar_source_table(scenario_df, baseline_df)

    baseline_df.write_csv(ASSET_DIR / "report_baseline_potential.csv")
    scenario_df.write_csv(ASSET_DIR / "report_scenario_potential.csv")
    radar_df.write_csv(ASSET_DIR / "report_radar_source.csv")
    scenario_df.write_csv(ASSET_DIR / "appendix_scenario_potential_all.csv")
    radar_df.write_csv(ASSET_DIR / "appendix_radar_source_all.csv")
    write_business_summary_markdown(
        baseline_df=baseline_df,
        scenario_df=scenario_df,
        path=ASSET_DIR / "report_potential_summary.md",
        top_n=top_n,
    )
    if generate_plots:
        write_radar_assets(radar_df, top_n=top_n)
    print(f"Wrote potential-analysis outputs to {ASSET_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(generate_plots=True, top_n=3))
