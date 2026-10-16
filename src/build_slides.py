"""Build slides/presentation.pptx (16:9) and slides/speaker_notes.md from outputs/results.json.

    python -m src.build_slides
"""
from PIL import Image as PILImage
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

from .data import FIG_DIR, ROOT
from .plots import plot_coefficients_compact, plot_importance
from .results_view import ResultsView, n, pct, pp

OUT = ROOT / "slides" / "presentation.pptx"
NOTES_MD = ROOT / "slides" / "speaker_notes.md"

NAVY = RGBColor(0x14, 0x23, 0x40)
BLUE = RGBColor(0x2A, 0x78, 0xD6)
DEEP = RGBColor(0x10, 0x42, 0x81)
LIGHTBLUE = RGBColor(0x86, 0xB6, 0xEF)
ORANGE = RGBColor(0xEB, 0x68, 0x34)
INK = RGBColor(0x0B, 0x0B, 0x0B)
INK2 = RGBColor(0x52, 0x51, 0x4E)
MUTED = RGBColor(0x8A, 0x89, 0x84)
TINT = RGBColor(0xF1, 0xF5, 0xFB)
LINE = RGBColor(0xD9, 0xE2, 0xEE)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
HEAD, BODY = "Cambria", "Calibri"
W, H = 13.333, 7.5
WPM = 140  # speaking rate used for timing estimates
TALK_MIN = 20  # length of the presentation slot (minutes)
N_PRESENTERS = 6


class Deck:
    def __init__(self):
        self.prs = Presentation()
        self.prs.slide_width, self.prs.slide_height = Inches(W), Inches(H)
        self.blank = self.prs.slide_layouts[6]
        self.notes = []          # (slide_no, title, notes)
        self.count = 0

    # ------------------------------------------------------------------ primitives
    def new(self, dark=False):
        s = self.prs.slides.add_slide(self.blank)
        self.count += 1
        bg = s.background.fill
        bg.solid()
        bg.fore_color.rgb = NAVY if dark else WHITE
        return s

    def text(self, s, x, y, w, h, content, size=16, color=INK, bold=False, font=BODY,
             align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, italic=False, spacing=None, name=None):
        """`content` is a string or a list of paragraphs; a paragraph is a string or a list
        of (text, {opts}) runs."""
        tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        if name:
            tb.name = name
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        tf.vertical_anchor = anchor
        paras = content if isinstance(content, list) else [content]
        for i, para in enumerate(paras):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = align
            if spacing:
                p.space_after = Pt(spacing)
            runs = para if isinstance(para, list) else [(para, {})]
            for txt, o in runs:
                r = p.add_run()
                r.text = txt
                f = r.font
                f.name = o.get("font", font)
                f.size = Pt(o.get("size", size))
                f.bold = o.get("bold", bold)
                f.italic = o.get("italic", italic)
                f.color.rgb = o.get("color", color)
        return tb

    def box(self, s, x, y, w, h, fill=TINT, line=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08):
        shp = s.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
        shp.fill.solid()
        shp.fill.fore_color.rgb = fill
        if line is None:
            shp.line.fill.background()
        else:
            shp.line.color.rgb = line
            shp.line.width = Pt(1.25)
        shp.shadow.inherit = False
        if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
            shp.adjustments[0] = radius
        return shp

    def badge(self, s, x, y, label, d=0.46, fill=ORANGE, color=WHITE, size=14):
        c = self.box(s, x, y, d, d, fill=fill, shape=MSO_SHAPE.OVAL)
        tf = c.text_frame
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        r = p.add_run()
        r.text = label
        r.font.size, r.font.bold, r.font.name = Pt(size), True, BODY
        r.font.color.rgb = color
        return c

    def arrow(self, s, x1, y1, x2, y2, color=MUTED, width=2):
        ln = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
        ln.line.color.rgb = color
        ln.line.width = Pt(width)
        line = ln.line._get_or_add_ln()
        from pptx.oxml.ns import qn
        tail = line.makeelement(qn("a:tailEnd"), {"type": "triangle", "w": "med", "len": "med"})
        line.append(tail)
        return ln

    def picture(self, s, path, x, y, w, h, align="center"):
        """Fit an image inside the (x, y, w, h) box, preserving aspect ratio."""
        iw, ih = PILImage.open(path).size
        scale = min(w / iw, h / ih)
        pw, ph = iw * scale, ih * scale
        px = x + (w - pw) / 2 if align == "center" else x
        py = y + (h - ph) / 2
        return s.shapes.add_picture(str(path), Inches(px), Inches(py), Inches(pw), Inches(ph))

    def header(self, s, section, title):
        self.text(s, 0.6, 0.38, 10, 0.3, section.upper(), size=12, color=ORANGE, bold=True,
                  name="Section label")
        self.text(s, 0.6, 0.68, 12.1, 0.8, title, size=30, color=NAVY, bold=True, font=HEAD,
                  name="Title")

    def footer(self, s, dark=False):
        col = LIGHTBLUE if dark else MUTED
        self.text(s, 0.6, 7.0, 8, 0.25, "Group [XX]  ·  Earthquake damage prediction: logistic regression, random forest, gradient boosting",
                  size=10, color=col)
        self.text(s, 11.9, 7.0, 0.85, 0.25, str(self.count), size=10, color=col, align=PP_ALIGN.RIGHT)

    def stat(self, s, x, y, w, big, label, color=NAVY, big_size=40, label_size=14, label_color=INK2):
        self.text(s, x, y, w, 0.75, big, size=big_size, bold=True, color=color, font=HEAD)
        self.text(s, x, y + 0.8, w, 0.7, label, size=label_size, color=label_color)

    def add_notes(self, s, title, notes):
        s.notes_slide.notes_text_frame.text = notes
        self.notes.append((self.count, title, notes))


def fig(name):
    return FIG_DIR / f"{name}.png"


