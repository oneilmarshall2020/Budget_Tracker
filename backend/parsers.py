"""Turn bank statement files into one common shape: ParsedRow.

Every parser returns (rows, problems):
  rows      -> list[ParsedRow], amounts signed the bank's way (negative = money out)
  problems  -> list[str] of things that didn't add up, shown in the import preview

Adding a bank later = write one parse_<bank>_pdf function and add it to PDF_PARSERS.
"""
import csv
import datetime
import io
import re
from dataclasses import dataclass

import pdfplumber

from models import TransactionType


@dataclass
class ParsedRow:
    date: datetime.date
    description: str
    amount: float                         # signed: negative = money out, positive = money in
    type: TransactionType | None = None   # only set when a CSV has a "type" column
    category_name: str | None = None      # only set when a CSV has a "category" column


def to_float(text: str) -> float:
    """'1,497.97' -> 1497.97"""
    return float(text.replace(",", "").strip())


# === CSV ===
# Columns: date,description,amount   (optional: type, category)
#   date      YYYY-MM-DD
#   amount    negative = money out, positive = money in (same as the bank)
def parse_csv(file_bytes: bytes):
    text = file_bytes.decode("utf-8-sig")  # -sig strips the invisible BOM Excel adds
    reader = csv.DictReader(io.StringIO(text))
    headers = {(name or "").strip().lower() for name in (reader.fieldnames or [])}
    if not {"date", "description", "amount"} <= headers:
        raise ValueError("The CSV needs date, description and amount columns")

    rows, problems = [], []
    for line_no, raw in enumerate(reader, start=2):  # line 1 is the header
        row = {
            key.strip().lower(): (value or "").strip()
            for key, value in raw.items()
            if key is not None and isinstance(value, (str, type(None)))
        }
        try:
            date = datetime.date.fromisoformat(row["date"])
            amount = to_float(row["amount"])
            description = row["description"]
            if not description or amount == 0:
                raise ValueError
        except (KeyError, ValueError):
            problems.append(f"Line {line_no}: skipped (couldn't read the date, description or amount)")
            continue

        tx_type = None
        if row.get("type"):
            try:
                tx_type = TransactionType(row["type"].lower())
            except ValueError:
                problems.append(f"Line {line_no}: unknown type '{row['type']}', guessed from the amount")

        rows.append(ParsedRow(date, description, amount, tx_type, row.get("category") or None))
    return rows, problems


# === NCB PDF ===
NCB_LINE = re.compile(
    r"^(\d{1,2}/[A-Za-z]{3})\s+(.+?)\s+(-?[\d,]+\.\d{2})\s+(-?[\d,]+\.\d{2})$"
)  # date, particulars, amount, balance
# The "BALANCE BROUGHT FORWARD" label is in a tiny font, so the PDF often splits it onto
# its own line and leaves "14/Sep 16,040.86" behind. A date followed by a single amount
# is never a transaction (those have two), so either form counts as brought forward.
NCB_BROUGHT_FORWARD = re.compile(
    r"^\d{1,2}/[A-Za-z]{3}\s+(?:BALANCE\s*BROUGHT\s*FORWARD\s+)?(-?[\d,]+\.\d{2})$",
    re.IGNORECASE,
)
NCB_STATEMENT_DATE = re.compile(r"STATEMENT\s*DATE\s*:?\s*(\d{2})-(\d{2})-(\d{4})", re.IGNORECASE)
NCB_FOOTER = re.compile(r"^(\d+)\s+([\d,]+\.\d{2})\s+(\d+)\s+([\d,]+(?:\.\d{2})?)(?:\s|$)")

MONTHS = {
    name: number
    for number, name in enumerate(
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
        start=1,
    )
}


def resolve_date(day_month: str, stmt_month: int, stmt_year: int) -> datetime.date:
    """'14/Sep' + statement month/year -> a real date.

    A row whose month is later than the statement's month belongs to the previous
    year (a January statement holding late-December rows). We look the month up
    ourselves because strptime without a year assumes 1900, which has no 29 Feb.
    """
    day_str, month_str = day_month.split("/")
    month = MONTHS[month_str.title()]
    year = stmt_year if month <= stmt_month else stmt_year - 1
    return datetime.date(year, month, int(day_str))


def open_pdf(file_bytes: bytes, password: str | None):
    try:
        pdf = pdfplumber.open(io.BytesIO(file_bytes), password=password or "")
        _ = pdf.pages[0]  # force it to actually read the file
        return pdf
    except Exception as exc:
        # pdfplumber wraps pdfminer's PDFPasswordIncorrect inside its own exception,
        # so look at the error and the errors it carries.
        details = f"{type(exc).__name__} {exc!r} {exc.__context__!r}".lower()
        if "password" in details:
            raise ValueError("This PDF is password-protected. Enter its password and try again.")
        raise ValueError("Couldn't read this PDF")


