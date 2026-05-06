from __future__ import annotations

import csv
import html
import shutil
import subprocess
from collections import defaultdict
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BASE_DIR / "doc" / "report2" / "assets"
CCR_DIR = BASE_DIR / "outputs" / "team_ccr"

SCENARIO_LABELS = {
    "balanced_improvement": "Balanced",
    "cost_led_development": "Cost-led",
    "delivery_reliability_led": "Delivery-led",
    "product_quality_led": "Quality-led",
}

TARGET_COLUMNS = [
    "price_improvement",
    "late_improvement",
    "error_improvement",
    "lead_improvement",
    "quality_gain",
]

EFF_GREEN = "#2f855a"
WARN_ORANGE = "#d97706"
BLUE = "#2b6cb0"
INK = "#102a43"
MUTED = "#52616b"
GRID = "#d9e2ec"
BG = "#ffffff"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def f(row: dict[str, str], key: str) -> float:
    value = row.get(key, "")
    return 0.0 if value == "" else float(value)


def fmt(value: float, digits: int = 3) -> str:
    return f"{value:.{digits}f}"


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def inefficient_suppliers(eff_rows: list[dict[str, str]], threshold: float = 0.999999) -> list[str]:
    return [row["Supplier"] for row in eff_rows if f(row, "CCR_Efficiency") < threshold]


def efficient_suppliers(eff_rows: list[dict[str, str]], threshold: float = 0.999999) -> list[str]:
    return [row["Supplier"] for row in eff_rows if f(row, "CCR_Efficiency") >= threshold]


class Svg:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
            "<defs>",
            '<marker id="arrow" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto" markerUnits="strokeWidth">',
            f'<path d="M0,0 L0,6 L8,3 z" fill="{MUTED}" />',
            "</marker>",
            "</defs>",
            f'<rect width="{width}" height="{height}" fill="{BG}"/>',
        ]

    def text(self, x: float, y: float, value: object, size: int = 14, fill: str = INK,
             anchor: str = "start", weight: str = "400") -> None:
        self.parts.append(
            f'<text x="{x:.2f}" y="{y:.2f}" font-family="Arial, Helvetica, sans-serif" '
            f'font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{esc(value)}</text>'
        )

    def rect(self, x: float, y: float, w: float, h: float, fill: str,
             stroke: str = "none", rx: float = 0, sw: float = 1) -> None:
        self.parts.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" rx="{rx:.2f}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'
        )

    def line(self, x1: float, y1: float, x2: float, y2: float,
             stroke: str = GRID, sw: float = 1, arrow: bool = False) -> None:
        marker = ' marker-end="url(#arrow)"' if arrow else ""
        self.parts.append(
            f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
            f'stroke="{stroke}" stroke-width="{sw}"{marker}/>'
        )

    def save(self, path: Path) -> None:
        self.parts.append("</svg>")
        path.write_text("\n".join(self.parts), encoding="utf-8")


def svg_to_png(svg_path: Path) -> None:
    converter = shutil.which("rsvg-convert")
    if not converter:
        print(f"Skipped PNG render because rsvg-convert is not installed: {svg_path.name}")
        return
    subprocess.run([converter, str(svg_path), "-o", str(svg_path.with_suffix(".png"))], check=True)


def save_svg(svg: Svg, name: str) -> None:
    svg_path = OUTPUT_DIR / f"{name}.svg"
    svg.save(svg_path)
    svg_to_png(svg_path)


def plot_workflow() -> None:
    svg = Svg(1180, 260)
    nodes = [
        ("Supplier data\nprice, delivery, quality", 35, 88),
        ("Efficient benchmark\nsuppliers from DEA", 205, 88),
        ("Feasible improvement\ntargets", 375, 88),
        ("Criterion scaling\npayoff table", 545, 88),
        ("Business-priority\nscenario weights", 715, 88),
        ("Preferred compromise\ntarget", 885, 88),
        ("Improvement targets\nand benchmark peers", 1040, 88),
    ]

    for i in range(len(nodes) - 1):
        _, x1, y1 = nodes[i]
        _, x2, y2 = nodes[i + 1]
        svg.line(x1 + 135, y1 + 38, x2 - 10, y2 + 38, stroke=MUTED, sw=2, arrow=True)

    for label, x, y in nodes:
        svg.rect(x, y, 135, 76, fill="#f8fafc", stroke=GRID, rx=8, sw=1.2)
        for j, line in enumerate(label.split("\n")):
            svg.text(x + 67.5, y + 32 + j * 17, line, size=12, anchor="middle", weight="700")

    save_svg(svg, "molp_workflow")


