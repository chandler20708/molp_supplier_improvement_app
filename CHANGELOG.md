# Changelog

## 2026-05-07 — Scenario Interpretation Refactor

### Changed

- Refactored page 3 from a selected-supplier Scenario Simulator into a stakeholder-facing Scenario Interpretation page.
- Added a Balanced base-case table covering all CCR-inefficient suppliers, their main development need, raw improvement amounts, theta, weighted normalised burden, and leading benchmark peer.
- Added a four-scenario interpretation table showing, for each predefined scenario, the inefficient supplier with the largest weighted normalised improvement burden, the driving criterion, benchmark peer, and managerial interpretation.
- Kept selected-supplier target charts and radar as an optional drill-down rather than the main page content.
- Kept live custom MOLP secondary inside an optional expander and only available when the optional optimiser stack is detected.
- Added transform helpers for inefficient-supplier filtering, base-case summaries, scenario burden summaries, and scenario-specific weighted criterion interpretation.
- Expanded the smoke test to verify base-case and scenario interpretation tables.
- Updated README and implementation notes to describe the Scenario Interpretation workflow.

### Method Boundaries

- MCDA and DEA remain upstream inputs.
- MOLP remains the scenario-specific target-setting layer.
- Customer service remains a strategic overlay, not a MOLP-optimised target.
- Peer weights remain benchmark intensities, not probabilities or order-allocation shares.
- Purchase remains commercial scale/context, not a direct supplier-controlled improvement action.

### Validation

- `./../.venv/bin/python -m compileall .` passed from the app root.
- `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 scripts/smoke_test_app_data.py` passed from the app root.

### Remaining Limitations

- Weighted normalised improvement burden is an interpretation layer based on precomputed target movements and scenario weights; it is not a new optimisation model.
- Browser-level visual regression testing was not added in this pass.
