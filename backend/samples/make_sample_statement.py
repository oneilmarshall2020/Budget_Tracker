"""Build samples/ncb_sample_statement.pdf: the made-up statement demo accounts import.

Everything in it is invented (merchants are well-known chains, amounts and dates are
made up), laid out like a real NCB statement so the app's NCB reader can read it.
It's built to show off the review screen:
  - most rows land in a category from the suggested keywords
  - POS Tx Fee / GCT rows are filed under Bank Fees
  - JUICI on Sep 21 (1,580) matches the lunch every demo has logged by hand
  - TRF-FROM / TRF-TO SAVINGS 9988 are transfers with the demo's NCB Savings account
  - a POSREV undoes the PriceSmart purchase, so it's a refund in Groceries
  - TRF-TO FRIEND and LOCAL VENDOR need you to decide

You only need this to change the sample. It needs reportlab (not in requirements.txt):
    pip install reportlab
    python samples/make_sample_statement.py
"""
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

OUT = Path(__file__).resolve().parent / "ncb_sample_statement.pdf"
OPENING_BALANCE = 24_318.40

FEE, GCT = ("POS Tx Fee", -10.30), ("GCT on POS Tx Fee", -1.54)


def card(day, merchant, amount, fee=FEE, gct=GCT):
    """A card purchase and the two small fees NCB adds after it."""
    return [(day, f"POS {merchant}", amount), (day, *fee), (day, *gct)]


PAGES = [
    [
        *card("01/Sep", "HI-LO FOOD STORES   LIGUANEA", -6_240.00),
        *card("02/Sep", "DIGICEL ONLINE TOPUP", -1_500.00),
        *card("04/Sep", "NETFLIX.COM          866-579-7172", -1_650.00, ("POS Tx Fee", -41.25), ("GCT on POS Tx Fee", -6.19)),
        *card("05/Sep", "TOTAL HALF WAY TREE  KINGSTON", -4_000.00),
        ("08/Sep", "ELink TRF-FROM SAVINGS 9988", 5_000.00),
        *card("10/Sep", "PRICESMART           KINGSTON", -3_450.00),
    ],
    [
        ("12/Sep", "POSREV", 3_450.00),
        *card("13/Sep", "KFC CONSTANT SPRING  KINGSTON", -1_890.00),
        ("15/Sep", "BILL PAYMENT JPS", -6_120.00),
        *card("16/Sep", "ISLAND GRILL HWT     KINGSTON", -1_350.00),
        ("17/Sep", "ELink TRF-TO FRIEND", -2_000.00),
        *card("18/Sep", "MEGAMART WATERLOO    KINGSTON", -5_780.00),
        *card("19/Sep", "LOCAL VENDOR         KINGSTON", -800.00),
        *card("21/Sep", "JUICI PATTIES HWT    KINGSTON", -1_580.00),
    ],
    [
        ("22/Sep", "BILL PAYMENT NWC", -2_300.00),
        *card("23/Sep", "FONTANA PHARMACY     KINGSTON", -2_150.00),
        ("25/Sep", "PAYROLL DEP EMPLOYER SALARY", 85_000.00),
        ("26/Sep", "ELink TRF-TO SAVINGS 9988", -15_000.00),
        *card("28/Sep", "SPOTIFY              STOCKHOLM", -1_100.00, ("POS Tx Fee", -27.50), ("GCT on POS Tx Fee", -4.13)),
    ],
]


def money(value: float) -> str:
    return f"{value:,.2f}"


def draw_page(c: canvas.Canvas, rows: list, balance: float, last: bool) -> float:
    width, height = letter
    c.setFont("Helvetica-Bold", 9)
    c.drawString(330, height - 50, "DATE OPENED:")
    c.drawString(330, height - 62, "STATEMENT DATE:")
    c.setFont("Courier", 10)
    c.drawString(410, height - 50, "15-01-2020")
    c.drawString(420, height - 62, "30-09-2026")
    c.setFont("Helvetica-Bold", 9)
    c.drawString(330, height - 85, "CURRENCY:")
    c.drawString(330, height - 97, "TYPE OF A/C:")
    c.setFont("Courier", 10)
    c.drawString(385, height - 85, "JMD")
    c.drawString(395, height - 97, "CHEQUING")
    c.setFont("Helvetica-Bold", 8)
    c.drawString(60, height - 120, "SAMPLE STATEMENT FOR THE LEDGER DEMO. NOT A REAL ACCOUNT.")

    y = height - 200
    c.setFont("Helvetica-Bold", 7)
    c.drawString(40, y, "DATE")
    c.drawString(200, y, "PARTICULARS")
    c.drawString(400, y, "AMOUNT")
    c.drawString(520, y, "BALANCE")

    y -= 18
    c.setFont("Courier", 10)
    c.drawString(30, y, rows[0][0])
    c.setFont("Helvetica-Bold", 5.5)
    c.drawString(80, y, "BALANCE BROUGHT FORWARD")
    c.setFont("Courier", 10)
    c.drawRightString(580, y, money(balance))

    y -= 18
    debits, debit_total, credits, credit_total = 0, 0.0, 0, 0.0
    for date, particulars, amount in rows:
        balance = round(balance + amount, 2)
        if amount < 0:
            debits, debit_total = debits + 1, debit_total - amount
        else:
            credits, credit_total = credits + 1, credit_total + amount
        c.drawString(30, y, date)
        c.drawString(82, y, particulars)
        c.drawRightString(460, y, money(amount))
        c.drawRightString(580, y, money(balance))
        y -= 12.5

    y = 120
    c.setFont("Helvetica-Bold", 6)
    c.drawString(30, y, "NO. OF DEBITS")
    c.drawString(120, y, "TOTAL AMOUNT DEBITS")
    c.drawString(250, y, "NO OF")
    c.drawString(250, y - 6, "CREDITS")
    c.drawString(330, y, "TOTAL AMOUNT CREDITS")
    c.drawString(440, y, "SERVICE CHARGE & STAMP DUTY")
    c.drawString(540, y, "NO. OF")
    y -= 20
    c.setFont("Courier", 10)
    c.drawString(60, y, str(debits))
    c.drawRightString(220, y, money(debit_total))
    c.drawString(260, y, str(credits))
    c.drawRightString(410, y, money(credit_total) if credits else "0")
    c.drawString(490, y, "0")
    y -= 14
    if last:
        c.drawString(60, y, "01-10-2026 09:15:00")
    c.drawString(400, y, "END OF STATEMENT" if last else "CONTINUED")
    c.setFont("Helvetica", 6)
    c.drawString(180, 60, "OVERDRAWN AND DEBIT AMOUNTS ARE INDICATED BY A MINUS (-)")
    return balance


def build(path: Path = OUT) -> None:
    c = canvas.Canvas(str(path), pagesize=letter)
    c.setTitle("Ledger demo: sample NCB statement (made up)")
    balance = OPENING_BALANCE
    for index, rows in enumerate(PAGES):
        balance = draw_page(c, rows, balance, last=index == len(PAGES) - 1)
        c.showPage()
    c.save()


if __name__ == "__main__":
    build()
    print(f"built {OUT}")
