---
name: pycaret-automl
description: "Use when: building an end-to-end AutoML workflow with PyCaret from CSV, Excel, SQL exports, or business tables. Handles data profiling, cleaning, leakage checks, task routing, classification, regression, time series forecasting, clustering, anomaly detection, churn prediction, sales forecast, demand forecast, risk scoring, model comparison, tuning, explainability, drift monitoring, deployment handoff, metrics reporting, predictions, reproducibility, testing, publishing, audit evidence, production readiness, and handoff documentation."
argument-hint: "business question, data path, target column, forecast horizon, and desired deliverables"
license: MIT
metadata:
  openclaw:
    homepage: https://github.com/Ieer/OpenClaw-PWTInstaller/tree/main/panopticon/global-skills/pycaret-automl
    os:
      - win32
      - darwin
      - linux
    requires:
      anyBins:
        - python
---

# PyCaret AutoML

Run practical, business-facing AutoML workflows with PyCaret while keeping context use and model search cost controlled.

## When to Use

- Churn prediction, sales forecasting, demand planning, risk scoring, segmentation, anomaly detection, or tabular business prediction.
- CSV, Excel, SQL-exported tables, or bundled datasets need analysis, cleaning, modeling, metrics, predictions, and handoff notes.
- The user asks to improve model accuracy, reduce AutoML runtime, reduce token usage, or benchmark against sample data.

Do not use this skill for deep learning, computer vision, NLP fine-tuning, real-time serving infrastructure, or production MLOps platform design unless the PyCaret workflow is only one clearly bounded part of the request.

## Route

| Situation | Action |
| --------- | ------ |
| Target is categorical | Use classification |
| Target is continuous | Use regression |
| Outcome depends on time progression | Use time series forecasting |
| No label, but segmentation is needed | Use clustering |
| Need to surface suspicious or rare records | Use anomaly detection |

Load [./references/pycaret-module-map.md](./references/pycaret-module-map.md) only when module names, function names, setup options, or metrics are needed.

## Default Workflow

1. Clarify business decision, target, prediction timing, data path, metric, and deliverable.
2. Inspect schema, file size, row count, target distribution, and compact data-quality summaries before reading or printing large data.
3. Clean identifiers, leakage fields, numeric-like strings, duplicate rows, and categorical whitespace before `setup`.
4. Separate business feature engineering from PyCaret preprocessing; keep prediction-time feature availability explicit.
5. Start with a narrow candidate shortlist and a compute budget before tuning.
6. Tune only validated candidates with `choose_better=True`; keep the simpler model if tuning does not improve the target metric.
7. For handoff-ready models, add explainability, drift baselines, deployment notes, and rollback/retraining guidance.
8. Report business conclusion, validation metrics, caveats, output paths, and reproducibility steps.

Load [./references/workflow-playbook.md](./references/workflow-playbook.md) only for full project planning or handoff reports.
Load [./references/performance-playbook.md](./references/performance-playbook.md) when optimizing accuracy, runtime, or token usage.
Load [./references/production-readiness.md](./references/production-readiness.md) when the user asks for production readiness, reproducibility, testing, publishing, audit evidence, model governance, or operational handoff.

## Final Response Contract

Always close with the business conclusion first, then the task route, target, prediction timing, excluded leakage fields, key validation or holdout metrics, output file paths, caveats, and reproducibility steps.

## Hard Rules

- Do not start modeling before the target and business decision are clear.
- Do not skip leakage, data quality, imbalance, or time-boundary checks.
- Do not rely on accuracy alone for classification.
- Time series workflows must avoid future leakage.
- Do not accept tuned, blended, or stacked models without comparing the target metric against the baseline.
- Do not run unbounded model searches on large or unknown-size data; set a candidate shortlist, sample strategy, or time budget first.
- Do not hand off a model without explainability evidence when decisions affect customers, money, risk, compliance, or operations.
- Do not treat a saved pickle alone as a production deployment plan; document serving boundary, environment, artifact risks, and rollback path.
- Do not paste large datasets or full comparison tables into the answer; save files and summarize the key rows.
- Present business conclusions before technical detail.

## Examples

- For churn classification, use [./examples/customer-churn.md](./examples/customer-churn.md).
- For sales forecasting, use [./examples/sales-forecast.md](./examples/sales-forecast.md) and [./sample_codes/run_sales_forecast.py](./sample_codes/run_sales_forecast.py).
- For demand planning, use [./examples/demand-planning.md](./examples/demand-planning.md).
- For a combined classification plus forecasting demo, use [./sample_codes/run_dual_workflows.py](./sample_codes/run_dual_workflows.py).
- For dataset-backed accuracy testing, use [./sample_codes/run_dataset_benchmark.py](./sample_codes/run_dataset_benchmark.py).

## References

- Workflow playbook: ./references/workflow-playbook.md
- Accuracy and token efficiency playbook: ./references/performance-playbook.md
- Production readiness and audit playbook: ./references/production-readiness.md
- PyCaret module map: ./references/pycaret-module-map.md
- Classification example: ./examples/customer-churn.md
- Time series example: ./examples/sales-forecast.md
- Demand planning example: ./examples/demand-planning.md
- Runnable Python template: ./sample_codes/run_sales_forecast.py
- Runnable dual-workflow demo: ./sample_codes/run_dual_workflows.py
- Dataset benchmark script: ./sample_codes/run_dataset_benchmark.py
- Sample CSV: ./sample_data/sales_forecast_sample.csv
- Demand planning sample CSV: ./sample_data/demand_planning_sample.csv