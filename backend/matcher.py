"""Rule-based, explainable eligibility matching.

No LLM here on purpose: every verdict comes with the exact rule that produced
it, so a student (and a judge) can see *why* a scheme matched.

Conventions
-----------
* A scheme field that is missing / "all" / empty  -> rule not applicable (neutral).
* A profile field the student left blank          -> neutral + a caution ("we could not check X").
* A clear mismatch on a hard rule                 -> blocker. Verdict becomes "Not eligible".
* Score = matched weight / applicable weight * 100, forced to <= 25 when blocked.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Iterable

from dateutil import parser as dateparser

# --------------------------------------------------------------------------- #
# Normalisation
# --------------------------------------------------------------------------- #

GENDER_SYNONYMS = {
    "female": {"female", "f", "girl", "girls", "woman", "women", "girl child", "girl students", "ladies"},
    "male": {"male", "m", "boy", "boys", "man", "men", "boy students"},
    "all": {"all", "any", "both", "open", "open to all", "co-ed", "coed", "everyone", "na", "n/a", ""},
}

CATEGORY_SYNONYMS = {
    "SC": {"sc", "scheduled caste", "scheduled castes", "sc category", "dalit"},
    "ST": {"st", "scheduled tribe", "scheduled tribes", "st category", "tribal"},
    "OBC": {
        "obc", "obc-ncl", "obc (ncl)", "obc ncl", "other backward class", "other backward classes",
        "backward class", "backward classes", "bc", "ebc", "extremely backward class", "mbc", "dnt",
        "obc/ebc/dnt", "obc, ebc, dnt",
    },
    "EWS": {"ews", "economically weaker section", "economically weaker sections", "economically weaker"},
    "General": {"general", "gen", "ur", "unreserved", "open category", "oc", "forward"},
    "all": {"all", "any", "all categories", "open to all", "any category", "na", "n/a", ""},
}

STATE_SYNONYMS = {
    "Andhra Pradesh": {"ap", "andhra", "andhra pradesh"},
    "Arunachal Pradesh": {"arunachal", "arunachal pradesh"},
    "Assam": {"assam", "as"},
    "Bihar": {"bihar", "br"},
    "Chhattisgarh": {"chhattisgarh", "chattisgarh", "cg"},
    "Delhi": {"delhi", "new delhi", "nct of delhi", "nct delhi", "dl"},
    "Goa": {"goa", "ga"},
    "Gujarat": {"gujarat", "gj"},
    "Haryana": {"haryana", "hr"},
    "Himachal Pradesh": {"himachal", "himachal pradesh", "hp"},
    "Jammu and Kashmir": {"jammu and kashmir", "jammu & kashmir", "j&k", "jk", "jammu kashmir"},
    "Jharkhand": {"jharkhand", "jh"},
    "Karnataka": {"karnataka", "ka"},
    "Kerala": {"kerala", "kl"},
    "Madhya Pradesh": {"madhya pradesh", "mp"},
    "Maharashtra": {"maharashtra", "mh"},
    "Manipur": {"manipur", "mn"},
    "Meghalaya": {"meghalaya", "ml"},
    "Mizoram": {"mizoram", "mz"},
    "Nagaland": {"nagaland", "nl"},
    "Odisha": {"odisha", "orissa", "od", "or"},
    "Punjab": {"punjab", "pb"},
    "Rajasthan": {"rajasthan", "rj"},
    "Sikkim": {"sikkim", "sk"},
    "Tamil Nadu": {"tamil nadu", "tamilnadu", "tn"},
    "Telangana": {"telangana", "telangana state", "ts", "tg"},
    "Tripura": {"tripura", "tr"},
    "Uttar Pradesh": {"uttar pradesh", "up"},
    "Uttarakhand": {"uttarakhand", "uttaranchal", "uk", "ua"},
    "West Bengal": {"west bengal", "wb", "bengal"},
    "Puducherry": {"puducherry", "pondicherry", "py"},
    "Chandigarh": {"chandigarh", "ch"},
    "Ladakh": {"ladakh", "la"},
}

LEVEL_SYNONYMS = {
    "UG": {"ug", "undergraduate", "under graduate", "under-graduate", "graduation", "bachelor", "bachelors",
           "bachelor's", "degree", "b.tech", "btech", "be", "b.e.", "bsc", "b.sc", "ba", "b.a.", "bcom", "b.com",
           "mbbs", "bds", "llb", "b.pharm", "bba", "bca", "b.ed", "first degree"},
    "PG": {"pg", "postgraduate", "post graduate", "post-graduate", "master", "masters", "master's", "m.tech",
           "mtech", "msc", "m.sc", "ma", "m.a.", "mcom", "m.com", "mba", "md", "ms", "llm", "m.pharm", "mca"},
    "Diploma": {"diploma", "polytechnic", "iti", "certificate", "d.pharm"},
    "PhD": {"phd", "ph.d", "ph.d.", "doctoral", "doctorate", "research", "m.phil", "mphil"},
    "School": {"class 11", "class 12", "class xi", "class xii", "11th", "12th", "+2", "intermediate",
               "higher secondary", "senior secondary", "hsc", "school"},
    "all": {"all", "any", "post matric", "post-matric", "post metric", "all courses", "any course", "na", "n/a", ""},
}

STREAM_KEYWORDS = {
    "engineering": {"engineering", "technical", "technology", "b.tech", "btech", "b.e", "be", "m.tech", "cse",
                    "ece", "eee", "mechanical", "civil", "it", "computer", "polytechnic", "architecture", "aicte"},
    "medicine": {"medicine", "medical", "mbbs", "bds", "bams", "bhms", "nursing", "pharmacy", "b.pharm",
                 "physiotherapy", "paramedical", "ayurveda", "dental", "veterinary", "health"},
    "arts": {"arts", "humanities", "b.a", "ba", "m.a", "ma", "history", "political", "sociology", "languages",
             "literature", "fine arts", "social science", "psychology", "economics"},
    "commerce": {"commerce", "b.com", "bcom", "m.com", "accounting", "ca", "cs", "cma", "bba", "mba", "management",
                 "business", "finance"},
    "science": {"science", "b.sc", "bsc", "m.sc", "msc", "physics", "chemistry", "mathematics", "biology",
                "biotech", "bca", "mca", "agriculture"},
    "law": {"law", "llb", "ll.b", "llm", "legal", "ba llb"},
    "education": {"b.ed", "bed", "d.el.ed", "teacher training", "education"},
}


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().lower().strip(".")


def _lookup(table: dict[str, set[str]], value: Any, default: str | None = None) -> str | None:
    text = _clean(value)
    if text in ("", "none", "null", "not specified", "unspecified"):
        return default
    for canon, synonyms in table.items():
        if text == canon.lower() or text in synonyms:
            return canon
    # phrase match ("Scheduled Caste students", "Girls only", "state of Telangana")
    for canon, synonyms in table.items():
        for syn in sorted(synonyms, key=len, reverse=True):
            if len(syn) >= 4 and re.search(r"\b" + re.escape(syn) + r"\b", text):
                return canon
    return default


def normalize_gender(value: Any) -> str | None:
    """Girls/Women/Female -> 'female'; Boys/Men -> 'male'; All/Any -> 'all'; unknown -> None."""
    return _lookup(GENDER_SYNONYMS, value)


def normalize_category(value: Any) -> str | None:
    """Scheduled Caste -> 'SC', Other Backward Classes -> 'OBC', etc. unknown -> None."""
    return _lookup(CATEGORY_SYNONYMS, value)


def normalize_state(value: Any) -> str | None:
    """'TS' -> 'Telangana', 'UP' -> 'Uttar Pradesh', 'All India' -> 'all'."""
    text = _clean(value)
    if text in ("", "none"):
        return None
    if text in ("all", "any", "all india", "pan india", "india", "national", "all states", "central"):
        return "all"
    return _lookup(STATE_SYNONYMS, value)


def normalize_level(value: Any) -> str | None:
    return _lookup(LEVEL_SYNONYMS, value)


def normalize_list(values: Any, fn) -> list[str]:
    """Normalise a scheme-side list (or comma string). 'all' anywhere collapses to ['all']."""
    if values is None:
        return []
    if isinstance(values, str):
        values = re.split(r"[,/;]|\band\b|\bor\b", values)
    out: list[str] = []
    for v in values:
        n = fn(v)
        if n and n not in out:
            out.append(n)
    if "all" in out:
        return ["all"]
    return out


def course_stream(course: Any, branch: Any = "") -> str | None:
    text = f"{_clean(course)} {_clean(branch)}"
    tokens = set(re.findall(r"[a-z.]+", text))
    for stream, kws in STREAM_KEYWORDS.items():
        if tokens & kws:
            return stream
    return None


def normalize_streams(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        values = re.split(r"[,/;]|\band\b|\bor\b", values)
    out: list[str] = []
    for v in values:
        if _clean(v) in LEVEL_SYNONYMS["all"] | {"all streams", "any stream", "professional", "professional courses"}:
            return ["all"]
        s = course_stream(v)
        if s and s not in out:
            out.append(s)
    return out


# --------------------------------------------------------------------------- #
# Money and deadlines
# --------------------------------------------------------------------------- #

_LAKH = 100_000
_CRORE = 10_000_000


def parse_money(value: Any) -> int | None:
    """'₹2.5 lakh' -> 250000; '8,00,000' -> 800000; 'Rs 4.5 L p.a.' -> 450000; None if unknown."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).lower().replace(",", "")
    m = re.search(r"(\d+(?:\.\d+)?)\s*(lakhs?|lacs?|l\b|crores?|cr\b|k\b)?", text)
    if not m:
        return None
    num = float(m.group(1))
    unit = (m.group(2) or "").strip()
    if unit.startswith(("lakh", "lac")) or unit == "l":
        num *= _LAKH
    elif unit.startswith("cr"):
        num *= _CRORE
    elif unit == "k":
        num *= 1000
    return int(num)


