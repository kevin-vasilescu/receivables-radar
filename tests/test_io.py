from pathlib import Path

from receivables_radar import load_invoices, load_payments
from receivables_radar.io import load_all

from .conftest import FIXTURES


def test_load_fixture_types() -> None:
    inv = load_invoices(FIXTURES / 'invoices.csv')
    assert str(inv['invoice_date'].dtype).startswith('datetime64')
    assert inv['amount'].dtype == float
    assert len(inv) == 6
    assert len(load_payments(FIXTURES / 'payments.csv')) == 4


def test_bom_and_whitespace(tmp_path: Path) -> None:
    p = tmp_path / 'i.csv'
    p.write_bytes(b'\xef\xbb\xbfinvoice_id,customer_id,invoice_date,due_date,amount\n A ,C,2025-01-01,2025-02-01,10\n')
    assert load_invoices(p).loc[0, 'invoice_id'] == 'A'


def test_load_all_returns_no_issues_for_fixture() -> None:
    _, _, issues = load_all(FIXTURES / 'invoices.csv', FIXTURES / 'payments.csv')
    assert issues == []
