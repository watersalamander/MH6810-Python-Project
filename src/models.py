"""Model factory: experiment configurations, the ordinal logistic model and pipelines."""
from dataclasses import dataclass, field, replace

import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.utils.validation import check_is_fitted

from .data import RANDOM_STATE
from .features import AgeCleaner, FeatureEngineer, build_preprocessor

MAX_ITER = 5000


@dataclass(frozen=True)
class Config:
    name: str
    description: str
    baseline: bool = False
    use_geo1: bool = False
    use_geo23: bool = False
    engineered: tuple = field(default_factory=tuple)
    class_weight: str | None = None
    ordinal: bool = False
    C: float = 1.0

    def with_(self, **kw) -> "Config":
        return replace(self, **kw)


class OrdinalLogisticRegression(ClassifierMixin, BaseEstimator):
    """Ordinal classifier built from K-1 cumulative binary logistic models.

    Model k estimates P(y > c_k). Cumulative probabilities are forced non-increasing,
    class probabilities are their successive differences, and the prediction is the most
    probable class.
    """

    def __init__(self, C=1.0, class_weight=None, max_iter=MAX_ITER):
        self.C = C
        self.class_weight = class_weight
        self.max_iter = max_iter

    def fit(self, X, y):
        y = np.asarray(y)
        self.classes_ = np.unique(y)
        self.models_ = []
        for c in self.classes_[:-1]:
            m = LogisticRegression(C=self.C, class_weight=self.class_weight, solver="lbfgs",
                                   max_iter=self.max_iter, random_state=RANDOM_STATE)
            m.fit(X, (y > c).astype(int))
            self.models_.append(m)
        return self

    @property
    def n_iter_(self):
        return np.array([int(np.max(m.n_iter_)) for m in self.models_])

    def cumulative_proba(self, X):
        """Columns: P(y > c_1), ..., P(y > c_{K-1}), forced non-increasing."""
        check_is_fitted(self, "models_")
        cum = np.column_stack([m.predict_proba(X)[:, 1] for m in self.models_])
        return np.minimum.accumulate(cum, axis=1)

    def predict_proba(self, X):
        cum = self.cumulative_proba(X)
        n = cum.shape[0]
        full = np.hstack([np.ones((n, 1)), cum, np.zeros((n, 1))])
        return full[:, :-1] - full[:, 1:]

    def predict(self, X):
        return self.classes_[np.argmax(self.predict_proba(X), axis=1)]


def make_model(cfg: Config) -> Pipeline:
    if cfg.baseline:
        return Pipeline([("clf", DummyClassifier(strategy="most_frequent"))])
    if cfg.ordinal:
        clf = OrdinalLogisticRegression(C=cfg.C, class_weight=cfg.class_weight)
    else:
        # lbfgs with 3 classes fits a multinomial (softmax) logistic regression.
        clf = LogisticRegression(C=cfg.C, class_weight=cfg.class_weight, solver="lbfgs",
                                 max_iter=MAX_ITER, random_state=RANDOM_STATE)
    return Pipeline([
        ("age", AgeCleaner()),
        ("fe", FeatureEngineer(cfg.engineered)),
        ("pre", build_preprocessor(cfg.use_geo1, cfg.use_geo23, cfg.engineered)),
        ("clf", clf),
    ])


def max_n_iter(pipe: Pipeline) -> int:
    clf = pipe.named_steps["clf"]
    return int(np.max(clf.n_iter_)) if hasattr(clf, "n_iter_") else 0


E0 = Config("E0", "Majority-class baseline", baseline=True)
E1 = Config("E1", "Logistic regression, structural features only")
E2 = E1.with_(name="E2", description="E1 + one-hot geo_level_1_id", use_geo1=True)
E3 = E2.with_(name="E3", description="E2 + target-encoded geo_level_2/3_id", use_geo23=True)
