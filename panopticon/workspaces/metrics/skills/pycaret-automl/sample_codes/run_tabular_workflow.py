from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from pycaret.classification import compare_models as compare_cls_models
from pycaret.classification import finalize_model as finalize_cls_model
from pycaret.classification import predict_model as predict_cls_model
from pycaret.classification import pull as pull_cls
from pycaret.classification import save_model as save_cls_model
from pycaret.classification import setup as setup_cls
from pycaret.classification import tune_model as tune_cls_model
from pycaret.regression import compare_models as compare_reg_models
from pycaret.regression import finalize_model as finalize_reg_model
from pycaret.regression import predict_model as predict_reg_model
from pycaret.regression import pull as pull_reg
from pycaret.regression import save_model as save_reg_model
from pycaret.regression import setup as setup_reg
from pycaret.regression import tune_model as tune_reg_model

from quality_checks import summarize_tabular_data, write_report


def parse_args() -> argparse.Namespace:
    base_dir = Path(__file__).resolve().parent.parent
    default_csv = base_dir / "sample_data" / "revenue_regression_sample.csv"
    default_output = base_dir / "outputs" / "tabular_workflow"

    parser = argparse.ArgumentParser(description="Run a PyCaret tabular workflow with data quality checks.")
    parser.add_argument("--csv", type=Path, default=default_csv, help="Path to the input CSV file.")
    parser.add_argument("--target", default="revenue", help="Target column name.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_output,
        help="Directory where reports, predictions, and model artifacts will be written.",
    )
    parser.add_argument(
        "--ignore-features",
        nargs="*",
        default=["month"],
        help="Optional feature names to exclude from modeling.",
    )
    parser.add_argument("--session-id", type=int, default=42, help="Random seed for PyCaret.")
    return parser.parse_args()


def infer_task_type(data: pd.DataFrame, target: str) -> str:
    target_series = data[target]
    if pd.api.types.is_numeric_dtype(target_series) and target_series.nunique(dropna=True) > 10:
        return "regression"
    return "classification"


def ensure_parent(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)


def run_classification_workflow(
    data: pd.DataFrame,
    target: str,
    ignore_features: list[str],
    output_dir: Path,
    session_id: int,
) -> None:
    class_balance = data[target].value_counts(normalize=True, dropna=False)
    use_imbalance_fix = len(class_balance) > 1 and float(class_balance.min()) < 0.20
    sort_metric = "AUC" if data[target].nunique(dropna=True) == 2 else "F1"

    setup_cls(
        data=data,
        target=target,
        session_id=session_id,
        fold=5,
        train_size=0.8,
        numeric_imputation="median",
        categorical_imputation="mode",
        normalize=True,
        remove_outliers=True,
        fix_imbalance=use_imbalance_fix,
        ignore_features=[column for column in ignore_features if column in data.columns],
        verbose=False,
    )

    candidate_models = compare_cls_models(sort=sort_metric, n_select=3)
    comparison_table = pull_cls().copy()
    best_candidate = candidate_models[0] if isinstance(candidate_models, list) else candidate_models

    tuned_model = tune_cls_model(best_candidate, optimize=sort_metric, choose_better=True)
    tuning_table = pull_cls().copy()
    holdout_predictions = predict_cls_model(tuned_model)
    holdout_metrics = pull_cls().copy()
    final_model = finalize_cls_model(tuned_model)
    full_scored_data = predict_cls_model(final_model, data=data.copy())

    comparison_table.to_csv(output_dir / "classification_model_comparison.csv", index=False)
    tuning_table.to_csv(output_dir / "classification_tuning_results.csv", index=False)
    holdout_metrics.to_csv(output_dir / "classification_holdout_metrics.csv", index=False)
    holdout_predictions.to_csv(output_dir / "classification_holdout_predictions.csv", index=False)
    full_scored_data.to_csv(output_dir / "classification_full_scored_data.csv", index=False)
    save_cls_model(final_model, str(output_dir / "classification_model"))


def run_regression_workflow(
    data: pd.DataFrame,
    target: str,
    ignore_features: list[str],
    output_dir: Path,
    session_id: int,
) -> None:
    sort_metric = "MAE"

    setup_reg(
        data=data,
        target=target,
        session_id=session_id,
        fold=5,
        train_size=0.8,
        numeric_imputation="median",
        categorical_imputation="mode",
        normalize=True,
        remove_outliers=True,
        transform_target=True,
        ignore_features=[column for column in ignore_features if column in data.columns],
        verbose=False,
    )

    candidate_models = compare_reg_models(sort=sort_metric, n_select=3)
    comparison_table = pull_reg().copy()
    best_candidate = candidate_models[0] if isinstance(candidate_models, list) else candidate_models

    tuned_model = tune_reg_model(best_candidate, optimize=sort_metric, choose_better=True)
    tuning_table = pull_reg().copy()
    holdout_predictions = predict_reg_model(tuned_model)
    holdout_metrics = pull_reg().copy()
    final_model = finalize_reg_model(tuned_model)
    full_scored_data = predict_reg_model(final_model, data=data.copy())

    comparison_table.to_csv(output_dir / "regression_model_comparison.csv", index=False)
    tuning_table.to_csv(output_dir / "regression_tuning_results.csv", index=False)
    holdout_metrics.to_csv(output_dir / "regression_holdout_metrics.csv", index=False)
    holdout_predictions.to_csv(output_dir / "regression_holdout_predictions.csv", index=False)
    full_scored_data.to_csv(output_dir / "regression_full_scored_data.csv", index=False)
    save_reg_model(final_model, str(output_dir / "regression_model"))


def main() -> None:
    args = parse_args()
    ensure_parent(args.output_dir)

    data = pd.read_csv(args.csv)
    task_type = infer_task_type(data, args.target)
    quality_report = summarize_tabular_data(data=data, target=args.target, time_col="month" if "month" in data.columns else None)
    quality_report["task_type"] = task_type
    quality_report["source_csv"] = args.csv.resolve()
    quality_report["ignored_features"] = [column for column in args.ignore_features if column in data.columns]
    write_report(args.output_dir / "tabular_quality_report.json", quality_report)

    if task_type == "classification":
        run_classification_workflow(
            data=data,
            target=args.target,
            ignore_features=args.ignore_features,
            output_dir=args.output_dir,
            session_id=args.session_id,
        )
    else:
        run_regression_workflow(
            data=data,
            target=args.target,
            ignore_features=args.ignore_features,
            output_dir=args.output_dir,
            session_id=args.session_id,
        )

    print(f"PyCaret {task_type} workflow completed.")
    print(f"Source CSV: {args.csv}")
    print(f"Outputs saved to: {args.output_dir}")


if __name__ == "__main__":
    main()
