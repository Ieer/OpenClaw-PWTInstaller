from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class DatasetConfig:
    name: str
    path: str
    task: str
    target: str
    sort_metric: str
    include_models: tuple[str, ...]
    ignore_features: tuple[str, ...] = ()
    optimize_metric: str | None = None


DATASETS: dict[str, DatasetConfig] = {
    "churn": DatasetConfig(
        name="churn",
        path="datasets/churn.csv",
        task="classification",
        target="Churn",
        sort_metric="AUC",
        optimize_metric="AUC",
        include_models=("lr", "lightgbm", "rf", "et", "gbc"),
        ignore_features=("customerID",),
    ),
    "house": DatasetConfig(
        name="house",
        path="datasets/house.csv",
        task="regression",
        target="SalePrice",
        sort_metric="MAE",
        optimize_metric="MAE",
        include_models=("lightgbm", "gbr", "rf", "et", "ridge", "lasso"),
        ignore_features=("Id",),
    ),
}


LOWER_IS_BETTER = {"MAE", "MSE", "RMSE", "RMSLE", "MAPE", "MASE", "SMAPE"}


def normalize_string_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if not stripped:
        return pd.NA
    return re.sub(r"\s+", "_", stripped)


def coerce_numeric_like(series: pd.Series, threshold: float = 0.9) -> pd.Series:
    if not pd.api.types.is_object_dtype(series) and not pd.api.types.is_string_dtype(series):
        return series

    cleaned = series.astype("string").str.strip()
    non_empty = cleaned.notna() & (cleaned != "")
    if non_empty.sum() == 0:
        return series

    numeric_text = cleaned.str.replace(r"[$,%]", "", regex=True).str.replace(",", "", regex=False)
    numeric = pd.to_numeric(numeric_text, errors="coerce")
    if numeric[non_empty].notna().mean() >= threshold:
        return numeric
    return series


def clean_tabular_data(data: pd.DataFrame) -> pd.DataFrame:
    cleaned = data.copy()
    cleaned.columns = [str(column).strip() for column in cleaned.columns]
    cleaned = cleaned.drop_duplicates().reset_index(drop=True)

    for column in cleaned.columns:
        coerced = coerce_numeric_like(cleaned[column])
        if coerced is not cleaned[column] and pd.api.types.is_numeric_dtype(coerced):
            cleaned[column] = coerced
            continue

        if pd.api.types.is_object_dtype(cleaned[column]) or pd.api.types.is_string_dtype(cleaned[column]):
            unique_count = cleaned[column].nunique(dropna=True)
            average_length = cleaned[column].dropna().astype(str).str.len().mean()
            if unique_count <= max(50, int(len(cleaned) * 0.2)) and (pd.isna(average_length) or average_length < 80):
                cleaned[column] = cleaned[column].map(normalize_string_value)
            else:
                cleaned[column] = cleaned[column].astype("string").str.strip().replace("", pd.NA)

    return cleaned


def write_table(table: pd.DataFrame | None, output_path: Path) -> None:
    if table is None:
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(output_path, index=True)


def first_metric_value(table: pd.DataFrame | None, metric: str) -> float | None:
    if table is None or metric not in table.columns or table.empty:
        return None
    value = table.iloc[0][metric]
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def mean_metric_value(table: pd.DataFrame | None, metric: str) -> float | None:
    if table is None or metric not in table.columns or table.empty:
        return None
    if "Mean" in table.index:
        value = table.loc["Mean", metric]
    elif "Fold" in table.columns and "Mean" in set(table["Fold"].astype(str)):
        value = table.loc[table["Fold"].astype(str) == "Mean", metric].iloc[0]
    else:
        numeric = pd.to_numeric(table[metric], errors="coerce")
        value = numeric.mean()
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def is_better(metric: str, candidate: float | None, baseline: float | None) -> bool:
    if candidate is None:
        return False
    if baseline is None:
        return True
    return candidate < baseline if metric.upper() in LOWER_IS_BETTER else candidate > baseline


def run_classification(config: DatasetConfig, data: pd.DataFrame, output_dir: Path, fold: int, tune_iterations: int) -> dict[str, Any]:
    from pycaret.classification import ClassificationExperiment

    experiment = ClassificationExperiment()
    experiment.setup(
        data=data,
        target=config.target,
        ignore_features=list(config.ignore_features),
        train_size=0.8,
        fold=fold,
        session_id=42,
        numeric_imputation="median",
        categorical_imputation="mode",
        normalize=True,
        transformation=True,
        remove_multicollinearity=True,
        multicollinearity_threshold=0.9,
        log_experiment=False,
        system_log=False,
        html=False,
        verbose=False,
    )

    best_models = experiment.compare_models(
        include=list(config.include_models),
        sort=config.sort_metric,
        n_select=min(3, len(config.include_models)),
        errors="ignore",
        turbo=True,
        verbose=False,
    )
    compare_table = experiment.pull()
    write_table(compare_table, output_dir / f"{config.name}_classification_compare.csv")

    best_model = best_models[0] if isinstance(best_models, list) else best_models
    baseline_metric = first_metric_value(compare_table, config.sort_metric)
    final_model = best_model
    tuned_metric = None

    if tune_iterations > 0:
        tuned_model = experiment.tune_model(
            best_model,
            optimize=config.optimize_metric or config.sort_metric,
            n_iter=tune_iterations,
            choose_better=True,
            verbose=False,
        )
        tune_table = experiment.pull()
        write_table(tune_table, output_dir / f"{config.name}_classification_tune.csv")
        tuned_metric = mean_metric_value(tune_table, config.sort_metric)
        if is_better(config.sort_metric, tuned_metric, baseline_metric):
            final_model = tuned_model

    holdout_predictions = experiment.predict_model(final_model, verbose=False)
    holdout_table = experiment.pull()
    write_table(holdout_table, output_dir / f"{config.name}_classification_holdout.csv")
    holdout_predictions.to_csv(output_dir / f"{config.name}_classification_predictions.csv", index=False)

    return {
        "dataset": config.name,
        "task": config.task,
        "rows": int(data.shape[0]),
        "columns": int(data.shape[1]),
        "target": config.target,
        "sort_metric": config.sort_metric,
        "baseline_cv_metric": baseline_metric,
        "tuned_cv_metric": tuned_metric,
        "holdout_metric": first_metric_value(holdout_table, config.sort_metric),
        "chosen_model": type(final_model).__name__,
        "outputs": str(output_dir),
    }


