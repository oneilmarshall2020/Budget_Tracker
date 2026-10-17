"""Matching statement rows to things that already exist.

Used by the import preview to answer, for each row:
  - Did I import this already (maybe under a new name, like a pending charge)?
  - Did I log this by hand already?
  - Is this a transfer between my own accounts?
  - If it's a refund, which purchase does it undo?
"""
import re
from dataclasses import dataclass
from datetime import date

from categorize import normalize
from models import TransactionType


@dataclass
class Draft:
    """One statement row while the preview works on it."""

    key: int
    date: date
    description: str
    amount: float  # always positive
    money_out: bool  # the statement's sign: True = money left the account
    type: TransactionType
    category_id: int | None = None
    source: str | None = None  # why it has its category: csv, fee, rule, history, reversal
    rule_keyword: str | None = None
    keyword: str | None = None  # what to learn if you categorize it yourself
    flag: str | None = None  # duplicate, possible, match, transfer, review
    note: str | None = None
    include: bool = True
    match_id: int | None = None  # your hand-logged entry that this row is
    pair_id: int | None = None  # the other side of a transfer between your accounts
    reverses: str | None = None  # "APPLE.COM/BILL (Sep 13)" for a refund
    imported_from: str | None = None  # file name of the import a duplicate came from

    @property
    def settled(self) -> bool:
        """Already explained by something that exists (so later checks skip it)."""
        return self.flag in ("duplicate", "possible", "match")


def same_money(a: float, b: float) -> bool:
    return abs(a - b) < 0.005


def pair_closest(drafts, candidates, can_pair, window_days):
    """Pair drafts with candidates, closest dates first.

    Going row by row and taking the first fit can pair the wrong two: a Sep 29 row
    grabs your Oct 1 entry and the real Oct 1 row is left over, so both months come
    out wrong. Instead: list every possible pair, sort by how many days apart they
    are, and take them in that order. Each draft and each candidate is used once.
    Returns {draft.key: candidate}.
    """
    options = []
    for draft in drafts:
        for candidate in candidates:
            gap = abs((candidate.date - draft.date).days)
            if gap <= window_days and can_pair(draft, candidate):
                options.append((gap, draft.date, draft.key, candidate))
    options.sort(key=lambda option: option[:3])

    paired, used = {}, set()
    for _gap, _date, key, candidate in options:
        if key in paired or candidate.id in used:
            continue
        paired[key] = candidate
        used.add(candidate.id)
    return paired


def first_word(description: str) -> str:
    words = re.findall(r"[A-Z0-9][A-Z0-9'&.\-]*", normalize(description))
    return words[0] if words else ""


def looks_renamed(description_a: str, description_b: str) -> bool:
    """Same purchase under a new name? Pending charges often change when they post:
    'UBER * PENDING help.uber.co' -> 'UBER *TRIP help.uber.com'. Same first word,
    or either says PENDING."""
    a, b = normalize(description_a), normalize(description_b)
    return first_word(a) == first_word(b) or "PENDING" in a or "PENDING" in b


def looks_like_transfer(description: str) -> bool:
    upper = normalize(description)
    return "ELINK" in upper or "TRF-" in upper or "TRANSFER" in upper


def mentions_account(description: str, last_four: str) -> bool:
    """Does the description name an account ending in these 4 digits?
    'ELink TRF-FROM SAVINGS 9988' -> 9988. Long numbers count if they END in the digits."""
    return any(run.endswith(last_four) for run in re.findall(r"\d{4,}", description))


def short_date(day: date) -> str:
    return f"{day.strftime('%b')} {day.day}"
