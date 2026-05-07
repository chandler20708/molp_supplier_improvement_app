from __future__ import annotations

"""Post-DEA supplier-development MOLP.

The module is organised in the same sequence as the formulation:
parameters, decision variables, constraints, payoff table, minimax preference
model, and export records. The public API at the bottom is intentionally small
so the CLI and sensitivity code can stay stable while the formulation evolves.
"""

from dataclasses import dataclass
from enum import Enum

import gurobipy as gp
import polars as pl
from gurobipy import GRB


# =============================================================================
# 1. Formulation Parameters
# =============================================================================


class CriterionSense(str, Enum):
    MINIMISE = "minimise"
    MAXIMISE = "maximise"


@dataclass(frozen=True)
class CriterionSpec:
    """One MOLP criterion in the order used by the formulation."""

    name: str
    column: str
    sense: CriterionSense
    current_key: str
    target_key: str
    improvement_key: str

    @property
    def is_desirable(self) -> bool:
        return self.sense == CriterionSense.MAXIMISE


@dataclass(frozen=True)
class OutputSpec:
    """Desirable output that must be preserved in the DEA feasible set."""

    name: str
    column: str
    current_key: str
    target_key: str
    gain_key: str


CRITERIA: tuple[CriterionSpec, ...] = (
    CriterionSpec(
        name="price",
        column="price",
        sense=CriterionSense.MINIMISE,
        current_key="current_price",
        target_key="target_price",
        improvement_key="price_improvement",
    ),
    CriterionSpec(
        name="late",
        column="late_pct",
        sense=CriterionSense.MINIMISE,
        current_key="current_late_pct",
        target_key="target_late_pct",
        improvement_key="late_improvement",
    ),
    CriterionSpec(
        name="error",
        column="error_pct",
        sense=CriterionSense.MINIMISE,
        current_key="current_error_pct",
        target_key="target_error_pct",
        improvement_key="error_improvement",
    ),
    CriterionSpec(
        name="lead",
        column="lead_days",
        sense=CriterionSense.MINIMISE,
        current_key="current_lead_days",
        target_key="target_lead_days",
        improvement_key="lead_improvement",
    ),
    CriterionSpec(
        name="quality",
        column="quality_score",
        sense=CriterionSense.MAXIMISE,
        current_key="current_quality_score",
        target_key="target_quality_score",
        improvement_key="quality_gain",
    ),
)

PRESERVED_OUTPUTS: tuple[OutputSpec, ...] = (
    OutputSpec(
        name="quality",
        column="quality_score",
        current_key="current_quality_score",
        target_key="target_quality_score",
        gain_key="quality_gain",
    ),
    OutputSpec(
        name="purchase",
        column="purchase",
        current_key="current_purchase",
        target_key="target_purchase",
        gain_key="purchase_gain",
    ),
)

CRITERIA_BY_NAME = {criterion.name: criterion for criterion in CRITERIA}
OUTPUTS_BY_NAME = {output.name: output for output in PRESERVED_OUTPUTS}

CRITERIA_COLUMNS = {criterion.name: criterion.column for criterion in CRITERIA}
MINIMISE_CRITERIA = {criterion.name for criterion in CRITERIA if criterion.sense == CriterionSense.MINIMISE}
MAXIMISE_CRITERIA = {criterion.name for criterion in CRITERIA if criterion.sense == CriterionSense.MAXIMISE}
OUTPUT_COLUMNS = [output.column for output in PRESERVED_OUTPUTS]

DEFAULT_SCENARIOS = {
    "balanced_improvement": {
        "price": 0.20,
        "late": 0.20,
        "error": 0.20,
        "lead": 0.20,
        "quality": 0.20,
    },
    "cost_led_development": {
        "price": 0.35,
        "late": 0.15,
        "error": 0.15,
        "lead": 0.10,
        "quality": 0.25,
    },
    "delivery_reliability_led": {
        "price": 0.10,
        "late": 0.30,
        "error": 0.25,
        "lead": 0.25,
        "quality": 0.10,
    },
    "product_quality_led": {
        "price": 0.10,
        "late": 0.15,
        "error": 0.10,
        "lead": 0.15,
        "quality": 0.50,
    },
}


