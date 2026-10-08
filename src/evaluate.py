"""Cross-validation, holdout metrics, prioritisation (capture) analysis and coefficients."""
import json
import time

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (confusion_matrix, f1_score, make_scorer,
                             precision_recall_fscore_support, recall_score, roc_auc_score)
from sklearn.model_selection import cross_validate

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


def save_results(results: dict, path=RESULTS_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)


def load_results(path=RESULTS_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)
