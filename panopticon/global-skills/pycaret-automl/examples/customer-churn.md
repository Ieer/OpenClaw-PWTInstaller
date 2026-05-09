# Customer Churn Example

## Scenario

A subscription business wants to predict which customers are likely to churn within the next 30 days so the retention team can intervene earlier.

## Example Fields

- `customer_id`: unique customer identifier
- `signup_date`: signup date
- `plan_type`: subscription plan
- `monthly_fee`: recurring fee
- `tenure_months`: customer lifetime in months
- `support_tickets_30d`: support tickets in the last 30 days
- `active_days_30d`: active days in the last 30 days
- `payment_failures_90d`: failed payments in the last 90 days
- `last_login_days_ago`: days since last login
- `churned_30d`: whether the customer churns in the next 30 days

## Business Objective

- Flag high-risk customers early
- Produce a prioritized outreach list for the retention team
- Explain the most important churn drivers

## Recommended Flow

1. Verify that `churned_30d` is defined without future leakage.
2. Exclude fields such as cancellation date, refund status, or post-event support outcomes.
3. Check class imbalance and emphasize Recall and PR AUC if churn is rare.
4. Create behavior, payment-risk, and recency features.
5. Use the PyCaret classification module to compare and tune models.
6. Produce a high-risk customer list and a threshold recommendation.

## PyCaret Example

```python
from pycaret.classification import setup, compare_models, tune_model, finalize_model, predict_model, save_model, pull
import pandas as pd

data = pd.read_csv("customer_churn.csv")
candidate_models = ["lr", "lightgbm", "rf", "et", "gbc"]

setup(
    data=data,
    target="churned_30d",
    session_id=42,
    train_size=0.8,
    categorical_imputation="mode",
    numeric_imputation="median",
    remove_outliers=True,
    normalize=True,
    fold=5,
    html=False,
    log_experiment=False,
    system_log=False,
    verbose=False,
)

best_model = compare_models(include=candidate_models, sort="AUC", errors="ignore", verbose=False)
comparison_table = pull()
baseline_auc = float(comparison_table.iloc[0]["AUC"])

tuned_model = tune_model(best_model, optimize="AUC", choose_better=True, verbose=False)
tuning_table = pull()
tuned_auc = float(tuning_table.loc["Mean", "AUC"] if "Mean" in tuning_table.index else tuning_table["AUC"].mean())

selected_model = tuned_model if tuned_auc > baseline_auc else best_model
final_model = finalize_model(selected_model)

holdout_predictions = predict_model(final_model, verbose=False)
save_model(final_model, "customer_churn_model")
```

## Example Output

```text
Customer Churn Summary

1. Final Model
- LightGBM classifier

2. Core Metrics
- AUC: 0.87
- Recall: 0.78
- Precision: 0.54

3. Top Risk Signals
- Long time since last login
- More failed payments
- Drop in active days during the last 30 days
- Rising support ticket volume

4. Recommended Actions
- Prioritize outreach to the highest-risk segment
- Route payment-failure cases to billing recovery
- Offer targeted retention incentives to high-value low-activity users
```

## Extensions

- Export a top-N high-risk customer list
- Tune the probability threshold based on intervention cost
- Retrain weekly and monitor drift
