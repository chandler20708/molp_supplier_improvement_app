# Changelog

## 2026-05-07 — MOLP Target Distance Potential Metric

### Changed

- Updated supplier development potential to use unweighted normalised MOLP target distance `d`, not theta, CCR efficiency, or weighted scenario burden.
- Added the same post-solve `d` calculation to `solutions_to_frames()` so future MOLP target exports carry supplier potential fields directly.
- Added/used the derived fields `molp_target_distance`, `molp_potential_rank`, `bottleneck_gap`, `bottleneck_criterion`, and `norm_*_gap` in the app interpretation layer.
- Updated Scenario Interpretation so top-potential suppliers are selected by the lowest target distance under the selected scenario.
- Kept scenario weights inside the MOLP target-setting model only; the potential-distance metric is deliberately unweighted.
- Updated README, implementation notes, smoke checks, and report-output sync language to state that theta is target-quality context and CCR efficiency is DEA context.

### Validation

- `./.venv/bin/python -m compileall risk_supplier_improvement molp_supplier_improvement_app` passed from the modelling project root.
- `./.venv/bin/python -m risk_supplier_improvement.potential_analysis` regenerated potential outputs.
- `./.venv/bin/python -m risk_supplier_improvement.generate_report_assets` regenerated report assets.
- `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 scripts/smoke_test_app_data.py` passed from the app root.
- `/Library/Frameworks/Python.framework/Versions/3.11/bin/streamlit run app.py --server.headless true --server.port 8561` started successfully and was stopped after verification.

## 2026-05-07 — Scenario Interpretation Refactor

### Changed

- Refactored page 3 from a selected-supplier Scenario Simulator into a stakeholder-facing Scenario Interpretation page.
- Added a Balanced base-case table covering all CCR-inefficient suppliers, their main development need, raw improvement amounts, theta context, target distance, and leading benchmark peer.
- Added a four-scenario interpretation table showing, for each predefined scenario, the inefficient supplier with the lowest unweighted normalised MOLP target distance, the bottleneck criterion, benchmark peer, and managerial interpretation.
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
- `/Library/Frameworks/Python.framework/Versions/3.11/bin/streamlit run app.py --server.headless true --server.port 8561` started successfully and was stopped after verification.

## 2026-05-07 — Potential Analysis Layer

### Changed

- Synced the app Scenario Interpretation page to the new potential definitions.
- Baseline potential now ranks CCR-inefficient suppliers by unweighted normalised MOLP target distance under the Balanced scenario.
- Scenario potential now ranks CCR-inefficient suppliers by unweighted normalised MOLP target distance under the selected scenario.
- Bottleneck improvement gap is selected using the largest unweighted normalised criterion gap and reported in original business units.
- Added `risk_supplier_improvement/potential_analysis.py` to the deployable app package for consistency with the source modelling package.
- Added `total_real_improvement` as a derived output field in `risk_supplier_improvement/post_dea_molp.py`; this is a rough exported indicator, not the main potential ranking metric.

### Validation

- `./../.venv/bin/python -m compileall .` passed from the app root.
- `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 scripts/smoke_test_app_data.py` passed from the app root.
- `/Library/Frameworks/Python.framework/Versions/3.11/bin/streamlit run app.py --server.headless true --server.port 8561` started successfully and was stopped after verification.

### Remaining Limitations

- Browser-level visual regression testing was not added in this pass.

## 2026-05-07 — Scenario Interpretation Interaction Refinement

### Changed

- Added a scenario selector to the Scenario story section so stakeholders can focus on one predefined scenario at a time.
- Replaced the previously table-first scenario view with a prominent management read-out card that states the supplier, development burden, driving criterion, benchmark peer, and interpretation.
- Added cross-supplier burden and driving-criterion contribution bar charts so the page tells the scenario story visually before showing tables.
- Moved selected-supplier drill-down into a dedicated tab instead of an optional expander.
- Moved live custom MOLP and method notes into tabs so they remain accessible but secondary.
- Updated README and implementation notes for the scenario selector, tabbed drill-down, and visual-first scenario story.

### Validation

- `./../.venv/bin/python -m compileall .` passed from the app root.
- `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 scripts/smoke_test_app_data.py` passed from the app root.
