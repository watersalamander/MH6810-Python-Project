"""Data loading, constants and the train/holdout split."""
from pathlib import Path

import pandas as pd
from sklearn.model_selection import StratifiedKFold, train_test_split

RANDOM_STATE = 42
TARGET = "damage_grade"
ID_COL = "building_id"
CLASSES = [1, 2, 3]
AGE_PLACEHOLDER = 995

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
FIG_DIR = ROOT / "figures"
OUT_DIR = ROOT / "outputs"
RESULTS_PATH = OUT_DIR / "results.json"
SUBMISSION_PATH = OUT_DIR / "submission.csv"


def load_labelled() -> pd.DataFrame:
    """Merge train_values and train_labels on building_id (inner join, validated 1:1)."""
    values = pd.read_csv(DATA_DIR / "train_values.csv")
    labels = pd.read_csv(DATA_DIR / "train_labels.csv")
    df = values.merge(labels, on=ID_COL, how="inner", validate="one_to_one")
    assert len(df) == len(values) == len(labels), "values/labels do not align"
    return df


def load_test() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "test_values.csv")


def split_xy(df: pd.DataFrame):
    X = df.drop(columns=[ID_COL, TARGET])
    y = df[TARGET].astype(int)
    return X, y


def train_holdout_split(df: pd.DataFrame, test_size: float = 0.2):
    """Stratified 80/20 split. The holdout is only scored once, at the very end."""
    train_df, holdout_df = train_test_split(
        df, test_size=test_size, stratify=df[TARGET], random_state=RANDOM_STATE
    )
    return train_df.reset_index(drop=True), holdout_df.reset_index(drop=True)


def cv_splitter(n_splits: int = 5) -> StratifiedKFold:
    return StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=RANDOM_STATE)