def write_scenario_summary(targets: list[dict[str, str]], ineff: list[str]) -> None:
    rows_out = []

    for scenario, label in SCENARIO_LABELS.items():
        rows = [row for row in targets if row["scenario"] == scenario and row["supplier"] in ineff]
        if not rows:
            continue

        rows_out.append({
            "Scenario": label,
            "Price": fmt(sum(f(row, "price_improvement") for row in rows) / len(rows), 3),
            "Late": fmt(sum(f(row, "late_improvement") for row in rows) / len(rows), 3),
            "Error": fmt(sum(f(row, "error_improvement") for row in rows) / len(rows), 3),
            "Lead": fmt(sum(f(row, "lead_improvement") for row in rows) / len(rows), 3),
            "Quality": fmt(sum(f(row, "quality_gain") for row in rows) / len(rows), 3),
        })

    write_csv(OUTPUT_DIR / "report_molp_scenario_summary.csv", rows_out)


def write_appendix_targets(targets: list[dict[str, str]], ineff: list[str]) -> None:
    rows_out = []

    for row in targets:
        if row["supplier"] not in ineff:
            continue
        rows_out.append({
            "Supplier": row["supplier"],
            "Scenario": SCENARIO_LABELS.get(row["scenario"], row["scenario"]),
            "Theta": fmt(f(row, "theta"), 3),
            "Price improvement": fmt(f(row, "price_improvement"), 3),
            "Late improvement": fmt(f(row, "late_improvement"), 3),
            "Error improvement": fmt(f(row, "error_improvement"), 3),
            "Lead improvement": fmt(f(row, "lead_improvement"), 3),
            "Quality gain": fmt(f(row, "quality_gain"), 3),
            "Purchase scale gain": fmt(f(row, "purchase_gain"), 3),
            "CCR efficiency": fmt(f(row, "ccr_efficiency"), 3),
        })

    write_csv(OUTPUT_DIR / "appendix_molp_scenario_targets.csv", rows_out)


def write_appendix_peer_weights(peers: list[dict[str, str]], ineff: list[str]) -> None:
    rows_out = []

    for row in peers:
        if row["supplier"] not in ineff:
            continue
        rows_out.append({
            "Supplier": row["supplier"],
            "Scenario": SCENARIO_LABELS.get(row["scenario"], row["scenario"]),
            "Benchmark peer": row["peer_supplier"],
            "Lambda": fmt(f(row, "lambda_value"), 4),
        })

    write_csv(OUTPUT_DIR / "appendix_molp_peer_weights.csv", rows_out)


def write_appendix_payoff(payoff: list[dict[str, str]], ineff: list[str]) -> None:
    keep = {"price", "late", "error", "lead", "quality", "ideal", "nadir"}
    rows_out = []

    for row in payoff:
        if row["supplier"] not in ineff or row["optimised_criterion"] not in keep:
            continue
        rows_out.append({
            "Supplier": row["supplier"],
            "Scenario": SCENARIO_LABELS.get(row["scenario"], row["scenario"]),
            "Optimised criterion": row["optimised_criterion"],
            "Price": fmt(f(row, "price"), 3),
            "Late": fmt(f(row, "late"), 3),
            "Error": fmt(f(row, "error"), 3),
            "Lead": fmt(f(row, "lead"), 3),
            "Quality objective": fmt(f(row, "quality"), 3),
        })

    write_csv(OUTPUT_DIR / "appendix_molp_payoff_table.csv", rows_out)


