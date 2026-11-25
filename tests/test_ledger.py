from datetime import date
from typing import Any

import pandas as pd
import pytest

from receivables_radar.ledger import assign_bucket, compute_ledger

from .conftest import make_invoices, make_payments


@pytest.mark.parametrize(
    ('days', 'bucket'),
    [(0, 'Current'), (1, '1-30'), (30, '1-30'), (31, '31-60'), (60, '31-60'), (61, '61-90'), (90, '61-90'), (91, '90+'), (400, '90+')],
)
def test_bucket_boundaries(days: int, bucket: str) -> None:
    assert assign_bucket(days) == bucket


def test_worked_example(worked: Any) -> None:
    inv, pay, as_of = worked
    row = compute_ledger(inv, pay, as_of).iloc[0]
    # outstanding = 10000 - 4000 = 6000; 2025-03-01 -> 2025-04-15 = 31 + 14 = 45 days
    assert row['outstanding'] == 6000
    assert row['days_past_due'] == 45
    assert row['bucket'] == '31-60'
    assert row['status'] == 'OVERDUE'
    assert bool(row['partially_paid']) is True


def test_vectorised_bucket_matches_scalar() -> None:
    inv = make_invoices([(f'I{d}', 'C', '2024-01-01', '2024-01-02', 10.0) for d in (0, 1, 30, 31, 60, 61, 90, 91)])
    for n, d in enumerate((0, 1, 30, 31, 60, 61, 90, 91)):
        inv.loc[n, 'due_date'] = pd.Timestamp('2025-01-01') - pd.Timedelta(days=d)
    led = compute_ledger(inv, make_payments([]), date(2025, 1, 1))
    for r in led.itertuples():
        assert r.bucket == assign_bucket(int(r.days_past_due))


def test_open_not_due_and_due_on_as_of() -> None:
    inv = make_invoices([('A', 'C', '2025-01-01', '2025-02-01', 100.0), ('B', 'C', '2025-01-01', '2025-03-01', 100.0)])
    led = compute_ledger(inv, make_payments([]), date(2025, 2, 1))
    assert list(led['bucket']) == ['Current', 'Current']
    assert list(led['status']) == ['OPEN', 'OPEN']
    assert list(led['days_past_due']) == [0, 0]


def test_partial_not_overdue_is_partial() -> None:
    inv = make_invoices([('A', 'C', '2025-01-01', '2025-03-01', 100.0)])
    pay = make_payments([('P', 'A', '2025-01-10', 30.0)])
    row = compute_ledger(inv, pay, date(2025, 2, 1)).iloc[0]
    assert row['status'] == 'PARTIAL'
    assert row['outstanding'] == 70


def test_overpayment_goes_to_credit_balance() -> None:
    inv = make_invoices([('A', 'C', '2025-01-01', '2025-02-01', 100.0)])
    pay = make_payments([('P', 'A', '2025-01-10', 130.0)])
    row = compute_ledger(inv, pay, date(2025, 2, 15)).iloc[0]
    assert row['outstanding'] == 0
    assert row['credit_balance'] == 30
    assert row['status'] == 'PAID'
    assert row['days_past_due'] == 0


def test_payment_on_as_of_counts_and_later_ignored() -> None:
    inv = make_invoices([('A', 'C', '2025-01-01', '2025-02-01', 100.0)])
    pay = make_payments([('P1', 'A', '2025-02-10', 60.0), ('P2', 'A', '2025-02-11', 40.0)])
    row = compute_ledger(inv, pay, date(2025, 2, 10)).iloc[0]
    assert row['paid'] == 60
    assert row['outstanding'] == 40


def test_invoices_after_as_of_ignored() -> None:
    inv = make_invoices([('A', 'C', '2025-01-01', '2025-02-01', 100.0), ('B', 'C', '2025-03-01', '2025-04-01', 50.0)])
    led = compute_ledger(inv, make_payments([]), date(2025, 2, 1))
    assert list(led['invoice_id']) == ['A']


def test_settle_date_is_payment_reaching_amount() -> None:
    inv = make_invoices([('A', 'C', '2025-01-01', '2025-02-01', 100.0)])
    pay = make_payments([('P2', 'A', '2025-02-20', 40.0), ('P1', 'A', '2025-02-05', 30.0), ('P3', 'A', '2025-03-01', 30.0)])
    row = compute_ledger(inv, pay, date(2025, 4, 1)).iloc[0]
    # cumulative 30 (02-05), 70 (02-20), 100 (03-01)
    assert row['settle_date'] == pd.Timestamp('2025-03-01')


def test_paid_exactly_on_due_date_has_zero_days_late() -> None:
    inv = make_invoices([('A', 'C', '2025-01-01', '2025-02-01', 100.0)])
    pay = make_payments([('P', 'A', '2025-02-01', 100.0)])
    row = compute_ledger(inv, pay, date(2025, 3, 1)).iloc[0]
    assert (row['settle_date'] - row['due_date']).days == 0


def test_zero_payments_file() -> None:
    inv = make_invoices([('A', 'C', '2025-01-01', '2025-02-01', 100.0)])
    row = compute_ledger(inv, make_payments([]), date(2025, 3, 1)).iloc[0]
    assert row['outstanding'] == 100
    assert pd.isna(row['settle_date'])