def build(rv: ResultsView):
    d = Deck()
    R = rv
    e3_gain = R.mic("E3") - R.mic("E2")
    geo1_gain = R.mic("E2") - R.mic("E1")
    ord_diff = R.mic("E6") - R.mic("E4")
    bal_diff = R.mic("E5") - R.mic("E4")
    ord_mac = R.mac("E6") - R.mac("E4")
    bal_mac = R.mac("E5") - R.mac("E4")
    kept_txt = ", ".join(R.kept) if R.kept else "none"
    fe_gain = R.mic("E4") - R.mic("E3")
    H_mic, H_mac = R.hold["f1_micro"], R.hold["f1_macro"]
    base = R.mic("E0")
    F, FL = R.F, R.label(R.F)
    LR, RF, HGB = "logreg", "random_forest", "hist_gb"
    tree_won = F != LR
    gain_cv, gain_ho = R.final["cv_gain_over_logreg"], R.final["holdout_gain_over_logreg"]
    short = {LR: "LR", RF: "RF", HGB: "HGB"}

    # 1 ---------------------------------------------------------------- Title
    s = d.new(dark=True)
    for i, col in enumerate([LIGHTBLUE, BLUE, ORANGE]):
        d.box(s, 0.6 + i * 0.42, 0.9, 0.32, 0.32, fill=col, radius=0.15)
    d.text(s, 0.6, 1.55, 11.5, 2.0, "Predicting Earthquake Damage to Prioritise Building Inspections",
           size=44, bold=True, color=WHITE, font=HEAD)
    d.text(s, 0.6, 3.55, 11, 0.9,
           f"Logistic regression, random forest and gradient boosting on {n(R.data['n_train_rows'])} buildings from the 2015 Gorkha earthquake, Nepal",
           size=20, color=LIGHTBLUE)
    d.text(s, 0.6, 5.0, 11, 1.4, [
        [("Course: ", {"bold": True}), ("[COURSE CODE] – [COURSE NAME]", {})],
        [("Group [XX]: ", {"bold": True}),
         ("[Member 1 (ID)] · [Member 2 (ID)] · [Member 3 (ID)] · [Member 4 (ID)] · [Member 5 (ID)] · [Member 6 (ID)]", {})],
    ], size=15, color=WHITE, spacing=6)
    d.footer(s, dark=True)
    d.add_notes(s, "Title", (
        "Good morning everyone. We are Group [XX], and our project asks a very practical question: "
        "after a major earthquake, can a simple, transparent model tell inspectors which buildings to visit first? "
        f"We worked with records of {n(R.data['n_train_rows'])} buildings surveyed after the 2015 Gorkha earthquake in Nepal, "
        "and we compared three models: a transparent logistic regression, a random forest and gradient boosting. "
        "Over the next twenty minutes, six of us will walk you through the data, our preprocessing, the two ideas we are most proud of, "
        "how we trained and tested the models, what we found, and where we would go next."))

    # 2 ---------------------------------------------------------------- Dataset
    s = d.new()
    d.header(s, "Data set description", "Richter's Predictor: one row per building, three damage grades")
    stats = [(n(R.data["n_train_rows"]), "labelled buildings"),
             (str(R.data["n_features"]), "features per building"),
             ("3", "ordered damage grades"),
             (n(R.data["n_test_rows"]), "unlabelled test buildings")]
    for i, (big, lab) in enumerate(stats):
        d.stat(s, 0.6 + i * 3.1, 1.75, 2.9, big, lab, color=ORANGE if i == 0 else NAVY)
    groups = [
        ("Location", f"3 nested region levels: {n(R.data['n_unique']['geo_level_1_id'])} / "
                     f"{n(R.data['n_unique']['geo_level_2_id'])} / {n(R.data['n_unique']['geo_level_3_id'])} ids"),
        ("Size & age", "age, footprint area, height, number of floors"),
        ("Construction", "foundation, roof, floor types and 11 superstructure-material flags"),
        ("Use & ownership", "secondary uses, legal ownership, number of families"),
    ]
    for i, (t, body) in enumerate(groups):
        x = 0.6 + i * 3.1
        d.box(s, x, 3.65, 2.85, 2.35)
        d.badge(s, x + 0.25, 3.9, str(i + 1))
        d.text(s, x + 0.25, 4.55, 2.4, 0.4, t, size=18, bold=True, color=NAVY)
        d.text(s, x + 0.25, 5.0, 2.4, 1.0, body, size=14, color=INK2)
    d.text(s, 0.6, 6.3, 12, 0.5,
           f"Clean data: {R.data['n_missing_train']} missing values. Category codes are anonymised letters. "
           "Source: DrivenData / Nepal 2015 earthquake building survey.", size=12, color=MUTED)
    d.footer(s)
    d.add_notes(s, "Data set description", (
        "Our data come from the DrivenData competition Richter's Predictor, based on Nepal's post-earthquake building survey. "
        f"There are {n(R.data['n_train_rows'])} labelled buildings, each described by {R.data['n_features']} features, plus "
        f"{n(R.data['n_test_rows'])} unlabelled buildings that we only use for a competition submission. "
        f"The features fall into four groups. Location is given as three nested region levels, from {R.data['n_unique']['geo_level_1_id']} broad regions down to {n(R.data['n_unique']['geo_level_3_id'])} local areas. "
        "Then size and age, construction details such as foundation, roof and eleven superstructure-material flags, and finally use and ownership. "
        "The data are clean, with no missing values, but the categorical codes are anonymised letters, so we can say a foundation of type 'i' is safer, not exactly what 'i' is. "
        "Every one of these features was recorded by the survey, so a model built on them could in principle be applied to the next earthquake as soon as the building register exists, "
        "before a single inspector has visited."))

    # 3 ---------------------------------------------------------------- Problem statement
    s = d.new()
    d.header(s, "Problem statement", "Which buildings should inspectors visit first?")
    d.box(s, 0.6, 1.75, 6.4, 4.55, fill=NAVY)
    d.text(s, 1.0, 2.1, 5.7, 3.9,
           "“Can we predict how badly a building was damaged in the 2015 Gorkha earthquake "
           "from its structure and location, so post-disaster inspectors can prioritise which "
           "buildings to assess first?”", size=22, color=WHITE, font=HEAD, italic=True,
           anchor=MSO_ANCHOR.MIDDLE)
    items = [
        ("Task", "3-class ordinal classification: grade 1 (low), 2 (medium), 3 (near-destroyed)."),
        ("Metric", "Micro-F1 (the competition metric, equal to accuracy) plus macro-F1 so that the rare grade 1 counts too."),
        ("Use", "Rank buildings by predicted P(grade 3) and measure how many destroyed buildings an inspection list finds."),
        ("Models", "Logistic regression (transparent) vs random forest and HistGradientBoosting (flexible)."),
    ]
    for i, (t, body) in enumerate(items):
        y = 1.75 + i * 1.17
        d.badge(s, 7.45, y + 0.05, str(i + 1), fill=BLUE)
        d.text(s, 8.1, y, 4.7, 0.35, t, size=17, bold=True, color=NAVY)
        d.text(s, 8.1, y + 0.37, 4.7, 0.75, body, size=14, color=INK2)
    d.footer(s)
    d.add_notes(s, "Problem statement", (
        "Here is our problem statement. After an earthquake, inspection teams are scarce and there are hundreds of thousands of buildings. "
        "If a model can estimate how badly each building was damaged from information that is already on record, its structure and its location, "
        "teams can visit the most dangerous buildings first. "
        "Technically this is a three-class classification problem, and the classes are ordered, grade 1 to grade 3. "
        "We report micro-F1, which is the competition metric and equals accuracy, and macro-F1, which gives the rare low-damage class equal weight. "
        "Because the real goal is prioritisation, we also rank buildings by their predicted probability of grade 3 and measure how many destroyed buildings an inspection list catches. "
        "Finally, we compare three models: logistic regression, which is transparent and easy to audit, and two tree ensembles, which are more flexible but harder to explain. "
        "Keep that trade-off in mind, accuracy against explainability, because it comes back at the end of our talk."))

    # 4 ---------------------------------------------------------------- EDA 0: class imbalance
    cs = R.data["class_share"]
    s = d.new()
    d.header(s, "Dataset pre-processing · exploration", "The damage grades are imbalanced")
    d.picture(s, fig("fig01_class_distribution"), 0.5, 1.6, 7.6, 5.2)
    cards = [
        (pct(cs["2"], 0), "of buildings are grade 2",
         f"Grade 3: {pct(cs['3'], 0)} · grade 1: only {pct(cs['1'], 0)} (about 1 in {round(1 / cs['1'])})"),
        (f"{base:.3f}", "micro-F1 from always guessing grade 2",
         f"…but macro-F1 only {R.mac('E0'):.3f}: grades 1 and 3 are never found"),
    ]
    for i, (big, lab, sub) in enumerate(cards):
        y = 1.7 + i * 1.72
        d.box(s, 8.45, y, 4.3, 1.55)
        d.text(s, 8.7, y + 0.12, 1.75, 0.7, big, size=30, bold=True, color=ORANGE if i == 0 else NAVY, font=HEAD)
        d.text(s, 10.45, y + 0.17, 2.2, 0.7, lab, size=14, bold=True, color=NAVY)
        d.text(s, 8.7, y + 0.88, 3.9, 0.6, sub, size=13, color=INK2)
    d.box(s, 8.45, 5.14, 4.3, 1.7, fill=NAVY)
    d.text(s, 8.7, 5.24, 3.9, 0.35, "How we handled it", size=15, bold=True, color=WHITE)
    d.text(s, 8.7, 5.62, 3.9, 1.2, [
        f"Stratified split and CV folds keep the {' / '.join(f'{100 * cs[c]:.0f}' for c in ('1', '2', '3'))} mix",
        "Report macro-F1 and per-class recall, not only accuracy",
        "Tested class weighting (E5) as a fix",
    ], size=12.5, color=LIGHTBLUE, spacing=3)
    d.footer(s)
    d.add_notes(s, "Exploration: class imbalance", (
        "Before looking at any feature, we looked at the target itself. This chart shows how many buildings fall into each damage grade, measured on our training split. "
        f"Grade 2 dominates with {pct(cs['2'], 0)} of buildings, grade 3 follows with {pct(cs['3'], 0)}, and grade 1, low damage, is only {pct(cs['1'], 0)}, about one building in {round(1 / cs['1'])}. "
        "This matters for three reasons. "
        f"First, it sets the bar: a model that ignores the data and always answers grade 2 is already right {pct(base, 0)} of the time, a micro-F1 of {base:.3f}. Anything we build has to beat that. "
        "Second, it is why we report two metrics. Micro-F1 counts every building equally, so it is dominated by grade 2; it equals plain accuracy. "
        f"Macro-F1 averages the F1 score of each grade with equal weight, so the rare grade 1 counts as much as grade 2. The always-grade-2 model gets a macro-F1 of only {R.mac('E0'):.3f}, which exposes it immediately. "
        f"Third, it shaped our procedure. Every split and every cross-validation fold is stratified, so each one keeps the same {', '.join(f'{100 * cs[c]:.0f}' for c in ('1', '2', '3'))} percent mix, "
        "and we tested class weighting, which tells the model to pay more attention to rare grades. We will come back to that experiment in the highlights."))

    # 5 ---------------------------------------------------------------- EDA 1
    ss = R.eda["superstructure"]
    mms, rce = ss["has_superstructure_mud_mortar_stone"], ss["has_superstructure_rc_engineered"]
    s = d.new()
    d.header(s, "Dataset pre-processing · exploration", "Building material is the clearest structural signal")
    d.picture(s, fig("fig03_damage_by_superstructure"), 0.5, 1.6, 7.9, 5.25)
    cards = [
        (pct(mms["prevalence"], 0), "of buildings use mud-mortar stone", f"{pct(mms['grade3_share'], 0)} of them were destroyed (grade 3)"),
        (pct(rce["grade3_share"], 0), "grade-3 rate for engineered RC", f"{pct(rce['grade1_share'], 0)} of RC buildings had only low damage"),
        (pct(R.eda["foundation_type"]["grade3_share"]["i"], 0), "grade-3 rate, foundation type i",
         f"vs {pct(R.eda['foundation_type']['grade3_share']['r'], 0)} for type r, used by {pct(R.eda['foundation_type']['prevalence']['r'], 0)} of buildings"),
    ]
    for i, (big, lab, sub) in enumerate(cards):
        y = 1.7 + i * 1.72
        d.box(s, 8.75, y, 4.0, 1.55)
        d.text(s, 9.0, y + 0.12, 1.6, 0.7, big, size=30, bold=True, color=ORANGE if i == 0 else NAVY, font=HEAD)
        d.text(s, 10.55, y + 0.17, 2.1, 0.7, lab, size=14, bold=True, color=NAVY)
        d.text(s, 9.0, y + 0.88, 3.6, 0.6, sub, size=13, color=INK2)
    d.footer(s)
    d.add_notes(s, "Exploration: materials", (
        "We started with exploratory analysis, done on the training split only so the holdout stayed untouched. "
        f"The biggest structural signal is the building material. About {pct(mms['prevalence'], 0)} of buildings are built from mud-mortar stone, "
        f"and {pct(mms['grade3_share'], 0)} of those were essentially destroyed. "
        f"Compare engineered reinforced concrete: only {pct(rce['grade3_share'], 0)} reached grade 3, and {pct(rce['grade1_share'], 0)} had only low damage. "
        f"Foundation and roof types show the same pattern. Foundation type r, used by {pct(R.eda['foundation_type']['prevalence']['r'], 0)} of buildings, has a grade-3 rate of {pct(R.eda['foundation_type']['grade3_share']['r'], 0)}, "
        f"while foundation type i has only {pct(R.eda['foundation_type']['grade3_share']['i'], 0)}, and roof type x only {pct(R.eda['roof_type']['grade3_share']['x'], 0)}. "
        "The codes are anonymised, but these protective types behave exactly like engineered, reinforced construction. "
        "The lesson for modelling: what a building is made of carries real signal, and we should expect the models to pick it up."))

    # 5 ---------------------------------------------------------------- EDA 2
    g = R.eda["geo1_grade3_share"]
    s = d.new()
    d.header(s, "Dataset pre-processing · exploration", "Location matters as much as structure")
    d.picture(s, fig("fig04_damage_by_geo1"), 0.5, 1.6, 12.3, 4.3)
    d.box(s, 0.6, 6.0, 12.15, 0.8)
    d.text(s, 0.85, 6.05, 11.7, 0.7, [[
        ("Grade-3 share ranges from ", {}), (pct(g["min"], 0), {"bold": True, "color": NAVY}),
        (f" (region {g['argmin']}) to ", {}), (pct(g["max"], 0), {"bold": True, "color": ORANGE}),
        (f" (region {g['argmax']}). Region is a proxy for shaking intensity, so finer location levels should help even more.", {})]],
        size=15, color=INK2, anchor=MSO_ANCHOR.MIDDLE)
    d.footer(s)
    d.add_notes(s, "Exploration: location", (
        f"The second key finding is geography. Each bar is one of the {R.data['n_unique']['geo_level_1_id']} top-level regions, sorted by its share of destroyed buildings. "
        f"In region {g['argmin']} only {pct(g['min'], 0)} of buildings reached grade 3; in region {g['argmax']} it was {pct(g['max'], 0)}. "
        "The same mud-stone house fares very differently depending on how strongly the ground shook, and location is our best proxy for that. "
        f"Remember that location comes at three nested levels: {R.data['n_unique']['geo_level_1_id']} regions, {n(R.data['n_unique']['geo_level_2_id'])} sub-regions and {n(R.data['n_unique']['geo_level_3_id'])} local areas, "
        "each sitting inside the level above, a bit like province, district and village. This chart only uses the coarsest level. "
        "This told us two things: location must be in the model, and the finer location levels, with thousands of local areas, probably carry even more signal, "
        "if we can encode them without overfitting. That is one of our highlights."))

    # 6 ---------------------------------------------------------------- Cleaning & FE
    s = d.new()
    d.header(s, "Dataset pre-processing · cleaning & feature engineering", "Every step lives inside one leakage-safe sklearn Pipeline")
    steps = [("Age clean", "995 → flag +\ntraining median"), ("Engineer", f"kept: {kept_txt}"),
             ("Scale (LR)", "log1p + standardise\nage, area, height"), ("Encode", "8 categoricals + region:\nLR one-hot, trees codes"),
             ("Target-encode", "geo levels 2 & 3\n(multiclass, cross-fit)"), ("3 models", "LR · random forest\n· gradient boosting")]
    bw, gap = 1.85, 0.21
    for i, (t, body) in enumerate(steps):
        x = 0.6 + i * (bw + gap)
        last = i == len(steps) - 1
        d.box(s, x, 1.75, bw, 1.9, fill=NAVY if last else TINT)
        d.text(s, x + 0.15, 1.9, bw - 0.3, 0.75, t, size=16, bold=True, color=WHITE if last else NAVY)
        d.text(s, x + 0.15, 2.65, bw - 0.3, 0.95, body, size=12.5, color=LIGHTBLUE if last else INK2)
        if not last:
            d.arrow(s, x + bw + 0.02, 2.7, x + bw + gap - 0.02, 2.7)
    d.text(s, 0.6, 3.95, 6, 0.4, "Cleaning", size=18, bold=True, color=NAVY)
    d.text(s, 0.6, 4.4, 5.8, 2.4, [
        f"No missing values, but {n(R.data['n_age_placeholder'])} buildings have age = 995, a placeholder (the next real age is {R.data['age_max_real']}).",
        f"These have a lower grade-3 rate ({pct(R.eda['age_placeholder_grade3_share'], 0)} vs {pct(R.eda['age_real_grade3_share'], 0)}), so we keep an indicator flag and impute the training-fold median.",
        f"Skewed numerics: area skew {R.eda['skewness']['area_percentage']:.1f} → {R.eda['skewness_after_log1p']['area_percentage']:.1f} after log1p.",
    ], size=14, color=INK2, spacing=8)
    d.text(s, 7.0, 3.95, 6, 0.4, "Feature engineering (paired add-one test)", size=18, bold=True, color=NAVY)
    rows = sorted(R.abl["candidates"].items(), key=lambda kv: -kv[1]["mean_gain"])
    for i, (f, a) in enumerate(rows):
        y = 4.45 + i * 0.55
        d.box(s, 7.0, y, 5.75, 0.46, fill=TINT if not a["kept"] else RGBColor(0xFD, 0xEB, 0xE2))
        d.text(s, 7.2, y + 0.08, 3.0, 0.3, f, size=13, color=INK, bold=a["kept"])
        d.text(s, 10.0, y + 0.08, 1.3, 0.3, pp(a["mean_gain"], 2), size=13, color=INK2)
        d.text(s, 11.25, y + 0.08, 1.4, 0.3, ("kept" if a["kept"] else "dropped") + f" ({a['folds_improved']}/5)",
               size=13, color=ORANGE if a["kept"] else MUTED, bold=a["kept"])
    d.footer(s)
    d.add_notes(s, "Cleaning and feature engineering", (
        "Every preprocessing step lives inside a single scikit-learn pipeline, so in cross-validation each step is re-fitted on the training folds only. That is how we avoid data leakage. "
        "Leakage would happen, for example, if we computed the median age or a village's damage rate on all the data before splitting: the validation buildings would then have helped build their own features, and our scores would look better than they really are. "
        f"The data had no missing values, but {n(R.data['n_age_placeholder'])} buildings have an age of 995 years, which is clearly a placeholder. "
        "Instead of treating them as very old buildings, we add a flag and replace the age with the training median; the flag matters because these buildings are actually damaged less often. "
        "For logistic regression, age, area and height are log-transformed and standardised, and categoricals are one-hot encoded; the tree models skip the scaling and use integer codes instead. "
        "The two fine location levels are target-encoded for all three models, which we'll explain next. "
        f"For feature engineering we tested four candidates, each added on its own and compared fold by fold. We kept only features that improved the mean and won in at least four of five folds: {kept_txt}. "
        f"Overall, engineered features changed micro-F1 by {pp(fe_gain, 2)}, which is small. Most of the signal is already in the raw features."))

    # 7 ---------------------------------------------------------------- Highlight: target encoding
    s = d.new()
    d.header(s, "Highlights · geo target encoding", f"Encoding {n(R.data['n_unique']['geo_level_3_id'])} villages as damage rates")
    d.box(s, 0.6, 1.75, 5.1, 4.95, fill=NAVY)
    d.text(s, 0.95, 2.0, 4.5, 0.4, "CV micro-F1", size=16, color=LIGHTBLUE, bold=True)
    for i, (k, lab) in enumerate([("E1", "structure only"), ("E2", "+ region (one-hot)"), ("E3", "+ target-encoded geo 2 & 3")]):
        y = 2.55 + i * 1.3
        d.text(s, 0.95, y, 2.2, 0.7, f"{R.mic(k):.3f}", size=36, bold=True, color=ORANGE if k == "E3" else WHITE, font=HEAD)
        d.text(s, 3.05, y + 0.2, 2.5, 0.6, f"{k}: {lab}", size=14, color=WHITE)
    d.text(s, 0.95, 6.15, 4.5, 0.4, f"Target encoding alone: {pp(e3_gain)}", size=15, bold=True, color=ORANGE)
    d.text(s, 6.2, 1.8, 6.5, 0.4, "How it works", size=18, bold=True, color=NAVY)
    d.box(s, 6.2, 2.3, 1.9, 1.0, fill=TINT)
    d.text(s, 6.3, 2.4, 1.7, 0.8, f"village id\n({n(R.data['n_unique']['geo_level_3_id'])} levels)", size=13, color=NAVY, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    d.arrow(s, 8.15, 2.8, 8.75, 2.8, color=ORANGE)
    for j, (lab, col) in enumerate([("P(g1)", LIGHTBLUE), ("P(g2)", BLUE), ("P(g3)", DEEP)]):
        b = d.box(s, 8.85 + j * 1.3, 2.3, 1.15, 1.0, fill=col)
        d.text(s, 8.85 + j * 1.3, 2.3, 1.15, 1.0, lab, size=14, bold=True, color=INK if j == 0 else WHITE,
               align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    d.text(s, 6.2, 3.6, 6.55, 3.1, [
        [("Compact: ", {"bold": True, "color": NAVY}), (f"3 numbers per level instead of {n(R.data['n_unique']['geo_level_2_id'] + R.data['n_unique']['geo_level_3_id'])} one-hot columns.", {})],
        [("Smoothed: ", {"bold": True, "color": NAVY}), ("rare villages shrink toward the overall class mix.", {})],
        [("Leakage-safe: ", {"bold": True, "color": NAVY}), ("cross-fitted, so no building ever sees its own label, and re-fitted inside every CV fold.", {})],
        [("Interpretable: ", {"bold": True, "color": NAVY}), ("“how badly was this neighbourhood hit?”", {})],
    ], size=15, color=INK2, spacing=10)
    d.footer(s)
    d.add_notes(s, "Highlight: geo target encoding", (
        f"Our first highlight is how we used location. The finest level has {n(R.data['n_unique']['geo_level_3_id'])} villages. One-hot encoding that would create thousands of sparse columns and overfit. "
        "Instead, we used target encoding: each village is replaced by three numbers, its observed share of grade 1, 2 and 3 buildings, smoothed toward the overall mix when a village is small. "
        "For example, a village with only three buildings, all destroyed, does not get a grade-3 rate of one hundred percent; its estimate is pulled toward the national average, because three buildings are weak evidence. "
        "The danger with target encoding is leakage, because a building's own label would leak into its feature. "
        "scikit-learn's TargetEncoder cross-fits internally, so a building's encoding is always computed from other buildings, and because it sits in our pipeline it is re-fitted inside every CV fold. "
        f"The effect is the biggest jump in the whole project. Structure alone gives {R.mic('E1'):.3f}; adding the region one-hot gives {R.mic('E2'):.3f}; "
        f"and the target-encoded villages take us to {R.mic('E3'):.3f}, a gain of {pp(e3_gain)} from this one idea. "
        "Intuitively, the model now knows how badly each neighbourhood was hit, which is exactly the information an inspector would ask for first. "
        f"Villages that never appear in training, {pct(R.data['test_geo3_unseen_share'], 1)} of the test set, simply receive the overall class mix."))

    # 8 ---------------------------------------------------------------- Highlight: ordinal
    s = d.new()
    d.header(s, "Highlights · ordinal vs multinomial", "Does respecting the order of damage grades help?")
    d.picture(s, fig("fig12_recall_comparison"), 0.5, 1.6, 7.6, 5.2)
    verdict_ord = ("helped" if ord_diff > 0.001 else "did not help" if ord_diff < -0.001 else "made no real difference")
    verdict_bal = ("raised" if bal_mac > 0.001 else "lowered")
    d.box(s, 8.45, 1.7, 4.3, 2.45)
    d.text(s, 8.7, 1.85, 3.9, 0.4, "Ordinal logistic (E6)", size=17, bold=True, color=NAVY)
    d.text(s, 8.7, 2.3, 3.9, 1.8, [
        "Two binary models, P(grade > 1) and P(grade > 2), combined into 3 class probabilities.",
        [("Micro-F1 ", {}), (pp(ord_diff, 2), {"bold": True, "color": ORANGE}),
         (", macro-F1 ", {}), (pp(ord_mac, 2), {"bold": True, "color": ORANGE}), (f" vs multinomial: it {verdict_ord}.", {})],
    ], size=14, color=INK2, spacing=6)
    d.box(s, 8.45, 4.35, 4.3, 2.45)
    d.text(s, 8.7, 4.5, 3.9, 0.4, "Class weighting (E5)", size=17, bold=True, color=NAVY)
    d.text(s, 8.7, 4.95, 3.9, 1.8, [
        [("Grade-1 recall ", {}), (f"{R.rec('E4', 1):.2f} → {R.rec('E5', 1):.2f}", {"bold": True, "color": ORANGE})],
        [("Micro-F1 ", {}), (pp(bal_diff, 2), {"bold": True, "color": ORANGE}), (", macro-F1 ", {}),
         (pp(bal_mac, 2), {"bold": True, "color": ORANGE})],
        "A trade-off: it finds more low-damage buildings but costs overall accuracy.",
    ], size=14, color=INK2, spacing=6)
    d.footer(s)
    d.add_notes(s, "Highlight: ordinal vs multinomial", (
        "Our second highlight tests whether the ordering of the damage grades can be exploited. A standard multinomial model treats grades 1, 2 and 3 as unrelated labels. "
        "Our ordinal version instead fits two binary logistic models: one for 'worse than grade 1' and one for 'worse than grade 2', then turns them into three class probabilities. "
        f"Compared with the multinomial model on identical features, the ordinal approach changed micro-F1 by {pp(ord_diff, 2)} and macro-F1 by {pp(ord_mac, 2)}, so it {verdict_ord}. "
        f"{'This is a negative result, but an informative one: ' if ord_diff <= 0.001 else ''}"
        "with only three classes the multinomial model is flexible enough to learn the ordering on its own. "
        f"We also tried class weighting. It {verdict_bal} macro-F1 by {pp(abs(bal_mac), 2).lstrip('+')} and raised grade-1 recall from {R.rec('E4', 1):.2f} to {R.rec('E5', 1):.2f}, "
        f"but micro-F1 moved by {pp(bal_diff, 2)}. Macro-F1 does not improve either, because many grade-2 buildings are now wrongly called grade 1, so grade-1 precision collapses. "
        "So weighting is a policy choice, not a free improvement."))

    # 9 ---------------------------------------------------------------- Training & testing
    s = d.new()
    d.header(s, "Training and testing procedure", "Select on cross-validation, test once on the holdout")
    d.box(s, 0.6, 1.8, 2.6, 1.3, fill=NAVY)
    d.text(s, 0.6, 1.8, 2.6, 1.3, [f"{n(R.data['n_train_rows'])}", "labelled buildings"], size=16, color=WHITE, bold=True,
           align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    d.arrow(s, 3.25, 2.2, 3.95, 1.95, color=ORANGE)
    d.arrow(s, 3.25, 2.7, 3.95, 4.55, color=ORANGE)
    d.box(s, 4.0, 1.55, 4.6, 2.25, fill=TINT)
    d.text(s, 4.25, 1.7, 4.2, 0.4, f"80% training split · {n(R.split['n_train'])}", size=16, bold=True, color=NAVY)
    d.text(s, 4.25, 2.15, 4.2, 1.6, [
        "Stratified 5-fold CV: LR experiments E0–E6",
        f"GridSearchCV, micro-F1: LR ({len(R.tun['grid'])} values of C), random forest ({R.models[RF]['n_candidates']}), boosting ({R.models[HGB]['n_candidates']})",
        "Encoders, imputers re-fit inside each fold",
    ], size=13.5, color=INK2, spacing=5)
    d.box(s, 4.0, 4.15, 4.6, 1.55, fill=RGBColor(0xFD, 0xEB, 0xE2))
    d.text(s, 4.25, 4.3, 4.2, 0.4, f"20% holdout · {n(R.split['n_holdout'])}", size=16, bold=True, color=ORANGE)
    d.text(s, 4.25, 4.75, 4.2, 0.9, "Locked away; each of the 3 tuned models scored exactly once.", size=13.5, color=INK2)
    d.arrow(s, 8.65, 2.65, 9.35, 2.65, color=ORANGE)
    d.box(s, 9.4, 1.55, 3.35, 2.25, fill=NAVY)
    d.text(s, 9.6, 1.7, 3.0, 2.0, [
        [("Final model", {"bold": True, "size": 16, "color": WHITE})],
        f"{FL}: highest CV micro-F1 of the 3 tuned models",
        f"LR: {R.best}, C = {R.best_C:g}; all fits converged",
    ], size=13.5, color=LIGHTBLUE, spacing=5)
    d.box(s, 9.4, 4.15, 3.35, 1.55, fill=TINT)
    d.text(s, 9.6, 4.3, 3.0, 1.3, [
        [("Submission", {"bold": True, "size": 16, "color": NAVY})],
        f"Refit on all {n(R.sub['refit_rows'])} rows → {n(R.sub['n_rows'])} test predictions",
    ], size=13.5, color=INK2, spacing=5)
    d.text(s, 0.6, 6.05, 12.1, 0.7,
           f"Random state 42 everywhere. Model 1 experiments: E0 baseline → E1 structure → E2 + region → E3 + geo target encoding → "
           f"E4 + engineered → E5 balanced → E6 ordinal. Models 2–3 reuse the E4 features.", size=13, color=MUTED)
    d.footer(s)
    d.add_notes(s, "Training and testing procedure", (
        "Now, how we trained and tested. We split the labelled data 80 to 20, stratified by damage grade, "
        f"and locked the {n(R.split['n_holdout'])}-building holdout away until the very end. "
        "All comparisons and tuning used stratified five-fold cross-validation on the 80 percent, with every encoder re-fitted inside each fold. "
        "Five-fold means we train five times, each time holding out a different fifth of the training data, and average the five scores. "
        "That gives us both a mean and a spread, so we can tell a real improvement from noise, and it means we never need to look at the holdout while making decisions. "
        f"For logistic regression we ran seven experiments and tuned C on the best one, {R.best}. "
        "The random forest and gradient boosting reuse the same features and folds, with small tuning grids. "
        f"Each tuned model was scored once on the holdout, but the final model was chosen by cross-validation alone: {FL}. "
        "It was then refit on all labelled data for our submission."))

    # 10 --------------------------------------------------------------- Results table
    s = d.new()
    d.header(s, "Experimental study · model 1: logistic regression", "Location drives the gains; reweighting and ordinal do not"
             if (bal_diff < 0 and ord_diff <= 0.001) else "Each step's contribution to cross-validated micro-F1")
    d.picture(s, fig("fig07_experiments"), 0.5, 1.6, 8.3, 5.2)
    pts = [
        [("Baseline ", {"bold": True, "color": NAVY}), (f"always predicts grade 2: {base:.3f}", {})],
        [("Structure alone ", {"bold": True, "color": NAVY}), (f"{R.mic('E1'):.3f} ({pp(R.mic('E1') - base)})", {})],
        [("Location ", {"bold": True, "color": NAVY}), (f"adds {pp(geo1_gain)} (region) and {pp(e3_gain)} (villages)", {})],
        [("Engineered features ", {"bold": True, "color": NAVY}), (f"{pp(fe_gain, 2)}", {})],
        [("Fold std ", {"bold": True, "color": NAVY}), (f"≤ {max(R.mic_sd(k) for k in R.exp):.4f}, so gaps of ≥ {pp(5 * max(R.mic_sd(k) for k in R.exp)).lstrip('+')} are well beyond noise", {})],
    ]
    d.text(s, 9.1, 1.8, 3.7, 5.0, pts, size=14.5, color=INK2, spacing=12)
    d.footer(s)
    d.add_notes(s, "Experimental results", (
        "We start with model one. This chart shows cross-validated micro-F1 for every logistic-regression experiment, with error bars across the five folds. "
        f"The majority baseline scores {base:.3f}. Structure alone lifts this to {R.mic('E1'):.3f}, which is useful but modest. "
        f"Adding the {R.data['n_unique']['geo_level_1_id']} regions gains {pp(geo1_gain)}, and the target-encoded village levels add another {pp(e3_gain)}, the largest single step. "
        f"Engineered features change micro-F1 by only {pp(fe_gain, 2)}. "
        f"The balanced and ordinal variants score {R.mic('E5'):.3f} and {R.mic('E6'):.3f}, which is why we carried E4 forward. "
        f"Tuning the regularisation strength C barely mattered: the best value, {R.best_C:g}, is within a hair of the default, because with {n(R.split['n_train'])} training buildings the model is not starved of data. "
        f"The fold-to-fold standard deviations are tiny, at most {100 * max(R.mic_sd(k) for k in R.exp):.2f} percentage points, so the big steps are not noise. "
        "The lesson: building material matters, but only location tells a mud-stone house near the epicentre from one far away, and once location is in, hand-made features add almost nothing."))

    # 11 --------------------------------------------------------------- Three-model comparison
    s = d.new()
    d.header(s, "Experimental study · three models", f"{FL} wins on cross-validation" if tree_won
             else "Logistic regression holds its own against the trees")
    d.picture(s, fig("fig13_model_comparison"), 0.45, 1.55, 7.9, 4.9)
    for i, k in enumerate(R.order):
        y = 1.6 + i * 1.62
        win = k == F
        d.box(s, 8.6, y, 4.15, 1.45, fill=NAVY if win else TINT)
        d.text(s, 8.8, y + 0.1, 3.8, 0.35, R.label(k) + ("  ·  final model" if win else ""), size=15, bold=True,
               color=WHITE if win else NAVY)
        d.text(s, 8.8, y + 0.48, 3.8, 0.95, [
            [("CV ", {}), (f"{R.mcv(k):.3f}", {"bold": True, "color": ORANGE}), ("   holdout ", {}),
             (f"{R.mho(k):.3f}", {"bold": True, "color": ORANGE}), ("  micro-F1", {})],
            R.params_txt(k),
        ], size=12.5, color=LIGHTBLUE if win else INK2, spacing=2)
    d.text(s, 0.6, 6.55, 12.1, 0.35,
           f"Same features, same 5 folds. Final model chosen by CV micro-F1; vs LR: {pp(gain_cv, 2)} in CV, {pp(gain_ho, 2)} on the holdout.",
           size=12.5, color=MUTED)
    d.footer(s)
    d.add_notes(s, "Three-model comparison", (
        "Now the comparison our course asked for: three models on exactly the same features and folds. "
        "A quick word on the two new models. A random forest grows many decision trees, each on a random sample of buildings and features, and lets them vote; averaging makes it stable. "
        "Gradient boosting instead grows trees one after another, each new tree correcting the mistakes of the trees before it. "
        "Both can learn interactions and thresholds automatically, which logistic regression cannot do unless we hand-craft them. "
        f"Logistic regression reaches {R.mcv(LR):.3f} cross-validated micro-F1 and {R.mho(LR):.3f} on the holdout. "
        f"The random forest reaches {R.mcv(RF):.3f} and {R.mho(RF):.3f}, and HistGradientBoosting {R.mcv(HGB):.3f} and {R.mho(HGB):.3f}. "
        + (f"So {FL} is our final model, chosen on cross-validation only. Its gain over logistic regression is {pp(gain_cv, 2)} in cross-validation and {pp(gain_ho, 2)} on the holdout: "
           "real and consistent, but small. The trees can combine features by themselves, for example a material that is only dangerous where shaking was strong. "
           + (f"The two tree models are practically tied: on the holdout the {R.label(R.final['runner_up']).lower()} is even {pp(R.mho(R.final['runner_up']) - R.mho(F), 2)} ahead, "
              "but we fixed in advance that cross-validation decides, so the holdout stays an honest check. "
              if R.mho(R.final["runner_up"]) > R.mho(F) else "")
           if tree_won else "So logistic regression keeps the top spot, and the extra flexibility of the trees buys nothing here. ")
        + f"Macro-F1 tells a similar story: {R.mcv(LR, 'f1_macro'):.3f}, {R.mcv(RF, 'f1_macro'):.3f} and {R.mcv(HGB, 'f1_macro'):.3f} in cross-validation."))

    # 12 --------------------------------------------------------------- Holdout of the final model
    s = d.new()
    d.header(s, "Experimental study and analysis", f"Final model on the holdout: {FL}")
    fm = R.models[F]
    d.stat(s, 0.6, 1.75, 3.3, f"{R.mho(F):.3f}", "holdout micro-F1\n(competition metric)", color=ORANGE, big_size=48)
    d.stat(s, 0.6, 3.4, 3.3, f"{R.mho(F, 'f1_macro'):.3f}", "holdout macro-F1", big_size=40)
    d.stat(s, 0.6, 4.85, 3.3, f"{R.mcv(F):.3f}", "CV micro-F1\n(holdout agrees with CV)", big_size=32)
    d.picture(s, fig("fig15_confusion_final" if tree_won else "fig09_confusion_matrix"), 3.9, 1.55, 5.2, 5.3)
    d.text(s, 9.4, 1.75, 3.4, 0.4, "Holdout recall (vs LR)", size=17, bold=True, color=NAVY)
    for i, c in enumerate([1, 2, 3]):
        y = 2.3 + i * 1.05
        d.box(s, 9.4, y, 3.35, 0.9)
        d.text(s, 9.6, y + 0.12, 1.3, 0.7, f"Grade {c}", size=15, bold=True, color=NAVY, anchor=MSO_ANCHOR.MIDDLE)
        d.text(s, 10.75, y + 0.08, 1.0, 0.75, f"{R.mrec(F, c):.2f}", size=26, bold=True, color=ORANGE if c == 3 else NAVY,
               font=HEAD, align=PP_ALIGN.RIGHT, anchor=MSO_ANCHOR.MIDDLE)
        d.text(s, 11.85, y + 0.08, 0.8, 0.75, f"({R.mrec(LR, c):.2f})", size=13, color=MUTED, align=PP_ALIGN.RIGHT,
               anchor=MSO_ANCHOR.MIDDLE)
    d.text(s, 9.4, 5.55, 3.4, 1.3,
           f"Errors are almost all between adjacent grades: only {pct(R.fcm(3, 1), 1)} of grade-3 buildings are predicted as grade 1.",
           size=13.5, color=INK2)
    d.footer(s)
    d.add_notes(s, "Holdout performance", (
        f"Here is the final model, {FL}, on the holdout. It scores a micro-F1 of {R.mho(F):.3f} and a macro-F1 of {R.mho(F, 'f1_macro'):.3f}, "
        f"close to its cross-validated {R.mcv(F):.3f}, so our model selection did not overfit. "
        f"Grade 2 is recalled {pct(R.mrec(F, 2), 0)} of the time and grade 3 {pct(R.mrec(F, 3), 0)}; grade 1 is hardest at {pct(R.mrec(F, 1), 0)}, because it is rare and often looks like grade 2. "
        "The grey numbers are logistic regression, for comparison. "
        f"Importantly, mistakes are almost always between neighbouring grades: only {pct(R.fcm(3, 1), 1)} of destroyed buildings are mistaken for low damage, which is the costly error for inspectors. "
        f"The biggest remaining error is grade-3 buildings predicted as grade 2, {pct(R.fcm(3, 2), 0)} of them: many destroyed buildings look ordinary on paper, and what tipped them over, such as local shaking, is not in the data."))

    # 13 --------------------------------------------------------------- Prioritisation
    s = d.new()
    d.header(s, "Experimental study and analysis", "Ranking finds destroyed buildings far faster than random")
    d.picture(s, fig("fig14_capture_comparison"), 0.5, 1.55, 7.4, 5.3)
    fa = R.models[F]["prioritisation"]
    for i, k in enumerate([10, 20, 30]):
        y = 1.7 + i * 1.6
        d.box(s, 8.3, y, 4.45, 1.42)
        d.text(s, 8.55, y + 0.15, 1.9, 0.8, pct(R.mcap(F, k), 0), size=40, bold=True, color=ORANGE, font=HEAD)
        d.text(s, 10.45, y + 0.2, 2.2, 1.1, [f"of grade-3 buildings found in the top {k}%",
                                              [(f"{fa['at_fraction'][str(k)]['lift']:.1f}× better than random", {"bold": True, "color": NAVY})]],
               size=13.5, color=INK2, spacing=3)
    d.text(s, 8.3, 6.5, 4.45, 0.4, f"{FL} (final model); grade-3 ROC-AUC = {R.mauc(F):.3f}",
           size=12, color=MUTED)
    d.footer(s)
    d.add_notes(s, "Prioritisation analysis", (
        "This slide connects the models back to our problem statement. We ranked every holdout building by its predicted probability of grade 3 and asked: "
        "if inspectors work down this list, how many destroyed buildings do they find? "
        f"With the final model, the top 10 percent finds {pct(R.mcap(F, 10), 0)} of all grade-3 buildings, the top 20 percent {pct(R.mcap(F, 20), 0)}, and the top 30 percent {pct(R.mcap(F, 30), 0)}, "
        f"against 10, 20 and 30 percent for a random order. "
        f"The three curves almost overlap: at 20 percent, logistic regression finds {pct(R.mcap(LR), 1)}, the forest {pct(R.mcap(RF), 1)} and boosting {pct(R.mcap(HGB), 1)}. "
        f"Concretely, in our holdout the first {n(fa['at_fraction']['10']['n_inspected'])} visits would reach about {n(round(R.mcap(F, 10) * fa['n_grade3']))} destroyed buildings, "
        f"instead of about {n(round(0.10 * fa['n_grade3']))} in random order. "
        "The curve also shows diminishing returns: the first part of the list is rich in destroyed buildings, and after about half the list most remaining buildings are lower risk, "
        "which helps an agency decide how many teams it needs in the first days."))

    # 14 --------------------------------------------------------------- Interpretation
    up = R.top_features("raising", 3)
    down = R.top_features("lowering", 3)
    s = d.new()
    d.header(s, "Experimental study and analysis", "What drives the predictions?")
    d.text(s, 0.6, 1.5, 6.0, 0.35, "Logistic regression: odds ratios for grade 3", size=15, bold=True, color=NAVY)
    d.picture(s, plot_coefficients_compact(R.coef["top_raising"], R.coef["top_lowering"], k=6), 0.5, 1.9, 6.0, 4.6)
    d.text(s, 6.9, 1.5, 5.9, 0.35, "All three models: permutation importance", size=15, bold=True, color=NAVY)
    imp_png = plot_importance({k: R.models[k]["importance"] for k in R.order}, top=7, order_by=F,
                              name="fig16b_importance_slide", figsize=(7.2, 7.0), fontsize=12.5,
                              title="Drop in micro-F1 when a column is shuffled")
    d.picture(s, imp_png, 6.8, 1.9, 6.0, 4.6)
    mat = R.coef["materials"]
    d.box(s, 0.6, 6.5, 12.15, 0.42, fill=TINT)
    d.text(s, 0.8, 6.54, 11.8, 0.35, [[
        ("Mud-mortar stone ", {}), (f"×{mat['has_superstructure_mud_mortar_stone']['odds_ratio']:.2f}", {"bold": True, "color": ORANGE}),
        ("   Engineered RC ", {}), (f"×{mat['has_superstructure_rc_engineered']['odds_ratio']:.2f}", {"bold": True, "color": DEEP}),
        ("   ·   location ranks first for every model; trees say how much, LR also says which direction", {})]],
        size=13, color=INK2)
    d.footer(s)
    d.add_notes(s, "Interpretation", (
        "Why does a model call a building high-risk? On the left is logistic regression, which we can read directly: odds ratios for grade-3 damage, red raising and blue lowering the odds. "
        f"The strongest risk factors are {up[0][0]} and {up[1][0]}; the strongest protective ones are {down[0][0]} and {down[1][0]}. "
        f"Mud-mortar stone multiplies the odds of destruction by about {mat['has_superstructure_mud_mortar_stone']['odds_ratio']:.1f}, engineered reinforced concrete by {mat['has_superstructure_rc_engineered']['odds_ratio']:.2f}. "
        "Tree ensembles have no coefficients, so on the right we use permutation importance: how much micro-F1 drops when we shuffle one input column. "
        "All three models rely first on location, then on construction details such as foundation, material and age, which matches our exploration and engineering intuition. "
        "The difference is that importance says how much a feature matters, while the odds ratios also say in which direction."))

    # 15 --------------------------------------------------------------- Summary
    s = d.new()
    d.header(s, "Summary of project achievements", "What we delivered")
    ach = [
        (f"{R.mho(F):.3f}", "holdout micro-F1", f"{FL} vs {base:.3f} for the majority baseline"),
        (pct(R.mcap(F), 0), "of destroyed buildings", "found by inspecting just the top 20% of the ranked list"),
        (pp(e3_gain), "from geo target encoding", f"leakage-safe encoding of {n(R.data['n_unique']['geo_level_3_id'])} villages"),
        ("3", "models compared fairly", f"same features and folds; trees {pp(gain_cv, 2)} over LR in CV" if tree_won
         else "same features and folds; LR remained best"),
        ("7", "controlled LR experiments", "incl. an honest negative result for the ordinal model" if ord_diff <= 0.001
         else "incl. a custom ordinal logistic model"),
        ("1", "command to reproduce", "python -m src.run_all → figures, results.json, report, slides"),
    ]
    for i, (big, lab, sub) in enumerate(ach):
        col, row = i % 3, i // 3
        x, y = 0.6 + col * 4.12, 1.75 + row * 2.55
        d.box(s, x, y, 3.9, 2.3)
        d.text(s, x + 0.3, y + 0.2, 3.4, 0.8, big, size=36, bold=True, color=ORANGE if i < 2 else NAVY, font=HEAD)
        d.text(s, x + 0.3, y + 1.0, 3.4, 0.4, lab, size=16, bold=True, color=NAVY)
        d.text(s, x + 0.3, y + 1.45, 3.4, 0.8, sub, size=13, color=INK2)
    d.footer(s)
    d.add_notes(s, "Summary of achievements", (
        f"To summarise. Our final model, {FL}, reaches a holdout micro-F1 of {R.mho(F):.3f}, against {base:.3f} for always guessing grade 2. "
        f"Translated into the problem statement, inspecting the top 20 percent of buildings on its list finds {pct(R.mcap(F), 0)} of the destroyed ones. "
        "The biggest technical contribution was leakage-safe target encoding of village-level location, which helps every model. "
        + (f"We compared three models fairly, and the trees beat logistic regression by {pp(gain_cv, 2)}, so transparency costs a little accuracy but not much. "
           if tree_won else "We compared three models fairly, and logistic regression held its own. ")
        + "We were strict about methodology: every transformation is inside one pipeline, so nothing is learned from validation data, and each tuned model saw the holdout exactly once. "
        "We also report the experiments that did not help, such as class weighting and the ordinal model, as honestly as the ones that did. "
        "Finally, the whole project, from the raw CSV files to the figures, the report and this deck, is reproducible with one command, "
        "and every number you have seen today is read automatically from a single results file."))

    # 16 --------------------------------------------------------------- Future directions
    s = d.new()
    d.header(s, "Future directions for further improvements", "Where we would go next")
    fut = [
        ("Richer location signal", "Add measured ground shaking (USGS ShakeMap PGA) and distance to the epicentre instead of using region ids as proxies."),
        ("Interactions for LR", "Material × region and floors × age terms or splines, to close the gap to the trees while staying interpretable."),
        ("Explain the ensembles", "SHAP values for per-building explanations of the tree models, and wider tuning (LightGBM, CatBoost)."),
        ("Cost-aware decisions", "Pick decision thresholds from inspection capacity and the cost of missing a destroyed building."),
        ("Probability calibration", "Check and calibrate predicted risks so that teams can trust the percentages, not only the ranking."),
        ("Validate & deploy", "Spatially grouped CV for unseen areas; package the final pipeline as a simple triage tool."),
    ]
    for i, (t, body) in enumerate(fut):
        col, row = i % 2, i // 2
        x, y = 0.6 + col * 6.15, 1.7 + row * 1.6
        d.badge(s, x, y + 0.05, str(i + 1), fill=BLUE)
        d.text(s, x + 0.65, y, 5.3, 0.4, t, size=17, bold=True, color=NAVY)
        d.text(s, x + 0.65, y + 0.42, 5.3, 1.0, body, size=14, color=INK2)
    d.text(s, 0.6, 6.5, 12.1, 0.4, "Thank you. Questions are welcome.", size=16, bold=True, color=ORANGE)
    d.footer(s)
    d.add_notes(s, "Future directions", (
        "Finally, where would we go next? The most valuable addition would be measured ground shaking, for example peak ground acceleration from USGS ShakeMap, "
        "instead of letting region ids act as a proxy. "
        "Second, interaction terms such as material by region could close the gap between logistic regression and the trees while staying interpretable. "
        "Third, SHAP values would give the tree models per-building explanations, so the more accurate model could also tell an inspector why a building is flagged. "
        "A wider search, or libraries such as LightGBM or CatBoost, might add a little more accuracy. "
        "Fourth, decision thresholds should come from inspection capacity and from the cost of missing a destroyed building, and the probabilities should be calibrated so teams can trust the percentages. "
        "Lastly, before deploying a triage tool, we would test the model with spatially grouped cross-validation, to see how it performs in areas it has never seen. "
        "Thank you for listening; we are happy to take questions."))

    return d


def balanced_segments(words, k=N_PRESENTERS):
    """Split slides 1..n into k contiguous segments with speaking times as equal as possible
    (minimises the longest segment, ties broken by the smallest spread)."""
    nsl = len(words)
    pref = [0]
    for w in words:
        pref.append(pref[-1] + w)
    best = {}

    def solve(i, parts):
        # returns (max_segment, -min_segment, cuts) for slides i..n-1 split into `parts`
        if (i, parts) in best:
            return best[(i, parts)]
        if parts == 1:
            seg = pref[nsl] - pref[i]
            res = (seg, -seg, [nsl])
        else:
            res = None
            for j in range(i + 1, nsl - parts + 2):
                seg = pref[j] - pref[i]
                mx, negmn, cuts = solve(j, parts - 1)
                cand = (max(seg, mx), max(-seg, negmn), [j] + cuts)
                if res is None or cand[:2] < res[:2]:
                    res = cand
        best[(i, parts)] = res
        return res

    cuts = solve(0, k)[2]
    segs, start = [], 0
    for c in cuts:
        segs.append(list(range(start + 1, c + 1)))
        start = c
    return [(f"Presenter {i}", sl) for i, sl in enumerate(segs, 1)]


def write_notes_md(d: Deck):
    by_no = {no: (t, txt) for no, t, txt in d.notes}
    SEGMENTS = balanced_segments([len(by_no[k][1].split()) for k in sorted(by_no)])

    def secs(txt):
        return len(txt.split()) / WPM * 60

    lines = [f"# Speaker notes: {TALK_MIN}-minute talk, {N_PRESENTERS} presenters", "",
             f"Timing is estimated from word count at {WPM} words per minute. Each segment is about "
             f"{TALK_MIN / N_PRESENTERS:.1f} minutes; segments are contiguous slides balanced automatically by speaking time. "
             "The same script is in the notes pane of every slide in `presentation.pptx`. "
             "Replace *Presenter N* with names.", "",
             "| Segment | Presenter | Slides | Words | Est. time |", "|---|---|---|---|---|"]
    total = 0
    for i, (who, slides) in enumerate(SEGMENTS, 1):
        w = sum(len(by_no[k][1].split()) for k in slides)
        t = sum(secs(by_no[k][1]) for k in slides)
        total += t
        lines.append(f"| {i} | {who} | {', '.join(map(str, slides))} | {w} | {int(t // 60)}:{int(t % 60):02d} |")
    lines += [f"| | **Total** | 1–{d.count} | | **{int(total // 60)}:{int(total % 60):02d}** |", ""]
    for i, (who, slides) in enumerate(SEGMENTS, 1):
        t = sum(secs(by_no[k][1]) for k in slides)
        lines += [f"## Segment {i}: {who} (slides {slides[0]}–{slides[-1]}, ≈ {int(t // 60)}:{int(t % 60):02d})", ""]
        for k in slides:
            title, txt = by_no[k]
            lines += [f"### Slide {k}: {title} (≈ {secs(txt):.0f} s)", "", txt, ""]
        nxt = SEGMENTS[i][0] if i < len(SEGMENTS) else None
        if nxt:
            lines += [f"*Hand over to {nxt}.*", ""]
    NOTES_MD.write_text("\n".join(lines), encoding="utf-8")
    return total


def main():
    rv = ResultsView()
    d = build(rv)
    OUT.parent.mkdir(exist_ok=True)
    d.prs.save(OUT)
    total = write_notes_md(d)
    print(f"wrote {OUT} ({d.count} slides) and {NOTES_MD} (est. {total / 60:.1f} min)")


if __name__ == "__main__":
    main()
