# Supplier Improvement App UX Quick Review

Date: 2026-05-08  
Reviewer / research subject: single-user cognitive walkthrough by the project author/reviewer  
App reviewed: `supplier_improvement_molp/molp_supplier_improvement_app`

## Research Question

Can a stakeholder use the app to quickly understand each supplier, know what to do next, and think about suppliers in line with the report recommendation?

Target recommendation logic:

- Preferred strategic suppliers: H, B and A.
- Operational benchmarks: G and I.
- Primary development candidate: C, with late delivery as the priority improvement area.
- Conditional development candidates: F, K and D.
- Lower-priority suppliers: E, J and L.

## Method

This was a lightweight UX research pass using:

- Cognitive walkthrough: "I am a stakeholder opening the app. Can I understand the portfolio and decide what to do?"
- Heuristic review: clarity, decision hierarchy, consistency, actionability, and trust.
- Rendered app check in Streamlit on `http://localhost:8563`.
- Data/logic check using the app's loaded CSVs and recommendation functions.

This is not a formal user study. It is a fast expert review suitable for deciding what to change next.

## Overall Finding

The app is directionally useful, but it is not yet strong enough as a stakeholder-facing decision tool.

It has the right analytical ingredients: portfolio diagnosis, supplier deep dive, scenario potential, benchmark peers, and robustness/export. The Scenario Interpretation page is the strongest page because it directly answers "who has the best development potential and why?"

The main problem is decision communication. The app does not open with the final management recommendation, and some pages tell different stories about the same supplier. Most importantly, the Scenario page says Supplier C's balanced-scenario bottleneck is late delivery, but the Supplier Deep Dive page presents price renegotiation as C's primary action. That conflicts with the report recommendation and could mislead a stakeholder.

## What Worked

### 1. Scenario Interpretation gives the clearest management answer

The Scenario page successfully identifies Supplier C as the strongest development candidate under all four scenarios. Under Balanced it states:

- Supplier C is rank 1.
- MOLP target distance is 0.311.
- Bottleneck is late delivery.
- Biggest gap is 2.695 percentage points.

This matches the report's core development logic for C better than the deep-dive page does.

### 2. Deep Dive supports individual supplier understanding

Selecting Supplier C updates the page correctly and shows:

- Portfolio status: Development candidate.
- CCR efficiency: 0.642.
- Product quality: 0.436.
- Customer service: 0.573.
- Target late delivery: 3.3% versus current 6.0%.
- Benchmark peers: B, A and H.

This is useful for explaining why C should be developed and which efficient suppliers should guide improvement.

### 3. The app separates MCDA, DEA and MOLP roles

The app repeatedly warns that:

- MCDA and DEA are imported upstream evidence.
- DEA efficiency is not the same as strategic desirability.
- Peer weights are benchmark intensities, not order shares.
- Customer service is a strategic overlay, not MOLP-optimised.

This is good because it prevents common method misinterpretations.

## What Did Not Work

### 1. The first screen is not stakeholder-facing

The app opens on a generic landing page with navigation cards and an "Expected project structure" code block. For a stakeholder, this is not the first question.

The first screen should answer:

- Who should we prefer?
- Who should we develop?
- Who should we deprioritise?
- What is the next action?

Current landing page content is more useful for deployment/debugging than decision-making.

### 2. Supplier categories do not fully match the report recommendation

The app's automated portfolio statuses are median-threshold based. This creates mismatches with the final recommendation:

- I is shown as `Deprioritise`, but the recommendation treats I as an operational benchmark.
- F and K are shown as `Deprioritise`, but the recommendation treats them as conditional development candidates.
- L is shown as `Development candidate`, but the recommendation says L should be lower priority.

This makes the app look less aligned with the report even when the underlying data can support the report logic.

### 3. Deep Dive recommendations can conflict with scenario interpretation

For Supplier C under Balanced:

- Scenario page: bottleneck is late delivery.
- Deep Dive page: primary action is price renegotiation; late delivery is secondary.

This happens because `utils/recommendations.py` orders improvement checks by a fixed sequence: price, late delivery, shipping errors, lead time, then product quality. It does not use the largest normalised gap or scenario bottleneck to choose the primary action.

Stakeholder impact: a manager could leave the Deep Dive thinking C is mainly a price case, while the report says C is mainly a late-delivery development case.

### 4. Page names and labels weaken the story

The navigation still says "Scenario Simulator", but the page title says "Scenario Interpretation". Since the live optimiser is secondary and often unavailable, "Simulator" overpromises. "Scenario Interpretation" is more accurate.

The sidebar label "app" is also not meaningful to stakeholders. It should be "Executive Summary" or "Decision Summary".

### 5. Plotly deprecation warnings are visible in the app

Multiple chart areas show:

> The keyword arguments have been deprecated and will be removed in a future release. Use config instead to specify Plotly configuration options.

This reduces trust. Stakeholders should not see implementation warnings.

### 6. The 3D portfolio chart may be cognitively heavy

The 3D matrix is useful for analytical exploration, but it is not the fastest way to understand what to do. It requires users to reason across axes, depth, table, and status legend.

For a stakeholder, a 2D decision matrix or ranked action table should come before the 3D chart.

## Stakeholder Task Assessment

Task: "Open the app and decide how to think about suppliers."

Result: Partially successful.

What the stakeholder can learn:

- H, B and A are strong strategic partners if they inspect portfolio/deep-dive statuses.
- C is the best development candidate if they inspect Scenario Interpretation.
- G is efficient but strategically weak.
- Supplier-level targets and peers are available.

What is difficult:

- The final recommendation is not visible as a single management summary.
- The user must assemble the answer across several pages.
- Some app classifications conflict with the report recommendation.
- Deep Dive primary actions may not match scenario bottlenecks.

## Priority UX Fixes

1. Replace the landing page with an executive decision summary.
2. Add a recommendation-tier field that directly encodes the report conclusion: strategic partner, operational benchmark, primary development, conditional development, lower priority.
3. Make Deep Dive primary action use the scenario bottleneck / largest normalised gap, not fixed metric order.
4. Rename navigation from "Scenario Simulator" to "Scenario Interpretation".
5. Remove visible Plotly warnings by updating chart calls to use `config=`.
6. Add a simple "What should we do next?" table before advanced charts.

## Bottom Line

The app works as an analytical dashboard after dependencies are installed, but it does not yet work fully as a stakeholder decision cockpit. The main change should be to bring the report recommendation into the app's information architecture, so the first screen and every supplier page reinforce the same decision story.
