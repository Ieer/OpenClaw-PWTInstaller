# Production Readiness and Audit Playbook

Use this reference when the user asks for production readiness, reproducibility, testing, publishing, audit evidence, model governance, or handoff to an engineering or operations team.

## 1. Production Scope

This skill is strongest as an offline AutoML workflow for tabular modeling, forecasting, benchmark evidence, and business handoff. Treat real-time serving, feature stores, CI/CD deployment, model registries, access control, and production monitoring as downstream platform work unless the user explicitly asks to design that layer.

Before calling a workflow production-ready, document:

- Business decision and model owner
- Target, prediction timing, and decision grain
- Input dataset path, row count, column count, and refresh cadence
- Excluded leakage fields and fields unavailable at prediction time
- Feature engineering boundary, source fields, lookback windows, and prediction-time availability
- Validation split, fold strategy, random seed, model shortlist, and target metric
- Baseline metric, tuned metric, holdout metric, and selected model rationale
- Explainability evidence for the selected model or a documented reason it is not required
- Output file paths for comparison tables, metrics, predictions, and saved model artifacts
- Serving boundary, deployment format, dependency lock, rollback owner, and retraining trigger

## 2. Reproducibility Gate

Use the pinned runtime baseline in `requirements.txt` for local reproduction:

```bash
python -m pip install -r requirements.txt
```

For production deployment, create a fully resolved lock file in the target operating system and Python version. Record the resolved package list with the run artifacts.

Every run should capture:

- Python version, PyCaret version, platform, and dependency lock or package freeze
- Source data checksum or immutable data snapshot ID
- Script name, command-line arguments, and git commit or package version
- `session_id`, fold count, train size, validation strategy, and forecast horizon
- Candidate model list and optional model libraries that were available or skipped
- File size, sampling method, row filtering logic, and any compute budget used for comparison or tuning

## 3. Testing Gate

Run the lightweight tests before publishing or modifying the skill:

```bash
python -m py_compile sample_codes/run_dataset_benchmark.py sample_codes/run_dual_workflows.py sample_codes/run_sales_forecast.py
python -m pytest
```

Run PyCaret smoke workflows when the runtime dependencies are installed:

```bash
python sample_codes/run_sales_forecast.py
python sample_codes/run_dataset_benchmark.py --datasets churn house --fold 3 --tune-iterations 2
```

Expected evidence:

- Forecasting outputs include `model_comparison.csv`, `holdout_metrics.csv`, `holdout_predictions.csv`, `future_forecast.csv`, and a saved model artifact.
- Benchmark outputs include `summary.csv`, `summary.json`, per-dataset comparison tables, tuning tables, holdout metrics, and prediction CSV files.
- Tuned, blended, or stacked models are accepted only when the target metric improves against the baseline and holdout metrics remain credible.

## 4. Publishing Gate

Before publishing the skill package, confirm generated artifacts are absent from the release folder:

```bash
find . -maxdepth 2 \( -path "./outputs" -o -name "logs.log" -o -name "__pycache__" -o -name ".pytest_cache" -o -name ".venv" \) -print
```

The command should print nothing for a clean release folder. Keep benchmark results in documentation, not as generated CSV or model artifacts in the published package, unless the registry explicitly supports bundled example outputs.

## 5. Audit Handoff

Include these artifacts in the handoff package:

- Model card: intended use, excluded use, owner, model type, target, metrics, and known limitations
- Data card: source, grain, time range, target definition, data quality issues, leakage exclusions, and sensitive-field review
- Decision log: baseline model, tuned model, selection reason, rejected alternatives, and business threshold
- Reproducibility record: command, environment, data checksum, random seed, and output paths
- Explainability report: top drivers, segment-level caveats, local explanation approach for disputed predictions, and artifact paths
- Monitoring plan: drift checks, label arrival schedule, retraining trigger, threshold review cadence, and rollback owner

## 6. Deployment Handoff

Treat `save_model` pickle artifacts as Python-environment artifacts, not a complete production deployment plan. Document:

- Model artifact path, checksum, PyCaret version, Python version, and package lock
- Serving mode: offline batch scoring, scheduled batch job, analyst notebook, API wrapper, or downstream platform integration
- API or batch contract: required input columns, data types, allowed ranges, missing-value policy, output schema, and failure handling
- Security posture for pickle loading: only load trusted artifacts in controlled environments
- Alternative export or wrapper options such as `create_api`, MLflow registration, ONNX/PMML conversion when compatible, or a platform-native model package
- Rollback process, previous model artifact, owner, and acceptance threshold for switching models

## 7. Monitoring Handoff

For production scoring, define monitoring before release:

- Data drift: missingness, category emergence, numeric range shift, and schema changes
- Prediction drift: score distribution, positive-rate changes, forecast bias, and confidence interval misses
- Outcome drift: delayed labels, metric decay, intervention impact, and segment-level errors
- Operational drift: scoring latency, batch completeness, failed records, and model artifact version

Capture baseline distributions from the training or validation data so future monitors have a reference. At minimum, persist schema, missingness, categorical levels, numeric quantiles, target rate or target distribution, prediction score distribution, and segment-level metrics for priority groups.

Retrain only after diagnosing whether degradation comes from data quality, target definition, business process changes, or model aging.