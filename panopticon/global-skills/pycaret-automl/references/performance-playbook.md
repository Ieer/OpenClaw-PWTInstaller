# PyCaret Accuracy and Token Efficiency Playbook

Use this reference when the user asks for higher model accuracy, faster AutoML runs, lower context usage, or dataset-backed validation.

## 1. Reduce Token and Runtime Cost

- Keep `SKILL.md` short; load this file only for optimization work.
- Inspect schema, file size, row counts, target distribution, missingness, and a small sample before reading full files.
- For files that may not fit comfortably in memory, use chunked profiling or a stratified/time-aware sample for the first modeling pass.
- Summarize wide datasets instead of pasting whole tables into the response.
- Start with a narrow model shortlist before running full `compare_models`.
- Use `budget_time` or an equivalent wall-clock limit for broad `compare_models` runs when runtime is uncertain.
- Save comparison tables and predictions to files; report only the winning metrics and caveats.
- Disable noisy PyCaret output in scripts: `verbose=False`, `html=False`, `log_experiment=False`, and `system_log=False`.
- Avoid plots, profiling reports, SHAP, and interpretation steps unless the user explicitly asks or the model is near handoff.

Suggested first-pass limits:

| Situation | Default constraint |
| --------- | ------------------ |
| Unknown or large CSV | Profile schema and row count first; sample before full `setup` |
| Agent-run benchmark | Shortlist models and cap broad comparisons with `budget_time` |
| Low-memory machine | Prefer fewer folds, fewer candidates, and no high-cost plots or profiling reports |
| Handoff or audit workflow | Spend extra budget on holdout checks, explainability, and reproducibility artifacts |

## 2. Clean Data Before Comparing Models

Always do these before `setup`:

- Strip column names and categorical values.
- Convert numeric-like strings to numbers, such as currency, percentages, comma-formatted numbers, and blank numeric fields.
- Drop duplicate rows.
- Exclude identifiers, future outcome fields, post-event statuses, manually derived labels, and fields unavailable at prediction time.
- Normalize low-cardinality categorical values with internal whitespace, for example `Month to month` -> `Month_to_month`, to reduce fragile one-hot feature names.
- Keep free-text fields as text only when the workflow intentionally handles text; otherwise ignore them or engineer compact numeric features first.

## 3. Start With Stable Shortlists

Use narrow candidate sets for the first pass. Expand only when the first pass plateaus.

| Task | First-pass candidate models |
| ---- | --------------------------- |
| Classification | `lr`, `lightgbm`, `rf`, `et`, `gbc` |
| Regression | `lightgbm`, `gbr`, `rf`, `et`, `ridge`, `lasso` |
| Time series | baseline, exponential smoothing, ARIMA-family, and lightweight seasonal models |
| Clustering | `kmeans`, `hclust`, `dbscan` when shape supports it |
| Anomaly detection | `iforest`, `knn`, `lof`, `pca` |

Do not include optional models such as XGBoost, CatBoost, or GPU models unless the environment has those packages installed and the added runtime is acceptable.

## 4. Tune Conservatively

- Compare baselines first, then tune only the best one to three candidates.
- Use small `n_iter` values first, then increase only if the metric moves.
- Set a tuning budget before increasing `n_iter`, folds, ensembling, or optional model libraries.
- Always pass `choose_better=True` when using `tune_model`.
- Keep both cross-validation and holdout metrics; do not accept a tuned model only because it completed successfully.
- For lower-is-better metrics such as MAE, RMSE, MAPE, and MASE, verify that the value actually decreased.

Dataset-backed observation from this package:

- `datasets/churn.csv`: cleaned shortlist baseline reached AUC `0.8499`; light tuning reached AUC `0.8501`; holdout AUC was `0.8449`.
- `datasets/house.csv`: baseline MAE was `11165.1922`; tuned MAE was worse at `11938.1479`; holdout MAE was `16937.8475`.

Conclusion: tuning can help, but it is not automatically better. The skill should prefer validated improvement over automatic complexity.

## 5. Use Ensembling Carefully

- Blend only models that expose compatible probability or prediction outputs.
- For classification blends, avoid models without probability output unless the workflow explicitly handles that limitation.
- If a blend fails due to model compatibility, fall back to the best validated single model.
- Prefer simple blends over stacks for first-pass optimization; stacks cost more and are easier to overfit.

## 6. Expand the Search Only When Justified

Expand model search when:

- Baseline and tuned metrics are below the business threshold.
- The target metric is stable across folds but underpowered.
- Runtime budget allows a broader comparison.
- Optional model libraries are installed.

Do not expand search when:

- Leakage, bad target definition, missing time boundaries, or dirty categorical values remain unresolved.
- Holdout performance diverges sharply from cross-validation.
- The user needs a quick decision memo rather than a production-grade model.
- The dataset size or environment capacity has not been profiled.

## 7. Explainability Budget

Use interpretation selectively but do not skip it for high-impact handoff. Generate explainability artifacts when:

- The model informs customer treatment, pricing, credit, fraud, hiring, compliance, safety, or operational allocation.
- Business users must understand the main drivers before acting on predictions.
- A model card or audit package is requested.

Keep interpretation lightweight during exploration. Prefer top feature importance, compact SHAP summaries, or model-specific explanations saved to files. Avoid expensive plots for every candidate; explain only the chosen baseline/tuned model and any challenger that materially changes the business decision.

## 8. Benchmark Script

Run the bundled benchmark on representative datasets:

```bash
python sample_codes/run_dataset_benchmark.py --datasets churn house --fold 3 --tune-iterations 2
```

Outputs are written to `outputs/dataset_benchmark/`:

- `summary.csv` and `summary.json`
- comparison tables
- tuning tables
- holdout metric tables
- prediction CSV files

Use these results as a local smoke test, not as universal model rankings.