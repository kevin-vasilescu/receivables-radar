from typing import Any

import pytest

from receivables_radar import analyze
from receivables_radar.worklist import ACTIONS, priority_score

from .conftest import make_invoices, make_payments


def test_worked_priority() -> None:
    # 6000 * (1 + 45/30) = 6000 * 2.5
    assert priority_score(6000, 45) == pytest.approx(15000)


def test_fixture_worklist(fixture_result: Any) -> None:
    wl = fixture_result.worklist()
    assert list(wl['customer_id']) == ['ACME']
    row = wl.iloc[0]
    assert row['total_overdue'] == 6000
    assert row['oldest_days_past_due'] == 45
    assert row['invoice_count'] == 1
    assert row['priority_score'] == pytest.approx(15000)
    assert row['suggested_action'] == 'Phone call and firm reminder'
    assert row['risk_tier'] == 'MEDIUM'


def test_actions_cover_all_overdue_buckets() -> None:
    assert ACTIONS[1] == 'Friendly reminder'
    assert ACTIONS[3].startswith('Escalate')
    assert ACTIONS[4].startswith('Final notice')


def test_nothing_overdue_gives_empty_worklist() -> None:
    res = analyze(make_invoices([('A', 'C', '2025-01-01', '2025-03-01', 100.0)]), make_payments([]))
    assert res.worklist().empty
    assert res.dunning_drafts() == {}


def test_ties_broken_by_customer_id() -> None:
    inv = make_invoices(
        [('A', 'Z', '2025-01-01', '2025-01-10', 100.0), ('B', 'A', '2025-01-01', '2025-01-10', 100.0), ('C', 'M', '2025-03-01', '2025-03-05', 1.0)]
    )
    wl = analyze(inv, make_payments([])).worklist()
    assert list(wl['customer_id'])[:2] == ['A', 'Z']
