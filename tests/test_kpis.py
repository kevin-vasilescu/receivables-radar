from datetime import date
from typing import Any

import pytest

from receivables_radar.kpis import average_days_delinquent, best_possible_dso, cei, dso, top_customers


def test_worked_kpis() -> None:
    # DSO = 60000 / 180000 * 90 = 30; BPDSO = 40000 / 180000 * 90 = 20; ADD = 10
    assert dso(60000, 180000, 90) == pytest.approx(30.0)
    assert best_possible_dso(40000, 180000, 90) == pytest.approx(20.0)
    assert average_days_delinquent(30.0, 20.0) == pytest.approx(10.0)
    # CEI = (50000 + 180000 - 60000) / (50000 + 180000 - 40000) = 170000 / 190000
    assert cei(50000, 180000, 60000, 40000) == pytest.approx(89.4736842, rel=1e-6)


def test_division_by_zero_returns_none() -> None:
    assert dso(10, 0, 90) is None
    assert best_possible_dso(10, 0, 90) is None
    assert average_days_delinquent(None, 1.0) is None
    assert cei(0, 0, 0, 0) is None


def test_fixture_kpis(fixture_result: Any) -> None:
    assert fixture_result.as_of == date(2025, 4, 15)
    k = fixture_result.kpis()
    # outstanding: 6000 + 5000 + 4000 = 15000; overdue 6000; current 9000
    assert k['total_outstanding'] == 15000
    assert k['overdue_outstanding'] == 6000
    assert k['overdue_share'] == pytest.approx(0.4)
    # window (2025-01-15, 2025-04-15]: 10000 + 5000 + 3000 + 1000 + 4000 = 23000 (INV-3 on 01-10 excluded)
    assert k['billed_in_window'] == 23000
    # beginning AR at 2025-01-15: only INV-3 (2000) unpaid
    assert k['beginning_ar'] == 2000
    assert k['dso'] == pytest.approx(15000 / 23000 * 90)
    assert k['bpdso'] == pytest.approx(9000 / 23000 * 90)
    assert k['add'] == pytest.approx(6000 / 23000 * 90)
    # CEI = (2000 + 23000 - 15000) / (2000 + 23000 - 9000) = 10000 / 16000 = 62.5
    assert k['cei'] == pytest.approx(62.5)


def test_top_customers_share(fixture_result: Any) -> None:
    top = top_customers(fixture_result.ledger)
    # ACME 11000 / 15000, BETA 4000 / 15000
    assert list(top['customer_id']) == ['ACME', 'BETA']
    assert top.loc[0, 'share'] == pytest.approx(11000 / 15000)
