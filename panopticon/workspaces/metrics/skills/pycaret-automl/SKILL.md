---
name: pycaret-automl
description: End-to-end AutoML workflow with PyCaret for data analysis, data cleaning, problem framing, model selection, sales forecasting, demand prediction, churn modeling, metrics reporting, and handoff documentation. Use when the user asks for a churn model, sales forecast, demand forecast, regression model, time series workflow, or a full data-to-report machine learning pipeline from CSV, Excel, SQL exports, or business tables.
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

An OpenClaw skill for running a practical end-to-end AutoML workflow with PyCaret.

## When to Use

- The user wants churn prediction, sales forecasting, demand forecasting, risk scoring, or anomaly detection.
- The user provides CSV, Excel, or SQL-exported business tables and wants a full workflow, not just model code.
- The user is unsure whether the task is classification, regression, time series forecasting, clustering, or anomaly detection.
- The user asks for "analyze the data first, then clean it, then build the model, then generate a report or documentation".

## Quick Reference

| Situation | Action |
| --------- | ------ |
| Target is categorical | Use classification |
| Target is continuous | Use regression |
| Outcome depends on time progression | Use time series forecasting |
| No label, but segmentation is needed | Use clustering |
| Need to surface suspicious or rare records | Use anomaly detection |

## Workflow

1. Clarify the business question, decision unit, target, forecast horizon, and delivery format.
2. Inspect the data for missing values, anomalies, duplicates, leakage, imbalance, and time boundaries.
3. Clean and reshape the dataset so it is safe to pass into PyCaret.
4. Map the problem to the correct PyCaret module.
5. Run the included quality checks and save a data-readiness report before modeling.
6. Run `setup`, `compare_models`, `tune_model`, and `finalize_model`.
7. Generate predictions for holdout data, future periods, or what-if scenarios.
8. Deliver metrics, business conclusions, risks, and handoff documentation.

## Execution Rules

- Do not start modeling before the target and business decision are clear.
- Do not skip leakage checks or basic data quality review.
- Do not rely on accuracy alone for classification problems.
- Time series workflows must avoid future leakage.
- Present business conclusions before technical detail.

## Deliverables

- AutoML execution plan
- Data-readiness report
- Data quality and leakage findings
- Cleaning and feature engineering summary
- Model comparison and final model decision
- Forecast or simulation output
- Metrics report
- Project handoff document

## References

- Accuracy checklist: ./references/accuracy-maximization-checklist.md
- Workflow playbook: ./references/workflow-playbook.md
- PyCaret module map: ./references/pycaret-module-map.md
- Classification example: ./examples/customer-churn.md
- Regression example: ./examples/revenue-regression.md
- Time series example: ./examples/sales-forecast.md
- Demand planning example: ./examples/demand-planning.md
- Data-quality helper: ./sample_codes/quality_checks.py
- Generic tabular workflow: ./sample_codes/run_tabular_workflow.py
- Runnable Python template: ./sample_codes/run_sales_forecast.py
- Runnable dual-workflow demo: ./sample_codes/run_dual_workflows.py
- Sample CSV: ./sample_data/sales_forecast_sample.csv
- Regression sample CSV: ./sample_data/revenue_regression_sample.csv