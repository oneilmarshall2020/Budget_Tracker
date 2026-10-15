"""See exactly what the NCB parser sees in a statement.

Usage (from the backend folder, venv active):
    python inspect_statement.py path/to/statement.pdf
    python inspect_statement.py path/to/statement.pdf YOUR_PDF_PASSWORD

Every extracted line is printed with a tag:
    ROW   a transaction the parser keeps
    BF    a "balance brought forward" line (used for the balance check)
    FOOT  a page-total line (used for the totals check)
    DATE  a line with a full date (dd-mm-yyyy); the latest one sets the year
          (blank) ignored
"""
import sys

from parsers import (
    FULL_DATE,
    account_number_endings,
    NCB_BROUGHT_FORWARD,
    NCB_FOOTER,
    NCB_LINE,
    find_reference_date,
    open_pdf,
    parse_ncb_text,
)


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        return
    path = sys.argv[1]
    password = sys.argv[2] if len(sys.argv) > 2 else None
    with open(path, "rb") as f:
        file_bytes = f.read()

    with open_pdf(file_bytes, password) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]

    for page_no, text in enumerate(pages, start=1):
        print(f"\n=================== page {page_no} ===================")
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if NCB_LINE.match(line):
                tag = "ROW "
            elif NCB_BROUGHT_FORWARD.match(line):
                tag = "BF  "
            elif NCB_FOOTER.match(line):
                tag = "FOOT"
            elif FULL_DATE.search(line):
                tag = "DATE"
            else:
                tag = "    "
            print(f"{tag} | {line}")

    endings = account_number_endings(pages)
    print(f"\nAccount number in the header ends in: {', '.join(sorted(endings)) or 'none found'}")
    reference = find_reference_date(pages)
    print(f"Year taken from: {reference.strftime('%d %b %Y') if reference else 'nothing found (uses today)'}")
    try:
        rows, problems = parse_ncb_text(pages)
    except ValueError as exc:
        print(f"Couldn't parse: {exc}")
        return
    if rows:
        print(f"Parsed {len(rows)} transactions, {rows[0].date:%d %b %Y} to {rows[-1].date:%d %b %Y}.")
    print("Problems:" if problems else "No problems: every balance and page total checks out.")
    for problem in problems:
        print(f"  - {problem}")


if __name__ == "__main__":
    main()
