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

## Use Cases

- 客户流失预测、营收回归、销售/需求预测。
- 用户提供业务表格，要求“数据清洗 + 建模 + 报告”一体化。
- 需要快速比较多模型并给出业务可解释结论。

## Run

1. 明确业务问题、目标变量、评估指标与交付格式。
2. 完成数据质量检查（缺失、异常、泄漏、时序边界）。
3. 进行清洗与特征处理，形成可建模数据集。
4. 选择对应 PyCaret 模块并执行 `setup -> compare_models -> tune_model -> finalize_model`。
5. 输出预测结果、指标、风险与交接文档。

## Inputs

- 原始数据（CSV/Excel/SQL 导出表）。
- 任务定义（分类/回归/时序/聚类/异常检测）。
- 业务约束（预测窗口、目标阈值、解释需求）。

## Outputs

- 数据准备与质量检查报告。
- 模型比较结果与最终模型选择说明。
- 预测或评分输出（含关键指标）。
- 业务结论、风险提示与后续行动建议。

## Safety

- 禁止在目标定义不清时直接建模。
- 必须执行数据泄漏检查与时序边界检查。
- 不用单一指标做最终结论，需给出局限性说明。

## Version

- 1.0.0 (2026-03-18)