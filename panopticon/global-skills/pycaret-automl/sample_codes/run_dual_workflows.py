from pathlib import Path

import numpy as np
import pandas as pd
from pycaret.classification import compare_models as compare_cls_models
from pycaret.classification import finalize_model as finalize_cls_model
from pycaret.classification import predict_model as predict_cls_model
from pycaret.classification import save_model as save_cls_model
from pycaret.classification import setup as setup_cls
from pycaret.time_series import TSForecastingExperiment


def build_churn_sample() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    rows = 120

    tenure = rng.integers(1, 48, size=rows)
    tickets = rng.integers(0, 8, size=rows)
    active_days = rng.integers(1, 30, size=rows)
    payment_failures = rng.integers(0, 4, size=rows)
    last_login_days = rng.integers(1, 45, size=rows)
    monthly_fee = rng.integers(29, 129, size=rows)
    plan_type = rng.choice(["basic", "pro", "enterprise"], size=rows, p=[0.45, 0.4, 0.15])

    risk_score = (
        0.08 * tickets
        + 0.12 * payment_failures
        + 0.05 * last_login_days
        - 0.03 * active_days
        - 0.01 * tenure
    )
    churn_flag = (risk_score > np.median(risk_score)).astype(int)

    return pd.DataFrame(
        {
            "plan_type": plan_type,
            "monthly_fee": monthly_fee,
            "tenure_months": tenure,
            "support_tickets_30d": tickets,
            "active_days_30d": active_days,
            "payment_failures_90d": payment_failures,
            "last_login_days_ago": last_login_days,
            "churned_30d": churn_flag,
        }
    )


def run_churn_workflow(output_dir: Path) -> None:
    churn_data = build_churn_sample()

    setup_cls(
        data=churn_data,
        target="churned_30d",
        session_id=42,
        train_size=0.8,
        fold=3,
        numeric_imputation="median",
        categorical_imputation="mode",
        verbose=False,
    )

    best_model = compare_cls_models(sort="AUC")
    final_model = finalize_cls_model(best_model)
    predictions = predict_cls_model(final_model)

    predictions.to_csv(output_dir / "churn_predictions.csv", index=False)
    save_cls_model(final_model, str(output_dir / "customer_churn_model"))


def run_forecast_workflow(base_dir: Path, output_dir: Path) -> None:
    sample_csv = base_dir / "sample_data" / "sales_forecast_sample.csv"
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
    final_model = experiment.finalize_model(best_model)
    future_predictions = experiment.predict_model(final_model, fh=6)

    future_predictions.to_csv(output_dir / "future_sales_forecast.csv")
    experiment.save_model(final_model, str(output_dir / "sales_forecast_model"), model_only=True)


def main() -> None:
    base_dir = Path(__file__).resolve().parent.parent
    output_dir = base_dir / "outputs"
    output_dir.mkdir(exist_ok=True)

    run_churn_workflow(output_dir)
    run_forecast_workflow(base_dir, output_dir)

    print("Dual PyCaret demo completed.")
    print(f"Outputs saved to: {output_dir}")


if __name__ == "__main__":
    main()