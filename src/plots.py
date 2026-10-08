"""All figures (EDA and results). One consistent, slide-readable style."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.ticker import PercentFormatter  # noqa: E402

from .data import CLASSES, FIG_DIR, TARGET  # noqa: E402
from .features import SUPERSTRUCTURE  # noqa: E402

# Palette: ordinal one-hue (blue) ramp for damage grade; blue<->red diverging pair.
GRADE_COLORS = {1: "#86b6ef", 2: "#2a78d6", 3: "#104281"}
GRADE_LABELS = {1: "Grade 1 (low)", 2: "Grade 2 (medium)", 3: "Grade 3 (destroyed)"}
BLUE, RED, ORANGE, GRAY = "#2a78d6", "#e34948", "#eb6834", "#8a8984"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
DIVERGING = LinearSegmentedColormap.from_list("bgr", ["#104281", BLUE, "#f0efec", RED, "#a12828"])
DPI = 200

plt.rcParams.update({
    "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
    "font.family": "DejaVu Sans", "font.size": 12, "axes.titlesize": 14,
    "axes.titleweight": "bold", "axes.titlelocation": "left", "axes.labelsize": 12,
    "axes.labelcolor": INK2, "axes.edgecolor": GRID, "axes.spines.top": False,
    "axes.spines.right": False, "xtick.color": INK2, "ytick.color": INK2,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
    "legend.frameon": False, "legend.fontsize": 11, "text.color": INK,
})


def _save(fig, name):
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    path = FIG_DIR / f"{name}.png"
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    return path


def _grade_shares(df, col):
    return pd.crosstab(df[col], df[TARGET], normalize="index").reindex(columns=CLASSES, fill_value=0)


def _stacked_hbar(ax, shares, counts=None, title=None, label_min=0.08):
    """100% stacked horizontal bars, sorted so the most-damaged category is on top."""
    shares = shares.sort_values(3)
    left = np.zeros(len(shares))
    ylab = [str(i) for i in shares.index]
    for c in CLASSES:
        v = shares[c].values
        ax.barh(ylab, v, left=left, color=GRADE_COLORS[c], edgecolor="white", linewidth=1.5,
                height=0.75, label=GRADE_LABELS[c])
        for y_i, (l, w) in enumerate(zip(left, v)):
            if w >= label_min:
                ax.text(l + w / 2, y_i, f"{w:.0%}", ha="center", va="center", fontsize=10,
                        color="white" if c > 1 else INK)
        left += v
    if counts is not None:
        for y_i, k in enumerate(shares.index):
            ax.text(1.01, y_i, f"n={counts[k]:,}", va="center", fontsize=9.5, color=INK2)
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(PercentFormatter(1.0))
    ax.grid(axis="y", visible=False)
    if title:
        ax.set_title(title)


# ----------------------------------------------------------------------------- EDA
def plot_class_distribution(y):
    counts = y.value_counts().reindex(CLASSES)
    shares = counts / counts.sum()
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    bars = ax.bar([GRADE_LABELS[c] for c in CLASSES], counts.values,
                  color=[GRADE_COLORS[c] for c in CLASSES], width=0.6)
    for b, n, s in zip(bars, counts.values, shares.values):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height(), f"{s:.1%}\n({n:,})",
                ha="center", va="bottom", fontsize=11)
    ax.set_ylabel("Buildings")
    ax.set_ylim(0, counts.max() * 1.22)
    ax.grid(axis="x", visible=False)
    ax.set_title("Class distribution of damage grade (training split)")
    return _save(fig, "fig01_class_distribution")


def plot_damage_by_foundation_roof(df):
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.2), gridspec_kw={"wspace": 0.45})
    for ax, col, title in [(axes[0], "foundation_type", "Foundation type"),
                           (axes[1], "roof_type", "Roof type")]:
        _stacked_hbar(ax, _grade_shares(df, col), df[col].value_counts(), title)
    axes[0].legend(loc="upper center", bbox_to_anchor=(1.1, -0.12), ncol=3)
    fig.suptitle("Damage grade by foundation and roof type (category codes are anonymised)",
                 x=0.06, ha="left", y=1.02, fontsize=12, color=INK2)
    return _save(fig, "fig02_damage_by_foundation_roof")


def plot_superstructure(df):
    rows = []
    for col in SUPERSTRUCTURE:
        sub = df[df[col] == 1]
        rows.append({"material": col.replace("has_superstructure_", "").replace("_", " "),
                     "n": len(sub), **sub[TARGET].value_counts(normalize=True)
                     .reindex(CLASSES, fill_value=0).to_dict()})
    shares = pd.DataFrame(rows).set_index("material")
    fig, ax = plt.subplots(figsize=(10, 5.5))
    _stacked_hbar(ax, shares[CLASSES], shares["n"],
                  "Damage grade by superstructure material (buildings may use several)")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=3)
    return _save(fig, "fig03_damage_by_superstructure")


def plot_damage_by_geo1(df):
    shares = _grade_shares(df, "geo_level_1_id").sort_values(3, ascending=False)
    fig, ax = plt.subplots(figsize=(13, 4.8))
    x = np.arange(len(shares))
    bottom = np.zeros(len(shares))
    for c in [3, 2, 1]:
        ax.bar(x, shares[c].values, bottom=bottom, color=GRADE_COLORS[c], width=0.8,
               edgecolor="white", linewidth=1, label=GRADE_LABELS[c])
        bottom += shares[c].values
    ax.set_xticks(x, shares.index.astype(str), fontsize=10)
    ax.set_xlabel("geo_level_1_id (region), sorted by share of grade 3")
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.set_ylim(0, 1)
    ax.grid(axis="x", visible=False)
    ax.set_title("Damage mix varies strongly by region")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.17), ncol=3)
    return _save(fig, "fig04_damage_by_geo1")


def plot_numeric_distributions(df):
    import seaborn as sns
    d = df[df["age"] != 995]
    specs = [("age", "Age (years, placeholder 995 excluded)", True),
             ("area_percentage", "Normalised footprint area", True),
             ("height_percentage", "Normalised height", True),
             ("count_floors_pre_eq", "Floors before the earthquake", False)]
    fig, axes = plt.subplots(2, 2, figsize=(13, 7.5), gridspec_kw={"hspace": 0.45, "wspace": 0.2})
    for ax, (col, title, logx) in zip(axes.ravel(), specs):
        if logx:
            vals = np.log1p(d[col])
            bins = np.linspace(vals.min(), vals.max(), 40)
            sns.histplot(d.assign(_v=vals), x="_v", hue=TARGET, multiple="stack", bins=bins,
                         palette=GRADE_COLORS, hue_order=CLASSES[::-1], ax=ax, legend=False,
                         edgecolor="white", linewidth=0.4, alpha=1)
            ticks = [t for t in [0, 1, 5, 10, 20, 50, 100, 200] if np.log1p(t) <= vals.max() + 0.1]
            ax.set_xticks(np.log1p(ticks), [str(t) for t in ticks])
            ax.set_xlabel(f"{col} (log scale)")
        else:
            sns.histplot(d, x=col, hue=TARGET, multiple="stack", discrete=True,
                         palette=GRADE_COLORS, hue_order=CLASSES[::-1], ax=ax, legend=False,
                         edgecolor="white", linewidth=0.4, alpha=1)
            ax.set_xlabel(col)
        ax.set_title(title, fontsize=12.5)
        ax.set_ylabel("Buildings")
        ax.grid(axis="x", visible=False)
    handles = [plt.Rectangle((0, 0), 1, 1, color=GRADE_COLORS[c]) for c in CLASSES]
    fig.legend(handles, [GRADE_LABELS[c] for c in CLASSES], loc="lower center", ncol=3,
               bbox_to_anchor=(0.5, -0.03))
    fig.suptitle("Numeric features are right-skewed (shown on log scale); stacked by damage grade",
                 x=0.07, ha="left", fontsize=13, y=0.98)
    return _save(fig, "fig05_numeric_distributions")


def plot_correlation(df):
    cols = ["age", "area_percentage", "height_percentage", "count_floors_pre_eq",
            "count_families", "has_superstructure_mud_mortar_stone",
            "has_superstructure_cement_mortar_brick", "has_superstructure_rc_engineered",
            "has_superstructure_timber", "has_secondary_use", TARGET]
    d = df[df["age"] != 995][cols]
    corr = d.corr(method="spearman")
    short = {c: c.replace("has_superstructure_", "ss_").replace("_percentage", "_pct")
             .replace("count_floors_pre_eq", "floors") for c in cols}
    corr = corr.rename(index=short, columns=short)
    fig, ax = plt.subplots(figsize=(10, 8))
    im = ax.imshow(corr.values, cmap=DIVERGING, vmin=-1, vmax=1)
    ax.set_xticks(range(len(corr)), corr.columns, rotation=45, ha="right", fontsize=10.5)
    ax.set_yticks(range(len(corr)), corr.index, fontsize=10.5)
    for i in range(len(corr)):
        for j in range(len(corr)):
            v = corr.values[i, j]
            ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=8.5,
                    color="white" if abs(v) > 0.55 else INK)
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    fig.colorbar(im, ax=ax, shrink=0.75, label="Spearman correlation")
    ax.set_title("Spearman correlation of numeric/structural features and damage grade")
    return _save(fig, "fig06_correlation")


# ------------------------------------------------------------------------- results
def plot_experiments(table: pd.DataFrame, best_name: str):
    t = table.reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(11, 4.8))
    x = np.arange(len(t))
    colors = [ORANGE if n == best_name else (GRAY if n == "E0" else BLUE) for n in t["name"]]
    ax.bar(x, t["f1_micro_mean"], yerr=t["f1_micro_std"], color=colors, width=0.62,
           capsize=4, error_kw={"ecolor": INK2, "elinewidth": 1})
    for xi, v in zip(x, t["f1_micro_mean"]):
        ax.text(xi, v + 0.012, f"{v:.3f}", ha="center", fontsize=10.5)
    ax.set_xticks(x, [f"{n}\n{s}" for n, s in zip(t["name"], t["short"])], fontsize=10)
    ax.set_ylabel("CV micro-F1 (mean ± std)")
    lo = max(0, t["f1_micro_mean"].min() - 0.08)
    ax.set_ylim(lo, min(1, t["f1_micro_mean"].max() + 0.06))
    ax.grid(axis="x", visible=False)
    ax.set_title("5-fold CV micro-F1 by experiment (orange = selected for tuning)")
    return _save(fig, "fig07_experiments")


def plot_c_tuning(cv_results: pd.DataFrame, best_c: float):
    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.errorbar(cv_results["C"], cv_results["mean"], yerr=cv_results["std"], color=BLUE,
                marker="o", markersize=7, linewidth=2, capsize=3)
    ax.axvline(best_c, color=ORANGE, linestyle="--", linewidth=1.5)
    ax.text(best_c, ax.get_ylim()[0], f"  best C = {best_c:g}", color=ORANGE, va="bottom")
    ax.set_xscale("log")
    ax.set_xlabel("Inverse regularisation strength C (log scale)")
    ax.set_ylabel("CV micro-F1")
    ax.set_title("Tuning C with GridSearchCV (5-fold)")
    return _save(fig, "fig08_c_tuning")


def plot_confusion(cm_norm, cm_counts):
    cm_norm, cm_counts = np.asarray(cm_norm), np.asarray(cm_counts)
    cmap = LinearSegmentedColormap.from_list("blues", ["#f4f8fd", "#86b6ef", "#2a78d6", "#104281"])
    fig, ax = plt.subplots(figsize=(6.4, 5.4))
    im = ax.imshow(cm_norm, cmap=cmap, vmin=0, vmax=1)
    for i in range(3):
        for j in range(3):
            ax.text(j, i, f"{cm_norm[i, j]:.1%}\n(n={cm_counts[i, j]:,})", ha="center",
                    va="center", fontsize=11, color="white" if cm_norm[i, j] > 0.5 else INK)
    ax.set_xticks(range(3), [f"Grade {c}" for c in CLASSES])
    ax.set_yticks(range(3), [f"Grade {c}" for c in CLASSES])
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Actual")
    ax.grid(False)
    fig.colorbar(im, ax=ax, shrink=0.8, format=PercentFormatter(1.0), label="Share of actual class")
    ax.set_title("Holdout confusion matrix (row-normalised)")
    return _save(fig, "fig09_confusion_matrix")


def plot_capture(share_inspected, share_captured, summary):
    fig, ax = plt.subplots(figsize=(8, 5.6))
    step = max(1, len(share_inspected) // 2000)
    ax.plot(share_inspected[::step], share_captured[::step], color=BLUE, linewidth=2.5,
            label="Model ranking by P(grade 3)")
    ax.plot([0, 1], [0, 1], color=GRAY, linestyle="--", linewidth=1.5, label="Random order")
    for k, v in summary["at_fraction"].items():
        fr, cap = int(k) / 100, v["capture_rate"]
        ax.plot([fr], [cap], "o", color=ORANGE, markersize=9, markeredgecolor="white",
                markeredgewidth=2, zorder=5)
        ax.annotate(f"top {k}% → {cap:.0%} of grade-3", (fr, cap), xytext=(12, -16),
                    textcoords="offset points", fontsize=11)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
    ax.xaxis.set_major_formatter(PercentFormatter(1.0))
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.set_xlabel("Share of buildings inspected (highest risk first)")
    ax.set_ylabel("Share of grade-3 buildings found")
    ax.legend(loc="lower right")
    ax.set_title("Prioritisation: grade-3 buildings captured vs inspection effort (holdout)")
    return _save(fig, "fig10_prioritisation_curve")


def pretty_feature(name: str) -> str:
    n = name.replace("has_superstructure_", "superstructure: ").replace("has_secondary_use_", "secondary use: ")
    for k in ["foundation_type", "roof_type", "ground_floor_type", "other_floor_type",
              "position", "plan_configuration", "land_surface_condition", "legal_ownership_status"]:
        if n.startswith(k + "_"):
            n = f"{k.replace('_', ' ')} = {n[len(k) + 1:]}"
    return n.replace("_", " ")


def plot_coefficients(coefs: pd.DataFrame, top=15, source="", min_prevalence=0.01):
    rare = coefs["prevalence"] < min_prevalence          # NaN (continuous) -> kept
    d = coefs[~coefs["is_location"] & ~rare].sort_values("coef")
    sel = pd.concat([d.head(top), d.tail(top)]).drop_duplicates("feature")
    fig, ax = plt.subplots(figsize=(10, 10))
    colors = [RED if c > 0 else BLUE for c in sel["coef"]]
    y = np.arange(len(sel))
    ax.barh(y, sel["odds_ratio"] - 1, left=1, color=colors, height=0.7)
    ax.set_xscale("log")
    ax.axvline(1, color=INK2, linewidth=1)
    ax.set_yticks(y, [pretty_feature(f) for f in sel["feature"]], fontsize=10.5)
    for yi, orr in zip(y, sel["odds_ratio"]):
        ax.text(orr * (1.04 if orr > 1 else 0.96), yi, f"{orr:.2f}", va="center",
                ha="left" if orr > 1 else "right", fontsize=9.5, color=INK2)
    lo, hi = sel["odds_ratio"].min(), sel["odds_ratio"].max()
    ax.set_xlim(lo / 1.5, hi * 1.5)
    ticks = [t for t in [0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 1, 1.5, 2, 3, 5, 10, 20]
             if lo / 1.5 <= t <= hi * 1.5]
    ax.set_xticks(ticks, [f"{t:g}" for t in ticks])
    ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax.set_xlabel("Odds ratio for grade-3 damage (log scale; <1 protective, >1 risk-raising)")
    ax.grid(axis="y", visible=False)
    ax.set_title(f"Top {top} features raising (red) and lowering (blue) grade-3 odds")
    if source:
        ax.text(0, -0.10, f"Source: {source}. Excluded: location features and flags present in "
                f"<{min_prevalence:.0%} of buildings. Numeric features: per 1 SD change.", transform=ax.transAxes, fontsize=9.5,
                color=INK2)
    return _save(fig, "fig11_coefficients")


def plot_recall_comparison(rows: pd.DataFrame):
    """Grouped bars of per-class CV recall for selected experiments."""
    fig, ax = plt.subplots(figsize=(9, 4.6))
    names = list(rows["label"])
    width = 0.8 / len(names)
    pal = [BLUE, ORANGE, "#1baf7a", "#4a3aa7"]
    x = np.arange(3)
    for i, (_, r) in enumerate(rows.iterrows()):
        vals = [r[f"recall_{c}"] for c in CLASSES]
        bars = ax.bar(x + (i - (len(names) - 1) / 2) * width, vals, width * 0.92,
                      color=pal[i], label=r["label"])
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + 0.01, f"{v:.2f}", ha="center", fontsize=9.5)
    ax.set_xticks(x, [GRADE_LABELS[c] for c in CLASSES])
    ax.set_ylabel("CV recall")
    ax.set_ylim(0, 1.05)
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=len(names))
    ax.set_title("Per-class recall: multinomial vs class-weighted vs ordinal")
    return _save(fig, "fig12_recall_comparison")


def plot_coefficients_compact(raising, lowering, k=7):
    """Slide-sized version of fig11 built from the results.json coefficient lists."""
    rows = sorted(raising[:k] + lowering[:k], key=lambda r: r["coef"])
    names = [pretty_feature(r["feature"]) for r in rows]
    orr = np.array([r["odds_ratio"] for r in rows])
    fig, ax = plt.subplots(figsize=(7.2, 6.0))
    y = np.arange(len(rows))
    ax.barh(y, orr - 1, left=1, color=[RED if o > 1 else BLUE for o in orr], height=0.68)
    ax.set_xscale("log")
    ax.axvline(1, color=INK2, linewidth=1)
    ax.set_yticks(y, names, fontsize=12.5)
    for yi, o in zip(y, orr):
        ax.text(o * (1.03 if o > 1 else 0.97), yi, f"{o:.2f}", va="center",
                ha="left" if o > 1 else "right", fontsize=11.5, color=INK2)
    ax.set_xlim(orr.min() / 1.35, orr.max() * 1.25)
    ticks = [t for t in [0.3, 0.5, 0.7, 1, 1.5, 2] if orr.min() / 1.35 <= t <= orr.max() * 1.25]
    ax.set_xticks(ticks, [f"{t:g}" for t in ticks])
    ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax.set_xlabel("Odds ratio for grade-3 damage (log scale)")
    ax.grid(axis="y", visible=False)
    ax.set_title(f"Top {k} risk-raising and protective features")
    return _save(fig, "fig11b_coefficients_slide")
