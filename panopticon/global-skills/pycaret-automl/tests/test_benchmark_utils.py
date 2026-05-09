from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sample_codes.run_dataset_benchmark import (  # noqa: E402
    clean_tabular_data,
    first_metric_value,
    is_better,
    mean_metric_value,
)


def test_clean_tabular_data_normalizes_columns_values_and_numeric_strings() -> None:
    raw = pd.DataFrame(
        {
            " amount ": [" $1,200.50 ", "2,000", ""],
            " plan ": [" Month to month ", "Two   year", ""],
        }
    )

    cleaned = clean_tabular_data(raw)

    assert cleaned.columns.tolist() == ["amount", "plan"]
    assert cleaned["amount"].iloc[0] == 1200.50
    assert cleaned["amount"].iloc[1] == 2000.00
    assert pd.isna(cleaned["amount"].iloc[2])
    assert cleaned["plan"].iloc[0] == "Month_to_month"
    assert cleaned["plan"].iloc[1] == "Two_year"
    assert pd.isna(cleaned["plan"].iloc[2])


def test_metric_helpers_extract_first_and_mean_rows() -> None:
    table = pd.DataFrame(
        {
            "Fold": [0, 1, "Mean"],
            "AUC": [0.81, 0.83, 0.82],
            "MAE": [20.0, 18.0, 19.0],
        }
    )

    assert first_metric_value(table, "AUC") == 0.81
    assert mean_metric_value(table, "AUC") == 0.82
    assert abs(mean_metric_value(pd.DataFrame({"AUC": [0.80, 0.90]}), "AUC") - 0.85) < 1e-12


def test_is_better_respects_metric_direction_and_missing_values() -> None:
    assert is_better("AUC", 0.86, 0.84)
    assert not is_better("AUC", 0.82, 0.84)
    assert is_better("MAE", 100.0, 120.0)
    assert not is_better("MAE", 130.0, 120.0)
    assert not is_better("AUC", None, 0.84)
    assert is_better("AUC", 0.84, None)


def test_sales_forecast_template_pulls_comparison_before_predictions() -> None:
    source = (ROOT / "sample_codes" / "run_sales_forecast.py").read_text(encoding="utf-8")

    assert source.index("comparison_table = experiment.pull()") < source.index(
        "holdout_predictions = experiment.predict_model"
    )