# Changelog

## Unreleased

- Added production optimization guidance for explainability, large-data preflight, compute budgets, deployment handoff, drift baselines, and feature engineering boundaries
- Added pinned runtime and development requirement files for reproducible installs
- Added pytest coverage for benchmark utility functions and metric direction checks
- Added a production readiness and audit playbook covering reproducibility, test gates, publishing hygiene, audit artifacts, and monitoring handoff
- Fixed the forecasting demo so the model comparison table is captured immediately after `compare_models`
- Added `.publishignore` and stricter release hygiene guidance for generated outputs, logs, caches, and local virtual environments
- Aligned the customer churn example with the conservative tuning rule by using `choose_better=True` and comparing tuned AUC against the baseline
- Added low-noise PyCaret settings to runnable forecasting and dual-workflow examples
- Added a compact final response contract to the skill entrypoint

## 0.2.0

- Reduced `SKILL.md` body size by moving lower-frequency optimization detail into progressive reference docs
- Added `references/performance-playbook.md` for token-efficient PyCaret usage, conservative tuning, model shortlist strategy, and dataset-backed accuracy guidance
- Added `sample_codes/run_dataset_benchmark.py` to benchmark bundled `churn` and `house` datasets with cleaning, shortlist comparison, light tuning, and CSV/JSON output summaries
- Added `.gitignore` entries for generated benchmark outputs, PyCaret logs, and Python caches
- Recorded local PyCaret 3.3.2 benchmark results showing that tuning should be accepted only when the target metric improves

## 0.1.1

- Strengthened `SKILL.md` discovery keywords and execution guidance
- Fixed frontmatter indentation to avoid YAML parsing failures caused by tabs
- Added argument hints, output contract, quality guardrails, and clearer example routing
- Aligned README and metadata scope across classification, regression, time series, clustering, anomaly detection, and business reporting
- Removed an external teaching-notes reference from the skill entrypoint so package links stay self-contained

## 0.1.0

- Initial public packaging of the `pycaret-automl` OpenClaw skill
- Added a publish-ready `SKILL.md` with English frontmatter and workflow guidance
- Added workflow references for task routing, metrics, and PyCaret module mapping
- Added a customer churn example for classification workflows
- Added a sales forecast example for time series workflows
- Added sample CSV data and a runnable Python forecasting template
- Added `LICENSE`, `_meta.json`, and `PUBLISHING.md`
