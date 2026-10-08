"""Read-only view over outputs/results.json used by the report and slide builders.

Every number that appears in the report or slides is formatted from this object, so the
documents can never drift from the computed results."""
from .evaluate import load_results
from .plots import pretty_feature


def pct(x, d=1):
    return f"{100 * x:.{d}f}%"


def pp(x, d=1):
    """Difference in percentage points, signed."""
    return f"{100 * x:+.{d}f} pp"


def f3(x):
    return f"{x:.3f}"


def f4(x):
    return f"{x:.4f}"


def n(x):
    return f"{int(x):,}"


class ResultsView:
    def __init__(self, results=None):
        self.r = results or load_results()
        r = self.r
        self.data, self.split, self.eda = r["data"], r["split"], r["eda"]
        self.exp, self.tun, self.hold = r["experiments"], r["tuning"], r["holdout"]
        self.prio, self.coef, self.sub = r["prioritisation"], r["coefficients"], r["submission"]
        self.abl, self.conv = r["feature_ablation"], r["convergence"]
        self.best = r["best_config"]["name"]

    # --- experiment helpers
    def mic(self, k):
        return self.exp[k]["f1_micro"]["mean"]

    def mac(self, k):
        return self.exp[k]["f1_macro"]["mean"]

    def mic_sd(self, k):
        return self.exp[k]["f1_micro"]["std"]

    def mac_sd(self, k):
        return self.exp[k]["f1_macro"]["std"]

    def rec(self, k, c):
        return self.exp[k][f"recall_{c}"]["mean"]

    def cv_cell(self, k, metric="f1_micro"):
        e = self.exp[k][metric]
        return f"{e['mean']:.4f} ± {e['std']:.4f}"

    @property
    def kept(self):
        return self.abl["kept"]

    @property
    def best_C(self):
        return self.tun["best_C"]

    def cap(self, k):
        return self.prio["at_fraction"][str(k)]["capture_rate"]

    def lift(self, k):
        return self.prio["at_fraction"][str(k)]["lift"]

    def prec_top(self, k):
        return self.prio["at_fraction"][str(k)]["precision_in_top"]

    def pc(self, c, m):
        return self.hold["per_class"][str(c)][m]

    def cmn(self, i, j):
        return self.hold["confusion_matrix_normalised"][i - 1][j - 1]

    def top_features(self, which="raising", k=5):
        return [(pretty_feature(d["feature"]), d["odds_ratio"]) for d in self.coef[f"top_{which}"][:k]]

    def coef_of(self, feature):
        for lst in (self.coef["top_raising"], self.coef["top_lowering"]):
            for d in lst:
                if d["feature"] == feature:
                    return d["odds_ratio"]
        return None
