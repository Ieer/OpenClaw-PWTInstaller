# Demand Planning Example

## Scenario

An operations team wants to forecast product demand for the next 8 weeks so purchasing and replenishment can be planned before stockouts happen.

## Example Fields

- `week`: weekly period
- `demand_units`: units demanded during the week

In larger projects you may also have exogenous variables such as promotions, price changes, lead times, holidays, and channel traffic.

## Business Objective

- Estimate near-term demand for inventory planning
- Reduce stockout and overstock risk
- Provide a baseline forecast before scenario overlays

## Recommended Flow

1. Confirm the dataset has one row per time bucket and no missing weeks.
2. Check for demand spikes caused by one-off promotions or supply constraints.
3. Decide the forecast horizon and how often the forecast will be refreshed.
4. Compare PyCaret time series models on rolling or expanding validation.
5. Finalize the chosen forecaster and produce an 8-week demand plan.
6. Add scenario overlays for conservative, baseline, and optimistic planning.

## Sample Assets

- Sample CSV: [../sample_data/demand_planning_sample.csv](../sample_data/demand_planning_sample.csv)
- General forecasting template: [../sample_codes/run_sales_forecast.py](../sample_codes/run_sales_forecast.py)

## Example Output

```text
Demand Planning Summary

1. Forecast Horizon
- Next 8 weekly periods

2. Key Insight
- Demand has a mild upward trend with intermittent promotional spikes

3. Planning Guidance
- Use the baseline forecast for purchasing
- Add safety stock for peak weeks
- Re-run the forecast weekly as actual demand arrives
```

## Common Extensions

- Build separate forecasts by SKU or warehouse
- Add promotion and holiday calendars as exogenous features
- Convert unit demand into purchase quantities using lead time and safety stock rules
