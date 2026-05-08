from __future__ import annotations

import pandas as pd


RECOMMENDATION_TIERS = {
    "H": "Preferred strategic supplier",
    "B": "Preferred strategic supplier",
    "A": "Preferred strategic supplier",
    "G": "Operational benchmark",
    "I": "Operational benchmark",
    "C": "Primary development candidate",
    "F": "Conditional development candidate",
    "K": "Conditional development candidate",
    "D": "Conditional development candidate",
    "E": "Lower-priority supplier",
    "J": "Lower-priority supplier",
    "L": "Lower-priority supplier",
}

SUPPLIER_MANAGEMENT_NOTES = {
    "H": "Premium supplier. Retain as the strongest strategic quality-service partner.",
    "B": "Scalable sourcing partner and primary operational benchmark for inefficient suppliers.",
    "A": "Scalable sourcing partner with strong price-quality balance.",
    "G": "DEA-efficient operational benchmark, but too weak on strategic quality-service evidence to define the supplier standard.",
    "I": "DEA-efficient operational benchmark, but weaker strategic scores mean it should be monitored rather than treated as a preferred partner.",
    "C": "Strongest development candidate. Start with late delivery and use B, A and H as benchmark references.",
    "F": "Conditional development case. Develop only if shipping errors and service weakness can be reduced.",
    "K": "Conditional development case focused mainly on lead-time improvement.",
    "D": "Conditional development case. It is close to the frontier but remains constrained by late delivery.",
    "E": "Lower priority. Monitor, renegotiate or use selectively rather than prioritising immediate development investment.",
    "J": "Lower priority. Monitor, renegotiate or use selectively rather than prioritising immediate development investment.",
    "L": "Lower priority. Use selectively or monitor before committing development resources.",
}

TIER_ACTIONS = {
    "Preferred strategic supplier": "Retain and deepen partnership.",
    "Operational benchmark": "Use as an operational reference, but do not set the strategic supplier standard.",
    "Primary development candidate": "Create the first supplier-development plan.",
    "Conditional development candidate": "Develop only with clear improvement conditions and review gates.",
    "Lower-priority supplier": "Monitor, renegotiate or use selectively.",
}

TIER_ORDER = {
    "Preferred strategic supplier": 1,
    "Operational benchmark": 2,
    "Primary development candidate": 3,
    "Conditional development candidate": 4,
    "Lower-priority supplier": 5,
}

SUPPLIER_ORDER = {
    "H": 1,
    "B": 2,
    "A": 3,
    "G": 4,
    "I": 5,
    "C": 6,
    "F": 7,
    "K": 8,
    "D": 9,
    "E": 10,
    "J": 11,
    "L": 12,
}


def recommendation_tier(supplier: object) -> str:
    key = str(supplier).strip().upper()
    return RECOMMENDATION_TIERS.get(key, "Unclassified")


def supplier_management_note(supplier: object) -> str:
    key = str(supplier).strip().upper()
    return SUPPLIER_MANAGEMENT_NOTES.get(key, "Review supplier evidence before making a management recommendation.")


def tier_action(tier: object) -> str:
    return TIER_ACTIONS.get(str(tier), "Review before action.")


def add_recommendation_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty or "supplier" not in df.columns:
        return df
    out = df.copy()
    out["recommendation_tier"] = out["supplier"].map(recommendation_tier)
    out["management_note"] = out["supplier"].map(supplier_management_note)
    out["recommended_action"] = out["recommendation_tier"].map(tier_action)
    out["recommendation_order"] = out["recommendation_tier"].map(TIER_ORDER).fillna(99).astype(int)
    out["supplier_recommendation_order"] = out["supplier"].map(SUPPLIER_ORDER).fillna(99).astype(int)
    return out
