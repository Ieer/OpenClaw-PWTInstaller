# pycaret-automl

Publish-ready OpenClaw skill package for end-to-end AutoML with PyCaret across classification, regression, time series forecasting, clustering, anomaly detection, and business-facing handoff documentation.

## Features

- Data analysis before modeling
- Data cleaning and integration guidance
- Problem framing for classification, regression, clustering, anomaly detection, and time series
- Leakage checks, validation design, and task routing before PyCaret execution
- Large-data preflight guidance, compute budgets, and constrained-runtime fallbacks
- Token-efficient PyCaret model comparison and conservative tuning workflow
- Explainability, drift-baseline, and deployment handoff guidance for production workflows
- Dataset-backed benchmark script for classification and regression smoke tests
- Reproducible runtime and development dependency files
- Lightweight pytest coverage for data-cleaning and metric-selection utilities
- Production readiness and audit handoff checklist
- Forecasting and what-if simulation guidance
- Metrics reporting and business-facing handoff documentation
- Included sample CSV files and runnable Python templates

## Repository Layout

```text
pycaret-automl/
├── SKILL.md
├── README.md
├── LICENSE
├── CHANGELOG.md
├── PUBLISHING.md
├── _meta.json
├── .gitignore
├── .publishignore
├── requirements.txt
├── requirements-dev.txt
├── examples/
│   ├── customer-churn.md
│   ├── demand-planning.md
│   └── sales-forecast.md
├── datasets/
│   └── bundled PyCaret-style reference datasets
├── references/
│   ├── performance-playbook.md
│   ├── production-readiness.md
│   ├── pycaret-module-map.md
│   └── workflow-playbook.md
├── sample_codes/
│   ├── run_dataset_benchmark.py
│   ├── run_dual_workflows.py
│   └── run_sales_forecast.py
├── tests/
│   └── test_benchmark_utils.py
└── sample_data/
    ├── demand_planning_sample.csv
    └── sales_forecast_sample.csv
```

## Installation

Manual install:

```bash
mkdir -p ~/.openclaw/skills
rsync -a --delete --exclude-from=pycaret-automl/.publishignore pycaret-automl/ ~/.openclaw/skills/pycaret-automl/
```

Workspace install:

```bash
mkdir -p .github/skills
rsync -a --delete --exclude-from=pycaret-automl/.publishignore pycaret-automl/ .github/skills/pycaret-automl/
```

## Requirements

- Python 3.9+
- Reproducible runtime baseline: `python -m pip install -r requirements.txt`
- Test dependencies: `python -m pip install -r requirements-dev.txt`
- Recommended dependency set for exploratory environments: `pip install pycaret[full]`
- Local access to CSV, Excel, or exported business tables
- For time series examples, confirm the installed PyCaret version includes `pycaret.time_series`

## Quick Usage

Example prompt:

```text
Use PyCaret AutoML to build a sales forecasting workflow.
Start by validating the time series structure and leakage risks,
then compare candidate forecasting models,
and finish with a 6-period forecast, metrics summary, and handoff notes.
```

For best results, include:

- Business question and decision being supported
- Data file path or table description
- Target column, if known
- Forecast horizon or prediction timing
- Required outputs such as report, CSV predictions, saved model, or notebook

## Accuracy and Cost Optimization

The skill separates high-frequency instructions from deeper optimization guidance. The entrypoint stays compact, while [references/performance-playbook.md](./references/performance-playbook.md) covers:

- Reducing token use and noisy PyCaret output
- Profiling large files before full loading and using sample-first modeling when memory is uncertain
- Cleaning numeric-like strings and categorical whitespace before `setup`
- Starting with stable candidate shortlists instead of full-model searches
- Setting compute budgets for broad comparison and tuning runs
- Tuning with `choose_better=True` and metric verification
- Adding explainability artifacts when a model is near handoff or affects high-impact decisions
- Expanding search only when the baseline is clean and still below target

Run the bundled smoke benchmark:

