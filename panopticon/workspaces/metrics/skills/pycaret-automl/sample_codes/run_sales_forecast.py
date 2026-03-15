from pathlib import Path

import pandas as pd
from pycaret.time_series import TSForecastingExperiment

from quality_checks import summarize_time_series, write_report


def main() -> None:
    base_dir = Path(__file__).resolve().parent.parent
    sample_csv = base_dir / "sample_data" / "sales_forecast_sample.csv"
    output_dir = base_dir / "outputs"
    output_dir.mkdir(exist_ok=True)

    data = pd.read_csv(sample_csv)
    quality_report = summarize_time_series(data=data, time_col="month", value_col="sales", freq="M")
    quality_report["source_csv"] = sample_csv.resolve()
    write_report(output_dir / "sales_forecast_quality_report.json", quality_report)

    prepared = data.copy()
    prepared["month"] = pd.PeriodIndex(pd.to_datetime(prepared["month"]), freq="M")
    prepared = prepared.sort_values("month").drop_duplicates(subset="month", keep="last")
    sales_series = prepared.set_index("month")["sales"].astype(float)
    full_index = pd.period_range(sales_series.index.min(), sales_series.index.max(), freq="M")
    sales_series = sales_series.reindex(full_index).interpolate(limit_direction="both")

    experiment = TSForecastingExperiment()
    experiment.setup(
        data=sales_series,
        fh=3,
        fold=3,
        fold_strategy="expanding",
        session_id=42,
        verbose=False,
    )

    candidate_models = experiment.compare_models(sort="MASE", n_select=3)
    comparison_table = experiment.pull().copy()
    best_model = candidate_models[0] if isinstance(candidate_models, list) else candidate_models
    tuned_model = experiment.tune_model(best_model, optimize="MASE", choose_better=True)
    tuning_table = experiment.pull().copy()
    holdout_predictions = experiment.predict_model(tuned_model)
    holdout_metrics = experiment.pull().copy()
    final_model = experiment.finalize_model(tuned_model)
    future_predictions = experiment.predict_model(final_model, fh=6)

    comparison_table.to_csv(output_dir / "model_comparison.csv", index=False)
    tuning_table.to_csv(output_dir / "tuning_results.csv", index=False)
    holdout_metrics.to_csv(output_dir / "holdout_metrics.csv", index=False)
    holdout_predictions.to_csv(output_dir / "holdout_predictions.csv")
    future_predictions.to_csv(output_dir / "future_forecast.csv")

    experiment.save_model(final_model, str(output_dir / "sales_forecast_model"), model_only=True)

    print("PyCaret sales forecasting demo completed.")
    print(f"Sample CSV: {sample_csv}")
    print(f"Outputs saved to: {output_dir}")


if __name__ == "__main__":
    main()