# Publishing pycaret-automl

## Pre-Publication Checklist

- `SKILL.md` exists and uses English frontmatter
- `SKILL.md` frontmatter uses spaces, not tabs
- `README.md` explains installation, layout, and usage
- `LICENSE` is included
- `CHANGELOG.md` contains the release entry
- `requirements.txt` and `requirements-dev.txt` document the reproducible runtime and test baseline
- Examples and sample files are present
- Benchmark script and performance playbook are present
- Production readiness and audit guidance is present in `references/production-readiness.md`
- No secrets, tokens, or private datasets are included
- Package-relative links resolve inside the skill folder
- Generated `outputs/`, `logs.log`, `.venv/`, and Python cache files are ignored and absent from the release folder

## Suggested Repository Layout

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
├── datasets/
├── references/
├── sample_codes/
├── tests/
└── sample_data/
```

## Suggested ClawHub Metadata

- Slug: `pycaret-automl`
- Name: `PyCaret AutoML`
- Version: `0.2.0`
- Tags: `latest,automl,pycaret,forecasting,classification,regression,time-series,demand-planning,churn-prediction,clustering,anomaly-detection,business-reporting,accuracy-optimization,benchmarking,token-efficient`

## GitHub Repository Checklist

- Repository name is clear and searchable, for example `pycaret-automl-openclaw-skill`
- Public README shows install, examples, and repository layout
- Release files are visible in the root of the skill package
- Bundled datasets are intentional for distribution and documented in the README
- No proprietary datasets or secrets are committed

## GitHub Repository Description

Use this description in the GitHub repository "About" section:

```text
Publish-ready OpenClaw skill for token-efficient, dataset-backed AutoML with PyCaret across churn modeling, sales forecasting, demand planning, regression, clustering, anomaly detection, and business reporting workflows.
```

## Suggested GitHub Topics

```text
openclaw, openclaw-skill, automl, pycaret, machine-learning, forecasting, time-series, demand-planning, churn-prediction, anomaly-detection, clustering, data-science, benchmark, automl-benchmark
```

## GitHub Release Title

```text
v0.2.0 - Token-efficient PyCaret AutoML with dataset benchmarks
```

## GitHub Release Notes

```md
## Highlights

- Reduced the skill entrypoint size by moving deep optimization guidance into progressive references
- Added dataset-backed accuracy and runtime optimization guidance
- Added a reusable PyCaret benchmark script for bundled `churn` and `house` datasets
- Added reproducible dependency files, pytest checks, and production readiness guidance
- Added clean publishing guards for generated outputs, logs, and Python caches

## Included Assets

- `SKILL.md` with trigger-oriented frontmatter and workflow guidance
- `examples/customer-churn.md` for classification
- `examples/sales-forecast.md` for sales forecasting
- `examples/demand-planning.md` for demand planning
- `references/performance-playbook.md` for token and accuracy optimization
- `references/production-readiness.md` for reproducibility, testing, publishing, audit, and monitoring handoff
- `sample_codes/run_dataset_benchmark.py` for bundled dataset benchmarks
- `sample_codes/run_sales_forecast.py` for a focused forecasting demo
- `sample_codes/run_dual_workflows.py` for a churn + forecast walkthrough

## Notes

- Recommended dependency install: `pip install pycaret[full]`
- Sample data is synthetic and intended for demonstration only
```

## ClawHub Submission Notes

Suggested short listing description:

```text
OpenClaw skill for token-efficient AutoML with PyCaret, including churn modeling, forecasting, demand planning, accuracy benchmarking, metrics reporting, and handoff documentation.
```

Suggested submission checklist:

- Validate the package structure locally
- Confirm `SKILL.md` frontmatter is in English
- Confirm sample code and sample CSV files are present
- Run `python -m py_compile sample_codes/run_dataset_benchmark.py sample_codes/run_dual_workflows.py sample_codes/run_sales_forecast.py`
- Run `python -m pytest`
- Confirm benchmark smoke test runs or document why PyCaret is unavailable
- Confirm `LICENSE`, `README.md`, and `CHANGELOG.md` are included
- Use the same version number in `_meta.json`, changelog, and release text

## Example Publish Command

Create a clean publish copy first when packaging from a working tree:

```bash
mkdir -p /tmp/pycaret-automl-release
rsync -a --delete --exclude-from=pycaret-automl/.publishignore pycaret-automl/ /tmp/pycaret-automl-release/
```

```bash
clawhub publish /tmp/pycaret-automl-release \
  --slug pycaret-automl \
  --name "PyCaret AutoML" \
  --version 0.2.0 \
  --tags latest,automl,pycaret,forecasting,classification,regression,time-series,demand-planning,churn-prediction,clustering,anomaly-detection,business-reporting,accuracy-optimization,benchmarking,token-efficient \
  --changelog "Production-readiness update with reproducible dependencies, pytest checks, audit guidance, and dataset benchmark safeguards"
```

## Validation Notes

- Confirm the folder name matches the `name` in `SKILL.md`
- Keep the frontmatter concise and strongly trigger-oriented
- Validate that frontmatter contains no tab indentation
- Confirm all package links are relative and self-contained
- Ensure sample code runs with `python -m pip install -r requirements.txt`
- Run `python sample_codes/run_sales_forecast.py` for a forecasting smoke test when PyCaret is available
- Run `python sample_codes/run_dataset_benchmark.py --datasets churn house --fold 3 --tune-iterations 2` for a smoke benchmark when PyCaret is available
- Verify links are relative and valid inside the package
- Verify release hygiene with `find . -maxdepth 2 \( -path "./outputs" -o -name "logs.log" -o -name "__pycache__" -o -name ".pytest_cache" -o -name ".venv" \) -print`

## Post-Publish Tasks

- Create a GitHub release using the same version number
- Add a short release summary copied from `CHANGELOG.md`
- Verify installation from ClawHub or the target registry
- Watch for user feedback on missing models, dependencies, or OS-specific issues
