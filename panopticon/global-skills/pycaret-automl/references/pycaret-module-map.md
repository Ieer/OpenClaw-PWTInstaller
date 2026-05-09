# PyCaret Module Map

## Task Type to Module Mapping

| Business Task | PyCaret Module | Common Use Cases |
| ------------- | -------------- | ---------------- |
| Classification | pycaret.classification | Churn, default, purchase, fraud |
| Regression | pycaret.regression | Sales, revenue, price, score |
| Time series forecasting | pycaret.time_series | Weekly sales, monthly revenue, demand |
| Clustering | pycaret.clustering | Customer segmentation, store grouping |
| Anomaly detection | pycaret.anomaly | Fraud, faults, unusual events |

## Core Functions

| Stage | Common Functions | Purpose |
| ----- | ---------------- | ------- |
| Initialization | setup | Configure data, validation, and preprocessing |
| Baseline selection | compare_models | Rank candidate models quickly |
| Tuning | tune_model | Optimize promising candidates |
| Ensembling | blend_model / stack_models | Improve robustness or performance |
| Evaluation | evaluate_model / plot_model | Review metrics and diagnostics |
| Interpretation | interpret_model | Inspect feature impact and explainability |
| Prediction | predict_model | Score holdout or unseen data |
| Finalization | finalize_model / save_model | Lock and save the chosen model |
| Deployment handoff | create_api / create_docker / create_app when available | Generate wrapper scaffolds for controlled deployment review |

## Metric Guidance

### Classification

- AUC: ranking quality across thresholds
- F1: balance between precision and recall
- Recall: prioritize when missing positives is costly
- Precision: prioritize when false alarms are costly

### Regression

- MAE: direct and stable average absolute error
- RMSE: penalizes larger misses more heavily
- MAPE: useful when percentage error matters
- R2: descriptive only, not enough on its own for go-live decisions

### Time Series Forecasting

- MAE, RMSE, MAPE
- Backtest stability
- Error comparison across multiple horizons

## Common `setup` Inputs to Review

- `target`
- `index`
- `ignore_features`
- `train_size`
- `fold_strategy`
- `session_id`
- `use_gpu`
- `numeric_imputation`
- `categorical_imputation`
- `transformation`
- `transform_target` for regression
- `remove_outliers`
- `remove_multicollinearity`
- `normalize`
- `html`
- `system_log`

## Runtime and Handoff Options to Review

- `compare_models(..., budget_time=...)` for bounded broad searches
- `compare_models(..., include=[...])` for shortlist-first exploration
- `tune_model(..., choose_better=True)` for conservative tuning acceptance
- `save_model` for trusted Python-environment artifacts
- `create_api`, `create_docker`, or `create_app` only when supported by the installed PyCaret module and downstream deployment path

## Risk Notes

- A top-ranked `compare_models` result is not automatically the best production choice
- Best raw metric does not guarantee best interpretability
- Time series tasks should prioritize temporal stability, not just one score table
- Data leakage is often more damaging than model choice
- Tuning is not automatically better; accept tuned models only when the target metric improves against the baseline
- Full model searches cost more context and runtime than shortlists; expand only after the data is clean and the baseline is below target
- Pickle artifacts are not a deployment plan by themselves; document serving contract, environment, artifact trust, rollback, and monitoring
- High-impact decisions need explanation artifacts or a documented reason for skipping them
