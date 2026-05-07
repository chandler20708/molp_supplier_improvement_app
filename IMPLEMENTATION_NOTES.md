# Implementation Notes

## What each page should do

1. Portfolio Overview: diagnose the full supplier set. No scenario control is needed.
2. Supplier Deep Dive: choose supplier and scenario. Focus on target interpretation and improvement gaps.
3. Scenario Interpretation: answer cross-supplier stakeholder questions first, provide a visible scenario-specific management read-out, then offer selected-supplier and live MOLP drill-downs as secondary tabs.
4. Sensitivity & Export: judge robustness first, then filter outputs and download tables.

## Live optimiser behaviour

The live optimiser uses:

```python
from risk_supplier_improvement.post_dea_molp import solve_post_dea_for_supplier, solutions_to_frames
```

It constructs CCR-efficient peers from `dea_team_ccr_efficiency.csv`, normalises custom weights, and solves one supplier under scenario name `custom_live`.

`check_live_optimizer_available()` verifies imports, required functions, and required CSV columns without solving the model. If `polars`, `gurobipy`, the Gurobi licence, or the required inputs are unavailable, the app keeps live sliders hidden and uses precomputed scenarios only.

## Standalone GitHub deployment

The `streamlit_mvp_app/` folder is now self-contained for GitHub / Streamlit Community Cloud deployment. It includes:

- `data/` with imported MCDA and DEA input CSVs.
- `outputs/team_ccr/` with precomputed MOLP targets, peer weights, payoff, and sensitivity CSVs.
- `.streamlit/config.toml` for a consistent light theme.
- `.gitignore` for local Python, cache, and secret files.

Deploy this folder as the repository root and use `app.py` as the Streamlit entrypoint. The default deployment requirements intentionally omit `polars` and `gurobipy`, so live custom MOLP stays hidden unless a maintainer deliberately installs and licences the optional optimiser stack.

## UI design principles

- Keep sidebar controls page-specific.
- Use the 3D matrix only for portfolio diagnosis.
- Use radar immediately in the deep dive; do not ask the user to choose chart type.
- Use interpretation boxes to tell users what to do next.
- Use colour/highlight sparingly: blue for guidance, green for decision/action, orange for warnings.
- Treat customer service as a strategic overlay and purchase as commercial scale/context.
- Do not describe theta as DEA efficiency or peer weights as probabilities/order shares.
- CCR-efficient suppliers should be presented as benchmark/monitoring cases, not as suppliers needing the same target-improvement plan as inefficient suppliers.
- Baseline potential should rank CCR-inefficient suppliers by CCR efficiency descending, i.e. smallest frontier gap first.
- Scenario potential should rank CCR-inefficient suppliers by theta ascending, with CCR efficiency as tie-breaker.
- Biggest improvement gap should be selected by normalised gap size, then reported in original business units.
- Visuals on the Scenario page should show potential and biggest capability gap before detailed supplier charts.
- The Deep Dive improvement table uses `Styler.map` when available and falls back to `Styler.applymap` for older pandas versions.
- Run `streamlit_mvp_app/scripts/smoke_test_app_data.py` after chart-data changes.
