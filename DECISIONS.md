# Decision log

Non-obvious choices made while building the project, and why. Entries are in the order they were made.

## Environment and data

1. **Data files moved into `data/`.** The three CSVs were in the project root, but the brief (and the code) expect `data/`. They were moved, not copied, so only one copy exists.
2. **Python 3.11 via a `uv` virtual environment (`.venv/`).** The machine's default interpreter is 3.13, and the registered `py -3.11` pointed at a deleted install. `uv venv --python 3.11` gave a clean 3.11.14 and exact pins in `requirements.txt`. The pinned scikit-learn is 1.5.2, which is ≥ 1.4 as required for multiclass `TargetEncoder`.
3. **Every "known fact" is asserted in the notebook rather than assumed.** Verified: 260,601 / 86,868 rows, 0 missing values, a 9.6 / 56.9 / 33.5 % class split, 1,390 rows with `age == 995`, and 11,595 unique `geo_level_3_id` values. If the data changed, the notebook would fail loudly.
4. **EDA uses only the 80% training split.** Looking at holdout rows during exploration is a mild form of leakage (it can shape feature choices), so every EDA figure and number comes from the training split. Dataset-level facts such as the class split are reported on the full labelled set.

## Preprocessing

5. **`age == 995` is treated as missing, not as a very old building.** The next-largest real age is 200, and placeholder rows have a different damage mix (grade-3 share ≈29% vs ≈34%). So we add an `age_is_placeholder` flag and impute the *training-fold* median, computed in `AgeCleaner.fit` inside the pipeline.
6. **`log1p` rather than `log`** for age, area and height, because age can be 0. `count_floors_pre_eq` and `count_families` are small integer counts with little skew, so they are standard-scaled without a log.
7. **One-hot encoding without dropping a level.** Logistic regression here is L2-penalised, so a full set of dummies is identifiable, and keeping every level makes the coefficients easier to read (no hidden reference category). `handle_unknown="ignore"` guards against levels that are rare in a fold.
8. **`TargetEncoder(target_type="multiclass", cv=5, shuffle=True, random_state=42)` for geo levels 2 and 3.** It produces one column per class (3 per geo level). During `fit_transform` the encoder cross-fits internally, so a training row's encoding never uses its own label. Because the encoder sits inside the `Pipeline`, it is also refit on every outer CV training fold. Unseen IDs fall back to the global class prior.
9. **"Structural features" for E1 means every non-geographic column**, which includes ownership status, family count and secondary use. Only the three `geo_level_*` columns are excluded. The aim of E1 is to measure what the building itself tells us, without location.
10. **Engineered-feature selection uses a paired, fold-wise rule.** Each candidate is added to E3 on its own and scored on the same 5 folds. A candidate is kept only if it raises the mean micro-F1 *and* wins in at least 4 of 5 folds. Fold-to-fold std (~0.002) is about the size of the effects, so an unpaired "higher mean" rule would keep noise.

## Modelling

11. **lbfgs solver, `max_iter=5000`.** With every input scaled, lbfgs converges well inside the limit (the observed maximum is recorded in `results.json → convergence`). CV folds run in joblib worker processes, which do not pass warnings back to the parent. So we record `n_iter_` for every fitted model (via `return_estimator=True`, plus a custom pseudo-scorer inside `GridSearchCV`) and assert that it stays below `max_iter`. In the notebook process, `ConvergenceWarning` is turned into an error.
12. **Ordinal model (E6) = two independent binary logistic models** for P(y>1) and P(y>2), sharing the same preprocessing. This is not a proportional-odds model, because the slopes are not tied, so the cumulative probabilities can cross. We force them to be non-increasing (`np.minimum.accumulate`), take class probabilities as their differences, and predict the most probable class. The multiclass target encoding is still fitted on the 3-class label, since its per-class columns are informative for both thresholds.
13. **Choosing what to tune.** The configuration with the highest CV micro-F1 among E4, E5 and E6 goes into `GridSearchCV`. Micro-F1 is the competition metric, and the brief scores the grid on `f1_micro`.
14. **`N_JOBS=2` parallel folds** (originally 3; a later run hit a MemoryError in a worker while other applications were open, so the default was lowered). The machine has 8 GB of RAM (about 1 GB free at the start), and each worker holds a dense copy of the transformed training fold. The value can be overridden with the `N_JOBS` environment variable.

## Reporting

15. **Interpretation plot excludes location features.** Geo one-hots and target encodings are the strongest predictors, but they stand in for shaking intensity, not for building properties an engineer could act on. The three target-encoded columns per level also sum to 1, so their individual coefficients are not separately identifiable. They are summarised separately in `results.json → coefficients.location_top`.
16. **Odds-ratio reading of the multinomial model.** In softmax regression, the grade-3 coefficient row gives the change in log-odds of grade 3 relative to the model's (L2-centred) reference. We present exp(coef) as an odds ratio per unit of the feature (per 1 SD for scaled numerics, per presence for flags and dummies), and caution that dummies are relative to the average level.
17. **Holdout used exactly once**, for the tuned model only. The majority baseline is reported from CV, not the holdout. The notebook asserts the holdout has not been scored before.
18. **Submission model is refit on all 260,601 labelled rows**, with the tuned configuration and C, after the holdout evaluation. This is standard practice: it adds 20% more data and does not affect the reported holdout numbers.

## Added after the first full run

19. **Rare flags excluded from the interpretation chart.** In the first run, the largest "risk" odds ratio belonged to `has_secondary_use_school` (OR ≈ 2.1), a flag set on well under 1% of buildings, so its coefficient rests on very few buildings and is not credible. The chart and the plain-language discussion now cover only features present in at least 1% of training buildings, plus all continuous features. The excluded rare flags with the largest coefficients are still listed in `results.json → coefficients.excluded_rare_top`, so nothing is hidden. Only the reporting changed; the model is the same.
20. **E4 keeps only `floors_x_log_age`.** It was the only candidate that improved all 5 folds, and only by about +0.02 pp. We kept it to follow the pre-registered rule, but we report it as a negligible effect rather than a meaningful gain.
21. **The tuned C (0.3) is reported, but we do not oversell it.** The CV curve is flat to within about 0.05 pp across C = 0.01–100, which is less than one fold standard deviation.
22. **Run-to-run variation in the 4th decimal.** Repeated full runs reproduced the holdout metrics exactly (micro-F1 0.7405, macro-F1 0.6798). Some CV means moved by about ±0.0001 between runs with different `N_JOBS` (for example E3 0.7351 → 0.7350), and the maximum solver iterations went from 325 to 337. These differences come from multithreaded BLAS floating-point ordering, not randomness in the splits (every split uses `random_state=42`). They do not affect any conclusion. The submitted documents are built from the final run's `results.json`.
