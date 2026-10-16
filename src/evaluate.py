"""Cross-validation, holdout metrics, prioritisation (capture) analysis and coefficients."""
import json
import time

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (confusion_matrix, f1_score, make_scorer,
                             precision_recall_fscore_support, recall_score, roc_auc_score)
from sklearn.inspection import permutation_importance
from sklearn.model_selection import GridSearchCV, cross_validate

from .data import CLASSES, RESULTS_PATH, cv_splitter
from .features import GEO_COLS
from .models import OrdinalLogisticRegression, max_n_iter

SCORING = {"f1_micro": "f1_micro", "f1_macro": "f1_macro"}
# Per-class recall, to see *where* class weighting / the ordinal model change behaviour.
SCORING.update({f"recall_{c}": make_scorer(recall_score, labels=[c], average="macro",
                                           zero_division=0) for c in CLASSES})


def n_iter_scorer(estimator, X, y):
    """Pseudo-'score' that records the solver iterations of a fitted pipeline, so that
    GridSearchCV can report convergence for every fold (workers swallow warnings)."""
    return max_n_iter(estimator)


def run_cv(model, X, y, n_jobs=5) -> dict:
    """Stratified 5-fold CV; returns mean/std of each metric plus convergence info."""
    t0 = time.time()
    res = cross_validate(model, X, y, cv=cv_splitter(), scoring=SCORING, n_jobs=n_jobs,
                         return_estimator=True, error_score="raise")
    out = {}
    for k in SCORING:
        s = res[f"test_{k}"]
        out[k] = {"mean": float(s.mean()), "std": float(s.std()),
                  "folds": [float(v) for v in s]}
    out["max_n_iter"] = int(max(max_n_iter(e) for e in res["estimator"]))
    out["fit_time_s"] = float(np.mean(res["fit_time"]))
    out["wall_time_s"] = float(time.time() - t0)
    return out


def classification_summary(y_true, y_pred) -> dict:
    p, r, f, s = precision_recall_fscore_support(y_true, y_pred, labels=CLASSES,
                                                 zero_division=0)
    cm = confusion_matrix(y_true, y_pred, labels=CLASSES)
    cm_norm = cm / cm.sum(axis=1, keepdims=True)
    return {
        "f1_micro": float(f1_score(y_true, y_pred, average="micro")),
        "f1_macro": float(f1_score(y_true, y_pred, average="macro")),
        "per_class": {str(c): {"precision": float(p[i]), "recall": float(r[i]),
                               "f1": float(f[i]), "support": int(s[i])}
                      for i, c in enumerate(CLASSES)},
        "confusion_matrix": cm.tolist(),
        "confusion_matrix_normalised": cm_norm.tolist(),
        "n": int(len(y_true)),
    }


def capture_curve(y_true, p_grade3, fractions=(0.10, 0.20, 0.30)):
    """Rank buildings by P(grade 3) and compute the share of all grade-3 buildings found
    after inspecting the top x% of the list."""
    y3 = (np.asarray(y_true) == 3).astype(int)
    order = np.argsort(-np.asarray(p_grade3), kind="mergesort")
    hits = np.cumsum(y3[order])
    n, total = len(y3), y3.sum()
    share_inspected = np.arange(1, n + 1) / n
    share_captured = hits / total
    at = {}
    for fr in fractions:
        k = int(round(fr * n))
        cap = float(hits[k - 1] / total)
        prec = float(hits[k - 1] / k)
        at[f"{int(fr * 100)}"] = {"capture_rate": cap, "lift": cap / fr,
                                  "precision_in_top": prec, "n_inspected": k}
    summary = {
        "at_fraction": at,
        "base_rate_grade3": float(total / n),
        "auc_grade3_vs_rest": float(roc_auc_score(y3, p_grade3)),
        "n_buildings": int(n),
        "n_grade3": int(total),
    }
    return share_inspected, share_captured, summary


