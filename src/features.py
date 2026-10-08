"""Feature groups, custom transformers and the leakage-safe preprocessing ColumnTransformer."""
import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import (FunctionTransformer, OneHotEncoder, StandardScaler,
                                   TargetEncoder)

from .data import AGE_PLACEHOLDER, RANDOM_STATE

GEO1, GEO2, GEO3 = "geo_level_1_id", "geo_level_2_id", "geo_level_3_id"
GEO_COLS = [GEO1, GEO2, GEO3]
CATEGORICAL = [
    "land_surface_condition", "foundation_type", "roof_type", "ground_floor_type",
    "other_floor_type", "position", "plan_configuration", "legal_ownership_status",
]
NUMERIC_LOG = ["age", "area_percentage", "height_percentage"]   # right-skewed -> log1p + scale
NUMERIC_PLAIN = ["count_floors_pre_eq", "count_families"]         # small counts -> scale only
SUPERSTRUCTURE = [
    "has_superstructure_adobe_mud", "has_superstructure_mud_mortar_stone",
    "has_superstructure_stone_flag", "has_superstructure_cement_mortar_stone",
    "has_superstructure_mud_mortar_brick", "has_superstructure_cement_mortar_brick",
    "has_superstructure_timber", "has_superstructure_bamboo",
    "has_superstructure_rc_non_engineered", "has_superstructure_rc_engineered",
    "has_superstructure_other",
]
SECONDARY_USE = [
    "has_secondary_use", "has_secondary_use_agriculture", "has_secondary_use_hotel",
    "has_secondary_use_rental", "has_secondary_use_institution", "has_secondary_use_school",
    "has_secondary_use_industry", "has_secondary_use_health_post",
    "has_secondary_use_gov_office", "has_secondary_use_use_police", "has_secondary_use_other",
]
AGE_FLAG = "age_is_placeholder"
BINARY = SUPERSTRUCTURE + SECONDARY_USE + [AGE_FLAG]

# Candidate engineered features (E4). All are deterministic row-wise functions, so they
# cannot leak information across rows; they are still computed inside the pipeline.
ENGINEERED_CANDIDATES = ["n_superstructure", "log_area_height_ratio", "floors_x_log_age",
                         "height_per_floor"]


class AgeCleaner(BaseEstimator, TransformerMixin):
    """Flag the age==995 placeholder and replace it with the training-fold median age."""

    def __init__(self, placeholder: int = AGE_PLACEHOLDER):
        self.placeholder = placeholder

    def fit(self, X, y=None):
        age = X["age"]
        self.median_ = float(age[age != self.placeholder].median())
        return self

    def transform(self, X):
        X = X.copy()
        is_ph = X["age"] == self.placeholder
        X[AGE_FLAG] = is_ph.astype(int)
        X["age"] = X["age"].astype(float)
        X.loc[is_ph, "age"] = self.median_
        return X


class FeatureEngineer(BaseEstimator, TransformerMixin):
    """Add the selected engineered features (stateless, row-wise)."""

    def __init__(self, features=()):
        self.features = features

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        X = X.copy()
        f = set(self.features)
        if "n_superstructure" in f:
            X["n_superstructure"] = X[SUPERSTRUCTURE].sum(axis=1)
        if "log_area_height_ratio" in f:
            X["log_area_height_ratio"] = np.log(X["area_percentage"] / X["height_percentage"])
        if "floors_x_log_age" in f:
            X["floors_x_log_age"] = X["count_floors_pre_eq"] * np.log1p(X["age"])
        if "height_per_floor" in f:
            X["height_per_floor"] = X["height_percentage"] / X["count_floors_pre_eq"]
        return X


def build_preprocessor(use_geo1: bool, use_geo23: bool, engineered=()) -> ColumnTransformer:
    """Every statistic (medians, means, scales, category lists, target encodings) is
    learned in ``fit`` - i.e. on the training fold only when used inside CV."""
    transformers = [
        ("log_num", Pipeline([("log", FunctionTransformer(np.log1p, feature_names_out="one-to-one")),
                              ("scale", StandardScaler())]), NUMERIC_LOG),
        ("num", StandardScaler(), NUMERIC_PLAIN + list(engineered)),
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL),
        ("bin", "passthrough", BINARY),
    ]
    if use_geo1:
        transformers.append(
            ("geo1", OneHotEncoder(handle_unknown="ignore", sparse_output=False), [GEO1]))
    if use_geo23:
        # Multiclass target encoding; fit_transform cross-fits internally (5 folds) so a
        # building's own label never contributes to its own encoded training value.
        transformers.append(
            ("geo_te", TargetEncoder(target_type="multiclass", cv=5, shuffle=True,
                                     random_state=RANDOM_STATE), [GEO2, GEO3]))
    return ColumnTransformer(transformers, remainder="drop", verbose_feature_names_out=False)