def write_appendix_sensitivity(
    weight_rows: list[dict[str, str]],
    param_rows: list[dict[str, str]],
    ineff: list[str],
) -> None:
    weight_out = []
    for row in weight_rows:
        if row["supplier"] not in ineff:
            continue

        ranges = {
            "price": f(row, "target_price_range"),
            "late": f(row, "target_late_range"),
            "error": f(row, "target_error_range"),
            "lead": f(row, "target_lead_range"),
            "quality": f(row, "target_quality_range"),
        }
        main_mover = max(ranges, key=ranges.get)

        weight_out.append({
            "Supplier": row["supplier"],
            "Theta min": fmt(f(row, "theta_min"), 3),
            "Theta max": fmt(f(row, "theta_max"), 3),
            "Robustness index": f'{f(row, "robustness_index_weight"):.6f}',
            "Main moving dimension": main_mover,
            "Price range": fmt(ranges["price"], 3),
            "Late range": fmt(ranges["late"], 3),
            "Error range": fmt(ranges["error"], 3),
            "Lead range": fmt(ranges["lead"], 3),
            "Quality range": fmt(ranges["quality"], 3),
        })

    write_csv(OUTPUT_DIR / "appendix_molp_weight_sensitivity.csv", weight_out)

    param_out = []
    for row in param_rows:
        if row["supplier"] not in ineff:
            continue
        param_out.append({
            "Supplier": row["supplier"],
            "Scenario": SCENARIO_LABELS.get(row["scenario"], row["scenario"]),
            "Theta min": fmt(f(row, "theta_min"), 3),
            "Theta max": fmt(f(row, "theta_max"), 3),
            "Robustness index": f'{f(row, "robustness_index_parameter"):.6f}',
            "Run count": row["run_count"],
        })

    write_csv(OUTPUT_DIR / "appendix_molp_parameter_sensitivity.csv", param_out)


def validate_outputs(
    targets: list[dict[str, str]],
    peers: list[dict[str, str]],
    payoff: list[dict[str, str]],
    weight_rows: list[dict[str, str]],
) -> None:
    target_cols = set(targets[0])
    forbidden = {"service_gain", "target_service_score", "current_service_score"}
    leaked = forbidden.intersection(target_cols)
    if leaked:
        raise ValueError(f"Old service columns found in molp_targets.csv: {sorted(leaked)}")

    scenarios = {row["scenario"] for row in targets}
    unknown_scenarios = scenarios.difference(SCENARIO_LABELS)
    if unknown_scenarios:
        raise ValueError(f"Unexpected scenario names in molp_targets.csv: {sorted(unknown_scenarios)}")

    payoff_cols = set(payoff[0])
    if "service" in payoff_cols:
        raise ValueError("Old service column found in molp_payoff_table.csv.")

    weight_cols = set(weight_rows[0])
    if "target_service_range" in weight_cols:
        raise ValueError("Old target_service_range column found in sensitivity_weight_summary.csv.")

    peer_names = sorted({row["peer_supplier"] for row in peers})
    print("Benchmark peers used:", ", ".join(peer_names))


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    targets = read_csv(CCR_DIR / "molp_targets.csv")
    peers = read_csv(CCR_DIR / "molp_peer_weights.csv")
    eff_rows = read_csv(CCR_DIR / "dea_team_ccr_efficiency.csv")
    payoff = read_csv(CCR_DIR / "molp_payoff_table.csv")
    weight_rows = read_csv(CCR_DIR / "sensitivity_weight_summary.csv")
    param_rows = read_csv(CCR_DIR / "sensitivity_parameter_summary.csv")

    validate_outputs(targets, peers, payoff, weight_rows)

    ineff = inefficient_suppliers(eff_rows)
    eff = efficient_suppliers(eff_rows)

    plot_workflow()
    write_scenario_summary(targets, ineff)
    write_appendix_targets(targets, ineff)
    write_appendix_peer_weights(peers, ineff)
    write_appendix_payoff(payoff, ineff)
    write_appendix_sensitivity(weight_rows, param_rows, ineff)

    print(f"CCR-efficient suppliers: {', '.join(eff)}")
    print(f"Suppliers requiring development: {', '.join(ineff)}")
    print(f"Wrote MOLP report assets to {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())