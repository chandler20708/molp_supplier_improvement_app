from __future__ import annotations

import pandas as pd

from .recommendation_tiers import supplier_management_note


ACTION_TEXT = {
    "late": "agree a delivery-reliability improvement plan focused on late delivery.",
    "error": "reduce shipping errors through process checks and dispatch controls.",
    "lead": "shorten lead time to reduce stock-availability risk.",
    "price": "renegotiate the unit-price pathway while protecting supplier capability.",
    "quality": "close the product-quality capability gap with a joint improvement plan.",
}


def _gap_ratio(current_value, improvement_value) -> float:
    if pd.isna(current_value) or pd.isna(improvement_value):
        return 0.0
    current = float(current_value)
    improvement = float(improvement_value)
    if abs(current) <= 1e-12:
        return 0.0
    return max(0.0, improvement / current)


def _top_improvement_actions(current: pd.Series, target: pd.Series | None) -> list[tuple[str, str]]:
    if target is None:
        return []

    checks = [
        ("late", "delivery reliability", current.get("late_delivery_pct"), target.get("late_improvement")),
        ("error", "shipping accuracy", current.get("shipping_error_pct"), target.get("error_improvement")),
        ("lead", "lead-time responsiveness", current.get("lead_time_days"), target.get("lead_improvement")),
        ("price", "cost competitiveness", current.get("avg_unit_price"), target.get("price_improvement")),
        ("quality", "product quality", current.get("product_quality_score"), target.get("quality_gain")),
    ]
    ranked = [
        (label, ACTION_TEXT[key], _gap_ratio(current_value, improvement_value))
        for key, label, current_value, improvement_value in checks
    ]
    ranked = [item for item in ranked if item[2] > 1e-9]
    ranked.sort(key=lambda item: item[2], reverse=True)
    return [(label, text) for label, text, _score in ranked]


def _benchmark_interpretation(peer_weights_df: pd.DataFrame, supplier: str, scenario: str) -> str:
    if peer_weights_df is None or peer_weights_df.empty:
        return "No benchmark peer weights are available for this supplier/scenario."
    peers = peer_weights_df[(peer_weights_df["supplier"] == supplier) & (peer_weights_df["scenario"] == scenario)].copy()
    if peers.empty:
        return "No benchmark peer weights are available for this supplier/scenario."
    peers = peers.sort_values("lambda_value", ascending=False)
    dominant = peers.iloc[0]
    others = ", ".join(str(x) for x in peers["peer_supplier"].iloc[1:3].tolist())
    suffix = f" Secondary references: {others}." if others else ""
    return (
        f"Use Supplier {dominant['peer_supplier']} as the leading frontier benchmark "
        f"(lambda {float(dominant['lambda_value']):.2f}).{suffix} Peer weights are composite benchmark contributions, not probabilities or order shares."
    )


def generate_recommendation_summary(
    current: pd.Series,
    target: pd.Series | None,
    peer_weights_df: pd.DataFrame,
    supplier: str,
    scenario: str,
    robustness_caveat: str | None = None,
) -> dict[str, str]:
    actions = _top_improvement_actions(current, target)
    status = str(current.get("portfolio_status", ""))
    if actions:
        primary = f"Primary action: {actions[0][1]}"
        secondary = f"Secondary action: {actions[1][1]}" if len(actions) > 1 else "Secondary action: monitor the remaining scorecard dimensions during the supplier-development review."
    elif "Strategic" in status:
        primary = "Primary action: retain and deepen the supplier partnership; no material MOLP improvement gap is visible under this scenario."
        secondary = "Secondary action: keep product quality and customer service under periodic review."
    elif "Tactical" in status:
        primary = "Primary action: use selectively while monitoring strategic attractiveness."
        secondary = "Secondary action: avoid interpreting DEA efficiency as proof of overall supplier desirability."
    else:
        primary = "Primary action: review development feasibility before changing dependency; the selected scenario does not show a clear target movement."
        secondary = "Secondary action: inspect sensitivity and peer benchmarks before escalation."

    customer_service = current.get("customer_service_score")
    caution = "Customer-service overlay: no special caution from the imported score."
    if pd.notna(customer_service) and float(customer_service) < 0.55:
        caution = "Customer-service overlay caution: imported service attractiveness is weak, so treat the MOLP target as operational guidance rather than a full relationship endorsement."

    purchase_note = "Commercial scale: purchase is preserved as a scale/context condition; it is not a direct supplier-controlled improvement instruction."
    management_note = supplier_management_note(supplier)
    caveat = robustness_caveat or "Robustness caveat: check Sensitivity & Export before presenting the recommendation as stable."
    return {
        "primary_action": primary,
        "secondary_action": secondary,
        "management_interpretation": management_note,
        "benchmark_interpretation": _benchmark_interpretation(peer_weights_df, supplier, scenario),
        "customer_service_caution": caution,
        "purchase_note": purchase_note,
        "robustness_caveat": caveat,
    }


def generate_recommendations(current: pd.Series, target: pd.Series | None, peer_weights_df: pd.DataFrame, supplier: str, scenario: str) -> list[str]:
    summary = generate_recommendation_summary(current, target, peer_weights_df, supplier, scenario)
    return list(summary.values())

    if peer_weights_df is not None and not peer_weights_df.empty:
        peers = peer_weights_df[(peer_weights_df["supplier"] == supplier) & (peer_weights_df["scenario"] == scenario)].copy()
        if not peers.empty:
            peers = peers.sort_values("lambda_value", ascending=False)
            dominant = peers.iloc[0]
            recs.append(f"Use Supplier {dominant['peer_supplier']} as the primary benchmark reference; its peer weight is {float(dominant['lambda_value']):.2f}.")
            if len(peers) > 1:
                others = ", ".join(str(x) for x in peers["peer_supplier"].iloc[1:3].tolist())
                if others:
                    recs.append(f"Use secondary peers ({others}) to interpret the target as a composite frontier benchmark, not a single-supplier imitation plan.")

    if not recs:
        status = current.get("portfolio_status", "")
        if "Strategic" in str(status):
            recs.append("Maintain as a strategic partner; no material MOLP improvement gap is visible under the selected scenario.")
        else:
            recs.append("No strong target movement is available for this supplier/scenario; review the scenario choice or inspect sensitivity outputs.")
    return recs