def grade3_coefficients(pipe, X=None) -> pd.DataFrame:
    """Coefficients driving grade-3 damage, as odds ratios.

    Multinomial LR: the grade-3 row of ``coef_`` (log-odds of grade 3 relative to the
    model's softmax reference). Ordinal LR: the P(grade > 2) model."""
    names = pipe.named_steps["pre"].get_feature_names_out()
    clf = pipe.named_steps["clf"]
    if isinstance(clf, OrdinalLogisticRegression):
        coef = clf.models_[-1].coef_[0]
        source = "ordinal P(grade>2) model"
    elif isinstance(clf, LogisticRegression):
        coef = clf.coef_[list(clf.classes_).index(3)]
        source = "multinomial grade-3 row"
    else:
        raise TypeError(type(clf))
    df = pd.DataFrame({"feature": names, "coef": coef})
    df["odds_ratio"] = np.exp(df["coef"])
    df["is_location"] = df["feature"].str.startswith(tuple(GEO_COLS))
    df["prevalence"] = np.nan  # share of buildings with the flag/dummy set; NaN for continuous
    if X is not None:
        Z = np.asarray(pipe[:-1].transform(X), dtype=float)
        binary = np.all((Z == 0) | (Z == 1), axis=0)
        df.loc[binary, "prevalence"] = Z[:, binary].mean(axis=0)
    df.attrs["source"] = source
    return df.sort_values("coef", ascending=False).reset_index(drop=True)


def grid_search(model, param_grid, X, y, n_jobs=1, extra_scoring=None) -> GridSearchCV:
    """GridSearchCV on the shared 5 folds, scoring every SCORING metric, refit on f1_micro."""
    scoring = {**SCORING, **(extra_scoring or {})}
    grid = GridSearchCV(model, param_grid, cv=cv_splitter(), scoring=scoring, refit="f1_micro",
                        n_jobs=n_jobs, error_score="raise")
    t0 = time.time()
    grid.fit(X, y)
    grid.wall_time_s_ = float(time.time() - t0)
    return grid


def _jsonable(v):
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    return v


def grid_summary(grid: GridSearchCV, n_splits: int = 5) -> dict:
    """Best candidate's fold scores (same format as run_cv) plus one row per candidate."""
    cvr, b = grid.cv_results_, grid.best_index_
    best = {}
    for k in SCORING:
        folds = [float(cvr[f"split{i}_test_{k}"][b]) for i in range(n_splits)]
        best[k] = {"mean": float(np.mean(folds)), "std": float(np.std(folds)), "folds": folds}
    rows = []
    for i, params in enumerate(cvr["params"]):
        rows.append({"params": {k.replace("clf__", ""): _jsonable(v) for k, v in params.items()},
                     "f1_micro_mean": float(cvr["mean_test_f1_micro"][i]),
                     "f1_micro_std": float(cvr["std_test_f1_micro"][i]),
                     "f1_macro_mean": float(cvr["mean_test_f1_macro"][i]),
                     "mean_fit_time_s": float(cvr["mean_fit_time"][i]),
                     "rank": int(cvr["rank_test_f1_micro"][i])})
    return {"cv": best, "rows": rows,
            "best_params": {k.replace("clf__", ""): _jsonable(v) for k, v in grid.best_params_.items()},
            "grid": {k.replace("clf__", ""): [_jsonable(v) for v in vals]
                     for k, vals in grid.param_grid.items()},
            "n_candidates": len(rows), "time_s": getattr(grid, "wall_time_s_", None)}


def proba_of_grade3(model, X) -> np.ndarray:
    proba = model.predict_proba(X)
    return proba[:, list(model.classes_).index(3)]


def raw_permutation_importance(model, X, y, n_rows=10_000, n_repeats=5, random_state=42) -> list:
    """Permutation importance of the ORIGINAL input columns (the whole pipeline is the
    estimator, so e.g. geo_level_3_id covers its target-encoded columns), measured as the
    drop in micro-F1 on a random subsample of the holdout."""
    Xs = X.sample(n=min(n_rows, len(X)), random_state=random_state)
    ys = y.loc[Xs.index]
    r = permutation_importance(model, Xs, ys, scoring="f1_micro", n_repeats=n_repeats,
                               random_state=random_state, n_jobs=1)
    out = [{"feature": c, "mean": float(m), "std": float(sd)}
           for c, m, sd in zip(X.columns, r.importances_mean, r.importances_std)]
    return sorted(out, key=lambda d: -d["mean"])


def save_results(results: dict, path=RESULTS_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)


def load_results(path=RESULTS_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)
