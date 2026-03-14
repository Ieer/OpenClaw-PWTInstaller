# pycaret-automl

Publish-ready OpenClaw skill package for end-to-end AutoML with PyCaret across classification, regression, and time series forecasting.

## Features

- Data analysis before modeling
- Data cleaning and integration guidance
- Problem framing for classification, regression, clustering, anomaly detection, and time series
- PyCaret model comparison and tuning workflow
- Forecasting and what-if simulation guidance
- Metrics reporting and business-facing handoff documentation
- Included sample CSV and runnable Python template

## Repository Layout

```text
pycaret-automl/
├── SKILL.md
├── README.md
├── LICENSE
├── CHANGELOG.md
├── PUBLISHING.md
├── _meta.json
├── examples/
│   ├── customer-churn.md
│   ├── demand-planning.md
│   └── sales-forecast.md
├── references/
│   ├── pycaret-module-map.md
│   └── workflow-playbook.md
├── sample_codes/
│   ├── run_dual_workflows.py
│   └── run_sales_forecast.py
└── sample_data/
    ├── demand_planning_sample.csv
    └── sales_forecast_sample.csv
```

## Installation

Manual install:

```bash
mkdir -p ~/.openclaw/skills
cp -r pycaret-automl ~/.openclaw/skills/pycaret-automl
```

Workspace install:

```bash
mkdir -p .github/skills
cp -r pycaret-automl .github/skills/pycaret-automl
```

## Requirements

- Python 3.9+
- Recommended dependency set: `pip install pycaret[full]`
- Local access to CSV, Excel, or exported business tables

## Quick Usage

Example prompt:

```text
Use PyCaret AutoML to build a sales forecasting workflow.
Start by validating the time series structure and leakage risks,
then compare candidate forecasting models,
and finish with a 6-period forecast, metrics summary, and handoff notes.
```

## Included Examples

- [examples/customer-churn.md](./examples/customer-churn.md) for classification workflows
- [examples/demand-planning.md](./examples/demand-planning.md) for demand planning workflows
- [examples/sales-forecast.md](./examples/sales-forecast.md) for time series forecasting workflows
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

## License

MIT License. See [LICENSE](./LICENSE).
