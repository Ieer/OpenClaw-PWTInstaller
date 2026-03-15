from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

LEAKAGE_HINT_PATTERNS = (
    "target",
    "label",
    "outcome",
    "approved",
    "rejected",
    "cancel",
    "refund",
    "chargeback",
    "closed",
    "won",
    "lost",
    "future",
    "next_",
    "status",
)


def _to_json_safe(value: Any) -> Any:
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if isinstance(value, (pd.Timestamp, pd.Period)):
        return str(value)
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def write_report(output_path: Path, payload: dict[str, Any]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False, default=_to_json_safe)


def summarize_tabular_data(
    data: pd.DataFrame,
    target: str | None = None,
    time_col: str | None = None,
) -> dict[str, Any]:
    object_columns = data.select_dtypes(include=["object", "category", "bool"]).columns.tolist()
    numeric_columns = data.select_dtypes(include=["number"]).columns.tolist()
    constant_columns = [column for column in data.columns if data[column].nunique(dropna=False) <= 1]
    high_missing_columns = [
        column
        for column, ratio in data.isna().mean().sort_values(ascending=False).items()
        if ratio >= 0.30
    ]
    high_cardinality_columns = [
        column
        for column in object_columns
        if data[column].nunique(dropna=True) / max(len(data), 1) >= 0.60
    ]

    target_token = (target or "").lower()
    suspicious_leakage_columns = [
        column
        for column in data.columns
        if column != target
        and (
            (target_token and target_token in column.lower())
            or any(pattern in column.lower() for pattern in LEAKAGE_HINT_PATTERNS)
        )
    ]

    report: dict[str, Any] = {
        "row_count": int(len(data)),
        "column_count": int(len(data.columns)),
        "duplicate_rows": int(data.duplicated().sum()),
        "numeric_columns": numeric_columns,
        "categorical_columns": object_columns,
        "constant_columns": constant_columns,
        "high_missing_columns": high_missing_columns,
        "high_cardinality_columns": high_cardinality_columns,
        "missing_rate_by_column": {
            column: round(float(ratio), 4)
            for column, ratio in data.isna().mean().sort_values(ascending=False).items()
        },
        "suspicious_leakage_columns": suspicious_leakage_columns,
    }

    if target and target in data.columns:
        target_series = data[target]
        report["target_name"] = target
        report["target_missing_rate"] = round(float(target_series.isna().mean()), 4)
        report["target_unique_values"] = int(target_series.nunique(dropna=True))

        if pd.api.types.is_numeric_dtype(target_series) and target_series.nunique(dropna=True) > 10:
            report["target_summary"] = {
                "mean": round(float(target_series.mean()), 4),
                "median": round(float(target_series.median()), 4),
                "std": round(float(target_series.std()), 4),
                "min": round(float(target_series.min()), 4),
                "max": round(float(target_series.max()), 4),
            }
        else:
            report["target_distribution"] = {
                str(label): round(float(ratio), 4)
                for label, ratio in target_series.value_counts(normalize=True, dropna=False).items()
            }

    if time_col and time_col in data.columns:
        parsed_time = pd.to_datetime(data[time_col], errors="coerce")
        report["time_column"] = time_col
        report["time_parse_success_rate"] = round(float(parsed_time.notna().mean()), 4)
        report["time_start"] = parsed_time.min()
        report["time_end"] = parsed_time.max()

    return report


def summarize_time_series(
    data: pd.DataFrame,
    time_col: str,
    value_col: str,
    freq: str = "M",
) -> dict[str, Any]:
    prepared = data.copy()
    prepared[time_col] = pd.to_datetime(prepared[time_col], errors="coerce")
    prepared = prepared.sort_values(time_col)

    period_index = pd.PeriodIndex(prepared[time_col].dropna(), freq=freq)
    expected_periods = (
        pd.period_range(period_index.min(), period_index.max(), freq=freq)
        if len(period_index) > 0
        else pd.PeriodIndex([], freq=freq)
    )
    missing_periods = [str(period) for period in expected_periods.difference(period_index)]

    value_series = pd.to_numeric(prepared[value_col], errors="coerce")
    q1 = value_series.quantile(0.25)
    q3 = value_series.quantile(0.75)
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr
    outlier_count = int(((value_series < lower_bound) | (value_series > upper_bound)).sum()) if not np.isnan(iqr) else 0

    return {
        "row_count": int(len(prepared)),
        "time_column": time_col,
        "value_column": value_col,
        "duplicate_periods": int(period_index.duplicated().sum()),
        "missing_periods": missing_periods,
        "missing_period_count": int(len(missing_periods)),
        "missing_value_rows": int(value_series.isna().sum()),
        "time_start": prepared[time_col].min(),
        "time_end": prepared[time_col].max(),
        "outlier_count_iqr": outlier_count,
        "value_summary": {
            "mean": round(float(value_series.mean()), 4),
            "median": round(float(value_series.median()), 4),
            "std": round(float(value_series.std()), 4),
            "min": round(float(value_series.min()), 4),
            "max": round(float(value_series.max()), 4),
        },
    }
