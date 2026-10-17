"""Build a fake NCB statement PDF that mimics the real layout.

Page 2 and page 4 are copied from the user's screenshots; pages 1 and 3 are
filler so the balances chain from page to page.
"""
import sys

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

PAGES = [
    {
        "bf": ("01/Sep", "16,955.43"),
        "rows": [
            ("03/Sep", "POS HI-LO FOOD STORES KINGSTON", "-4,200.00", "12,755.43"),
            ("03/Sep", "POS Tx Fee", "-10.30", "12,745.13"),
            ("03/Sep", "GCT on POS Tx Fee", "-1.54", "12,743.59"),
            ("08/Sep", "ELink TRF-FROM SAVINGS 9988", "5,000.00", "17,743.59"),
            ("13/Sep", "APPLE.COM/BILL           866-712-7753", "-1,661.20", "16,082.39"),
            ("13/Sep", "POS Tx Fee", "-41.53", "16,040.86"),
        ],
        "footer": ("5", "5,914.57", "1", "5,000.00"),
        "end": "CONTINUED",
    },
    {
        "bf": ("14/Sep", "16,040.86"),
        "rows": [
            ("14/Sep", "GCT on POS Tx Fee", "-6.23", "16,034.63"),
            ("14/Sep", "POSREV", "1,497.97", "17,532.60"),
            ("14/Sep", "POSREV", "37.45", "17,570.05"),
            ("14/Sep", "POSREV", "5.62", "17,575.67"),
            ("14/Sep", "POS CAMPUS FOODS & ESSENTIALSKINGSTON", "-1,260.00", "16,315.67"),
            ("14/Sep", "POS Tx Fee", "-10.30", "16,305.37"),
            ("14/Sep", "GCT on POS Tx Fee", "-1.54", "16,303.83"),
            ("15/Sep", "POS SOCIAL WELFARE CANTEEN   12 GIBRA", "-1,100.00", "15,203.83"),
            ("15/Sep", "POS Tx Fee", "-12.13", "15,191.70"),
            ("15/Sep", "GCT on POS Tx Fee", "-1.82", "15,189.88"),
            ("16/Sep", "POS MAVIS BANK COFFEE JABLUM KINGSTON", "-1,000.00", "14,189.88"),
            ("16/Sep", "POS Tx Fee", "-10.30", "14,179.58"),
            ("16/Sep", "GCT on POS Tx Fee", "-1.54", "14,178.04"),
            ("17/Sep", "ELink TRF-TO SOMEONE ELSE", "-2,000.00", "12,178.04"),
            ("17/Sep", "POS NEW HOPE FOODS            KINGSTON", "-1,500.00", "10,678.04"),
            ("17/Sep", "POS Tx Fee", "-10.30", "10,667.74"),
            ("17/Sep", "GCT on POS Tx Fee", "-1.54", "10,666.20"),
            ("18/Sep", "POS CAMPUS FOODS & ESSENTIALSKINGSTON", "-690.00", "9,976.20"),
            ("18/Sep", "POS Tx Fee", "-10.30", "9,965.90"),
            ("18/Sep", "GCT on POS Tx Fee", "-1.54", "9,964.36"),
            ("18/Sep", "POS MOTHER'S-UWI MAIN CANTEENKINGSTON", "-2,550.01", "7,414.35"),
            ("18/Sep", "POS Tx Fee", "-10.30", "7,404.05"),
            ("18/Sep", "GCT on POS Tx Fee", "-1.54", "7,402.51"),
            ("21/Sep", "POS JUICI PATTIES - UWI      MONA 119", "-1,580.00", "5,822.51"),
            ("21/Sep", "POS Tx Fee", "-10.30", "5,812.21"),
            ("21/Sep", "GCT on POS Tx Fee", "-1.54", "5,810.67"),
            ("21/Sep", "POS CAMPUS FOODS & ESSENTIALSKING 319", "-500.00", "5,310.67"),
            ("21/Sep", "POS Tx Fee", "-10.30", "5,300.37"),
        ],
        "footer": ("25", "12,281.53", "3", "1,541.04"),
        "end": "CONTINUED",
    },
    {
        "bf": ("21/Sep", "5,300.37"),
        "rows": [
            ("21/Sep", "GCT on POS Tx Fee", "-1.54", "5,298.83"),
            ("25/Sep", "PAYROLL DEP EMPLOYER SALARY", "33,212.05", "38,510.88"),
        ],
        "footer": ("1", "1.54", "1", "33,212.05"),
        "end": "CONTINUED",
    },
    {
        "bf": ("30/Sep", "38,510.88"),
        "rows": [
            ("30/Sep", "APPLE.COM/BILL           866-712-7753", "-1,915.65", "36,595.23"),
            ("30/Sep", "POS Tx Fee", "-47.89", "36,547.34"),
            ("30/Sep", "GCT on POS Tx Fee", "-7.18", "36,540.16"),
        ],
        "footer": ("3", "1,970.72", "0", "0"),
        "end": "END OF STATEMENT",
    },
]


