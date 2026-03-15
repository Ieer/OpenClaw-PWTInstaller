# Publishing pycaret-automl

## Pre-Publication Checklist

- `SKILL.md` exists and uses English frontmatter
- `README.md` explains installation, layout, and usage
- `LICENSE` is included
- `CHANGELOG.md` contains the release entry
- Examples and sample files are present
- No secrets, tokens, or private datasets are included

## Suggested Repository Layout

```text
pycaret-automl/
├── SKILL.md
├── README.md
├── LICENSE
├── CHANGELOG.md
├── PUBLISHING.md
├── _meta.json
├── requirements.txt
├── examples/
├── references/
├── sample_codes/
└── sample_data/
```

## Suggested ClawHub Metadata

- Slug: `pycaret-automl`
- Name: `PyCaret AutoML`
- Version: `0.2.0`
- Tags: `latest,automl,pycaret,data-quality,model-evaluation,forecasting,classification,regression,time-series,demand-planning`

## GitHub Repository Checklist

- Repository name is clear and searchable, for example `pycaret-automl-openclaw-skill`
- Public README shows install, examples, and repository layout
- Release files are visible in the root of the skill package
- No proprietary datasets or secrets are committed

## GitHub Repository Description

Use this description in the GitHub repository "About" section:

```text
Publish-ready OpenClaw skill for end-to-end AutoML with PyCaret across churn modeling, sales forecasting, demand planning, regression, and business reporting workflows.
```

## Suggested GitHub Topics

```text
openclaw, openclaw-skill, automl, pycaret, machine-learning, forecasting, time-series, demand-planning, churn-prediction, data-science
```

## GitHub Release Title

```text
v0.1.0 - Initial public release of PyCaret AutoML for OpenClaw
```

## GitHub Release Notes

```md
## Highlights

- Added a publish-ready OpenClaw skill for end-to-end AutoML with PyCaret
- Included workflows for churn prediction, sales forecasting, and demand planning
- Added sample CSV datasets and runnable Python demos
- Added publishing assets for GitHub and ClawHub release workflows

## Included Assets

- `SKILL.md` with trigger-oriented frontmatter and workflow guidance
- `examples/customer-churn.md` for classification
- `examples/sales-forecast.md` for sales forecasting
- `examples/demand-planning.md` for demand planning
- `references/accuracy-maximization-checklist.md` for stronger validation and metric guidance
- `sample_codes/run_sales_forecast.py` for a focused forecasting demo
- `sample_codes/run_dual_workflows.py` for a churn + forecast walkthrough
- `sample_codes/run_tabular_workflow.py` for generic classification and regression workflows
- `sample_codes/quality_checks.py` for data-readiness reporting helpers

## Notes

- Recommended dependency install: `pip install pycaret[full]`
- Sample data is synthetic and intended for demonstration only
```

## ClawHub Submission Notes

Suggested short listing description:

```text
OpenClaw skill for end-to-end AutoML with PyCaret, including churn modeling, sales forecasting, demand planning, metrics reporting, and handoff documentation.
```

Suggested submission checklist:

- Validate the package structure locally
- Confirm `SKILL.md` frontmatter is in English
- Confirm sample code and sample CSV files are present
- Confirm `LICENSE`, `README.md`, and `CHANGELOG.md` are included
- Use the same version number in `_meta.json`, changelog, and release text

## Example Publish Command

```bash
clawhub publish ./pycaret-automl \
  --slug pycaret-automl \
  --name "PyCaret AutoML" \
  --version 0.2.0 \
  --tags latest,automl,pycaret,data-quality,model-evaluation,forecasting,classification,regression,time-series,demand-planning \
  --changelog "Added data-readiness checks, regression workflow coverage, and stronger accuracy guardrails"
```

## Validation Notes

- Confirm the folder name matches the `name` in `SKILL.md`
- Keep the frontmatter concise and strongly trigger-oriented
- Ensure sample code runs with `pip install pycaret[full]`
- Verify links are relative and valid inside the package

## Post-Publish Tasks

- Create a GitHub release using the same version number
- Add a short release summary copied from `CHANGELOG.md`
- Verify installation from ClawHub or the target registry
- Watch for user feedback on missing models, dependencies, or OS-specific issues