```bash
python sample_codes/run_dataset_benchmark.py --datasets churn house --fold 3 --tune-iterations 2
```

Observed local benchmark results with PyCaret 3.3.2:

| Dataset | Task | Baseline CV | Tuned CV | Holdout | Note |
| ------- | ---- | ----------- | -------- | ------- | ---- |
| `churn.csv` | Classification | AUC 0.8499 | AUC 0.8501 | AUC 0.8449 | Light tuning helped slightly |
| `house.csv` | Regression | MAE 11165.1922 | MAE 11938.1479 | MAE 16937.8475 | Tuning was worse, so baseline was kept |

## Verification

Run lightweight checks before editing, publishing, or handing off the skill:

```bash
python -m py_compile sample_codes/run_dataset_benchmark.py sample_codes/run_dual_workflows.py sample_codes/run_sales_forecast.py
python -m pytest
```

Run PyCaret smoke workflows when dependencies are installed:

```bash
python sample_codes/run_sales_forecast.py
python sample_codes/run_dataset_benchmark.py --datasets churn house --fold 3 --tune-iterations 2
```

The forecasting demo writes `model_comparison.csv`, `holdout_metrics.csv`, `holdout_predictions.csv`, `future_forecast.csv`, and a saved model artifact under `outputs/`.

## Production Readiness

Use [references/production-readiness.md](./references/production-readiness.md) when a workflow needs reproducibility, test evidence, release hygiene, model governance, or audit handoff. At minimum, capture the business decision, target, prediction timing, leakage exclusions, feature engineering boundary, validation design, dependency versions, data snapshot, metrics, explainability evidence, output paths, deployment contract, rollback path, drift baseline, and monitoring plan.

## Included Examples

- [examples/customer-churn.md](./examples/customer-churn.md) for classification workflows
- [examples/demand-planning.md](./examples/demand-planning.md) for demand planning workflows
- [examples/sales-forecast.md](./examples/sales-forecast.md) for time series forecasting workflows
- [references/performance-playbook.md](./references/performance-playbook.md) for token and accuracy optimization guidance
- [references/production-readiness.md](./references/production-readiness.md) for reproducibility, testing, publishing, and audit handoff guidance
- [sample_codes/run_dataset_benchmark.py](./sample_codes/run_dataset_benchmark.py) for bundled dataset benchmarking
- [sample_codes/run_sales_forecast.py](./sample_codes/run_sales_forecast.py) for a runnable PyCaret forecasting template
- [sample_codes/run_dual_workflows.py](./sample_codes/run_dual_workflows.py) for an end-to-end churn + forecast demo
- [sample_data/demand_planning_sample.csv](./sample_data/demand_planning_sample.csv) for a compact demand planning dataset
- [sample_data/sales_forecast_sample.csv](./sample_data/sales_forecast_sample.csv) for a compact monthly sales dataset

## Publishing

This package includes the common files expected in public OpenClaw skill repositories:

- `SKILL.md` for the agent-facing skill entrypoint
- `README.md` for GitHub and human readers
- `LICENSE` for open-source distribution
- `CHANGELOG.md` for release history
- `PUBLISHING.md` for release and ClawHub submission guidance
- `_meta.json` for registry-style metadata
- `.publishignore` for excluding generated artifacts from manual installs and release archives

## Quality Checklist

- `SKILL.md` frontmatter uses spaces, not tabs
- The `name` field matches the package folder name
- The `description` includes concrete trigger phrases such as churn, sales forecast, demand forecast, regression, time series, clustering, and anomaly detection
- Relative links point to files inside this package
- Sample code and sample CSV names match the repository layout
- Bundled datasets are intentional for distribution and do not contain private data
- Lightweight tests pass with `python -m pytest`
- Generated `outputs/`, `.venv/`, PyCaret logs, and cache files are ignored and absent from release archives
- Version numbers stay aligned across `_meta.json`, `CHANGELOG.md`, and release notes

## License

MIT License. See [LICENSE](./LICENSE).
