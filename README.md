# Earthquake Damage Classification: Logistic Regression, Random Forest and Gradient Boosting

NTU Python programming course: group project.

**Problem statement.** *Can we predict how badly a building was damaged in the 2015 Gorkha earthquake from its structure and location, so post-disaster inspectors can prioritise which buildings to assess first?*

We use the DrivenData competition [Richter's Predictor: Modeling Earthquake Damage](https://www.drivendata.org/competitions/57/nepal-earthquake/), which has 260,601 labelled buildings, 38 features and damage grades 1–3. We compare three classification models, with a majority-class baseline for reference:

1. **Logistic regression** (`sklearn.linear_model.LogisticRegression`), studied in depth: seven controlled experiments (structure only, coarse location, cross-fitted multiclass target encoding of fine location, engineered features, class weighting, and an ordinal cumulative-binary formulation), C tuning, an odds-ratio interpretation;
2. **Random forest** (`sklearn.ensemble.RandomForestClassifier`);
3. **HistGradientBoosting** (`sklearn.ensemble.HistGradientBoostingClassifier`, native categorical splits).

All three use the same features, the same stratified 80/20 split and the same 5 CV folds. Each is tuned with `GridSearchCV` (scored by micro-F1) and scored once on the holdout. The final model is the one with the best CV micro-F1; it is refit on all labelled rows for the submission. We also compare inspection prioritisation (share of grade-3 buildings found in the top 10/20/30% of each model's ranking) and permutation importances.

Headline results are in `outputs/results.json` → `models` (all three tuned models) and `final_model`; the logistic-regression detail is in `experiments`, `tuning`, `holdout`, `prioritisation` and `coefficients`. The report and slides read every number from that file.

## Reproduce (one command)

```bash
# Python 3.11
python -m venv .venv            # or: uv venv --python 3.11 .venv
.venv\Scripts\activate           # Windows   (source .venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
# put the three DrivenData CSVs in data/ first (see data/README.md)
python -m src.run_all
```

`python -m src.run_all` does three things:

1. executes `notebooks/earthquake_damage.ipynb` top to bottom in a fresh kernel (about 50–90 min on an 8 GB laptop, depending on free RAM: roughly 25 min for the logistic-regression experiments, 12 min for the random forest, 14 min for HistGradientBoosting, plus permutation importances and the final refit). This writes `figures/*.png`, `outputs/results.json` and `outputs/submission.csv`, and saves the outputs in the notebook;
2. builds `report/report.docx`, and `report/report.pdf` if Microsoft Word is installed on Windows (Word also refreshes the table of contents);
3. builds `slides/presentation.pptx` and `slides/speaker_notes.md`.

Use `python -m src.run_all --skip-notebook` to rebuild only the documents from an existing `results.json`. Parallel CV workers default to 2 to suit an 8 GB RAM machine (3 ran out of memory when other apps were open); set the `N_JOBS` environment variable to change this. The data CSVs must be in `data/`; they are not in this repository because the competition rules forbid redistribution, so download them from DrivenData as described in `data/README.md`.

## Folder map

```
README.md                 this file
requirements.txt          pinned dependencies (Python 3.11)
DECISIONS.md              log of non-obvious decisions and why
data/                     README.md with download steps; the three DrivenData CSVs go here (git-ignored)
src/
  data.py                 paths, constants (RANDOM_STATE = 42), loading, stratified split, CV splitter
  features.py             column groups, AgeCleaner, FeatureEngineer, leakage-safe ColumnTransformers (LR and trees)
  models.py               LR experiment configs E0–E6, OrdinalLogisticRegression, pipeline factories (LR, RF, HGB)
  evaluate.py             CV, GridSearchCV summaries, holdout metrics, capture curve, coefficients,
                          permutation importance, results I/O
  plots.py                every figure (consistent, slide-readable style)
  results_view.py         formatting layer over results.json shared by report and slides
  build_report.py         report/report.docx (+ PDF)
  build_slides.py         slides/presentation.pptx + slides/speaker_notes.md
  run_all.py              one-command pipeline
notebooks/earthquake_damage.ipynb   full narrative, executed with outputs saved
figures/                  fig01–fig16 PNGs (200 dpi): EDA, LR results, three-model comparison (fig13),
                          capture curves (fig14), final-model confusion matrix (fig15), permutation
                          importance (fig16); fig11b/fig16b are slide-sized versions made by build_slides
outputs/results.json      single source of truth for every reported number
outputs/submission.csv    DrivenData submission (building_id, damage_grade)
report/report.docx, report/report.pdf
slides/presentation.pptx, slides/speaker_notes.md
```

## To fill in before submission

- Group number, member names, student IDs and course code: highlighted placeholders on the report cover page, `[XX]`/`[...]` on slide 1 and in every slide footer, and *Presenter N* in `speaker_notes.md`.
- The report's Appendix E contribution statement.