def parse_ncb_pdf(file_bytes: bytes, password: str | None = None):
    rows, problems = [], []
    with open_pdf(file_bytes, password) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]

    match = next((NCB_STATEMENT_DATE.search(text) for text in pages if NCB_STATEMENT_DATE.search(text)), None)
    if not match:
        raise ValueError("Couldn't find the STATEMENT DATE. Is this an NCB statement?")
    stmt_month, stmt_year = int(match.group(2)), int(match.group(3))

    previous_page_close = None
    for page_no, text in enumerate(pages, start=1):
        balance = None
        debits = credits = 0
        debit_total = credit_total = 0.0

        for raw_line in text.splitlines():
            line = raw_line.strip()

            brought_forward = NCB_BROUGHT_FORWARD.match(line)
            if brought_forward:
                balance = to_float(brought_forward.group(1))
                if previous_page_close is not None and abs(balance - previous_page_close) > 0.005:
                    problems.append(
                        f"Page {page_no} opens at {balance:,.2f} but the previous page closed at "
                        f"{previous_page_close:,.2f}. Is a page missing?"
                    )
                continue

            row = NCB_LINE.match(line)
            if row:
                day_month, particulars, amount_text, balance_text = row.groups()
                if day_month.split("/")[1].title() not in MONTHS:
                    continue
                amount, row_balance = to_float(amount_text), to_float(balance_text)

                # Checksum 1: each balance = previous balance + this amount.
                if balance is not None and abs(balance + amount - row_balance) > 0.005:
                    problems.append(
                        f"Page {page_no}, {day_month} '{particulars}': the running balance doesn't add up"
                    )
                balance = row_balance

                if amount < 0:
                    debits += 1
                    debit_total += -amount
                else:
                    credits += 1
                    credit_total += amount
                rows.append(
                    ParsedRow(resolve_date(day_month, stmt_month, stmt_year), particulars, amount)
                )
                continue

            # Checksum 2: the page footer's debit/credit counts and totals.
            footer = NCB_FOOTER.match(line)
            if footer and (debits or credits):
                f_debits, f_debit_total, f_credits, f_credit_total = footer.groups()
                if (
                    int(f_debits) != debits
                    or int(f_credits) != credits
                    or abs(to_float(f_debit_total) - debit_total) > 0.005
                    or abs(to_float(f_credit_total) - credit_total) > 0.005
                ):
                    problems.append(
                        f"Page {page_no}: totals don't match the footer "
                        f"(read {debits} debits / {debit_total:,.2f}, "
                        f"footer says {f_debits} / {f_debit_total})"
                    )

        if balance is not None:
            previous_page_close = balance

    if not rows:
        raise ValueError("No transactions found. Is this an NCB statement?")
    return rows, problems


# === Dispatch ===
PDF_PARSERS = {"NCB": parse_ncb_pdf}


def bank_key(bank_name: str) -> str:
    upper = bank_name.upper()
    if "NCB" in upper or "NATIONAL COMMERCIAL" in upper:
        return "NCB"
    return upper.strip()


def parse_statement(file_bytes: bytes, filename: str, bank_name: str, password: str | None = None):
    if b"%PDF" in file_bytes[:1024]:  # every PDF starts with %PDF, whatever its name
        parser = PDF_PARSERS.get(bank_key(bank_name))
        if parser is None:
            raise ValueError(f"There's no PDF reader for {bank_name} yet. Use a CSV for this account.")
        return parser(file_bytes, password)
    if filename.lower().endswith(".csv"):
        return parse_csv(file_bytes)
    raise ValueError("Upload a .csv or .pdf file")


# --- Classification ---
FEE_MARKERS = ("POS TX FEE", "GCT ON POS TX FEE")
BANK_FEES = "Bank Fees"


def classify(description: str, amount: float) -> tuple[TransactionType, str | None, str | None]:
    """(type, suggested category name, flag) from a raw description and signed amount."""
    upper = " ".join(description.upper().split())
    money_out = amount < 0

    if any(marker in upper for marker in FEE_MARKERS):
        return (TransactionType.expense if money_out else TransactionType.refund), BANK_FEES, None
    if upper.startswith("POSREV"):  
        return (TransactionType.refund if not money_out else TransactionType.expense), None, None

    direction = TransactionType.expense if money_out else TransactionType.income
    if "ELINK" in upper or "TRF-" in upper:  
        return direction, None, "review"
    return direction, None, None


def clean_description(description: str) -> str:
    cleaned = " ".join(description.split())
    upper = cleaned.upper()
    if upper.startswith("POS ") and not any(marker in upper for marker in FEE_MARKERS):
        cleaned = cleaned[4:]
    return cleaned


def merchant_key(description: str) -> str:
    """First two words, uppercased: 'CAMPUS FOODS & ESSENTIALSKINGSTON' -> 'CAMPUS FOODS'."""
    return " ".join(description.upper().split()[:2])
