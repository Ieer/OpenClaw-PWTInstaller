# PyCaret AutoML Workflow Playbook

## 1. Route the Problem Correctly

Translate the business request into the right machine learning task:

- Will something happen: classification
- How much will happen: regression
- How will a value evolve over time: time series forecasting
- How can entities be grouped: clustering
- Which records are suspicious or unusual: anomaly detection

If the user is vague, clarify these points first:

- What is being predicted
- When the prediction is needed
- What the target variable is
- What business decision the output supports

## 2. Analyze the Data Before Modeling

Always check:

- File size, row count estimate, memory fit, and whether sampling is needed before full loading
- Row count, column count, and target distribution
- Missing-value rate and missingness patterns
- Duplicate records
- Outliers and impossible values
- Presence of time columns
- Suspected leakage fields such as decision outcomes, settlement states, future dates, or manually derived labels

The output should explicitly name:

- Fields that are safe to model with
- Fields that should be excluded
- Fields that still need business clarification

For large files or constrained machines, run a lightweight preflight before loading the full dataset. Prefer schema inspection, chunked row counts, and a stratified or time-aware sample for the first pass. Escalate to distributed or database-backed processing only after the small workflow proves the target, leakage rules, and metric are valid.

## 3. Integrate and Clean the Data

Common actions include:

- Joining multiple tables
- Standardizing keys and field names
- Normalizing time zones, units, and currencies
- Deduplicating, correcting, and imputing records
- Building rolling-window, aggregate, frequency, interval, and ratio features

When the data spans multiple periods, enforce a clear split boundary so future information does not enter training.

Keep feature engineering boundaries explicit:

- Build business features before PyCaret when they depend on domain definitions, time windows, joins, or production data availability.
- Let PyCaret own statistical preprocessing such as imputation, encoding, scaling, transformations, and optional dimensionality reduction.
- Record each engineered feature's source fields, lookback window, prediction-time availability, and refresh cadence.

## 4. Design the Modeling Plan

Define:

- The target variable
- The decision grain
- The validation design
- The core metrics
- The threshold for production readiness

Classification usually prioritizes:

- AUC
- F1
- Recall
- Precision
- PR AUC

Regression usually prioritizes:

- MAE
- RMSE
- MAPE
- R2

Time series forecasting must also specify:

- Forecast horizon
- Backtesting method
- Seasonality, holidays, promotions, and policy impacts

## 5. Run the PyCaret Workflow

Recommended sequence:

```python
setup(...)
compare_models()
tune_model(best)
finalize_model(best)
predict_model(best_or_final_model)
save_model(best_or_final_model, "model_name")
```

Use a compact first pass before expensive searches:

- Clean the data and exclude leakage fields
- Compare a short task-specific candidate list
- Set a runtime budget before `compare_models` or expensive tuning when data size or environment capacity is uncertain
- Tune only the strongest candidate with `choose_better=True`
- Keep the baseline if tuning, blending, or stacking does not improve the target metric
- Save large comparison tables to files and summarize only the key rows in the final response

Optional enhancements:

- `blend_model`
- `stack_models`
- `interpret_model` for feature impact, model explanation, or regulated/user-impacting decisions
- `plot_model`

## 6. Forecast and Simulate

Keep prediction modes distinct:

- Holdout validation
- New-record prediction
- Future-period forecasting
- What-if scenario simulation

Common business scenarios:

- Sales after a pricing change
- Churn after a retention campaign
- Demand shortfall under different inventory policies
- Revenue shifts under promotional assumptions

If future inputs drift far from training data, flag the result as unstable.

## 7. Report and Hand Off

Use a two-layer output structure:

- Business summary: conclusion, expected impact, recommended action, major risks
- Technical handoff: dataset scope, field definitions, parameters, model selection, metrics, and output file paths

Every conclusion should state whether it comes from:

- Observed data facts
- Model predictions
- Scenario assumptions

Do not present correlation as causation.

For production handoff, also include:

- Explainability artifact paths or a clear reason interpretation was skipped
- Training-data baseline distributions for drift monitoring
- Deployment format, serving boundary, dependency lock, and rollback owner
- Retraining triggers tied to metric decay, drift thresholds, or business cadence
