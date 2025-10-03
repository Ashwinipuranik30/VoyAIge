import re
import datetime
from typing import Dict, Any, List, Optional
from google.adk.agents import Agent

# -----------------------------
# Keyword dictionaries & helpers
# -----------------------------

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12
}
MONTH_ABBR = {m[:3]: n for m, n in MONTHS.items()}  # jan, feb, ...

WORD_NUMS = {
    "one":1,"two":2,"three":3,"four":4,"five":5,"six":6,"seven":7,
    "eight":8,"nine":9,"ten":10,"eleven":11,"twelve":12,"thirteen":13,
    "fourteen":14,"fifteen":15,"sixteen":16,"seventeen":17,"eighteen":18,
    "nineteen":19,"twenty":20
}

INTEREST_KEYWORDS = {
    "art": ["art", "museum", "galleries", "gallery", "exhibition"],
    "food": ["food", "cuisine", "restaurant", "dining", "culinary", "street food"],
    "history": ["history", "historic", "heritage", "castle", "monument", "ruins"],
    "nature": ["nature", "hike", "hiking", "park", "outdoors", "mountain", "forest"],
    "adventure": ["adventure", "kayak", "ski", "surf", "dive", "zipline", "trek", "climb"],
    "nightlife": ["nightlife", "club", "bars", "bar", "pub", "party"],
    "shopping": ["shopping", "shop", "boutique", "mall", "market", "souvenir"],
    "family": ["family", "kids", "children", "zoo", "theme park"],
    "romance": ["romance", "honeymoon", "couple", "romantic"],
}

CURRENCY_SIGNS = {
    "$": "USD", "€": "EUR", "£": "GBP", "₹": "INR", "¥": "JPY", "₩": "KRW", "A$": "AUD", "C$": "CAD"
}
CURRENCY_WORDS = {
    "usd": "USD", "dollar": "USD", "dollars": "USD",
    "eur": "EUR", "euro": "EUR", "euros": "EUR",
    "gbp": "GBP", "pound": "GBP", "pounds": "GBP",
    "inr": "INR", "rupee": "INR", "rupees": "INR",
    "jpy": "JPY", "yen": "JPY",
    "cad": "CAD", "aud": "AUD",
}

# -----------------------------
# Parsing utilities
# -----------------------------

def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())

def _find_destination(text: str) -> Optional[str]:
    """
    Look for 'to <place>'/'trip to <place>'/'visit <place>'.
    """
    pat = r"(?:trip\s+to|travel\s+to|fly\s+to|to|visit)\s+([A-Z][\w\-\s]+?)(?=(?:\s+for|\s+with|\s+in|\s+on|\s+by|,|\.|$))"
    m = re.search(pat, text, flags=re.IGNORECASE)
    if m:
        return _clean(m.group(1)).title()
    return None

def _find_departure_city(text: str) -> Optional[str]:
    m = re.search(r"\bfrom\s+([A-Z][\w\-\s]+?)(?=(?:\s+to|\s+for|,|\.|$))", text, re.IGNORECASE)
    return _clean(m.group(1)).title() if m else None

