# Revenue Regression Example

## Scenario

A commercial team wants to estimate expected revenue for each region-month so budgeting, discount planning, and marketing allocation can be adjusted before the next planning cycle.

## Example Fields

- `month`: reporting month
- `region`: sales region
- `marketing_spend`: marketing budget used in the month
- `discount_rate`: average discount ratio applied during the month
- `site_visits`: traffic volume
- `conversion_rate`: visit-to-order conversion rate
- `avg_order_value`: average order value
- `revenue`: realized revenue target

## Business Objective

- Estimate revenue sensitivity to traffic, pricing, and marketing changes
- Provide a planning baseline for finance and growth teams
- Highlight the strongest revenue drivers before scenario planning

## Recommended Flow

1. Confirm the target is actual recognized revenue, not booked pipeline.
2. Exclude fields that are direct rollups of the target after the reporting close.
3. Check for missing periods, region-level duplicates, and extreme promotional outliers.
4. Use the tabular PyCaret workflow to compare multiple regression models.
5. Tune the strongest candidate on MAE or RMSE, depending on business tolerance.
6. Export scored data and business-facing notes about controllable drivers.

## Runnable Template

Use the included assets:

- Sample CSV: [../sample_data/revenue_regression_sample.csv](../sample_data/revenue_regression_sample.csv)
- Python template: [../sample_codes/run_tabular_workflow.py](../sample_codes/run_tabular_workflow.py)

## Example Output

```text
Revenue Regression Summary

1. Final Model
- Tuned gradient boosting regressor

2. Core Metrics
- MAE: 1820
- RMSE: 2470
- R2: 0.89

3. Strongest Drivers
- Site visits
- Conversion rate
- Average order value
- Marketing spend

4. Recommended Actions
- Reallocate budget toward higher-conversion regions
- Test discount changes where conversion is strong but order value is stable
- Refresh the model monthly as new commercial data arrives
```

## Common Extensions

- Train separate models by channel or product line
- Add campaign calendar, seasonality, or macro indicators
- Turn the regression output into conservative, baseline, and upside scenarios
