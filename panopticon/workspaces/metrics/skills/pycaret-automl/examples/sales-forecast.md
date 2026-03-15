# Sales Forecast Example

## Scenario

A retail business wants to forecast the next 6 months of monthly sales so inventory and revenue planning can be updated before the next planning cycle.

## Example Fields

- `month`: calendar month
- `sales`: total monthly sales

This compact example uses a univariate monthly series so the time series route stays easy to reproduce. In real projects, you may also add exogenous variables such as promotions, pricing, holidays, or store traffic.

## Business Objective

- Forecast near-term revenue and demand
- Flag likely seasonal peaks and dips
- Give operations a planning baseline before scenario adjustments

## Recommended Flow

1. Confirm the data is sorted by month and has a stable monthly grain.
2. Check for missing months, duplicated periods, and sudden structural breaks.
3. Decide the forecast horizon and backtesting strategy.
4. Use the PyCaret time series module to compare candidate forecasters.
5. Finalize the selected model and generate a future-period forecast.
6. Report both the forecast output and the business caveats.

## Runnable Template

Use the included files:

- Sample CSV: [../sample_data/sales_forecast_sample.csv](../sample_data/sales_forecast_sample.csv)
- Python template: [../sample_codes/run_sales_forecast.py](../sample_codes/run_sales_forecast.py)

## Expected Outcome

```text
Sales Forecast Summary

1. Final Model
- Auto-selected baseline forecaster or tuned classical model

2. Forecast Horizon
- Next 6 monthly periods

3. Output
- Holdout forecast for evaluation
- Future forecast CSV
- Saved PyCaret model artifact

4. Business Notes
- Seasonality is present
- Forecast should be reviewed if pricing or promotion policy changes
- Use scenario overlays for optimistic and conservative planning
```

## Common Extensions

- Add holiday or promotion calendars as exogenous variables
- Forecast by store, region, or category
- Compare baseline, statistical, and regression-based forecasters
- Re-run monthly and track forecast drift