def _find_month_or_window(text: str) -> Dict[str, Any]:
    """
    Detect date windows like:
      - 2025-10-05 to 2025-10-15
      - Oct 5th to 15th, 2025
      - October 5–15, 2025
      - Oct 5 to Oct 15, 2025
      - 5–15 Oct 2025
      - between Oct 5 and 15, 2025
      - in October / in Oct
    Returns keys among: start_date, end_date, month
    """
    out: Dict[str, Any] = {}
    T = text

    # 0) ISO range: 2025-10-05 to 2025-10-15
    iso = re.search(r"(\d{4}-\d{2}-\d{2})\s*(?:to|-|–|—)\s*(\d{4}-\d{2}-\d{2})", T)
    if iso:
        out["start_date"] = iso.group(1)
        out["end_date"] = iso.group(2)
        return out

    # Helpers
    def _mon_num(tok: str) -> Optional[int]:
        tok = tok.lower()
        return MONTHS.get(tok) or MONTH_ABBR.get(tok[:3])

    def _strip_ord(d: str) -> int:
        return int(re.sub(r"(st|nd|rd|th)$", "", d, flags=re.IGNORECASE))

    year_now = datetime.date.today().year

    # 1) "Oct 5th to 15th, 2025"  OR  "October 5-15, 2025"
    pat1 = re.compile(
        r"\b([A-Za-z]{3,9})\s+(\d{1,2})(?:st|nd|rd|th)?"
        r"\s*(?:,?\s*(\d{4}))?\s*"
        r"(?:to|-|–|—|through|thru|until|till|up to|up\-to)\s*"
        r"(?:(?:([A-Za-z]{3,9})\s+)?(\d{1,2})(?:st|nd|rd|th)?)"
        r"(?:\s*,?\s*(\d{4}))?",
        re.IGNORECASE
    )
    m = pat1.search(T)
    if m:
        smon, sd, sy, emon, ed, ey = m.groups()
        sm = _mon_num(smon)
        em = _mon_num(emon) if emon else sm
        if sm and em:
            sd_i = _strip_ord(sd)
            ed_i = _strip_ord(ed)
            sy_i = int(sy) if sy else year_now
            ey_i = int(ey) if ey else sy_i
            try:
                start = datetime.date(sy_i, sm, sd_i)
                end = datetime.date(ey_i, em, ed_i)
                out["start_date"] = start.isoformat()
                out["end_date"] = end.isoformat()
                return out
            except ValueError:
                pass  # keep looking

    # 2) "5th to 15th Oct 2025"  OR  "5–15 October, 2025"
    pat2 = re.compile(
        r"\b(\d{1,2})(?:st|nd|rd|th)?\s*"
        r"(?:to|-|–|—|through|thru|until|till|up to|up\-to)\s*"
        r"(\d{1,2})(?:st|nd|rd|th)?\s*"
        r"([A-Za-z]{3,9})"
        r"(?:\s*,?\s*(\d{4}))?",
        re.IGNORECASE
    )
    m = pat2.search(T)
    if m:
        sd, ed, mon, yr = m.groups()
        mm = _mon_num(mon)
        if mm:
            sd_i = _strip_ord(sd)
            ed_i = _strip_ord(ed)
            y = int(yr) if yr else year_now
            try:
                start = datetime.date(y, mm, sd_i)
                end = datetime.date(y, mm, ed_i)
                out["start_date"] = start.isoformat()
                out["end_date"] = end.isoformat()
                return out
            except ValueError:
                pass

    # 3) "between Oct 5 and 15, 2025"
    pat3 = re.compile(
        r"\bbetween\s+([A-Za-z]{3,9})\s+(\d{1,2})(?:st|nd|rd|th)?\s+"
        r"and\s+(\d{1,2})(?:st|nd|rd|th)?(?:\s*,?\s*(\d{4}))?",
        re.IGNORECASE
    )
    m = pat3.search(T)
    if m:
        mon, sd, ed, yr = m.groups()
        mm = _mon_num(mon)
        if mm:
            sd_i = _strip_ord(sd)
            ed_i = _strip_ord(ed)
            y = int(yr) if yr else year_now
            try:
                start = datetime.date(y, mm, sd_i)
                end = datetime.date(y, mm, ed_i)
                out["start_date"] = start.isoformat()
                out["end_date"] = end.isoformat()
                return out
            except ValueError:
                pass

    # 4) Plain month: "in Oct" / "in October"
    mon = re.search(r"\b(?:in\s+)?([A-Za-z]{3,9})\b", T)
    if mon:
        key = mon.group(1).lower()
        month_num = MONTHS.get(key) or MONTH_ABBR.get(key[:3])
        if month_num:
            out["month"] = month_num
            return out

    return out


