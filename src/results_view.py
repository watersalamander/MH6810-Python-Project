"""Read-only view over outputs/results.json used by the report and slide builders.

Every number that appears in the report or slides is formatted from this object, so the
documents can never drift from the computed results."""
from .evaluate import load_results
from .plots import MODEL_ORDER, pretty_feature


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
        self.models, self.final = r["models"], r["final_model"]
        self.order = [k for k in MODEL_ORDER if k in self.models]
        self.F = self.final["key"]                      # key of the overall final model

    # --- three-model helpers (keys: logreg, random_forest, hist_gb)
    def label(self, k):
        return self.models[k]["label"]

    def mcv(self, k, metric="f1_micro"):
        return self.models[k]["cv"][metric]["mean"]

    def mcv_sd(self, k, metric="f1_micro"):
        return self.models[k]["cv"][metric]["std"]

    def mcv_cell(self, k, metric="f1_micro"):
        return f"{self.mcv(k, metric):.4f} ± {self.mcv_sd(k, metric):.4f}"

    def mho(self, k, metric="f1_micro"):
        return self.models[k]["holdout"][metric]

    def mrec(self, k, c, holdout=True):
        if holdout:
            return self.models[k]["holdout"]["per_class"][str(c)]["recall"]
        return self.models[k]["cv"][f"recall_{c}"]["mean"]

    def mcap(self, k, frac=20):
        return self.models[k]["prioritisation"]["at_fraction"][str(frac)]["capture_rate"]

    def mauc(self, k):
        return self.models[k]["prioritisation"]["auc_grade3_vs_rest"]

    def params_txt(self, k, sep=", "):
        return sep.join(f"{a} = {v:g}" if isinstance(v, (int, float)) else f"{a} = {v}"
                        for a, v in self.models[k]["best_params"].items())

    def grid_txt(self, k):
        return "; ".join(f"{a} ∈ {{{', '.join(f'{v:g}' if isinstance(v, (int, float)) else str(v) for v in vals)}}}"
                         for a, vals in self.models[k]["grid"].items())

    def fcm(self, i, j, k=None):
        """Row-normalised holdout confusion-matrix cell of model k (default: final model)."""
        return self.models[k or self.F]["holdout"]["confusion_matrix_normalised"][i - 1][j - 1]

    def top_importance(self, k, top=5):
        return self.models[k]["importance"][:top]

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