def run_regression(config: DatasetConfig, data: pd.DataFrame, output_dir: Path, fold: int, tune_iterations: int) -> dict[str, Any]:
    from pycaret.regression import RegressionExperiment

    experiment = RegressionExperiment()
    experiment.setup(
        data=data,
        target=config.target,
        ignore_features=list(config.ignore_features),
        train_size=0.8,
        fold=fold,
        session_id=42,
        numeric_imputation="median",
        categorical_imputation="mode",
        normalize=True,
        transformation=True,
        transform_target=True,
        remove_multicollinearity=True,
        multicollinearity_threshold=0.9,
        log_experiment=False,
        system_log=False,
        html=False,
        verbose=False,
    )

    best_models = experiment.compare_models(
        include=list(config.include_models),
        sort=config.sort_metric,
        n_select=min(3, len(config.include_models)),
        errors="ignore",
        turbo=True,
        verbose=False,
    )
    compare_table = experiment.pull()
    write_table(compare_table, output_dir / f"{config.name}_regression_compare.csv")

    best_model = best_models[0] if isinstance(best_models, list) else best_models
    baseline_metric = first_metric_value(compare_table, config.sort_metric)
    final_model = best_model
    tuned_metric = None

    if tune_iterations > 0:
        tuned_model = experiment.tune_model(
            best_model,
            optimize=config.optimize_metric or config.sort_metric,
            n_iter=tune_iterations,
            choose_better=True,
            verbose=False,
        )
        tune_table = experiment.pull()
        write_table(tune_table, output_dir / f"{config.name}_regression_tune.csv")
        tuned_metric = mean_metric_value(tune_table, config.sort_metric)
        if is_better(config.sort_metric, tuned_metric, baseline_metric):
            final_model = tuned_model

    holdout_predictions = experiment.predict_model(final_model, verbose=False)
    holdout_table = experiment.pull()
    write_table(holdout_table, output_dir / f"{config.name}_regression_holdout.csv")
    holdout_predictions.to_csv(output_dir / f"{config.name}_regression_predictions.csv", index=False)

    return {
        "dataset": config.name,
        "task": config.task,
        "rows": int(data.shape[0]),
        "columns": int(data.shape[1]),
        "target": config.target,
        "sort_metric": config.sort_metric,
        "baseline_cv_metric": baseline_metric,
        "tuned_cv_metric": tuned_metric,
        "holdout_metric": first_metric_value(holdout_table, config.sort_metric),
        "chosen_model": type(final_model).__name__,
        "outputs": str(output_dir),
    }


def run_dataset(config: DatasetConfig, root: Path, output_dir: Path, fold: int, tune_iterations: int) -> dict[str, Any]:
    data = pd.read_csv(root / config.path)
    cleaned = clean_tabular_data(data)
    dataset_output_dir = output_dir / config.name
    dataset_output_dir.mkdir(parents=True, exist_ok=True)
    cleaned.head(50).to_csv(dataset_output_dir / f"{config.name}_cleaned_preview.csv", index=False)

    if config.task == "classification":
        return run_classification(config, cleaned, dataset_output_dir, fold, tune_iterations)
    if config.task == "regression":
        return run_regression(config, cleaned, dataset_output_dir, fold, tune_iterations)
    raise ValueError(f"Unsupported task: {config.task}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run compact PyCaret benchmarks on bundled datasets.")
    parser.add_argument("--datasets", nargs="+", choices=sorted(DATASETS), default=["churn", "house"])
    parser.add_argument("--fold", type=int, default=3)
    parser.add_argument("--tune-iterations", type=int, default=5)
    parser.add_argument("--output-dir", default="outputs/dataset_benchmark")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(__file__).resolve().parent.parent
    output_dir = root / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    summaries = []
    for dataset_name in args.datasets:
        config = DATASETS[dataset_name]
        print(f"Running {config.task} benchmark for {dataset_name}...")
        summaries.append(run_dataset(config, root, output_dir, args.fold, args.tune_iterations))

    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summaries, indent=2), encoding="utf-8")
    summary_table = pd.DataFrame(summaries)
    summary_table.to_csv(output_dir / "summary.csv", index=False)
    print(summary_table.to_string(index=False))
    print(f"Benchmark outputs saved to: {output_dir}")


if __name__ == "__main__":
    main()