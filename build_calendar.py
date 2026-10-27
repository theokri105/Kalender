#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Grindeplan H26 - genererer plan.ics (abonnementskalender for Apple Kalender).

Kjør:   python3 build_calendar.py
Så:     git add plan.ics && git commit && git push
Abonnerte kalendere henter endringene automatisk.

Alle regler som er avtalt med Stig står i README.md. Endre KEY DATES under
når ny informasjon kommer (f.eks. eksakt dato for SOC1-eksamen).
"""
from __future__ import annotations

import hashlib
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

# ---------------------------------------------------------------------------
# KEY DATES - endre her
# ---------------------------------------------------------------------------
START = date(2026, 10, 27)
END = date(2026, 12, 16)

SOC1_EXAM = date(2026, 11, 16)        # PLASSHOLDER - muntlig eksamen er i uka 16.-20.11
SOC1_EXAM_CONFIRMED = False
SOC1_EXAM_TIME = None                 # f.eks. ("10:00", "10:30") når tiden er kjent
TECH2_HOME_EXAM = (date(2026, 11, 23), date(2026, 11, 25))
TECH1_EXAM = date(2026, 12, 1)
BUD1_EXAM = date(2026, 12, 9)         # 09:00-12:00 (BUD1-plan)
TECH2_EXAM = date(2026, 12, 16)

FINAL_START = date(2026, 11, 23)

# Innhold i blokker som allerede er passert låses, så de ikke får nytt innhold når planen endres.
# Ved hver ny endring: sett FREEZE_DATE til første dag som skal planlegges på nytt, og LOCKED til
# hvor langt hvert fag var planlagt før den dagen (BUD1 i sider, TECH1 i seksjonsvekt, TECH2 i ukeemner).
FREEZE_DATE = date(2026, 10, 28)
LOCKED = {"BUD1": 25, "TECH1": 0.0, "TECH2": 0.0}   # 27.10: BUD1 kap. 1 (s. 4-28)      # sal 06:00-17:30 (helg 17:00), ingen gym
TECH1_CHAPTERS_FROM = date(2026, 10, 29)
TECH2_REVIEW_FROM = date(2026, 11, 19)

# Annet fag i helgenes progresjonsblokk (11:30-12:30) når helgen er "normal"
WEEKEND_SECOND = {
    date(2026, 11, 1): "B",
    date(2026, 11, 8): "T2",
    date(2026, 11, 14): "B",
    date(2026, 11, 15): "T2",
    date(2026, 11, 22): "T2",
}


def tech2_hours(d: date) -> float:
    """TECH2 stiger fra 2 til 4 t/dag fram mot hjemmeeksamen 23.11."""
    if d <= date(2026, 10, 30):
        return 2.0
    if d <= date(2026, 11, 6):
        return 2.5
    if d <= date(2026, 11, 13):
        return 3.0
    if d <= date(2026, 11, 18):
        return 3.5
    return 4.0


# ---------------------------------------------------------------------------
# PENSUM
# ---------------------------------------------------------------------------
# TECH1: seksjoner fra TECH1 course outline (ikke 9.4, ikke 12.10), i bokrekkefølge.
# Titler: Pearsons innholdsfortegnelse, Essential Mathematics for Economic Analysis, 6. utg.
# Vekt 0.5 = anvendelser ("you need to see how the mathematical tool is set up") / første del av 7.11.
TECH1_SECTIONS = [
    ("6.5", "A Brief Introduction to Limits", 1),
    ("6.7", "Sums, Products, and Quotients", 1),
    ("7.1", "Implicit Differentiation", 1),
    ("7.4", "Linear Approximations", 1),
    ("7.5", "Polynomial Approximations", 1),
    ("7.6", "Taylor's Formula", 1),
    ("7.7", "Elasticities", 1),
    ("7.11", "Infinite Sequences (bare første del)", 0.5),
    ("7.12", "L'Hôpital's Rule", 1),
    ("8.1", "Intuition", 1),
    ("8.2", "Definitions", 1),
    ("8.3", "General Properties", 1),
    ("8.4", "First Derivative Tests", 1),
    ("8.5", "Second Derivative Tests", 1),
    ("8.6", "Inflection Points", 1),
    ("9.1", "Extreme Points", 1),
    ("9.2", "Simple Tests for Extreme Points", 1),
    ("9.3", "Economic Examples (anvendelse)", 0.5),
    ("9.5", "Further Economic Examples (anvendelse)", 0.5),
    ("9.6", "Local Extreme Points", 1),
    ("10.1", "Indefinite Integrals", 1),
    ("10.2", "Area and Definite Integrals", 1),
    ("10.3", "Properties of Definite Integrals", 1),
    ("10.4", "Economic Applications (anvendelse)", 0.5),
    ("10.5", "Integration by Parts", 1),
    ("10.6", "Integration by Substitution", 1),
    ("10.7", "Infinite Intervals of Integration", 1),
    ("11.1", "Interest Periods and Effective Rates", 1),
    ("11.2", "Continuous Compounding", 1),
    ("11.3", "Present Value", 1),
    ("11.4", "Geometric Series", 1),
    ("11.5", "Total Present Value", 1),
    ("11.6", "Mortgage Repayments", 1),
    ("11.7", "Internal Rate of Return", 1),
    ("11.8", "A Glimpse at Difference Equations", 1),
    ("12.1", "Matrices and Vectors", 1),
    ("12.2", "Systems of Linear Equations", 1),
    ("12.3", "Matrix Addition", 1),
    ("12.4", "Algebra of Vectors", 1),
    ("12.5", "Matrix Multiplication", 1),
    ("12.6", "Rules for Matrix Multiplication", 1),
    ("12.7", "The Transpose", 1),
    ("12.8", "Gaussian Elimination", 1),
    ("12.9", "Geometric Interpretation of Vectors", 1),
    ("13.1", "Determinants of Order 2", 1),
    ("13.2", "Determinants of Order 3", 1),
    ("13.3", "Determinants in General", 1),
    ("13.4", "Basic Rules for Determinants", 1),
    ("13.5", "Expansion by Cofactors", 1),
    ("13.6", "The Inverse of a Matrix", 1),
    ("13.7", "A General Formula for the Inverse", 1),
    ("13.8", "Cramer's Rule", 1),
    ("13.9", "The Leontief Model (anvendelse)", 0.5),
    ("13.10", "Eigenvalues and Eigenvectors", 1),
    ("13.11", "Diagonalization", 1),
    ("13.12", "Quadratic Forms", 1),
]

# BUD1: Drury, Management Accounting for Business, 9. utg. Pensum kap. 1-10, 12, 14-16
# (BUD1-plan). Seksjoner og sidetall fra Stigs bilder av innholdsfortegnelsen.
# (kapittel, tittel, startside, sluttside, [(seksjon, side), ...])
BUD1_CHAPTERS = [
    (1, "Introduction to management accounting", 4, 28, [
        ("The users of accounting information", 5),
        ("Differences between management accounting and financial accounting", 6),
        ("The decision-making, planning and control process", 7),
        ("The impact of the changing business environment on management accounting", 11),
        ("Focus on customer satisfaction and new management approaches", 19),
        ("Functions of management accounting", 22),
        ("Summary of the contents of this book", 23),
        ("Summary", 26), ("Key terms and concepts", 27), ("Assessment material", 28)]),
    (2, "An introduction to cost terms and concepts", 29, 53, [
        ("Cost objects", 30),
        ("Manufacturing, merchandising and service organizations", 31),
        ("Direct and indirect costs", 31), ("Period and product costs", 35),
        ("Cost behaviour", 37), ("Relevant and irrelevant costs and revenues", 41),
        ("Avoidable and unavoidable costs", 42), ("Sunk costs", 43),
        ("Opportunity costs", 44), ("Incremental and marginal costs", 45),
        ("Controllable and uncontrollable costs", 47),
        ("The cost and management accounting information system", 48),
        ("Summary", 49), ("Key terms and concepts", 50), ("Assessment material", 51)]),
    (3, "Cost-volume-profit analysis", 56, 85, [
        ("Curvilinear CVP relationships", 57), ("Linear CVP relationships", 58),
        ("A numerical approach to cost-volume-profit analysis", 60),
        ("The contribution margin ratio", 64), ("Relevant range", 65),
        ("Margin of safety", 65), ("Constructing the break-even or CVP chart", 66),
        ("Alternative presentation of cost-volume-profit analysis", 67),
        ("Multi-product cost-volume-profit analysis", 70), ("Operating leverage", 72),
        ("Cost-volume-profit analysis assumptions and limitations", 74),
        ("The impact of information technology", 76),
        ("Separation of costs into their fixed and variable elements", 77),
        ("Summary", 79), ("Key terms and concepts", 80), ("Assessment material", 80)]),
    (4, "Measuring relevant costs and revenues for decision-making", 86, 116, [
        ("Identifying relevant costs and revenues", 87),
        ("Importance of qualitative/non-financial factors", 88),
        ("Special pricing decisions", 88),
        ("Product mix decisions when capacity constraints exist", 93),
        ("Replacement of equipment: The irrelevance of past costs", 96),
        ("Outsourcing and make-or-buy decisions", 99), ("Discontinuation decisions", 103),
        ("Determining the relevant costs of direct materials", 105),
        ("Determining the relevant costs of direct labour", 105),
        ("Incorporating risk and uncertainty into the decision-making process", 106),
        ("Summary", 109), ("Key terms and concepts", 110), ("Assessment material", 111)]),
    (5, "Pricing decisions and profitability analysis", 117, 143, [
        ("The role of cost information in pricing decisions", 118),
        ("A price-setting firm facing short-run pricing decisions", 118),
        ("A price-setting firm facing long-run pricing decisions", 119),
        ("A price-taking firm facing short-run product mix decisions", 125),
        ("A price-taking firm facing long-run product mix decisions", 126),
        ("Surveys of practice relating to pricing decisions", 129),
        ("Limitations of cost-plus pricing", 129), ("Reasons for using cost-plus pricing", 131),
        ("Pricing policies", 131), ("Customer profitability analysis", 133),
        ("Summary", 137), ("Key terms and concepts", 139), ("Assessment material", 139)]),
    (6, "Capital investment decisions: Appraisal methods", 144, 175, [
        ("The opportunity cost of an investment", 145), ("Compounding and discounting", 147),
        ("The concept of net present value", 150), ("Calculating net present values", 151),
        ("Internal rate of return", 153), ("Relevant cash flows", 157),
        ("Comparison of net present value and internal rate of return", 157),
        ("Techniques that ignore the time value of money", 159), ("Payback method", 160),
        ("Accounting rate of return", 163), ("Qualitative factors", 164),
        ("Weighted average cost of capital", 166), ("Taxation and investment decisions", 166),
        ("Summary", 168), ("Key terms and concepts", 169), ("Assessment material", 171)]),
    (7, "Cost assignment", 178, 204, [
        ("Assignment of direct and indirect costs", 179),
        ("Different costs for different purposes", 181),
        ("Cost-benefit issues and cost system design", 181),
        ("Plant-wide (blanket) overhead rates", 182), ("The two-stage allocation process", 185),
        ("An illustration of the two-stage process for a traditional costing system", 186),
        ("Extracting relevant costs for decision-making", 191),
        ("Budgeted overhead rates", 192), ("Under- and over-recovery of overheads", 193),
        ("Non-manufacturing overheads", 195),
        ("Cost assignment in non-manufacturing organizations", 196),
        ("Summary", 198), ("Key terms and concepts", 200), ("Assessment material", 201)]),
    (8, "Activity-based costing", 205, 231, [
        ("Comparison of traditional and ABC systems", 206),
        ("Volume-based and non-volume-based cost drivers", 209),
        ("An illustration of the two-stage allocation process for ABC", 211),
        ("Designing ABC systems", 216), ("Activity hierarchies", 218),
        ("Cost versus benefit considerations", 221), ("ABC cost management applications", 221),
        ("Summary", 224), ("Key terms and concepts", 225), ("Assessment material", 226)]),
    (9, "Management control systems", 235, 272, [
        ("The scope of management control systems", 237),
        ("Different types of control mechanisms", 240),
        ("Feedback and feed-forward controls", 243),
        ("Management accounting control systems", 245), ("Responsibility centres", 247),
        ("Applying the controllability principle", 249),
        ("Setting performance targets and determining how challenging they should be", 253),
        ("Determining how much influence managers should have in setting targets", 255),
        ("Harmful side-effects of controls", 256), ("Rewards and incentives", 258),
        ("Different approaches that managers use to evaluate budgetees' performance", 259),
        ("Alternative uses of management accounting information", 261),
        ("Summary", 263), ("Key terms and concepts", 265), ("Assessment material", 267)]),
    (10, "The budgeting process", 273, 310, [
        ("The strategic planning, budgeting and control process", 274),
        ("The multiple functions of budgets", 277), ("Conflicting roles of budgets", 278),
        ("The budget period", 279), ("Administration of the budgeting process", 280),
        ("Stages in the budgeting process", 281), ("A detailed illustration", 284),
        ("Computerized budgeting", 292), ("Activity-based budgeting", 294),
        ("Zero-based budgeting", 296), ("Criticisms of budgeting", 298),
        ("Summary", 303), ("Key terms and concepts", 304), ("Assessment material", 306)]),
    (12, "Divisional financial performance measures", 347, 369, [
        ("Divisional organizational structures", 348),
        ("Advantages and disadvantages of divisionalization", 350),
        ("Prerequisites for successful divisionalization", 350),
        ("Distinguishing between the managerial and economic performance of the division", 351),
        ("Alternative divisional profit measures", 352), ("Surveys of practice", 353),
        ("Return on investment", 355), ("Residual income", 356),
        ("Economic value added (EVA)", 357),
        ("Addressing the dysfunctional consequences of short-term financial performance measures", 359),
        ("Summary", 363), ("Key terms and concepts", 364), ("Assessment material", 365)]),
    (14, "Strategic performance management", 395, 428, [
        ("The performance management framework", 396),
        ("Strategy and strategic positioning", 398),
        ("Performance measurement and performance management systems", 400),
        ("Alternative performance management frameworks", 401),
        ("The balanced scorecard", 402),
        ("Linking performance evaluation with the balanced scorecard", 412),
        ("Benefits and limitations of the balanced scorecard approach", 414),
        ("Summary", 420), ("Key terms and concepts", 422), ("Assessment material", 423)]),
    (15, "Strategic cost management and value creation", 429, 473, [
        ("Cost management and the value chain", 432), ("Life cycle cost management", 435),
        ("Target costing", 436), ("Activity-based management", 443), ("Benchmarking", 448),
        ("Business process reengineering", 449), ("Just-in-time systems", 450),
        ("Quality cost management", 456),
        ("Summary", 464), ("Key terms and concepts", 466), ("Assessment material", 468)]),
    (16, "Management accounting: Contemporary technologies and data analytics", 474, 497, [
        ("Information technology in management accounting: A brief history and context", 475),
        ("Data analytics for management accountants", 484),
        ("Summary", 493), ("Key terms and concepts", 494), ("Assessment material", 494)]),
]

# TECH2: ukeemner fra TECH2 course outline
TECH2_TOPICS = [
    (34, "Course intro & Getting started with VS Code"),
    (35, "Python basics & Version control with git"),
    (36, "Decisions"),
    (37, "Loops"),
    (38, "Functions"),
    (39, "Python packages & Virtual environments"),
    (40, "More on git and VS Code & NumPy"),
    (41, "Intro to pandas"),
    (42, "Plotting"),
    (43, "Grouping and aggregation"),
    (44, "Concatenating and merging"),
    (45, "AI week"),
]
TECH2_MATERIAL = ("Materiale (Jupyter-notebooks, skript, øvingsark, slides): "
                  "github.com/isabelhovdahl/TECH2 (uke 34-39) og "
                  "github.com/richardfoltyn/TECH2-H26 (uke 40-45). "
                  "Lenker per uke ligger under Modules på Canvas.")

# ---------------------------------------------------------------------------
# HENDELSER
# ---------------------------------------------------------------------------
@dataclass
class Ev:
    d: date
    start: str | None          # "HH:MM" eller None (heldags)
    end: str | None
    title: str
    desc: str = ""
    kind: str = ""             # TECH1, TECH2, BUD1, SOC1, COM1, CATCHUP, PAUSE, LECT, RUN, GYM, ROUTINE, EXAM, MARK
    queue: str | None = None   # TECH1 / TECH2 / BUD1 -> innhold fylles inn automatisk
    days: int = 1              # varighet for heldagshendelser
    alarm: bool = False        # varsel ved start (VALARM)


def mins(hm: str) -> int:
    h, m = hm.split(":")
    return int(h) * 60 + int(m)


def hm(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"


CATCHUP_DESC = ("Fyll hull fra uka: det du ikke rakk, det du ikke forsto, "
                "og oppgaver du hoppet over - i alle fag.")
PAUSE_DESC = {
    "P": "30 min buffer ved fagbytte (pusterom hvis noe tar lengre tid).",
    "P20": "20 min pause før forelesning.",
    "P15": "Bare 15 min før neste faste økt - kan ikke gjøres lengre.",
}
WORKOUT_DESC = ("Treningspause (styrke), 2 t. Normalt rundt 11:30-13:30; flyttes rundt "
                "forelesninger og workshops, og legges der et fag slutter så den også er "
                "pausen ved fagbytte.")
TECH2_REVIEW = ("Grinde på SAL: TECH2 - repetisjon og øving før hjemmeeksamen",
                "Hjemmeeksamen 23.-25.11 (3 dager, grupper på 2-3, 30 %). "
                "Gå gjennom uke 34-45 og gjør øvingsarkene på nytt der du er usikker. "
                "Info om hjemmeeksamen kommer på Canvas. " + TECH2_MATERIAL)


def sal(d: date, spec: list) -> list[Ev]:
    """Gjør om en dagsplan (liste med (start, slutt, type[, info])) til hendelser."""
    out = []
    for item in spec:
        s, e, t = item[:3]
        x = item[3] if len(item) > 3 else {}
        if t in PAUSE_DESC:
            out.append(Ev(d, s, e, "Pause", PAUSE_DESC[t], kind="PAUSE"))
        elif t == "T1":
            out.append(Ev(d, s, e, "", kind="TECH1", queue="TECH1"))
        elif t == "T2":
            if d >= TECH2_REVIEW_FROM:
                out.append(Ev(d, s, e, TECH2_REVIEW[0], TECH2_REVIEW[1], kind="TECH2"))
            else:
                out.append(Ev(d, s, e, "", kind="TECH2", queue="TECH2"))
        elif t == "B":
            out.append(Ev(d, s, e, "", kind="BUD1", queue="BUD1"))
        elif t == "C":
            out.append(Ev(d, s, e, "Gå igjennom der du henger etter", CATCHUP_DESC, kind="CATCHUP"))
        elif t == "W":
            out.append(Ev(d, s, e, "Være på gymmen", WORKOUT_DESC, kind="GYM"))
        else:  # "X" eller "L": ferdig tekst
            out.append(Ev(d, s, e, x["title"], x.get("desc", ""), kind=x["kind"]))
    return out


def X(s, e, title, desc, kind):
    return (s, e, "X", {"title": title, "desc": desc, "kind": kind})


def L(s, e, title, desc):
    return (s, e, "L", {"title": title, "desc": desc, "kind": "LECT"})


# --- rutiner ---------------------------------------------------------------
def morning_normal(d):
    return [Ev(d, "05:15", "05:35", "Våkne for faen - Grindetid", kind="ROUTINE", alarm=True),
            Ev(d, "05:35", "06:15", "Løpetur", kind="RUN"),
            Ev(d, "06:15", "07:00", "Dusj og til NHH", kind="ROUTINE")]


def evening_normal(d, clean=False):
    """Ingen løping etter skolen og ingen middagsblokk (endret 27.10)."""
    out = []
    if clean:
        out.append(Ev(d, "16:30", "17:30", "Rengjøring", kind="ROUTINE"))
    out.append(Ev(d, "20:00", "20:15", "Leggetid", "I seng kl. 20:00.", kind="ROUTINE"))
    return out


def gym(d):
    return [Ev(d, "08:00", "09:15", "Være på gymmen", kind="GYM")]


def morning_final(d):
    return [Ev(d, "05:00", "05:20", "Våkne for faen - Grindetid", kind="ROUTINE", alarm=True),
            Ev(d, "05:20", "06:00", "Til NHH", kind="ROUTINE")]


def evening_final(d, clean=False, bud_rev=None):
    """Ingen løping og ingen middagsblokk (endret 27.10)."""
    out = []
    if clean:
        out.append(Ev(d, "17:30", "18:30", "Rengjøring", kind="ROUTINE"))
    if bud_rev:
        out.append(Ev(d, "19:30", "20:00", f"BUD1 - repetisjon: {bud_rev}",
                      "30 min repetisjon hjemme. Ikke nytt stoff - BUD1 har ingen arbeidstid på dagtid denne uka.",
                      kind="BUD1REV"))
    out.append(Ev(d, "20:00", "20:15", "Leggetid", "I seng kl. 20:00.", kind="ROUTINE"))
    return out


# --- standarddager -----------------------------------------------------------
def weekday_spec(d):
    """Man-tor 07:00-19:00, fre 07:00-18:00: TECH1 -> trening (2 t) -> TECH2 -> pause -> BUD1.

    Treningen legges der TECH1 slutter (mellom 10:30 og 12:30), så den også er pausen ved
    fagbytte. TECH1 og TECH2 beholder tiden sin (TECH2 har nærmeste eksamen); BUD1, som har
    eksamen lengst unna, tar kuttet: 1,5 t man-tor. Fredag: TECH1 -30 min og BUD1 1 t.
    """
    d2 = int(tech2_hours(d) * 60)
    if d.weekday() <= 3:
        w, end = mins("15:00") - d2, mins("19:00")
    else:
        w, end = mins("14:30") - d2, mins("18:00")
    t2_end = w + 120 + d2
    return [("07:00", hm(w), "T1"), (hm(w), hm(w + 120), "W"),
            (hm(w + 120), hm(t2_end), "T2"), (hm(t2_end), hm(t2_end + 30), "P"),
            (hm(t2_end + 30), hm(end), "B")]


def weekend_spec(d):
    second = WEEKEND_SECOND.get(d, "B")
    return [("10:00", "11:00", "T1"), ("11:00", "11:30", "P"),
            ("11:30", "12:30", second), ("12:30", "13:00", "P"),
            ("13:00", "16:00", "C")]


# --- faste forelesninger og spesialdager --------------------------------------
COM1_W44 = ("Uke 44: Academic and professional writing; Information literacy; "
            "introduction to pitching. Gjesteforelesning Nicolai Tangen (CEO NBIM) "
            "kl. 12.15-13.15 står i uke 44 - sjekk hvilken dag. (COM1 course outline)")
COM1_W45 = ("Uke 45: Pitch workshop. Possible guest lecture. Language technology and "
            "academic writing. (COM1 course outline)")
TECH1_NOCH = "Ikke kapittelarbeid - det starter torsdag 29.10."

SPECIAL = {
    date(2026, 10, 27): [
        X("07:00", "09:55", "Grinde på SAL: TECH1 - oversikt (ikke kapittelarbeid)",
          TECH1_NOCH + "\n1) Se gjennom tidligere TECH1-eksamener på Canvas (Previous Exams) "
          "for å se format og nivå. NB: eksamensform og pensum avviker fra TECH1 i 2024.\n"
          "2) Lag oversikt over pensum (kap. 6-13) og samle notatene dine.\n"
          "3) Forbered forelesning 11 (Problems from Chapter 13).", "TECH1"),
        ("09:55", "10:15", "P20"),
        L("10:15", "12:00", "Forelesning TECH1 - nr. 11: Problems from Chapter 13",
          "TECH1 course outline, forelesning 11 (kap. 13)."),
        X("12:00", "15:30", "Grinde på SAL: TECH1 - gå gjennom forelesning 11 + forbered TA-økten",
          TECH1_NOCH + " Gå gjennom notatene fra forelesningen og start på problemsettet til "
          "TA-økten onsdag 16:15. (TECH2-økten i dag er byttet til TECH1.)", "TECH1"),
        ("15:30", "16:00", "P"),
        ("16:00", "18:00", "B"),
    ],
    # Uke 44: all TECH2-egenjobbing byttet til TECH1 (forelesning og workshop beholdes)
    date(2026, 10, 29): [
        ("07:00", "11:30", "T1"), ("11:30", "13:30", "W"), ("13:30", "17:00", "T1"),
        ("17:00", "17:30", "P"), ("17:30", "19:00", "B"),
    ],
    date(2026, 10, 28): [
        X("07:00", "07:55", "Grinde på SAL: TECH1 - forbered TA-økten (problemsett)",
          TECH1_NOCH, "TECH1"),
        ("07:55", "08:15", "P20"),
        L("08:15", "10:00", "Forelesning TECH2 - uke 44: Concatenating and merging",
          "Onsdager 08:15-10:00 (TECH2 course outline)."),
        ("10:00", "12:00", "W"),
        ("12:00", "12:15", "P15"),
        L("12:15", "14:00", "Forelesning COM1 (gruppe 1) - uke 44", COM1_W44),
        ("14:00", "14:30", "P"), ("14:30", "15:55", "B"), ("15:55", "16:15", "P20"),
        L("16:15", "18:00", "TA-økt TECH1 (siste)",
          "Du har allerede kursgodkjenning (4 av 6), men tar denne siste."),
        X("18:00", "19:00", "Grinde på SAL: TECH1 - gå gjennom TA-økten",
          TECH1_NOCH + " Gå gjennom oppgavene fra TA-økten mens de er ferske.", "TECH1"),
    ],
    date(2026, 10, 30): [
        X("07:00", "09:55", "Grinde på SAL: COM1 - EA3 refleksjonstekst: første utkast",
          "650-850 ord. Struktur fra EA3-oppgaven: 1) Introduction 2) Personal learning "
          "development: own performance, feedback on your work, activities in class and "
          "group work - bruk Gibbs' cycle 3) Bruk av generativ KI i kursarbeidet (hvis du har "
          "brukt det) 4) Generativ KI i utdanning og samfunn 5) Conclusion.\n"
          "NB: Generativ KI er ikke tillatt i utarbeidelsen av teksten.\n"
          "Feedback på CA1 kommer innen 1.11 - revisjon er lagt til lørdag 7.11.", "COM1"),
        ("09:55", "10:15", "P20"),
        L("10:15", "12:00", "TECH1 - reservetime (sjekk Canvas)",
          "TECH1 course outline: reservetime fredag 30.10. Tid antatt 10:15-12:00 som de "
          "andre TECH1-forelesningene. Brukes den ikke: jobb med TECH1-kapitlene i stedet."),
        ("12:00", "12:15", "P15"),
        L("12:15", "14:00", "Workshop TECH2 - uke 44",
          "Fredager 12:15-14:00 (TECH2 course outline)."),
        ("14:00", "16:00", "W"), ("16:00", "18:00", "B"),
    ],
    date(2026, 11, 2): [
        ("07:00", "09:55", "T1"), ("09:55", "10:15", "P20"),
        L("10:15", "12:00", "Forelesning BUD1 - wrap-up",
          "Course wrap-up: tips for the exam, questions from you. Send spørsmål på "
          "forhånd. (BUD1-plan)"),
        ("12:00", "12:15", "P15"),
        L("12:15", "14:00", "Forelesning COM1 (gruppe 1) - uke 45", COM1_W45),
        ("14:00", "16:00", "W"), ("16:00", "18:00", "T2"), ("18:00", "18:30", "P"),
        ("18:30", "19:00", "T1"),
    ],
    date(2026, 11, 4): [
        ("07:00", "07:55", "T1"), ("07:55", "08:15", "P20"),
        L("08:15", "10:00", "Forelesning TECH2 - uke 45: AI week",
          "Onsdager 08:15-10:00 (TECH2 course outline)."),
        ("10:00", "10:30", "P"), ("10:30", "11:55", "T1"), ("11:55", "12:15", "P20"),
        L("12:15", "14:00", "Forelesning COM1 (gruppe 1) - uke 45", COM1_W45),
        ("14:00", "16:00", "W"), ("16:00", "17:00", "T2"), ("17:00", "17:30", "P"),
        ("17:30", "19:00", "B"),
    ],
    date(2026, 11, 6): [
        ("07:00", "11:55", "T1"), ("11:55", "12:15", "P20"),
        L("12:15", "14:00", "Workshop TECH2 - uke 45",
          "Fredager 12:15-14:00 (TECH2 course outline)."),
        ("14:00", "15:00", "T2"), ("15:00", "17:00", "W"), ("17:00", "18:00", "B"),
    ],
    date(2026, 11, 9): [
        ("07:00", "11:25", "T1"), ("11:25", "11:55", "P"), ("11:55", "13:55", "T2"),
        ("13:55", "14:15", "P20"),
        L("14:15", "16:00", "SOC1 - posterpresentasjon (obligatorisk)",
          "Obligatorisk - gi beskjed på e-post på forhånd hvis du ikke kan møte (SOC1-plan). "
          "Tid antatt ut fra fast SOC1-tid mandag 14:15-16:00 - sjekk TimeEdit."),
        ("16:00", "18:00", "W"), ("18:00", "19:00", "B"),
    ],
    date(2026, 11, 11): [
        ("07:00", "11:55", "T1"), ("11:55", "12:15", "P20"),
        L("12:15", "14:00", "Forelesning SOC1 - summary lecture og mock exam",
          "SOC1-plan, 11.11. Tid antatt ut fra fast SOC1-tid onsdag 12:15-14:00 - sjekk TimeEdit."),
        ("14:00", "16:00", "W"), ("16:00", "17:00", "T2"), ("17:00", "17:30", "P"),
        ("17:30", "19:00", "B"),
    ],
    # --- helger med spesialinnhold ---
    date(2026, 10, 31): [
        X("10:00", "12:30", "Grinde på SAL: SOC1 - Reflection note 2 (individuell)",
          "Frist onsdag 4.11 kl. 23:59 på Canvas (SOC1-plan). Sjekk SOC1-reglene for "
          "KI-bruk på Canvas.", "SOC1"),
        ("12:30", "13:00", "P"), ("13:00", "16:00", "C"),
    ],
    date(2026, 11, 7): [
        ("10:00", "11:00", "T1"), ("11:00", "11:30", "P"),
        X("11:30", "12:30", "Grinde på SAL: COM1 - EA3: revider refleksjonsteksten etter CA1-feedback",
          "Feedback på CA1 (technical report) skulle komme innen 1.11. EA3 skal dekke hvordan "
          "du reagerte på feedbacken og hvordan du brukte den. NB: Generativ KI er ikke tillatt "
          "i utarbeidelsen av teksten.", "COM1"),
        ("12:30", "13:00", "P"), ("13:00", "16:00", "C"),
    ],
    date(2026, 11, 21): [
        X("10:00", "14:00", "Grinde på SAL: COM1 - EA1 individuell presentasjon: endelig versjon",
          "4 t: implementer feedbacken fra første forsøk og spill inn på nytt. Flyttet fra 26.11 "
          "fordi TECH1 har prioritet den uka. Endelig frist 27.11.", "COM1"),
        X("14:00", "15:00", "Grinde på SAL: COM1 - siste kontroll + lever porteføljen i WISEflow",
          "Porteføljen = EA1, EA2 og EA3. COM1 course outline: «Full portfolio» 13.11-27.11, "
          "frist 27.11 kl. 12:00. Sjekk at innleveringen i WISEflow er åpen.", "COM1"),
        ("15:00", "15:30", "P"), ("15:30", "16:00", "C"),
    ],
}

SOC1_MODULES = ("Modul 1: Technological change, economic growth, and sustainability at the "
                "country level. Modul 2: Technological change, labor markets, and product markets. "
                "Modul 3: Technological change and the firm. Modul 4: Technological change and "
                "political structure.")


def soc1_prep_days():
    return [SOC1_EXAM - timedelta(days=k) for k in (3, 2, 1)]


def soc1_prep_block(i):
    titles = {
        1: "Grinde på SAL: SOC1 - eksamensforberedelse 1/3: modul 1-2",
        2: "Grinde på SAL: SOC1 - eksamensforberedelse 2/3: modul 3-4",
        3: "Grinde på SAL: SOC1 - eksamensforberedelse 3/3: øv muntlig",
    }
    desc = ("Muntlig eksamen, 30 min, individuell, bestått/ikke bestått (SOC1 course information). "
            + SOC1_MODULES + " Pensum i Leganto.")
    if i == 3:
        desc += " I dag: forklar hovedpoengene høyt med utgangspunkt i eksamensarket (preparatory exam sheet)."
    if not SOC1_EXAM_CONFIRMED:
        desc += " NB: Eksamensdatoen er en plassholder - forberedelsesdagene flyttes når datoen er klar."
    return titles[i], desc


def prep_day(d, i):
    title, desc = soc1_prep_block(i)
    if d.weekday() == 4:   # fredag, slutt 18:00 - SOC1 beholder 4 t 45 min, BUD1 utgår denne dagen
        spec = [("07:00", "08:45", "T1"), ("08:45", "09:15", "P"),
                X("09:15", "11:30", title, desc, "SOC1"), ("11:30", "13:30", "W"),
                X("13:30", "16:00", title, desc, "SOC1"), ("16:00", "16:30", "P"),
                ("16:30", "18:00", "T2")]
        return morning_normal(d) + sal(d, spec) + evening_normal(d)
    if d.weekday() < 4:    # man-tor, slutt 19:00
        spec = [("07:00", "09:15", "T1"), ("09:15", "09:45", "P"),
                X("09:45", "11:30", title, desc, "SOC1"), ("11:30", "13:30", "W"),
                X("13:30", "16:30", title, desc, "SOC1"), ("16:30", "17:00", "P"),
                ("17:00", "19:00", "T2")]
        return morning_normal(d) + sal(d, spec) + evening_normal(d)
    spec = [X("10:00", "13:00", title, desc, "SOC1"), ("13:00", "13:30", "P"),
            ("13:30", "16:00", "C")]
    return gym(d) + sal(d, spec) + evening_normal(d, clean=(d.weekday() == 6))


# --- sluttperioden -------------------------------------------------------------
BUD1_REV = {
    date(2026, 11, 26): "kap. 1-2", date(2026, 11, 27): "kap. 3-4",
    date(2026, 11, 28): "kap. 5-6", date(2026, 11, 29): "kap. 7-8",
    date(2026, 11, 30): "kap. 9-10",
}
TECH1_MOCK_DESC = ("Tidligere eksamener ligger på Canvas (Previous Exams). NB: eksamensform og "
                   "pensum avviker fra TECH1 i 2024 (course outline). Eksamen: 4 t skoleeksamen, "
                   "penn og papir, ingen kalkulator, svar på engelsk.")
BUD1_MOCK_DESC = ("Eksamen: 3 t digital skoleeksamen med Excel, kalkulator og én tospråklig ordbok - "
                  "ingen bøker eller notater. Gruppeøvingene er eksamenslignende oppgavesett med "
                  "løsningsforslag på Canvas. (BUD1-plan)")
TECH2_MOCK_DESC = ("Eksamen: 3 t digital skoleeksamen med tilgang til Python (70 %). Bruk prøveeksamen "
                   "hvis den er publisert på Canvas, ellers øvingsarkene. " + TECH2_MATERIAL)


# Fredager rett før TECH1- og TECH2-eksamen: ingen treningsblokk, så eksamensfaget ikke kuttes 2 t
FINAL_FRIDAY_NO_WORKOUT = {date(2026, 11, 27), date(2026, 12, 11)}


def final_day(d):
    wd = d.weekday()
    weekend = wd >= 5
    sal_end = "17:00" if weekend else ("19:00" if wd <= 3 else "17:30")
    workout = (not weekend) and d not in FINAL_FRIDAY_NO_WORKOUT
    sunday = wd == 6
    out = morning_final(d)

    if TECH2_HOME_EXAM[0] <= d <= TECH2_HOME_EXAM[1]:
        t, x = ("Grinde på SAL: TECH2 - hjemmeeksamen (gruppe)",
                "Alt annet er strøket disse dagene. Sjekk Canvas for nøyaktig start- og innleveringstid.")
        spec = ([X("06:00", "11:30", t, x, "TECH2"), ("11:30", "13:30", "W"),
                 X("13:30", sal_end, t, x, "TECH2")] if workout else [X("06:00", sal_end, t, x, "TECH2")])
        return out + sal(d, spec) + evening_final(d)

    if date(2026, 11, 26) <= d <= date(2026, 11, 30):
        n = (d - date(2026, 11, 26)).days + 1
        mock = X("06:00", "10:00", f"Grinde på SAL: TECH1 - prøveeksamen {n} (4 t, uten kalkulator)",
                 TECH1_MOCK_DESC, "TECH1")
        ct = (f"Grinde på SAL: TECH1 - rett prøveeksamen {n} og noter hull",
              "Rett mot løsningsforslaget. Skriv ned hvilke seksjoner du bommet på.")
        ft = ("Grinde på SAL: TECH1 - tett hull (seksjonene du bommet på)",
              "Tilbake til boka: teori, eksempler og oppgaver i seksjonene fra dagens prøveeksamen.")
        if workout:
            spec = [mock, X("10:00", "11:30", *ct, "TECH1"), ("11:30", "13:30", "W"),
                    X("13:30", sal_end, *ft, "TECH1")]
        else:
            spec = [mock, X("10:00", "12:00", *ct, "TECH1"), X("12:00", sal_end, *ft, "TECH1")]
        return out + sal(d, spec) + evening_final(d, clean=sunday, bud_rev=BUD1_REV.get(d))

    if date(2026, 12, 2) <= d <= date(2026, 12, 8):
        n = (d - date(2026, 12, 2)).days + 1
        head = [X("06:00", "09:00", f"Grinde på SAL: BUD1 - prøveeksamen {n} (3 t på tid, med Excel)",
                  BUD1_MOCK_DESC, "BUD1"),
                X("09:00", "11:00", f"Grinde på SAL: BUD1 - rett prøveeksamen {n} og noter hull",
                  "Rett mot løsningsforslaget. Skriv ned hvilke kapitler du bommet på.", "BUD1")]
        rt = ("Grinde på SAL: BUD1 - repeter kapitlene du bommet på",
              "Drury (9. utg.), pensum kap. 1-10, 12 og 14-16. BUD1 har 7 t hver dag denne uka.")
        if workout:   # BUD1 beholder 7 t; treningen tas fra "Gå igjennom der du henger etter"
            spec = head + [X("11:00", "11:30", *rt, "BUD1"), ("11:30", "13:30", "W"),
                           X("13:30", "15:00", *rt, "BUD1"), ("15:00", "15:30", "P"),
                           ("15:30", sal_end, "C")]
        else:
            spec = head + [X("11:00", "13:00", *rt, "BUD1"), ("13:00", "13:30", "P"),
                           ("13:30", sal_end, "C")]
        return out + sal(d, spec) + evening_final(d, clean=sunday)

    if date(2026, 12, 10) <= d <= date(2026, 12, 15):
        themes = {
            date(2026, 12, 10): ("uke 34-39", "Python basics, git, decisions, loops, functions, packages"),
            date(2026, 12, 11): ("uke 40-42", "git/VS Code & NumPy, intro to pandas, plotting"),
            date(2026, 12, 12): ("uke 43-45", "grouping and aggregation, concatenating and merging, AI week"),
        }
        if d in themes:
            wk, topics = themes[d]
            rep = (f"Grinde på SAL: TECH2 - repetisjon {wk}", f"{wk}: {topics}. " + TECH2_MATERIAL)
            ov = (f"Grinde på SAL: TECH2 - øvinger {wk}",
                  "Gjør øvingsarkene på nytt uten å se på løsningen først. " + TECH2_MATERIAL)
            if workout:
                spec = [X("06:00", "11:30", *rep, "TECH2"), ("11:30", "13:30", "W"),
                        X("13:30", sal_end, *ov, "TECH2")]
            else:
                spec = [X("06:00", "12:00", *rep, "TECH2"), X("12:00", sal_end, *ov, "TECH2")]
        else:
            n = (d - date(2026, 12, 13)).days + 1
            head = [X("06:00", "09:00", f"Grinde på SAL: TECH2 - prøveeksamen {n} (3 t på tid, med Python)",
                      TECH2_MOCK_DESC, "TECH2"),
                    X("09:00", "11:00", f"Grinde på SAL: TECH2 - rett prøveeksamen {n} og noter hull",
                      "Skriv ned hvilke uker/emner du bommet på.", "TECH2")]
            fh = ("Grinde på SAL: TECH2 - tett hull (emnene du bommet på)", TECH2_MATERIAL)
            if workout:
                spec = head + [X("11:00", "11:30", *fh, "TECH2"), ("11:30", "13:30", "W"),
                               X("13:30", sal_end, *fh, "TECH2")]
            else:
                spec = head + [X("11:00", sal_end, *fh, "TECH2")]
        return out + sal(d, spec) + evening_final(d, clean=sunday)

    raise ValueError(f"Ingen plan for {d}")


# --- eksamensdager ---------------------------------------------------------------
def exam_day(d):
    out = []
    if d == SOC1_EXAM:
        desc = ("Individuell muntlig eksamen, 30 min, bestått/ikke bestått. Eksamen holdes i uka "
                "16.-20.11 (SOC1-plan).")
        if not SOC1_EXAM_CONFIRMED:
            desc += ("\n\nPLASSHOLDER - OPPDATER NÅR DATOEN ER KLAR: Send eksakt dato og tid til "
                     "Claude, så flyttes eksamen og de 3 forberedelsesdagene (halve sal-tiden til "
                     "SOC1) automatisk. Endres i build_calendar.py: SOC1_EXAM, SOC1_EXAM_TIME og "
                     "SOC1_EXAM_CONFIRMED.")
        title = "EKSAMEN SOC1 - muntlig" + ("" if SOC1_EXAM_CONFIRMED else " (PLASSHOLDER)")
        if SOC1_EXAM_TIME:
            out.append(Ev(d, SOC1_EXAM_TIME[0], SOC1_EXAM_TIME[1], title, desc, kind="EXAM"))
        else:
            out.append(Ev(d, None, None, title, desc, kind="EXAM"))
        out += evening_normal(d)
        return out
    if d == TECH1_EXAM:
        out.append(Ev(d, None, None, "EKSAMEN TECH1 - 4 t skoleeksamen (tid ikke lagt inn)",
                      "Penn og papir, ingen kalkulator, svar på engelsk. Tillatt: én tospråklig "
                      "ordbok. Resten av dagen fri. Legg inn klokkeslett når du vet det.", kind="EXAM"))
    elif d == BUD1_EXAM:
        out.append(Ev(d, "09:00", "12:00", "EKSAMEN BUD1 - 3 t digital skoleeksamen",
                      "Excel, kalkulator og én tospråklig ordbok - ingen bøker eller notater. "
                      "Møt opp i god tid (BUD1-plan). Resten av dagen fri.", kind="EXAM"))
    elif d == TECH2_EXAM:
        out.append(Ev(d, None, None, "EKSAMEN TECH2 - 3 t digital med Python (tid ikke lagt inn)",
                      "70 % av karakteren. Legg inn klokkeslett når du vet det.", kind="EXAM"))
        return out
    out.append(Ev(d, "20:00", "20:15", "Leggetid", "I seng kl. 20:00.", kind="ROUTINE"))
    return out


# --- dag-dispatcher -------------------------------------------------------------
def build_day(d: date) -> list[Ev]:
    if d in (SOC1_EXAM, TECH1_EXAM, BUD1_EXAM, TECH2_EXAM):
        return exam_day(d)
    if d >= FINAL_START:
        return final_day(d)
    prep = soc1_prep_days()
    if d in prep:
        if d in SPECIAL:
            raise ValueError(f"SOC1-forberedelse kolliderer med spesialdag {d} - lag egen plan for dagen.")
        return prep_day(d, prep.index(d) + 1)
    weekend = d.weekday() >= 5
    spec = SPECIAL.get(d) or (weekend_spec(d) if weekend else weekday_spec(d))
    if weekend:
        return gym(d) + sal(d, spec) + evening_normal(d, clean=(d.weekday() == 6))
    return morning_normal(d) + sal(d, spec) + evening_normal(d)


def markers() -> list[Ev]:
    h1, h2 = TECH2_HOME_EXAM
    return [
        Ev(date(2026, 10, 30), None, None, "FRIST SOC1: Final term paper (gruppe) kl. 23:59",
           "Leveres på Canvas (SOC1-plan).", kind="MARK"),
        Ev(date(2026, 11, 4), None, None, "FRIST SOC1: Reflection note 2 kl. 23:59",
           "Individuell, leveres på Canvas (SOC1-plan). Skrives lørdag 31.10.", kind="MARK"),
        Ev(date(2026, 11, 12), None, None, "FRIST SOC1: Preparatory exam sheet kl. 23:59",
           "Bruk dokumentet på Canvas (SOC1-plan).", kind="MARK"),
        Ev(h1, None, None, "TECH2 hjemmeeksamen (30 %, gruppe)",
           "3-dagers hjemmeeksamen i grupper på 2-3 (TECH2 course outline). Mer info kommer på Canvas.",
           kind="MARK", days=(h2 - h1).days + 1),
        Ev(date(2026, 11, 27), None, None, "FRIST COM1: Porteføljen (EA1-EA3) kl. 12:00",
           "WISEflow. Planlagt levert lørdag 21.11.", kind="MARK"),
    ]


# ---------------------------------------------------------------------------
# INNHOLDSFORDELING (jevnt fordelt etter tid)
# ---------------------------------------------------------------------------
def dur(e: Ev) -> int:
    return mins(e.end) - mins(e.start)


def compact_sections(ids: list[str]) -> str:
    """['8.1','8.2','8.3','9.1'] -> '8.1-8.3, 9.1'"""
    parts, run = [], []
    for sid in ids:
        if run:
            pc, pn = run[-1].split(".")
            c, n = sid.split(".")
            if c == pc and int(n) == int(pn) + 1:
                run.append(sid)
                continue
            parts.append(run)
        run = [sid]
    if run:
        parts.append(run)
    return ", ".join(r[0] if len(r) == 1 else f"{r[0]}-{r[-1]}" for r in parts)


def allocate_tech1(blocks: list[Ev], a0: float = 0.0, a1: float | None = None):
    items = TECH1_SECTIONS
    W = sum(w for *_, w in items)
    a1 = W if a1 is None else a1
    T = sum(dur(b) for b in blocks)
    starts, acc = [], 0.0
    for *_, w in items:
        starts.append(acc)
        acc += w
    t = 0
    for b in blocks:
        a = a0 + (a1 - a0) * t / T
        t += dur(b)
        z = a0 + (a1 - a0) * t / T
        chosen = []
        for (sid, title, w), s0 in zip(items, starts):
            s1 = s0 + w
            overlap = min(z, s1) - max(a, s0)
            if overlap > 0.08 * w or (overlap > 0 and overlap >= 0.5 * (z - a)):
                chosen.append((sid, title, s0 < a - 0.08 * w))
        ids = [c[0] for c in chosen]
        if chosen and chosen[0][2]:
            label = f"{ids[0]} (forts.)" + (", " + compact_sections(ids[1:]) if len(ids) > 1 else "")
        else:
            label = compact_sections(ids)
        b.title = f"Grinde på SAL: TECH1 - {label}"
        lines = [f"{sid} {title}" + (" - fortsett der du slapp" if cont else "")
                 for sid, title, cont in chosen]
        b.desc = ("Sydsæter, Essential Mathematics for Economic Analysis:\n" + "\n".join(lines) +
                  "\n\nLes teorien, regn eksemplene og gjør oppgavene. Pensum fra TECH1 course "
                  "outline (ikke 9.4, ikke 12.10); for anvendelser trenger du bare se hvordan "
                  "verktøyet settes opp. Seksjonstitler fra Pearsons innholdsfortegnelse (6. utg.).")


def bud1_points():
    """Kuttpunkter (kumulative sider) ved hver unike seksjonsstart + kapittelslutt."""
    pts, segs, acc = [], [], 0
    for ch, title, p0, p1, secs in BUD1_CHAPTERS:
        # ikke kutt rett etter kapittelstarten (unngår biter som "s. 29-29")
        starts = sorted({p0} | {p for _, p in secs if p - p0 > 2})
        for p in starts:
            pts.append((acc + (p - p0), ch, p))
        segs.append((ch, title, p0, p1, acc, secs))
        acc += p1 - p0 + 1
    pts.append((acc, None, None))
    return pts, segs, acc


def allocate_bud1(blocks: list[Ev], a0: float = 0, a1: float | None = None):
    pts, segs, total = bud1_points()
    a1 = total if a1 is None else a1
    offsets = [p[0] for p in pts if a0 < p[0] <= a1]
    T = sum(dur(b) for b in blocks)
    t, prev = 0, a0
    for i, b in enumerate(blocks):
        t += dur(b)
        target = a0 + (a1 - a0) * t / T
        cand = [o for o in offsets if o > prev]
        cut = min(cand, key=lambda o: abs(o - target)) if i < len(blocks) - 1 else a1
        a, z = prev, cut
        prev = cut
        ranges, lines = [], []
        for ch, title, p0, p1, off, secs in segs:
            lo, hi = max(a, off), min(z, off + (p1 - p0 + 1))
            if hi <= lo:
                continue
            pa, pb = p0 + (lo - off), p0 + (hi - off) - 1
            ranges.append(f"kap. {ch}, s. {pa}" + (f"-{pb}" if pb > pa else ""))
            lines.append(f"Kap. {ch} {title}:")
            if pa == p0:
                lines.append(f"  s. {p0} (kapittelstart)")
            for name, p in secs:
                if pa <= p <= pb:
                    lines.append(f"  s. {p} {name}")
        b.title = "Grinde på SAL: BUD1 - " + " + ".join(ranges)
        b.desc = ("Drury, Management Accounting for Business (9. utg.)\n" + "\n".join(lines) +
                  "\n\nPensum: kap. 1-10, 12 og 14-16 (BUD1-plan). Alle kapitler skal være "
                  "gjennomgått innen 22.11.")


def allocate_tech2(blocks: list[Ev], a0: float = 0.0, a1: float | None = None):
    a1 = len(TECH2_TOPICS) if a1 is None else a1
    T = sum(dur(b) for b in blocks)
    t = 0
    for b in blocks:
        a = a0 + (a1 - a0) * t / T
        t += dur(b)
        z = a0 + (a1 - a0) * t / T
        chosen = []
        for i, (wk, topic) in enumerate(TECH2_TOPICS):
            overlap = min(z, i + 1) - max(a, i)
            if overlap > 0.08 or (overlap > 0 and overlap >= 0.5 * (z - a)):
                chosen.append((wk, topic, i < a - 0.08))
        parts = [f"uke {wk} (forts.)" if cont else f"uke {wk}: {topic}" for wk, topic, cont in chosen]
        b.title = "Grinde på SAL: TECH2 - " + " + ".join(parts)
        b.desc = ("\n".join(f"Uke {wk}: {topic}" + (" - fortsett der du slapp" if cont else "")
                            for wk, topic, cont in chosen) +
                  "\n\nGå gjennom notebooken og gjør øvingsarket for uka. " + TECH2_MATERIAL)


# ---------------------------------------------------------------------------
# ICS
# ---------------------------------------------------------------------------
VTIMEZONE = """BEGIN:VTIMEZONE
TZID:Europe/Oslo
X-LIC-LOCATION:Europe/Oslo
BEGIN:DAYLIGHT
TZOFFSETFROM:+0100
TZOFFSETTO:+0200
TZNAME:CEST
DTSTART:19700329T020000
RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU
END:DAYLIGHT
BEGIN:STANDARD
TZOFFSETFROM:+0200
TZOFFSETTO:+0100
TZNAME:CET
DTSTART:19701025T030000
RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU
END:STANDARD
END:VTIMEZONE"""


def typo(s: str) -> str:
    """Norsk typografi: tankestrek og intervallstrek (–). Stigs egen tittel beholdes som den er."""
    if s == "Våkne for faen - Grindetid":
        return s
    s = s.replace(" - ", " – ")
    s = re.sub(r"(?<=[\d.])-(?=\d)", "–", s)      # 4-28, 06:00-17:30, 23.-25.11
    s = re.sub(r"(?<=EA\d)-(?=EA)", "–", s)       # EA1-EA3
    return s


def esc(s: str) -> str:
    s = typo(s)
    return (s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
             .replace("\r\n", "\\n").replace("\n", "\\n"))


def fold(line: str) -> list[str]:
    out, cur, n = [], "", 0
    for ch in line:
        b = len(ch.encode("utf-8"))
        if n + b > 75:
            out.append(cur)
            cur, n = " " + ch, 1 + b
        else:
            cur += ch
            n += b
    out.append(cur)
    return out


def uid_for(e: Ev, seen: dict) -> str:
    key = f"{e.d:%Y%m%d}-{(e.start or 'heldag').replace(':', '')}-{e.kind}"
    if e.start is None:
        key += "-" + hashlib.sha1(e.title.encode()).hexdigest()[:8]
    seen[key] = seen.get(key, 0) + 1
    if seen[key] > 1:
        key += f"-{seen[key]}"
    return f"{key}@grindeplan-h26"


def to_ics(events: list[Ev]) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Grindeplan//H26//NO",
             "CALSCALE:GREGORIAN", "METHOD:PUBLISH", "X-WR-CALNAME:Grindeplan H26",
             "X-WR-TIMEZONE:Europe/Oslo",
             "X-WR-CALDESC:Studieplan 27.10.-16.12.2026. Genereres av build_calendar.py.",
             "REFRESH-INTERVAL;VALUE=DURATION:PT1H", "X-PUBLISHED-TTL:PT1H"]
    lines += VTIMEZONE.split("\n")
    seen: dict = {}
    for e in events:
        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:{uid_for(e, seen)}")
        lines.append(f"DTSTAMP:{stamp}")
        if e.start is None:
            lines.append(f"DTSTART;VALUE=DATE:{e.d:%Y%m%d}")
            lines.append(f"DTEND;VALUE=DATE:{e.d + timedelta(days=e.days):%Y%m%d}")
            lines.append("TRANSP:TRANSPARENT")
        else:
            s, z = e.start.replace(":", ""), e.end.replace(":", "")
            lines.append(f"DTSTART;TZID=Europe/Oslo:{e.d:%Y%m%d}T{s}00")
            lines.append(f"DTEND;TZID=Europe/Oslo:{e.d:%Y%m%d}T{z}00")
            lines.append("TRANSP:OPAQUE")
        lines.append(f"SUMMARY:{esc(e.title)}")
        if e.desc:
            lines.append(f"DESCRIPTION:{esc(e.desc)}")
        lines.append(f"CATEGORIES:{esc(e.kind)}")
        if e.alarm:
            lines += ["BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{esc(e.title)}",
                      "TRIGGER:PT0S", "END:VALARM"]
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    folded = []
    for ln in lines:
        folded += fold(ln)
    return "\r\n".join(folded) + "\r\n"


# ---------------------------------------------------------------------------
def build() -> list[Ev]:
    events: list[Ev] = []
    d = START
    while d <= END:
        events += build_day(d)
        d += timedelta(days=1)
    events += markers()

    def q(name):
        return sorted([e for e in events if e.queue == name], key=lambda e: (e.d, mins(e.start)))

    if any(e.d < TECH1_CHAPTERS_FROM for e in q("TECH1")):
        raise ValueError("TECH1-kapittelblokk før kapittelstart")
    totals = {"TECH1": sum(w for *_, w in TECH1_SECTIONS), "BUD1": bud1_points()[2],
              "TECH2": float(len(TECH2_TOPICS))}
    allocs = {"TECH1": allocate_tech1, "BUD1": allocate_bud1, "TECH2": allocate_tech2}
    for name in ("TECH1", "BUD1", "TECH2"):
        past = [b for b in q(name) if b.d < FREEZE_DATE]
        future = [b for b in q(name) if b.d >= FREEZE_DATE]
        if past:
            if not LOCKED[name]:
                raise ValueError(f"{name}: blokker før FREEZE_DATE, men LOCKED[{name!r}] er 0")
            allocs[name](past, 0, LOCKED[name])
        allocs[name](future, LOCKED[name], totals[name])
    events.sort(key=lambda e: (e.d, e.start is not None, mins(e.start) if e.start else 0))
    return events


if __name__ == "__main__":
    evs = build()
    out = sys.argv[1] if len(sys.argv) > 1 else "plan.ics"
    with open(out, "w", encoding="utf-8", newline="") as f:
        f.write(to_ics(evs))
    print(f"Skrev {len(evs)} hendelser til {out}")