@dataclass(frozen=True)
class MOLPRunConfig:
    """Scenario-level parameters for one supplier solve."""

    supplier: str
    scenario_name: str
    weights: dict[str, float]
    peer_suppliers: tuple[str, ...]
    rts: str = "CCR"
    tolerance: float = 1e-6

    @property
    def rts_label(self) -> str:
        return normalise_rts(self.rts)


@dataclass(frozen=True)
class SupplierDataset:
    """Numeric model data in a format that is fast and explicit to use in LPs."""

    suppliers: tuple[str, ...]
    values: dict[str, dict[str, float]]

    @classmethod
    def from_frame(cls, df: pl.DataFrame) -> "SupplierDataset":
        required_columns = {"supplier", *CRITERIA_COLUMNS.values(), "purchase"}
        missing = required_columns.difference(df.columns)
        if missing:
            raise ValueError(f"MOLP input is missing required columns: {sorted(missing)}")

        suppliers = tuple(str(value) for value in df["supplier"].to_list())
        values = {
            row["supplier"]: {
                column: float(row[column])
                for column in sorted(required_columns - {"supplier"})
            }
            for row in df.to_dicts()
        }
        return cls(suppliers=suppliers, values=values)

    def value(self, supplier: str, column: str) -> float:
        return self.values[supplier][column]


# =============================================================================
# 2. Decision Variables, Expressions, and Solution Records
# =============================================================================


@dataclass(frozen=True)
class PostDEASolution:
    supplier: str
    scenario: str
    rts: str
    theta: float
    active_criteria: tuple[str, ...]
    target_metrics: dict[str, float]
    current_metrics: dict[str, float]
    lambda_weights: dict[str, float]
    payoff_rows: list[dict[str, float | str]]


@dataclass(frozen=True)
class DecisionVariables:
    lambdas: gp.tupledict


@dataclass(frozen=True)
class ModelExpressions:
    """Positive target measures and signed minimisation objectives."""

    targets: dict[str, gp.LinExpr]
    objectives: dict[str, gp.LinExpr]


@dataclass(frozen=True)
class PayoffTable:
    rows: list[dict[str, float | str]]
    ideal: dict[str, float]
    nadir: dict[str, float]
    active_criteria: tuple[str, ...]


@dataclass(frozen=True)
class SolvedTarget:
    theta: float
    target_metrics: dict[str, float]
    lambda_weights: dict[str, float]


# =============================================================================
# 3. Helpers That Mirror the Formulation Vocabulary
# =============================================================================


def normalise_rts(rts: str) -> str:
    value = rts.upper()
    return "CCR" if value == "CRS" else value


def _current_metrics(data: SupplierDataset, supplier: str) -> dict[str, float]:
    metrics = {
        criterion.current_key: data.value(supplier, criterion.column)
        for criterion in CRITERIA
    }
    metrics["current_purchase"] = data.value(supplier, "purchase")
    return metrics


def _identity_target(current_metrics: dict[str, float]) -> dict[str, float]:
    return {
        criterion.target_key: current_metrics[criterion.current_key]
        for criterion in CRITERIA
    } | {"target_purchase": current_metrics["current_purchase"]}


def _positive_lambda_weights(
    variables: DecisionVariables,
    threshold: float = 1e-8,
) -> dict[str, float]:
    lambdas = variables.lambdas
    return {
        peer: float(lambdas[peer].X)
        for peer in lambdas.keys()
        if float(lambdas[peer].X) > threshold
    }


def _renormalise_weights(weights: dict[str, float], active_criteria: tuple[str, ...]) -> dict[str, float]:
    retained = {criterion: weights[criterion] for criterion in active_criteria}
    total = sum(retained.values())
    if total <= 0:
        raise ValueError("At least one active criterion must have a positive scenario weight.")
    return {criterion: value / total for criterion, value in retained.items()}


