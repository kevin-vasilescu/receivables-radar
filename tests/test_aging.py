from datetime import date
from typing import Any

from receivables_radar.aging import aging_table
from receivables_radar.ledger import compute_ledger

from .conftest import make_invoices, make_payments


def test_aging_fixture(fixture_result: Any) -> None:
    a = fixture_result.aging().set_index('bucket')
    # Current: INV-2 5000 + INV-6 4000 = 9000 (2 invoices); 31-60: INV-1 6000
    assert a.loc['Current', 'amount'] == 9000
    assert a.loc['Current', 'invoice_count'] == 2
    assert a.loc['31-60', 'amount'] == 6000
    assert a.loc['1-30', 'amount'] == 0
    assert a.loc['Current', 'share'] == 0.6
    assert a['amount'].sum() == 15000


def test_aging_nothing_outstanding_has_no_shares() -> None:
    inv = make_invoices([('A', 'C', '2025-01-01', '2025-02-01', 100.0)])
    pay = make_payments([('P', 'A', '2025-01-10', 100.0)])
    a = aging_table(compute_ledger(inv, pay, date(2025, 3, 1)))
    assert a['amount'].sum() == 0
    assert all(s is None for s in a['share'])