def _find_duration_days(text: str) -> Optional[int]:
    # Digits: "4-day", "4 day(s)", "3 nights"
    m = re.search(r"\b(\d{1,3})\s*(?:-\s*)?(?:day|days|night|nights)\b", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    # Words: "four day(s)", "seven nights"
    for w, n in WORD_NUMS.items():
        if re.search(rf"\b{w}\s*(?:day|days|night|nights)\b", text, re.IGNORECASE):
            return n
    return None

def _find_travelers(text: str) -> Dict[str, Any]:
    out = {"adults": None, "children": 0}

    # "family of N"
    m = re.search(r"\bfamily\s+of\s+(\d+)\b", text, re.IGNORECASE)
    if m:
        total = int(m.group(1))
        out["adults"] = max(2, total - 2) if total >= 3 else total
        out["children"] = max(0, total - out["adults"])
        return out

    # "N adults/people"
    m = re.search(r"\b(\d+)\s+(?:adults?|people|persons?)\b", text, re.IGNORECASE)
    if m:
        out["adults"] = int(m.group(1))
        return out

    # Word numbers: "four people", "two adults"
    for w, n in WORD_NUMS.items():
        if re.search(rf"\b{w}\s+(?:people|persons|adults?)\b", text, re.IGNORECASE):
            out["adults"] = n
            return out

    # "for two/for 2"
    m = re.search(r"\bfor\s+(one|two|three|four|five|six|\d+)\b", text, re.IGNORECASE)
    if m:
        word = m.group(1).lower()
        out["adults"] = WORD_NUMS.get(word, int(word) if word.isdigit() else 2)
        return out

    # "couple" / "honeymoon"
    if re.search(r"\b(couple|honeymoon)\b", text, re.IGNORECASE):
        out["adults"] = 2
        return out

    return out

def _normalize_budget_number(num_str: str) -> int:
    s = num_str.lower().replace(",", "").replace(" ", "")
    if s.endswith("k"):
        s = s[:-1]
        try:
            return int(float(s) * 1000)
        except ValueError:
            return 0
    try:
        return int(float(s))
    except ValueError:
        return 0

def _find_budget(text: str) -> Dict[str, Any]:
    # Currency sign: "$3k", "€ 2,500"
    for sign, code in CURRENCY_SIGNS.items():
        pat = rf"(?:{re.escape(sign)})\s*([\d,.\s]*k?)"
        m = re.search(pat, text, re.IGNORECASE)
        if m and m.group(1).strip():
            amt = _normalize_budget_number(m.group(1))
            if amt:
                return {"amount": amt, "currency": code, "tag": None}

    # Currency words: "3000 euros", "2500 usd"
    m = re.search(
        r"\b(\d[\d,.\s]*k?)\s*(usd|eur|gbp|inr|jpy|cad|aud|dollars?|euros?|pounds?|rupees?|yen)\b",
        text,
        re.IGNORECASE,
    )
    if m:
        amt = _normalize_budget_number(m.group(1))
        cur = CURRENCY_WORDS.get(m.group(2).lower(), "USD")
        return {"amount": amt, "currency": cur, "tag": None}

    # Plain number after 'budget'
    m = re.search(r"\bbudget(?:\s+of|\s*[:=])?\s*(\d[\d,.\s]*k?)\b", text, re.IGNORECASE)
    if m:
        amt = _normalize_budget_number(m.group(1))
        if amt:
            return {"amount": amt, "currency": "USD", "tag": None}

    # Keyword-based bands
    if re.search(r"\bbudget[- ]?friendly|cheap|affordable|low[ -]?cost\b", text, re.IGNORECASE):
        return {"amount": None, "currency": None, "tag": "budget-friendly"}
    if re.search(r"\bluxury|luxurious|high[- ]?end|premium|5[- ]?star\b", text, re.IGNORECASE):
        return {"amount": None, "currency": None, "tag": "luxury"}
    if re.search(r"\bmid[- ]?range|moderate|standard\b", text, re.IGNORECASE):
        return {"amount": None, "currency": None, "tag": "mid-range"}

    return {"amount": None, "currency": None, "tag": None}

def _find_interests(text: str) -> List[str]:
    hits = set()
    for tag, words in INTEREST_KEYWORDS.items():
        for w in words:
            if re.search(rf"\b{re.escape(w)}\b", text, re.IGNORECASE):
                hits.add(tag)
                break
    return sorted(hits)

def _find_constraints(text: str) -> List[str]:
    constraints: List[str] = []
    for kw in ["must", "need", "avoid", "no ", "prefer", "nonstop", "non-stop"]:
        for m in re.finditer(rf"\b{kw}\b[^.,;]*", text, re.IGNORECASE):
            constraints.append(_clean(m.group(0)))
    # De-dup
    seen = set()
    out = []
    for c in constraints:
        if c.lower() not in seen:
            out.append(c)
            seen.add(c.lower())
    return out

# -----------------------------
# Main tool
# -----------------------------

def parse_trip_request(text: str) -> Dict[str, Any]:
    text = text.strip()
    destination = _find_destination(text)
    departure = _find_departure_city(text)
    window = _find_month_or_window(text)
    duration = _find_duration_days(text)
    travelers = _find_travelers(text)
    budget = _find_budget(text)
    interests = _find_interests(text)
    constraints = _find_constraints(text)

    result: Dict[str, Any] = {
        "destination": destination,
        "departure_city": departure,
        "month": window.get("month"),
        "start_date": window.get("start_date"),
        "end_date": window.get("end_date"),
        "duration_days": duration,
        "travelers": {
            "adults": travelers.get("adults"),
            "children": travelers.get("children", 0),
        },
        "budget": {
            "amount": budget.get("amount"),
            "currency": budget.get("currency"),
            "tag": budget.get("tag"),   # << include tag in output
        },
        "interests": interests,
        "constraints": constraints,
        "notes": text,
    }
    return {"status": "success", "spec": result}

# -----------------------------
# (Optional) health/ping tool
# -----------------------------

def ping(_: str = "ping") -> Dict[str, str]:
    return {"status": "ok", "message": "ui-agent-ready"}

# -----------------------------
# Root agent
# -----------------------------

root_agent = Agent(
    name="trip_ui_agent",
    model="gemini-2.5-flash",
    description="Parses a natural-language trip request into structured queries for downstream agents.",
    instruction=(
        "You are the user-facing UI agent. When the user describes a trip, call the tool "
        "`parse_trip_request` to extract a structured spec. Return ONLY the JSON spec unless "
        "the user asks for prose. Do NOT invent details; leave missing fields as null."
    ),
    tools=[parse_trip_request, ping],
)
