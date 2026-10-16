"""Automatic categorizing with keyword rules (no AI needed).

A rule is: keyword -> category. "JUICI" -> Food & Dining.
A rule matches when the keyword appears in the description at the START of a word:
  "JUICI" matches "POS JUICI PATTIES - UWI MONA"
  "FLOW"  does NOT match "OVERFLOW" (it's in the middle of a word)
  "CANTEEN" matches "MOTHER'S-UWI MAIN CANTEENKINGSTON" (NCB glues words together at
  the end, so we only check where the keyword starts, not where it ends)
When several rules match, the longest keyword wins: "AMAZON PRIME" beats "AMAZON".
"""
import re

from parsers import FEE_MARKERS


def normalize(text: str) -> str:
    """Uppercase and single spaces, so 'Juici  Patties' and 'JUICI PATTIES' compare equal."""
    return " ".join(text.upper().split())


def keyword_matches(keyword: str, description: str) -> bool:
    pattern = r"(?<![A-Z0-9])" + re.escape(normalize(keyword))
    return re.search(pattern, normalize(description)) is not None


def match_rule(description: str, rules: list):
    """The best rule for this description, or None. `rules` items need .keyword."""
    for rule in sorted(rules, key=lambda r: len(r.keyword), reverse=True):
        if keyword_matches(rule.keyword, description):
            return rule
    return None


# Words too common to identify a place on their own ("NEW HOPE FOODS" -> "NEW HOPE").
GENERIC_WORDS = {
    "THE", "NEW", "MY", "BIG", "OLD", "POS", "WWW", "ONLINE", "PAYMENT", "PURCHASE",
    "SOCIAL", "MAIN", "BEST", "TOP", "GOOD", "FIRST",
}
WORD = re.compile(r"[A-Z][A-Z'&.\-]*")


def suggest_keyword(description: str) -> str | None:
    """The keyword to remember when you categorize this row yourself.

    Usually the first word (JUICI, DIGICEL, APPLE.COM). Short or common first words
    get the second word too (NEW HOPE, BOWL AND). Numbers and reference codes are
    skipped, so 'Digicel Ding*125761897' gives 'DIGICEL'.
    """
    words = WORD.findall(normalize(description))
    words = [w.strip(".-'&") for w in words]
    words = [w for w in words if len(w) >= 2]
    if not words:
        return None
    first = words[0]
    # "UBER * PENDING", "PAYPAL *SHOP": the part after * is a reference, not the name
    if re.search(re.escape(first) + r"\s*\*", normalize(description)):
        return first
    if (len(first) < 5 or first in GENERIC_WORDS) and len(words) > 1:
        return f"{first} {words[1]}"
    return first


def learnable(description: str, flag: str | None = None) -> bool:
    """Rows we shouldn't learn keywords from: bank fees (already automatic) and
    transfers/ELink payments (the same words cover very different things)."""
    upper = normalize(description)
    if any(marker in upper for marker in FEE_MARKERS) or upper.startswith("POSREV"):
        return False
    if flag == "review" or "ELINK" in upper or "TRF-" in upper:
        return False
    return True


# ---------------------------------------------------------------- the suggested set
# (category name, kind, keywords). Added with one click on a fresh start; all editable.
SUGGESTED = [
    ("Food & Dining", "expense", [
        "JUICI", "KFC", "BURGER KING", "WENDY", "ISLAND GRILL", "TASTEE", "CANTEEN",
        "CAMPUS FOODS", "MOTHERS", "MOTHER'S", "BOWL AND SPOON", "DEVON HOUSE", "PIZZA",
        "DOMINO", "POPEYES", "SUBWAY", "STARBUCKS", "COFFEE", "CAFE", "RESTAURANT",
    ]),
    ("Groceries", "expense", [
        "HI-LO", "HILO", "MEGAMART", "MEGA MART", "PRICESMART", "SHOPPERS FAIR",
        "LOSHUSAN", "GENERAL FOODS", "SUPERMARKET",
    ]),
    ("Transport & Gas", "expense", [
        "UBER", "KNUTSFORD", "JUTC", "TOTAL", "TEXACO", "RUBIS", "PETCOM", "FESCO", "SHELL",
    ]),
    ("Phone & Internet", "expense", ["DIGICEL", "FLOW"]),
    ("Subscriptions", "expense", [
        "APPLE.COM", "NETFLIX", "SPOTIFY", "GOOGLE", "YOUTUBE", "DISNEY", "AMAZON PRIME",
        "PRIME VIDEO", "OPENAI", "ANTHROPIC",
    ]),
    ("Utilities", "expense", ["JPS", "JAMAICA PUBLIC SERVICE", "NWC", "NATIONAL WATER"]),
    ("Health", "expense", ["FONTANA", "PHARMACY", "DRUG", "MEDICAL", "CLINIC", "HOSPITAL"]),
    ("Shopping", "expense", ["AMAZON", "SHEIN", "TEMU", "COURTS"]),
    ("Bank Fees", "expense", []),  # fees are filed automatically; no keywords needed
    ("Salary", "income", ["PAYROLL", "SALARY"]),
]
