"""The NCB statement reader, tested on plain text laid out like the real statement.

PAGE_1 copies the shape of a real page 1: the header labels (STATEMENT DATE, ...) aren't
text in the PDF, only their values, and the opening balance comes out as "/ 16,831.83".
Names, the address and reference numbers are made up.
"""
import datetime

import pytest

from parsers import NCB_BROUGHT_FORWARD, account_number_endings, find_reference_date, parse_ncb_text

PAGE_1 = """HS 30-09/1
SOME STREET
1 SOME LANE 27-04-2018
KINGSTON 11 30-09-2026
ST ANDREW
JAMAICA
JMD
REGULAR SAVINGS
Account Status : Active (Customer Operating within the past 12 months).
/ 16,831.83
01/Sep POS JUICI PATTIES - UWI MONA -1,120.00 15,711.83
01/Sep UBER * PENDING help.uber.co -887.22 14,824.61
01/Sep POS Tx Fee -19.96 14,804.65
01/Sep GCT on POS Tx Fee -2.99 14,801.66
02/Sep POS AFRESH MARKETPLACE LIMITEKINGSTON -900.00 13,901.66
02/Sep MAVIS BANK COFFEE FACT MARVIS BANK -1,750.00 12,151.66
02/Sep POS Tx Fee -12.13 12,139.53
02/Sep GCT on POS Tx Fee -1.82 12,137.71
03/Sep POS 1628 ENTERPRISE-MOTHERS OKINGST -1,300.00 10,837.71
03/Sep POS Tx Fee -12.13 10,825.58
03/Sep GCT on POS Tx Fee -1.82 10,823.76
03/Sep POS Bowl and Spoon Lady Mus Kingston -2,050.00 8,773.76
03/Sep POS Tx Fee -10.30 8,763.46
03/Sep GCT on POS Tx Fee -1.54 8,761.92
03/Sep POS CAMPUS FOODS & ESSENTIALSKINGSTON -1,430.00 7,331.92
03/Sep POS Tx Fee -10.30 7,321.62
03/Sep GCT on POS Tx Fee -1.54 7,320.08
03/Sep Digicel Ding*100000001 18760000000 -5,000.00 2,320.08
03/Sep POS Tx Fee -112.50 2,207.58
03/Sep GCT on POS Tx Fee -16.88 2,190.70
04/Sep POS JUICI PATTIES - UWI MONA -1,120.00 1,070.70
04/Sep POS Tx Fee -10.30 1,060.40
04/Sep GCT on POS Tx Fee -1.54 1,058.86
07/Sep APPLE.COM/BILL 866-712-7753 -158.67 900.19
07/Sep POS Tx Fee -3.57 896.62
07/Sep GCT on POS Tx Fee -0.54 896.08
07/Sep MAVIS BANK COFFEE FACT MARVIS BANK -750.00 146.08
07/Sep POS Tx Fee -12.13 133.95
28 16,697.88 0 0 0
CONTINUED"""

PAGE_2 = """07/Sep BALANCE BROUGHT FORWARD 133.95
07/Sep GCT on POS Tx Fee -1.82 132.13
25/Sep PAYROLL DEP EMPLOYER SALARY 33,212.05 33,344.18
1 1.82 1 33,212.05 0
08-10-2026 17:32:22 END OF STATEMENT"""

TODAY = datetime.date(2026, 10, 15)


@pytest.mark.parametrize("line", [
    "/ 16,831.83",
    "14/Sep 16,040.86",
    "14/Sep BALANCE BROUGHT FORWARD 16,040.86",
    "BALANCE BROUGHT FORWARD 16,040.86",
])
def test_opening_balance_lines_are_recognized(line):
    assert NCB_BROUGHT_FORWARD.match(line)


def test_a_transaction_line_is_not_an_opening_balance():
    assert not NCB_BROUGHT_FORWARD.match("01/Sep POS Tx Fee -19.96 14,804.65")


def test_page_one_reads_cleanly():
    rows, problems = parse_ncb_text([PAGE_1], today=TODAY)
    assert len(rows) == 28
    assert problems == [], "every balance and the page total add up"
    assert all((r.date.year, r.date.month) == (2026, 9) for r in rows)


def test_descriptions_with_numbers_are_read_whole():
    rows, _ = parse_ncb_text([PAGE_1], today=TODAY)
    assert any(r.description == "Digicel Ding*100000001 18760000000" and r.amount == -5000 for r in rows)


def test_two_pages_chain_together():
    rows, problems = parse_ncb_text([PAGE_1, PAGE_2], today=TODAY)
    assert len(rows) == 30 and problems == []


def test_a_missing_page_is_noticed():
    bad_page_2 = PAGE_2.replace("133.95\n", "999.99\n", 1)
    _, problems = parse_ncb_text([PAGE_1, bad_page_2], today=TODAY)
    assert any("Is a page missing?" in p for p in problems)


# ---------------------------------------------------------------- the year
def test_the_year_comes_from_the_latest_date_not_the_date_opened():
    assert find_reference_date([PAGE_1], TODAY) == datetime.date(2026, 9, 30)


def test_future_dates_are_ignored():
    assert find_reference_date([PAGE_1 + "\nOffer valid until 31-12-2027"], TODAY) == datetime.date(2026, 9, 30)


def test_no_date_falls_back_to_today_with_a_warning():
    no_dates = PAGE_1.replace("27-04-2018", "").replace("30-09-2026", "")
    rows, problems = parse_ncb_text([no_dates], today=TODAY)
    assert len(rows) == 28 and rows[0].date == datetime.date(2026, 9, 1)
    assert any("Couldn't find the statement date" in p for p in problems)


def test_december_rows_on_a_january_statement_are_last_year():
    january = PAGE_1.replace("30-09-2026", "31-01-2027").replace("/Sep", "/Dec")
    rows, _ = parse_ncb_text([january], today=datetime.date(2027, 2, 3))
    assert rows[0].date == datetime.date(2026, 12, 1)


# ---------------------------------------------------------------- wrong-account check
WITH_ACCOUNT = PAGE_1.replace("SOME STREET", "SOME STREET\nMR TEST PERSON 354001234", 1)


def test_account_number_ending_is_found_ignoring_dates_and_row_numbers():
    assert account_number_endings([WITH_ACCOUNT]) == {"1234"}
    assert account_number_endings(["A/C 354-001-234\n/ 1.00"]) == {"1234"}


def test_right_account_no_warning():
    _, problems = parse_ncb_text([WITH_ACCOUNT], today=TODAY, last_four="1234")
    assert problems == []


def test_wrong_account_warns():
    _, problems = parse_ncb_text([WITH_ACCOUNT], today=TODAY, last_four="9999")
    assert len(problems) == 1 and "ending in 1234" in problems[0] and "9999" in problems[0]


def test_no_account_number_found_means_no_warning():
    _, problems = parse_ncb_text([PAGE_1], today=TODAY, last_four="9999")
    assert problems == []