def draw_page(c: canvas.Canvas, page: dict) -> None:
    width, height = letter
    # Header boxes
    c.setFont("Helvetica-Bold", 9)
    c.drawString(330, height - 50, "DATE OPENED:")
    c.drawString(330, height - 62, "STATEMENT DATE:")
    c.setFont("Courier", 10)
    c.drawString(410, height - 50, "27-04-2018")
    c.drawString(420, height - 62, "30-09-2026")
    c.setFont("Helvetica-Bold", 9)
    c.drawString(330, height - 85, "CURRENCY:")
    c.drawString(330, height - 97, "TYPE OF A/C:")
    c.setFont("Courier", 10)
    c.drawString(385, height - 85, "JMD")
    c.drawString(395, height - 97, "REGULAR SAVINGS")
    c.drawString(60, height - 120, "Account Status : Active (Customer Operating within the past 12 months).")

    # Table header
    y = height - 200
    c.setFont("Helvetica-Bold", 7)
    c.drawString(40, y, "DATE")
    c.drawString(200, y, "PARTICULARS")
    c.drawString(400, y, "AMOUNT")
    c.drawString(520, y, "BALANCE")

    # Balance brought forward: small font for the label, like the real one
    y -= 18
    c.setFont("Courier", 10)
    c.drawString(30, y, page["bf"][0])
    c.setFont("Helvetica-Bold", 5.5)
    c.drawString(80, y, "BALANCE BROUGHT FORWARD")
    c.setFont("Courier", 10)
    c.drawRightString(580, y, page["bf"][1])

    y -= 18
    for date, particulars, amount, balance in page["rows"]:
        c.drawString(30, y, date)
        c.drawString(82, y, particulars)
        c.drawRightString(460, y, amount)
        c.drawRightString(580, y, balance)
        y -= 12.5

    # Footer
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
    debits, debit_total, credits, credit_total = page["footer"]
    c.drawString(60, y, debits)
    c.drawRightString(220, y, debit_total)
    c.drawString(260, y, credits)
    c.drawRightString(410, y, credit_total)
    c.drawString(490, y, "0")
    y -= 14
    if page["end"] == "END OF STATEMENT":
        c.drawString(60, y, "08-10-2026 17:32:22")
    c.drawString(400, y, page["end"])
    c.setFont("Helvetica", 6)
    c.drawString(180, 60, "OVERDRAWN AND DEBIT AMOUNTS ARE INDICATED BY A MINUS (-)")


def build(path: str, password: str | None = None, tamper: bool = False) -> None:
    c = canvas.Canvas(path, pagesize=letter, encrypt=password)
    for index, page in enumerate(PAGES):
        if tamper and index == 1:
            page = {**page, "rows": list(page["rows"])}
            date, particulars, _amount, balance = page["rows"][4]
            page["rows"][4] = (date, particulars, "-1,206.00", balance)  # misread amount
        draw_page(c, page)
        c.showPage()
    c.save()


if __name__ == "__main__":
    out = sys.argv[1]
    build(f"{out}/ncb_sept.pdf")
    build(f"{out}/ncb_sept_locked.pdf", password="0427")
    build(f"{out}/ncb_sept_tampered.pdf", tamper=True)
    print("built")
