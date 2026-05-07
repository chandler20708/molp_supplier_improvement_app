# Supplier Improvement Cockpit — Streamlit MVP v7 Scenario Interpretation

This bundle implements the Streamlit MVP as a **native multipage app**.

The app is intentionally framed as a **Post-DEA MOLP supplier improvement dashboard**:

- MCDA scores are imported as upstream strategic attractiveness evidence.
- DEA CCR efficiency is imported as upstream efficiency diagnosis.
- MOLP targets, peer weights, payoff tables, and sensitivity outputs drive the decision-support pages.

## 1. Run

This folder is prepared to be used as the GitHub repository root for Streamlit deployment. From this folder:

```bash
pip install -r requirements.txt
streamlit run app.py
```

Streamlit will show the native page navigation in the left sidebar.

## 2. Expected folder structure

```text
.
├── app.py
├── pages/
├── utils/
├── risk_supplier_improvement/
├── data/
│   ├── product_quality_scores.csv
│   ├── customer_service_scores.csv
│   ├── supplier_operational_inputs.csv
│   └── dea_ccr_efficiency.csv
└── outputs/team_ccr/
    ├── supplier_molp_inputs.csv
    ├── dea_team_ccr_efficiency.csv
    ├── dea_team_candidates.csv
    ├── molp_targets.csv
    ├── molp_peer_weights.csv
    ├── molp_payoff_table.csv
    ├── sensitivity_weight_summary.csv
    ├── sensitivity_parameter_summary.csv
    ├── sensitivity_parameter_runs.csv
    └── sensitivity_parameter_peer_weights.csv
```

The loader also supports a flat testing folder where the CSVs are placed beside `app.py`.

## 2.1 GitHub / Streamlit Community Cloud deployment

Upload the contents of this folder as the repository root:

```text
app.py
requirements.txt
pages/
utils/
data/
outputs/team_ccr/
.streamlit/config.toml
```

Set the Streamlit entrypoint to:

```text
app.py
```

The deployment uses precomputed CSV outputs. Live custom MOLP is intentionally not installed by default because it requires Gurobi runtime/licence support; the app will keep that mode unavailable and use precomputed scenarios.

## 3. Pages

### 1. Portfolio Overview

Uses a **3D portfolio matrix**:

- x-axis: DEA CCR efficiency
- y-axis: MCDA product quality score
- z-axis: MCDA customer service score

The plot includes explicit zero/reference axes and floor projections to make the 3D position readable.

### 2. Supplier Deep Dive

Shows:

- observed baseline metrics grouped as strategic attractiveness, operational risk, and commercial/efficiency;
- selected-scenario MOLP target metrics;
- current-vs-target radar chart with hover information;
- normalised room-to-improve table;
- benchmark peer weights;
- conservative supplier-development recommendations with primary action, secondary action, benchmark interpretation, customer-service caution, and robustness caveat.

### 3. Scenario Interpretation

Answers two stakeholder questions with precomputed MOLP outputs:

1. **Baseline potential** — among CCR-inefficient suppliers, who is closest to the DEA efficient frontier.
2. **Scenario potential** — for each predefined scenario, which inefficient suppliers have the lowest theta, with CCR efficiency used as tie-breaker, and what their biggest actionable improvement gap is.

The Scenario story tab has a scenario selector, a prominent management read-out, and potential/gap visuals. Selected-supplier charts and live custom MOLP remain secondary tabs rather than the main page content.

Live custom optimisation requires:

- `polars`
- `gurobipy`
- a valid Gurobi licence
- the included `risk_supplier_improvement/` package

If Gurobi is unavailable, use precomputed scenarios for the demo. The deployment requirements intentionally omit `polars` and `gurobipy` so public Streamlit deployments do not expose a live mode that cannot solve.
The app checks optional live dependencies before exposing live controls. If live mode is unavailable, the page stays with precomputed scenario interpretation.

### 4. Sensitivity & Export

Shows robustness summaries, parameter perturbation outputs, peer stability, and filtered CSV downloads.
The page now gives a plain-language robustness verdict before the export section.

## 4. Notes for the team

- Do **not** say the app re-runs MCDA or DEA. It imports MCDA and DEA outputs.
- The live optimiser only re-runs the post-DEA MOLP layer.
- MOLP targets are improvement directions, not forecasts.
- Peer weights are composite frontier benchmark weights, not probabilities.
- Customer service is a strategic/service overlay in this app, not a MOLP-optimised target.
- Purchase is commercial scale/context, not a direct supplier-controlled improvement action.
- If live optimisation fails in class, use the precomputed scenario mode.

## 5. Main changes from the previous version

- Uses Streamlit native `pages/` navigation instead of manual routing inside `app.py`.
- Uses page-specific sidebar controls only.
- Replaces deprecated `use_container_width` with `width="stretch"`.
- Keeps product quality and customer service separate in the portfolio view.
- Adds a live custom MOLP mode while keeping the stable precomputed mode.
- Improves visual guidance, section labels, and interpretation boxes.
- Adds live optimiser availability checks and compact CSV column validation.
- Adds stakeholder-facing action guidance and robustness verdicts.
- Hotfixes chart-data preparation so radar and selected-scenario charts render for CCR-inefficient suppliers.
- Uses pandas-version-safe Styler mapping on the Supplier Deep Dive improvement table.
- Adds `streamlit_mvp_app/scripts/smoke_test_app_data.py` for lightweight app-data and chart-data checks.
- Refactors the Scenario page into a stakeholder-facing Scenario Interpretation page focused on cross-supplier tables and Toyota-style development language.
