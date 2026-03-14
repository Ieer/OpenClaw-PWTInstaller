from pathlib import Path

import pandas as pd
from pycaret.time_series import TSForecastingExperiment


def main() -> None:
    base_dir = Path(__file__).resolve().parent.parent
    sample_csv = base_dir / "sample_data" / "sales_forecast_sample.csv"
    output_dir = base_dir / "outputs"
    output_dir.mkdir(exist_ok=True)

    data = pd.read_csv(sample_csv)
    data["month"] = pd.PeriodIndex(pd.to_datetime(data["month"]), freq="M")
    sales_series = data.set_index("month")["sales"]

    experiment = TSForecastingExperiment()
    experiment.setup(
        data=sales_series,
        fh=3,
        fold=3,
        fold_strategy="expanding",
        session_id=42,
        verbose=False,
    )

    best_model = experiment.compare_models(sort="MASE")
    holdout_predictions = experiment.predict_model(best_model)
    final_model = experiment.finalize_model(best_model)
    future_predictions = experiment.predict_model(final_model, fh=6)

    comparison_table = experiment.pull()

    comparison_table.to_csv(output_dir / "model_comparison.csv", index=False)
    holdout_predictions.to_csv(output_dir / "holdout_predictions.csv")
    future_predictions.to_csv(output_dir / "future_forecast.csv")

    experiment.save_model(final_model, str(output_dir / "sales_forecast_model"), model_only=True)

    print("PyCaret sales forecasting demo completed.")
    print(f"Sample CSV: {sample_csv}")
    print(f"Outputs saved to: {output_dir}")


if __name__ == "__main__":
    main()