def parse_percent(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    m = re.search(r"(\d+(?:\.\d+)?)", str(value))
    return float(m.group(1)) if m else None


ORDINAL_WORDS = {"first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3, "fourth": 4, "4th": 4,
                 "fifth": 5, "5th": 5, "final": 4}


def parse_years(value: Any) -> set[int]:
    """'1, 2' -> {1, 2}; 'First year (2nd year lateral)' -> {1, 2}; 'all years' -> set()."""
    low = _clean(value)
    if not low or low in ("all", "any", "all years", "any year"):
        return set()
    yrs = {int(x) for x in re.findall(r"\b([1-6])\b", low)}
    for word, n in ORDINAL_WORDS.items():
        if re.search(r"\b" + word + r"\b", low):
            yrs.add(n)
    return yrs


ROLLING_WORDS = ("rolling", "throughout the year", "open all year", "always open", "no deadline", "ongoing",
                 "year round", "year-round")
CLOSED_WORDS = ("closed", "expired", "over", "ended")


def parse_deadline(value: Any, today: date | None = None) -> dict[str, Any]:
    """Return {'date': date|None, 'rolling': bool, 'closed': bool, 'days_left': int|None, 'label': str}.

    Handles '31 Oct 2026', '2026-10-31', 'October 31, 2026', '31/10/2026', 'Last date: 31st October 2026',
    'Rolling', 'Closed', '' and garbage.
    """
    today = today or date.today()
    info: dict[str, Any] = {"date": None, "rolling": False, "closed": False, "days_left": None, "label": "Not stated"}
    if value is None:
        return info
    if isinstance(value, (date, datetime)):
        d = value.date() if isinstance(value, datetime) else value
    else:
        text = str(value).strip()
        low = text.lower()
        if not text:
            return info
        if any(w in low for w in ROLLING_WORDS):
            info.update(rolling=True, label="Rolling / open all year")
            return info
        if any(re.search(r"\b" + w + r"\b", low) for w in CLOSED_WORDS) and not re.search(r"\d{4}", low):
            info.update(closed=True, label="Closed")
            return info
        cleaned = re.sub(r"(?i)(last date|deadline|closes? on|apply by|till|by|:)", " ", text)
        cleaned = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", cleaned)
        try:
            d = dateparser.parse(cleaned, dayfirst=True, fuzzy=True).date()
        except (ValueError, OverflowError):
            return info
    info["date"] = d
    info["days_left"] = (d - today).days
    if info["days_left"] < 0:
        info["closed"] = True
        info["label"] = f"Closed on {d.strftime('%d %b %Y')}"
    elif info["days_left"] == 0:
        info["label"] = "Closes today"
    else:
        info["label"] = f"{d.strftime('%d %b %Y')} · closes in {info['days_left']} days"
    return info


# --------------------------------------------------------------------------- #
# Profile
# --------------------------------------------------------------------------- #

@dataclass
class Profile:
    name: str = ""
    state: str = ""                      # state where the student studies
    domicile_state: str = ""             # home state (often what state schemes check)
    gender: str = ""
    category: str = ""                   # General / SC / ST / OBC / EWS
    minority: bool | None = None         # religious minority community (separate from caste category)
    pwd: bool | None = None              # person with disability
    course_level: str = ""               # UG / PG / Diploma / PhD / School
    course: str = ""                     # B.Tech, MBBS, B.A., ...
    branch: str = ""                     # CSE, History, ...
    year: int | None = None
    marks_10: float | None = None
    marks_12: float | None = None
    marks_current: float | None = None   # last exam % or CGPA*10
    family_income: int | None = None     # annual, INR
    institution_type: str = ""           # government / private
    single_girl_child: bool | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Profile":
        def b(v):
            if v in (None, "", "unknown", "Unknown"):
                return None
            if isinstance(v, bool):
                return v
            return str(v).lower() in ("1", "true", "yes", "y", "on")

        def num(v, cast):
            if v in (None, ""):
                return None
            try:
                return cast(str(v).replace(",", "").replace("%", "").strip())
            except ValueError:
                return None

        return cls(
            name=str(data.get("name") or "").strip(),
            state=str(data.get("state") or "").strip(),
            domicile_state=str(data.get("domicile_state") or data.get("state") or "").strip(),
            gender=str(data.get("gender") or "").strip(),
            category=str(data.get("category") or "").strip(),
            minority=b(data.get("minority")),
            pwd=b(data.get("pwd")),
            course_level=str(data.get("course_level") or "").strip(),
            course=str(data.get("course") or "").strip(),
            branch=str(data.get("branch") or "").strip(),
            year=num(data.get("year"), int),
            marks_10=num(data.get("marks_10"), float),
            marks_12=num(data.get("marks_12"), float),
            marks_current=num(data.get("marks_current"), float),
            family_income=parse_money(data.get("family_income")),
            institution_type=str(data.get("institution_type") or "").strip().lower(),
            single_girl_child=b(data.get("single_girl_child")),
        )

    # normalised views
    @property
    def n_gender(self): return normalize_gender(self.gender)
    @property
    def n_category(self): return normalize_category(self.category)
    @property
    def n_state(self): return normalize_state(self.state)
    @property
    def n_domicile(self): return normalize_state(self.domicile_state) or self.n_state
    @property
    def n_level(self): return normalize_level(self.course_level) or normalize_level(self.course)
    @property
    def n_stream(self): return course_stream(self.course, self.branch)


# --------------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------------- #

WEIGHTS = {
    "state": 3, "gender": 3, "category": 3, "minority": 3, "pwd": 3, "level": 2, "stream": 2,
    "income": 3, "marks_12": 2, "marks_10": 1, "marks_current": 1, "institution": 1, "year": 1,
    "single_girl": 2,
}


@dataclass
class MatchResult:
    score: int
    verdict: str
    reasons: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    cautions: list[str] = field(default_factory=list)
    deadline: dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        d = dict(score=self.score, verdict=self.verdict, reasons=self.reasons, blockers=self.blockers,
                 cautions=self.cautions, deadline=dict(self.deadline))
        if d["deadline"].get("date"):
            d["deadline"]["date"] = d["deadline"]["date"].isoformat()
        return d


def _elig(scheme: dict[str, Any]) -> dict[str, Any]:
    e = scheme.get("eligibility") or {}
    # tolerate flat schemes (fields at top level)
    for k in ("states", "gender", "categories", "minority_only", "pwd_only", "course_levels", "streams",
              "income_limit", "min_marks_12", "min_marks_10", "min_marks_current", "institution_type",
              "single_girl_child_only", "years_of_study"):
        if k not in e and k in scheme:
            e[k] = scheme[k]
    return e


def score(profile: Profile, scheme: dict[str, Any], today: date | None = None) -> MatchResult:
    e = _elig(scheme)
    reasons, blockers, cautions = [], [], []
    got = 0.0
    applicable = 0.0

    def rule(key: str, ok: bool | None, reason: str, blocker: str, caution: str = ""):
        """ok=True -> reason, ok=False -> blocker, ok=None -> profile unknown -> caution."""
        nonlocal got, applicable
        w = WEIGHTS[key]
        applicable += w
        if ok is True:
            got += w
            reasons.append(reason)
        elif ok is False:
            blockers.append(blocker)
        else:
            got += w * 0.5
            if caution:
                cautions.append(caution)

    # --- state ------------------------------------------------------------
    states = normalize_list(e.get("states"), normalize_state)
    if states and states != ["all"]:
        home, study = profile.n_domicile, profile.n_state
        if home is None and study is None:
            rule("state", None, "", "", "Add your state to check this state-restricted scheme")
        elif home in states or study in states:
            which = home if home in states else study
            rule("state", True, f"Open to students of {which}", "")
        else:
            rule("state", False, "", f"Only for {', '.join(states)} students (you entered {home or study})")

    # --- gender -----------------------------------------------------------
    g = normalize_gender(e.get("gender"))
    if g and g != "all":
        pg = profile.n_gender
        if pg is None:
            rule("gender", None, "", "", f"Scheme is for {g} students — add your gender")
        else:
            rule("gender", pg == g, f"For {g} students — matches you", f"Only for {g} students")

    # --- category ---------------------------------------------------------
    cats = normalize_list(e.get("categories"), normalize_category)
    if cats and cats != ["all"]:
        pc = profile.n_category
        if pc is None:
            rule("category", None, "", "", f"Scheme is for {'/'.join(cats)} — add your category")
        else:
            rule("category", pc in cats, f"Category {pc} is eligible", f"Only for {'/'.join(cats)} category (you are {pc})")

    # --- minority / PwD / single girl child --------------------------------
    if e.get("minority_only"):
        rule("minority", profile.minority, "Minority community — matches you",
             "Only for notified minority communities", "Only for minority communities — tick the box if that applies")
    if e.get("pwd_only"):
        rule("pwd", profile.pwd, "For students with disabilities — matches you",
             "Only for students with a disability (40%+)", "Only for students with a disability — tick the box if that applies")
    if e.get("single_girl_child_only"):
        rule("single_girl", profile.single_girl_child, "Single girl child — matches you",
             "Only for a single girl child", "Only for a single girl child — tick the box if that applies")

    # --- course level / stream -------------------------------------------
    levels = normalize_list(e.get("course_levels"), normalize_level)
    if levels and levels != ["all"]:
        pl = profile.n_level
        if pl is None:
            rule("level", None, "", "", "Add your course level (UG/PG/Diploma)")
        else:
            rule("level", pl in levels, f"Covers {pl} courses", f"Only for {'/'.join(levels)} courses (you are {pl})")
    streams = normalize_streams(e.get("streams"))
    if streams and streams != ["all"]:
        ps = profile.n_stream
        if ps is None:
            rule("stream", None, "", "", f"Only for {'/'.join(streams)} courses — add your course")
        else:
            rule("stream", ps in streams, f"Covers {ps} courses", f"Only for {'/'.join(streams)} courses (you study {ps})")

    # --- income -----------------------------------------------------------
    limit = parse_money(e.get("income_limit"))
    if limit:
        inc = profile.family_income
        if inc is None:
            rule("income", None, "", "", f"Family income must be ≤ ₹{limit/_LAKH:g} lakh — add yours to confirm")
        else:
            rule("income", inc <= limit, f"Family income ₹{inc/_LAKH:g}L is within the ₹{limit/_LAKH:g}L limit",
                 f"Family income ₹{inc/_LAKH:g}L is above the ₹{limit/_LAKH:g}L limit")

    # --- marks ------------------------------------------------------------
    for key, label, pv in (("marks_12", "Class 12", profile.marks_12), ("marks_10", "Class 10", profile.marks_10),
                           ("marks_current", "last exam", profile.marks_current)):
        need = parse_percent(e.get("min_" + key))
        if need:
            if pv is None:
                rule(key, None, "", "", f"Needs {need:g}% in {label} — add your marks")
            else:
                rule(key, pv >= need, f"{label} marks {pv:g}% meet the {need:g}% minimum",
                     f"{label} marks {pv:g}% below the {need:g}% minimum")

    # --- institution type / year ------------------------------------------
    inst = _clean(e.get("institution_type"))
    if inst in ("government", "govt", "private"):
        inst = "government" if inst.startswith("gov") else "private"
        if not profile.institution_type:
            rule("institution", None, "", "", f"Only for {inst} institutions — add your institution type")
        else:
            rule("institution", profile.institution_type.startswith(inst[:3]),
                 f"Open to {inst} institutions", f"Only for {inst} institutions")
    years = e.get("years_of_study")
    if years:
        yrs = parse_years(years)
        if yrs:
            if profile.year is None:
                rule("year", None, "", "", f"Only for year {sorted(yrs)} students — add your year")
            else:
                rule("year", profile.year in yrs, f"Year {profile.year} students can apply",
                     f"Only for students in year {sorted(yrs)} (you are in year {profile.year})")

    # --- deadline (not an eligibility rule, but drives sorting) ------------
    dl = parse_deadline(scheme.get("deadline"), today)
    if dl["closed"]:
        cautions.append("Deadline has passed — watch for the next cycle")
    elif dl["days_left"] is not None and dl["days_left"] <= 14:
        cautions.append(f"Closing soon — only {dl['days_left']} days left")

    if scheme.get("sample"):
        cautions.append("Sample data — verify every detail on the official portal")
    elif scheme.get("source_url"):
        cautions.append("Extracted by the agent — verify on the official portal before applying")

    # --- verdict ----------------------------------------------------------
    if applicable == 0:
        pct = 50
        cautions.insert(0, "No eligibility rules found on the page — read the portal carefully")
    else:
        pct = round(100 * got / applicable)
    if blockers:
        verdict = "Not eligible"
        pct = min(pct, 25)
    elif pct >= 75 and not any("add your" in c or "tick the box" in c for c in cautions):
        verdict = "Likely eligible"
    elif pct >= 50:
        verdict = "Possibly eligible"
    else:
        verdict = "Unlikely"
    return MatchResult(int(pct), verdict, reasons, blockers, cautions, dl)


VERDICT_ORDER = {"Likely eligible": 0, "Possibly eligible": 1, "Unlikely": 2, "Not eligible": 3}


def rank(profile: Profile, schemes: Iterable[dict[str, Any]], today: date | None = None) -> list[dict[str, Any]]:
    """Score every scheme, attach the match, sort: open first, then verdict, then score, then soonest deadline."""
    out = []
    for s in schemes:
        m = score(profile, s, today)
        item = dict(s)
        item["match"] = m.to_dict()
        out.append(item)

    def key(item):
        m = item["match"]
        dl = m["deadline"]
        days = dl.get("days_left")
        return (
            1 if dl.get("closed") else 0,                   # closed schemes last
            VERDICT_ORDER.get(m["verdict"], 9),
            -m["score"],
            days if days is not None else 10_000,           # soonest deadline first
        )

    out.sort(key=key)
    return out


# --------------------------------------------------------------------------- #
# Document checklist
# --------------------------------------------------------------------------- #

DOC_SYNONYMS = [
    ("Aadhaar card", ("aadhaar", "aadhar", "uid")),
    ("Income certificate", ("income certificate", "income proof", "salary certificate", "income")),
    ("Caste / category certificate", ("caste", "category certificate", "community certificate", "sc/st", "obc certificate")),
    ("Bank passbook / account details", ("bank", "passbook", "ifsc", "account")),
    ("Domicile / residence certificate", ("domicile", "residence", "nativity", "bonafide resident")),
    ("Class 10 marksheet", ("10th", "class 10", "ssc", "matric", "x marksheet", "class x")),
    ("Class 12 marksheet", ("12th", "class 12", "hsc", "intermediate", "xii", "class xii", "+2")),
    ("Previous year marksheet", ("previous", "last exam", "latest marksheet", "semester", "marks memo")),
    ("Admission / fee receipt", ("fee receipt", "fee", "admission letter", "admission proof", "allotment")),
    ("Bonafide / institution verification", ("bonafide", "institution verification", "college certificate", "study certificate")),
    ("Disability certificate", ("disability", "pwd", "udid")),
    ("Minority community declaration", ("minority", "self-declaration of community", "community declaration")),
    ("Passport-size photograph", ("photo", "photograph")),
    ("Ration card", ("ration",)),
    ("Parent's declaration / affidavit", ("declaration", "affidavit", "undertaking")),
    ("Mobile number & email", ("mobile", "email", "phone")),
]


def canonical_document(raw: str) -> str:
    low = _clean(raw)
    for canon, keys in DOC_SYNONYMS:
        if any(k in low for k in keys):
            return canon
    return raw.strip().rstrip(".").capitalize()


def document_checklist(ranked: list[dict[str, Any]], verdicts=("Likely eligible", "Possibly eligible")) -> list[dict[str, Any]]:
    """De-duplicated documents across the student's likely/possibly-eligible, still-open schemes."""
    docs: dict[str, dict[str, Any]] = {}
    for item in ranked:
        m = item.get("match", {})
        if m.get("verdict") not in verdicts or m.get("deadline", {}).get("closed"):
            continue
        for raw in item.get("documents_required") or []:
            if not raw or not str(raw).strip():
                continue
            canon = canonical_document(str(raw))
            entry = docs.setdefault(canon, {"document": canon, "schemes": [], "count": 0})
            if item["name"] not in entry["schemes"]:
                entry["schemes"].append(item["name"])
                entry["count"] += 1
    return sorted(docs.values(), key=lambda d: (-d["count"], d["document"]))