# =============================================================================
# 4. Model Builder: Decision Variables and Constraints
# =============================================================================


def _new_model(config: MOLPRunConfig, suffix: str) -> gp.Model:
    model = gp.Model(f"post_dea_{config.supplier}_{config.rts_label.lower()}_{suffix}")
    model.Params.OutputFlag = 0
    return model


def _add_decision_variables(model: gp.Model, config: MOLPRunConfig) -> DecisionVariables:
    return DecisionVariables(lambdas=model.addVars(config.peer_suppliers, lb=0.0, name="lambda"))


def _target_expression(data: SupplierDataset, variables: DecisionVariables, column: str) -> gp.LinExpr:
    return gp.quicksum(
        data.value(peer, column) * variables.lambdas[peer]
        for peer in variables.lambdas.keys()
    )


def _build_expressions(data: SupplierDataset, variables: DecisionVariables) -> ModelExpressions:
    target_expressions = {
        criterion.name: _target_expression(data, variables, criterion.column)
        for criterion in CRITERIA
    }
    target_expressions["purchase"] = _target_expression(data, variables, "purchase")

    objective_expressions = {
        criterion.name: -target_expressions[criterion.name] if criterion.is_desirable else target_expressions[criterion.name]
        for criterion in CRITERIA
    }
    return ModelExpressions(targets=target_expressions, objectives=objective_expressions)


def _add_weak_improvement_constraints(
    model: gp.Model,
    data: SupplierDataset,
    config: MOLPRunConfig,
    expressions: ModelExpressions,
) -> None:
    for criterion in CRITERIA:
        current_value = data.value(config.supplier, criterion.column)
        if criterion.sense == CriterionSense.MINIMISE:
            model.addConstr(expressions.targets[criterion.name] <= current_value, name=f"improve_{criterion.name}")
        else:
            model.addConstr(expressions.targets[criterion.name] >= current_value, name=f"preserve_{criterion.name}")


def _add_purchase_preservation_constraint(
    model: gp.Model,
    data: SupplierDataset,
    config: MOLPRunConfig,
    expressions: ModelExpressions,
) -> None:
    model.addConstr(
        expressions.targets["purchase"] >= data.value(config.supplier, "purchase"),
        name="preserve_purchase",
    )


def _add_returns_to_scale_constraint(
    model: gp.Model,
    config: MOLPRunConfig,
    variables: DecisionVariables,
) -> None:
    if config.rts_label == "VRS":
        model.addConstr(
            gp.quicksum(variables.lambdas[peer] for peer in variables.lambdas.keys()) == 1.0,
            name="convexity",
        )


def _build_feasible_set(
    data: SupplierDataset,
    config: MOLPRunConfig,
    suffix: str,
) -> tuple[gp.Model, DecisionVariables, ModelExpressions]:
    """Builds lambda variables and Omega_o exactly once for a solve."""

    model = _new_model(config, suffix=suffix)
    variables = _add_decision_variables(model, config)
    expressions = _build_expressions(data, variables)

    _add_weak_improvement_constraints(model, data, config, expressions)
    _add_purchase_preservation_constraint(model, data, config, expressions)
    _add_returns_to_scale_constraint(model, config, variables)

    return model, variables, expressions


# =============================================================================
# 5. Payoff Table: Single-Objective Solves, Ideal, and Nadir
# =============================================================================


def _solve_single_objective(
    data: SupplierDataset,
    config: MOLPRunConfig,
    criterion_name: str,
) -> dict[str, float]:
    model, _, expressions = _build_feasible_set(data, config, suffix=f"payoff_{criterion_name}")
    model.setObjective(expressions.objectives[criterion_name], GRB.MINIMIZE)
    model.optimize()

    if model.Status != GRB.OPTIMAL:
        raise RuntimeError(
            f"Single-objective payoff problem for supplier {config.supplier} "
            f"and criterion {criterion_name} failed with status {model.Status}."
        )

    return {
        criterion.name: float(expressions.objectives[criterion.name].getValue())
        for criterion in CRITERIA
    }


