from datetime import date
from pathlib import Path

import pytest

from receivables_radar import Config, DataError, analyze, load_invoices, load_payments
from receivables_radar.io import check_files, load_all

HDR = 'invoice_id,customer_id,invoice_date,due_date,amount\n'
PHDR = 'payment_id,invoice_id,payment_date,amount\n'


def write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding='utf-8')
    return p


def errors(tmp_path: Path, inv: str, pay: str = PHDR) -> list[str]:
    found = check_files(write(tmp_path, 'i.csv', inv), write(tmp_path, 'p.csv', pay))
    return [str(i) for i in found if i.severity == 'error']


def test_missing_column(tmp_path: Path) -> None:
    e = errors(tmp_path, 'invoice_id,customer_id,amount\nA,C,5\n')
    assert any("missing required column 'invoice_date'" in x for x in e)


def test_empty_invoices(tmp_path: Path) -> None:
    assert any('no data rows' in x for x in errors(tmp_path, HDR))


def test_bad_rows_have_row_numbers(tmp_path: Path) -> None:
    text = HDR + 'A,C,2025-01-01,2025-02-01,10\nA,C,2025-13-01,2025-02-01,10\nB,,2025-01-01,2024-12-01,-5\n'
    e = '\n'.join(errors(tmp_path, text))
    assert 'invoices row 3: unparsable invoice_date' in e
    assert "invoices row 3: duplicate invoice_id 'A'" in e
    assert 'invoices row 4: empty customer_id' in e
    assert 'invoices row 4: due_date is before invoice_date' in e
    assert 'invoices row 4: amount must be a positive number' in e


def test_non_numeric_amount(tmp_path: Path) -> None:
    e = errors(tmp_path, HDR + 'A,C,2025-01-01,2025-02-01,abc\n')
    assert any('row 2' in x and 'amount' in x for x in e)


def test_mixed_currencies(tmp_path: Path) -> None:
    text = 'invoice_id,customer_id,invoice_date,due_date,amount,currency\nA,C,2025-01-01,2025-02-01,10,USD\nB,C,2025-01-01,2025-02-01,10,EUR\n'
    assert any('mixed currencies' in x for x in errors(tmp_path, text))
    inv = load_invoices(write(tmp_path, 'i.csv', text), currency='eur')
    assert list(inv['invoice_id']) == ['B']


def test_payment_warnings(tmp_path: Path) -> None:
    inv = write(tmp_path, 'i.csv', HDR + 'A,C,2025-01-10,2025-02-01,100\n')
    pay = write(tmp_path, 'p.csv', PHDR + 'P1,A,2025-01-01,10\nP1,A,2025-02-01,10\nP2,ZZ,2025-02-01,10\n')
    _, p, issues = load_all(inv, pay)
    msgs = [str(i) for i in issues]
    assert len(p) == 1
    assert any('payments row 3: duplicate payment_id' in m for m in msgs)
    assert any("payments row 4: unknown invoice_id 'ZZ'" in m for m in msgs)
    assert any('payments row 2: payment dated before its invoice date' in m for m in msgs)
    assert all(i.severity == 'warning' for i in issues)


def test_payments_header_only_is_valid(tmp_path: Path) -> None:
    inv = write(tmp_path, 'i.csv', HDR + 'A,C,2025-01-10,2025-02-01,100\n')
    _, p, issues = load_all(inv, write(tmp_path, 'p.csv', PHDR))
    assert p.empty
    assert issues == []


def test_bad_payment_rows(tmp_path: Path) -> None:
    inv = write(tmp_path, 'i.csv', HDR + 'A,C,2025-01-10,2025-02-01,100\n')
    with pytest.raises(DataError) as exc:
        load_all(inv, write(tmp_path, 'p.csv', PHDR + 'P1,A,not-a-date,10\nP2,A,2025-02-01,0\n'))
    assert 'payments row 2' in str(exc.value)
    assert 'payments row 3' in str(exc.value)


def test_missing_and_empty_files(tmp_path: Path) -> None:
    with pytest.raises(DataError, match='file not found'):
        load_invoices(tmp_path / 'nope.csv')
    with pytest.raises(DataError, match='expected a header row'):
        load_payments(write(tmp_path, 'p.csv', ''))
    issues = check_files(tmp_path / 'nope.csv', tmp_path / 'nope2.csv')
    assert issues and issues[0].severity == 'error'


def test_customer_name_defaults_to_id(tmp_path: Path) -> None:
    inv = load_invoices(write(tmp_path, 'i.csv', HDR + 'A,C1,2025-01-10,2025-02-01,100\n'))
    assert inv.loc[0, 'customer_name'] == 'C1'


def test_amount_is_float(tmp_path: Path) -> None:
    inv = load_invoices(write(tmp_path, 'i.csv', HDR + 'A,C1,2025-01-10,2025-02-01,100\n'))
    assert inv['amount'].dtype == float


def test_analysis_warnings_for_future_rows(tmp_path: Path) -> None:
    inv = write(tmp_path, 'i.csv', HDR + 'A,C,2025-01-10,2025-02-01,100\nB,C,2025-06-01,2025-07-01,50\n')
    pay = write(tmp_path, 'p.csv', PHDR + 'P1,A,2025-03-01,10\nP2,A,2025-02-01,5\n')
    i, p, _ = load_all(inv, pay)
    res = analyze(i, p, Config(as_of=date(2025, 2, 15)))
    assert any('1 invoice(s) dated after' in w for w in res.warnings)
    assert any('1 payment(s) dated after' in w for w in res.warnings)
