# Accuracy Maximization Checklist

Use this checklist before calling a PyCaret workflow when the user explicitly wants stronger model accuracy or more reliable forecasts.

## 1. Tighten the Data Definition

- Confirm the prediction target is the exact business outcome, not a proxy.
- Verify one row equals one decision unit, such as one customer, one order, one store-week, or one SKU-day.
- Remove or quarantine columns created after the prediction moment.
- Align time zones, currencies, units, and aggregation levels before training.

## 2. Raise Data Quality First

- Measure missing-value ratio by column and decide whether to impute, bucket, or drop.
- De-duplicate records on the business key, not only full-row duplicates.
- Check outliers separately for signal and data-entry error.
- Flag sparse, high-cardinality text or ID columns that can overfit quickly.

## 3. Optimize Validation Design

- For tabular problems, keep a clean holdout set untouched until the final check.
- For imbalanced classification, prefer stratified folds and review Recall, Precision, F1, AUC, and PR AUC together.
- For time series, use rolling or expanding backtests and score multiple horizons, not one split.
- Match the optimization metric to the business cost function instead of defaulting to accuracy.

## 4. Improve Feature Signal

- Build recency, frequency, rolling-window, and ratio features when they reflect the business process.
- Add exogenous drivers for forecasting, such as price, promotion, holiday, traffic, or weather.
- Collapse rare categories when the sample size is too small.
- Keep a feature exclusion list for IDs, leaked labels, and post-outcome fields.

## 5. Search More Than One Model

- Compare several PyCaret candidate models before tuning.
- Tune the top candidate with the production metric, not just the benchmark metric.
- Re-check whether the tuned model is still stable across folds.
- Prefer a slightly lower score if it is materially more stable or explainable.

## 6. Protect Forecast Reliability

- Fill or explain missing time buckets before modeling.
- Review structural breaks caused by policy, pricing, assortment, or channel changes.
- Separate baseline forecast from scenario overlays.
- Warn users when the requested horizon is much longer than the stable history length.

## 7. Final Delivery Standard

The final output should contain:

- Data readiness findings
- Leakage and risk findings
- Candidate model comparison
- Final model metrics on holdout or backtest
- Prediction or forecast files
- Business caveats and retraining recommendations