def _build_payoff_table(data: SupplierDataset, config: MOLPRunConfig) -> PayoffTable:
    single_objective_values: dict[str, dict[str, float]] = {}
    rows: list[dict[str, float | str]] = []

    for criterion in CRITERIA:
        objective_values = _solve_single_objective(data, config, criterion.name)
        single_objective_values[criterion.name] = objective_values
        rows.append({"optimised_criterion": criterion.name, **objective_values})

    ideal = {
        criterion.name: min(values[criterion.name] for values in single_objective_values.values())
        for criterion in CRITERIA
    }
    nadir = {
        criterion.name: max(values[criterion.name] for values in single_objective_values.values())
        for criterion in CRITERIA
    }
    active_criteria = tuple(
        criterion.name
        for criterion in CRITERIA
        if (nadir[criterion.name] - ideal[criterion.name]) > config.tolerance
    )

    rows.extend(
        [
            {"optimised_criterion": "ideal", **ideal},
            {"optimised_criterion": "nadir", **nadir},
        ]
    )
    return PayoffTable(rows=rows, ideal=ideal, nadir=nadir, active_criteria=active_criteria)


# =============================================================================
# 6. Preference Model: Weighted Minimax and Tie-Breaker
# =============================================================================


def _add_minimax_constraints(
    model: gp.Model,
    config: MOLPRunConfig,
    expressions: ModelExpressions,
    payoff_table: PayoffTable,
) -> tuple[gp.Var, dict[str, gp.LinExpr], dict[str, float]]:
    theta = model.addVar(lb=0.0, name="theta")
    active_weights = _renormalise_weights(config.weights, payoff_table.active_criteria)
    deviations: dict[str, gp.LinExpr] = {}

    for criterion_name in payoff_table.active_criteria:
        denominator = payoff_table.nadir[criterion_name] - payoff_table.ideal[criterion_name]
        deviation = (expressions.objectives[criterion_name] - payoff_table.ideal[criterion_name]) / denominator
        deviations[criterion_name] = deviation
        model.addConstr(active_weights[criterion_name] * deviation <= theta, name=f"minimax_{criterion_name}")

    return theta, deviations, active_weights


def _extract_target_metrics(expressions: ModelExpressions) -> dict[str, float]:
    metrics = {
        criterion.target_key: float(expressions.targets[criterion.name].getValue())
        for criterion in CRITERIA
    }
    metrics["target_purchase"] = float(expressions.targets["purchase"].getValue())
    return metrics


def _solve_minimax_target(
    data: SupplierDataset,
    config: MOLPRunConfig,
    payoff_table: PayoffTable,
) -> SolvedTarget:
    model, variables, expressions = _build_feasible_set(data, config, suffix="minimax")
    theta, deviations, active_weights = _add_minimax_constraints(model, config, expressions, payoff_table)

    model.setObjective(theta, GRB.MINIMIZE)
    model.optimize()

    if model.Status != GRB.OPTIMAL:
        raise RuntimeError(
            f"Minimax post-DEA model for supplier {config.supplier} under scenario "
            f"{config.scenario_name} failed with status {model.Status}."
        )

    theta_star = float(theta.X)

    model.addConstr(theta <= theta_star + config.tolerance, name="fix_theta")
    model.setObjective(
        gp.quicksum(active_weights[criterion] * deviations[criterion] for criterion in payoff_table.active_criteria),
        GRB.MINIMIZE,
    )
    model.optimize()

    if model.Status != GRB.OPTIMAL:
        raise RuntimeError(
            f"Tie-breaker post-DEA model for supplier {config.supplier} under scenario "
            f"{config.scenario_name} failed with status {model.Status}."
        )

    return SolvedTarget(
        theta=float(theta.X),
        target_metrics=_extract_target_metrics(expressions),
        lambda_weights=_positive_lambda_weights(variables),
    )


# =============================================================================
# 7. Solution Extraction and Public API
# =============================================================================


