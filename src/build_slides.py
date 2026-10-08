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
from .plots import plot_coefficients_compact
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
        self.text(s, 0.6, 7.0, 8, 0.25, "Group [XX]  ·  Earthquake damage prediction with logistic regression",
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

    # 1 ---------------------------------------------------------------- Title
    s = d.new(dark=True)
    for i, col in enumerate([LIGHTBLUE, BLUE, ORANGE]):
        d.box(s, 0.6 + i * 0.42, 0.9, 0.32, 0.32, fill=col, radius=0.15)
    d.text(s, 0.6, 1.55, 11.5, 2.0, "Predicting Earthquake Damage to Prioritise Building Inspections",
           size=44, bold=True, color=WHITE, font=HEAD)
    d.text(s, 0.6, 3.55, 11, 0.9,
           f"Logistic regression on {n(R.data['n_train_rows'])} buildings from the 2015 Gorkha earthquake, Nepal",
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
        "and we deliberately limited ourselves to logistic regression so that every prediction can be explained. "
        "Over the next fifteen minutes, six of us will walk you through the data, our preprocessing, the two ideas we are most proud of, "
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
        "The data are clean, with no missing values, but the categorical codes are anonymised letters, so we can say a foundation of type 'i' is safer, not exactly what 'i' is."))

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
        ("Constraint", "Logistic regression only: transparent, fast and easy to audit."),
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
        "Finally, we restricted ourselves to logistic regression, a model that is transparent and easy to audit."))

    # 4 ---------------------------------------------------------------- EDA 1
    ss = R.eda["superstructure"]
    mms, rce = ss["has_superstructure_mud_mortar_stone"], ss["has_superstructure_rc_engineered"]
    s = d.new()
    d.header(s, "Dataset pre-processing · exploration", "Building material is the clearest structural signal")
    d.picture(s, fig("fig03_damage_by_superstructure"), 0.5, 1.6, 7.9, 5.25)
    cards = [
        (pct(mms["prevalence"], 0), "of buildings use mud-mortar stone", f"{pct(mms['grade3_share'], 0)} of them were destroyed (grade 3)"),
        (pct(rce["grade3_share"], 0), "grade-3 rate for engineered RC", f"{pct(rce['grade1_share'], 0)} of RC buildings had only low damage"),
        (pct(R.data["class_share"]["1"], 0), "of buildings are grade 1", f"Imbalanced: grade 2 is {pct(R.data['class_share']['2'], 0)} of all buildings"),
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
        "Foundation and roof types show the same pattern, which you can see in our report. "
        f"Notice also that the classes are imbalanced: grade 2 is {pct(R.data['class_share']['2'], 0)} of buildings and grade 1 only {pct(R.data['class_share']['1'], 0)}, "
        f"so always guessing grade 2 already scores {R.mic('E0'):.2f}, and grade 1 will be the hardest class."))

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
        "This told us two things: location must be in the model, and the finer location levels, with thousands of local areas, probably carry even more signal, "
        "if we can encode them without overfitting. That is one of our highlights."))

    # 6 ---------------------------------------------------------------- Cleaning & FE
    s = d.new()
    d.header(s, "Dataset pre-processing · cleaning & feature engineering", "Every step lives inside one leakage-safe sklearn Pipeline")
    steps = [("Age clean", "995 → flag +\ntraining median"), ("Engineer", f"kept: {kept_txt}"),
             ("Scale", "log1p + standardise\nage, area, height"), ("One-hot", "8 categoricals +\nregion level 1"),
             ("Target-encode", "geo levels 2 & 3\n(multiclass, cross-fit)"), ("Logistic\nregression", "lbfgs, L2, tuned C")]
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
        f"The data had no missing values, but {n(R.data['n_age_placeholder'])} buildings have an age of 995 years, which is clearly a placeholder. "
        "Instead of treating them as very old buildings, we add a flag and replace the age with the training median; the flag matters because these buildings are actually damaged less often. "
        "Age, area and height are right-skewed, so we log-transform and standardise them. Categorical columns and the top region level are one-hot encoded, and the two fine location levels are target-encoded, which we'll explain next. "
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
        "Stratified 5-fold CV for every experiment (E0–E6)",
        f"GridSearchCV over C ∈ {{{min(R.tun['grid']):g} … {max(R.tun['grid']):g}}}, scored by micro-F1",
        "Encoders, scalers, imputers re-fit inside each fold",
    ], size=13.5, color=INK2, spacing=5)
    d.box(s, 4.0, 4.15, 4.6, 1.55, fill=RGBColor(0xFD, 0xEB, 0xE2))
    d.text(s, 4.25, 4.3, 4.2, 0.4, f"20% holdout · {n(R.split['n_holdout'])}", size=16, bold=True, color=ORANGE)
    d.text(s, 4.25, 4.75, 4.2, 0.9, "Locked away; scored exactly once, by the final tuned model.", size=13.5, color=INK2)
    d.arrow(s, 8.65, 2.65, 9.35, 2.65, color=ORANGE)
    d.box(s, 9.4, 1.55, 3.35, 2.25, fill=NAVY)
    d.text(s, 9.6, 1.7, 3.0, 2.0, [
        [("Final model", {"bold": True, "size": 16, "color": WHITE})],
        f"{R.best} configuration, C = {R.best_C:g}",
        f"At most {R.conv['max_n_iter_observed']} of {n(R.conv['max_iter_allowed'])} solver iterations: every fit converged",
    ], size=13.5, color=LIGHTBLUE, spacing=5)
    d.box(s, 9.4, 4.15, 3.35, 1.55, fill=TINT)
    d.text(s, 9.6, 4.3, 3.0, 1.3, [
        [("Submission", {"bold": True, "size": 16, "color": NAVY})],
        f"Refit on all {n(R.sub['refit_rows'])} rows → {n(R.sub['n_rows'])} test predictions",
    ], size=13.5, color=INK2, spacing=5)
    d.text(s, 0.6, 6.05, 12.1, 0.7,
           f"Random state 42 everywhere. Experiments: E0 majority baseline → E1 structure → E2 + region → E3 + geo target encoding → "
           f"E4 + engineered features → E5 class-balanced → E6 ordinal.", size=13, color=MUTED)
    d.footer(s)
    d.add_notes(s, "Training and testing procedure", (
        "Now, how we trained and tested. We first split the labelled data 80 to 20, stratified by damage grade. "
        f"The 20 percent holdout, {n(R.split['n_holdout'])} buildings, was locked away and used exactly once at the very end. "
        "Everything else, comparing experiments and tuning, used stratified five-fold cross-validation on the 80 percent. "
        "Because every preprocessing step lives in the pipeline, encoders and scalers are re-fitted inside each fold, so no fold ever sees statistics from its validation data. "
        "We ran seven experiments, each adding one idea: a majority baseline, structure only, plus region, plus target-encoded villages, plus engineered features, then a class-balanced and an ordinal variant. "
        f"The best of the last three, {R.best}, was tuned with GridSearchCV over C from {min(R.tun['grid']):g} to {max(R.tun['grid']):g}, and the best C was {R.best_C:g}. "
        "We checked convergence for every single fit. "
        "Finally, after the holdout evaluation, the model was refit on all labelled data to produce our competition submission."))

    # 10 --------------------------------------------------------------- Results table
    s = d.new()
    d.header(s, "Experimental study and analysis", "Location drives the gains; reweighting and ordinal do not"
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
        "This chart shows cross-validated micro-F1 for every experiment, with error bars across the five folds. "
        f"The majority baseline scores {base:.3f}. Structure alone lifts this to {R.mic('E1'):.3f}, which is useful but modest. "
        f"Adding the {R.data['n_unique']['geo_level_1_id']} regions gains {pp(geo1_gain)}, and the target-encoded village levels add another {pp(e3_gain)}, the largest single step. "
        f"Engineered features change micro-F1 by only {pp(fe_gain, 2)}. "
        f"The balanced and ordinal variants score {R.mic('E5'):.3f} and {R.mic('E6'):.3f}. "
        f"The fold-to-fold standard deviations are tiny, at most {100 * max(R.mic_sd(k) for k in R.exp):.2f} percentage points, so the big steps are not noise. "
        "The orange bar marks the configuration we carried forward to tuning. "
        "Two lessons stand out. First, what a building is made of matters, but on its own it cannot tell a mud-stone house near the epicentre from one far away; location supplies that context. "
        "Second, once location is in, extra hand-made features add almost nothing, so in this problem better information beats cleverer transformations."))

    # 11 --------------------------------------------------------------- Holdout
    s = d.new()
    d.header(s, "Experimental study and analysis", "Holdout performance of the tuned model")
    d.stat(s, 0.6, 1.75, 3.3, f"{H_mic:.3f}", "holdout micro-F1\n(competition metric)", color=ORANGE, big_size=48)
    d.stat(s, 0.6, 3.4, 3.3, f"{H_mac:.3f}", "holdout macro-F1", big_size=40)
    d.stat(s, 0.6, 4.85, 3.3, f"{R.tun['best_f1_micro_mean']:.3f}", f"CV micro-F1 at C = {R.best_C:g}\n(holdout agrees with CV)", big_size=32)
    d.picture(s, fig("fig09_confusion_matrix"), 3.9, 1.55, 5.2, 5.3)
    d.text(s, 9.4, 1.75, 3.4, 0.4, "Per-class recall", size=17, bold=True, color=NAVY)
    for i, c in enumerate([1, 2, 3]):
        y = 2.3 + i * 1.05
        d.box(s, 9.4, y, 3.35, 0.9)
        d.text(s, 9.6, y + 0.12, 1.6, 0.7, f"Grade {c}", size=15, bold=True, color=NAVY, anchor=MSO_ANCHOR.MIDDLE)
        d.text(s, 11.1, y + 0.08, 1.5, 0.75, f"{R.pc(c, 'recall'):.2f}", size=26, bold=True, color=ORANGE if c == 3 else NAVY,
               font=HEAD, align=PP_ALIGN.RIGHT, anchor=MSO_ANCHOR.MIDDLE)
    d.text(s, 9.4, 5.55, 3.4, 1.3,
           f"Errors are almost all between adjacent grades: only {pct(R.cmn(3, 1), 1)} of grade-3 buildings are predicted as grade 1.",
           size=13.5, color=INK2)
    d.footer(s)
    d.add_notes(s, "Holdout performance", (
        f"Now the moment of truth: the holdout, used once. The tuned model scores a micro-F1 of {H_mic:.3f} and a macro-F1 of {H_mac:.3f}. "
        f"That is almost identical to the cross-validated estimate of {R.tun['best_f1_micro_mean']:.3f}, which tells us we did not overfit our model selection. "
        f"The confusion matrix shows where the model succeeds and fails. Grade 2 is recalled {pct(R.pc(2, 'recall'), 0)} of the time and grade 3 {pct(R.pc(3, 'recall'), 0)}. "
        f"Grade 1 is the hardest, at {pct(R.pc(1, 'recall'), 0)}, because it is rare and often looks like grade 2. "
        f"Importantly, mistakes are almost always between neighbouring grades: only {pct(R.cmn(3, 1), 1)} of destroyed buildings are mistaken for low damage, which is the costly error for inspectors. "
        f"The largest error is grade-3 buildings predicted as grade 2, {pct(R.cmn(3, 2), 0)} of them. Many destroyed buildings look structurally ordinary on paper, and what tipped them over, such as local shaking, is not in the data. "
        f"Precision tells the other side: when the model says grade 3, it is right {pct(R.pc(3, 'precision'), 0)} of the time."))

    # 12 --------------------------------------------------------------- Prioritisation
    s = d.new()
    d.header(s, "Experimental study and analysis", "Ranking finds destroyed buildings far faster than random")
    d.picture(s, fig("fig10_prioritisation_curve"), 0.5, 1.55, 7.4, 5.3)
    for i, k in enumerate([10, 20, 30]):
        y = 1.7 + i * 1.6
        d.box(s, 8.3, y, 4.45, 1.42)
        d.text(s, 8.55, y + 0.15, 1.9, 0.8, pct(R.cap(k), 0), size=40, bold=True, color=ORANGE, font=HEAD)
        d.text(s, 10.45, y + 0.2, 2.2, 1.1, [f"of grade-3 buildings found by inspecting the top {k}%",
                                              [(f"{R.lift(k):.1f}× better than random", {"bold": True, "color": NAVY})]],
               size=13.5, color=INK2, spacing=3)
    d.text(s, 8.3, 6.5, 4.45, 0.4, f"Grade-3 vs rest ROC-AUC = {R.prio['auc_grade3_vs_rest']:.3f} on the holdout",
           size=13, color=MUTED)
    d.footer(s)
    d.add_notes(s, "Prioritisation analysis", (
        "This slide connects the model back to our problem statement. We ranked every holdout building by its predicted probability of grade 3, the near-destroyed class, and asked: "
        "if inspectors work down this list, how many destroyed buildings do they find? "
        f"Inspecting the top 10 percent finds {pct(R.cap(10), 0)} of all grade-3 buildings; the top 20 percent finds {pct(R.cap(20), 0)}; the top 30 percent finds {pct(R.cap(30), 0)}. "
        f"A random order would find only 10, 20 and 30 percent, so the ranking is {R.lift(10):.1f} times better than random at the top of the list. "
        f"Within the top 10 percent, {pct(R.prec_top(10), 0)} of buildings really are grade 3. "
        f"To make this concrete: in our holdout of {n(R.prio['n_buildings'])} buildings, the first {n(R.prio['at_fraction']['10']['n_inspected'])} visits on the list would reach "
        f"about {n(round(R.cap(10) * R.prio['n_grade3']))} destroyed buildings, while a random order would reach about {n(round(0.10 * R.prio['n_grade3']))}. "
        "In practice, that means the first teams sent out spend most of their time at the buildings that need them most. "
        "The curve also shows diminishing returns: after about half the list, most remaining buildings are lower risk, which is useful when planning how many teams to deploy."))

    # 13 --------------------------------------------------------------- Interpretation
    up = R.top_features("raising", 3)
    down = R.top_features("lowering", 3)
    s = d.new()
    d.header(s, "Experimental study and analysis", "What raises the odds of destruction?")
    d.picture(s, plot_coefficients_compact(R.coef["top_raising"], R.coef["top_lowering"], k=7), 0.5, 1.5, 6.7, 5.4)
    mat = R.coef["materials"]
    d.box(s, 7.4, 1.6, 5.35, 1.6, fill=RGBColor(0xFC, 0xEC, 0xEC))
    d.text(s, 7.65, 1.72, 4.9, 0.35, "Raise grade-3 odds", size=16, bold=True, color=RGBColor(0xB3, 0x2E, 0x2D))
    d.text(s, 7.65, 2.12, 4.9, 1.05, [f"{nm}: ×{orr:.2f}" for nm, orr in up], size=14, color=INK, spacing=2)
    d.box(s, 7.4, 3.35, 5.35, 1.6, fill=TINT)
    d.text(s, 7.65, 3.47, 4.9, 0.35, "Lower grade-3 odds", size=16, bold=True, color=DEEP)
    d.text(s, 7.65, 3.87, 4.9, 1.05, [f"{nm}: ×{orr:.2f}" for nm, orr in down], size=14, color=INK, spacing=2)
    d.box(s, 7.4, 5.1, 5.35, 1.55, fill=NAVY)
    d.text(s, 7.65, 5.22, 4.9, 0.35, "In plain words: the material matters", size=16, bold=True, color=WHITE)
    d.text(s, 7.65, 5.62, 4.9, 1.0, [
        [("Mud-mortar stone ", {}), (f"×{mat['has_superstructure_mud_mortar_stone']['odds_ratio']:.2f}", {"bold": True, "color": ORANGE}),
         ("   Stone flag ", {}), (f"×{mat['has_superstructure_stone_flag']['odds_ratio']:.2f}", {"bold": True, "color": ORANGE})],
        [("Cement-mortar brick ", {}), (f"×{mat['has_superstructure_cement_mortar_brick']['odds_ratio']:.2f}", {"bold": True, "color": LIGHTBLUE}),
         ("   Engineered RC ", {}), (f"×{mat['has_superstructure_rc_engineered']['odds_ratio']:.2f}", {"bold": True, "color": LIGHTBLUE})],
    ], size=14, color=WHITE, spacing=4)
    d.text(s, 7.4, 6.72, 5.35, 0.25, "Odds ratios from the final model; flags in <1% of buildings and location excluded.",
           size=10.5, color=MUTED)
    d.footer(s)
    d.add_notes(s, "Interpretation", (
        "Because we used logistic regression, we can open the model and read it. This chart shows odds ratios for grade-3 damage; red bars raise the odds and blue bars lower them. "
        f"The strongest risk factors are {up[0][0]}, {up[1][0]} and {up[2][0]}. "
        f"The strongest protective factors are {down[0][0]}, {down[1][0]} and {down[2][0]}. "
        f"For materials, mud-mortar stone multiplies the odds of destruction by about {mat['has_superstructure_mud_mortar_stone']['odds_ratio']:.1f}, while cement-mortar brick multiplies them by {mat['has_superstructure_cement_mortar_brick']['odds_ratio']:.2f} and engineered reinforced concrete by {mat['has_superstructure_rc_engineered']['odds_ratio']:.2f}. "
        "In plain language, heavy, brittle construction such as stone held together with mud fails badly in strong shaking, while engineered reinforced concrete and cement-bonded walls hold together. "
        "This matches engineering intuition, which gives us confidence that the model learned real physics rather than quirks of the data. "
        "We left two things out of this chart: location features, which are the strongest predictors but describe how hard the ground shook rather than the building, and very rare flags, whose estimates are unreliable."))

    # 14 --------------------------------------------------------------- Summary
    s = d.new()
    d.header(s, "Summary of project achievements", "What we delivered")
    ach = [
        (f"{H_mic:.3f}", "holdout micro-F1", f"vs {base:.3f} for the majority baseline ({pp(H_mic - base)})"),
        (pct(R.cap(20), 0), "of destroyed buildings", "found by inspecting just the top 20% of the ranked list"),
        (pp(e3_gain), "from geo target encoding", f"leakage-safe encoding of {n(R.data['n_unique']['geo_level_3_id'])} villages"),
        ("0", "leakage paths", "all preprocessing inside one pipeline; holdout scored exactly once"),
        ("7", "controlled experiments", "incl. an honest negative result for the ordinal model" if ord_diff <= 0.001
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
        f"To summarise. Our final logistic regression reaches a holdout micro-F1 of {H_mic:.3f}, {pp(H_mic - base)} above the majority baseline. "
        f"Translated into the problem statement, inspecting just the top 20 percent of buildings on our list finds {pct(R.cap(20), 0)} of the destroyed ones. "
        "The single biggest technical contribution was leakage-safe target encoding of the village-level location. "
        "We were strict about methodology: every transformation is inside one pipeline, and the holdout was scored once. "
        "We ran seven controlled experiments and report the ones that did not help as honestly as the ones that did. "
        "And the whole project, from raw CSV to this deck, is reproducible with one command."))

    # 15 --------------------------------------------------------------- Future directions
    s = d.new()
    d.header(s, "Future directions for further improvements", "Where we would go next")
    fut = [
        ("Richer location signal", "Add measured ground shaking (USGS ShakeMap PGA) and distance to the epicentre instead of using region ids as proxies."),
        ("Interactions, still linear", "Material × region and floors × age interactions, or spline terms, keeping the model interpretable."),
        ("True ordinal model", "A proportional-odds (cumulative-link) model with shared slopes, e.g. statsmodels OrderedModel or mord."),
        ("Cost-aware decisions", "Pick decision thresholds from inspection capacity and the cost of missing a destroyed building."),
        ("Probability calibration", "Check and calibrate predicted risks so that teams can trust the percentages, not only the ranking."),
        ("Benchmark & deploy", "Compare with gradient boosting as an upper bound; package the pipeline as a simple triage tool."),
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
        "Second, interactions such as material by region would let the model learn that mud-stone is especially dangerous where shaking was strongest, while staying linear and interpretable. "
        "Third, a proportional-odds model with shared slopes might use the ordering better. "
        "Fourth, decision thresholds should come from inspection capacity, with calibrated probabilities. Lastly, a gradient-boosting benchmark would show how much accuracy we trade for transparency. "
        "Thank you for listening; we are happy to take questions."))

    return d


SEGMENTS = [  # (presenter, slide numbers) - balanced by estimated speaking time
    ("Presenter 1", [1, 2, 3]),
    ("Presenter 2", [4, 5, 6]),
    ("Presenter 3", [7, 8]),
    ("Presenter 4", [9, 10]),
    ("Presenter 5", [11, 12]),
    ("Presenter 6", [13, 14, 15]),
]


def write_notes_md(d: Deck):
    by_no = {no: (t, txt) for no, t, txt in d.notes}

    def secs(txt):
        return len(txt.split()) / WPM * 60

    lines = ["# Speaker notes: 15-minute talk, 6 presenters", "",
             f"Timing is estimated from word count at {WPM} words per minute. Each segment is about 2.5 minutes. "
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
