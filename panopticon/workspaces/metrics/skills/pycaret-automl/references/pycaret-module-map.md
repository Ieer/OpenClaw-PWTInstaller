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
- `remove_outliers`
- `normalize`

## Risk Notes

- A top-ranked `compare_models` result is not automatically the best production choice
- Best raw metric does not guarantee best interpretability
- Time series tasks should prioritize temporal stability, not just one score table
- Data leakage is often more damaging than model choice