def _identity_solution(data: SupplierDataset, config: MOLPRunConfig, payoff_table: PayoffTable) -> PostDEASolution:
    current_metrics = _current_metrics(data, config.supplier)
    return PostDEASolution(
        supplier=config.supplier,
        scenario=config.scenario_name,
        rts=config.rts_label,
        theta=0.0,
        active_criteria=(),
        target_metrics=_identity_target(current_metrics),
        current_metrics=current_metrics,
        lambda_weights={config.supplier: 1.0} if config.supplier in config.peer_suppliers else {},
        payoff_rows=payoff_table.rows,
    )


def solve_post_dea_for_supplier(
    df: pl.DataFrame,
    supplier: str,
    scenario_name: str,
    weights: dict[str, float],
    peer_suppliers: list[str] | tuple[str, ...] | None = None,
    rts: str = "CCR",
    tolerance: float = 1e-6,
) -> PostDEASolution:
    """Solve the post-DEA weighted minimax MOLP for one supplier and scenario."""

    data = SupplierDataset.from_frame(df)
    if supplier not in data.suppliers:
        raise ValueError(f"Unknown supplier '{supplier}'.")

    allowed_peers = tuple(peer_suppliers) if peer_suppliers is not None else data.suppliers

    unknown_peers = sorted(set(allowed_peers).difference(data.suppliers))
    if unknown_peers:
        raise ValueError(f"Unknown peer suppliers: {unknown_peers}")

    if not allowed_peers:
        raise ValueError("At least one peer supplier is required.")

    config = MOLPRunConfig(
        supplier=supplier,
        scenario_name=scenario_name,
        weights=weights,
        peer_suppliers=allowed_peers,
        rts=rts,
        tolerance=tolerance,
    )
    payoff_table = _build_payoff_table(data, config)

    if not payoff_table.active_criteria:
        return _identity_solution(data, config, payoff_table)

    solved_target = _solve_minimax_target(data, config, payoff_table)
    return PostDEASolution(
        supplier=config.supplier,
        scenario=config.scenario_name,
        rts=config.rts_label,
        theta=solved_target.theta,
        active_criteria=payoff_table.active_criteria,
        target_metrics=solved_target.target_metrics,
        current_metrics=_current_metrics(data, config.supplier),
        lambda_weights=solved_target.lambda_weights,
        payoff_rows=payoff_table.rows,
    )


def solutions_to_frames(solutions: list[PostDEASolution]) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    target_rows: list[dict[str, object]] = []
    peer_rows: list[dict[str, object]] = []
    payoff_rows: list[dict[str, object]] = []

    for solution in solutions:
        row: dict[str, object] = {
            "supplier": solution.supplier,
            "scenario": solution.scenario,
            "rts": solution.rts,
            "theta": solution.theta,
            "active_criteria": ",".join(solution.active_criteria),
        }
        row.update(solution.current_metrics)
        row.update(solution.target_metrics)

        for criterion in CRITERIA:
            current_value = solution.current_metrics[criterion.current_key]
            target_value = solution.target_metrics[criterion.target_key]
            row[criterion.improvement_key] = (
                target_value - current_value
                if criterion.is_desirable
                else current_value - target_value
            )
        row["total_real_improvement"] = sum(
            float(row[criterion.improvement_key])
            for criterion in CRITERIA
        )
        row["purchase_gain"] = solution.target_metrics["target_purchase"] - solution.current_metrics["current_purchase"]
        target_rows.append(row)

        for peer, value in solution.lambda_weights.items():
            peer_rows.append(
                {
                    "supplier": solution.supplier,
                    "scenario": solution.scenario,
                    "rts": solution.rts,
                    "peer_supplier": peer,
                    "lambda_value": value,
                }
            )

        for payoff_row in solution.payoff_rows:
            payoff_rows.append(
                {
                    "supplier": solution.supplier,
                    "scenario": solution.scenario,
                    "rts": solution.rts,
                    **payoff_row,
                }
            )

    return pl.DataFrame(target_rows), pl.DataFrame(peer_rows), pl.DataFrame(payoff_rows)
