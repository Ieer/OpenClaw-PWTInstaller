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

## 3. Integrate and Clean the Data

Common actions include:

- Joining multiple tables
- Standardizing keys and field names
- Normalizing time zones, units, and currencies
- Deduplicating, correcting, and imputing records
- Building rolling-window, aggregate, frequency, interval, and ratio features

When the data spans multiple periods, enforce a clear split boundary so future information does not enter training.

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

Optional enhancements:

- `blend_model`
- `stack_models`
- `interpret_model`
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
