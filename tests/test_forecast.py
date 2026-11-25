from datetime import date
from typing import Any

import pandas as pd
import pytest

from receivables_radar import Config, analyze
from receivables_radar.config import Scenario
from receivables_radar.forecast import expected_date, uncollectable_risk, weekly_forecast

from .conftest import make_invoices, make_payments

AS_OF = date(2025, 4, 15)


def test_worked_expected_date() -> None:
    # 2025-04-15 + 21 days (31-60 bucket) = 2025-05-06
    assert expected_date(date(2025, 3, 1), AS_OF, '31-60', 0) == date(2025, 5, 6)


def test_current_invoice_uses_typical_delay() -> None:
    # due 2025-04-20 + 10 = 2025-04-30
    assert expected_date(date(2025, 4, 20), AS_OF, 'Current', 10) == date(2025, 4, 30)


def test_early_payer_never_before_next_day() -> None:
    assert expected_date(date(2025, 4, 16), AS_OF, 'Current', -20) == date(2025, 4, 16)


def _events(offsets: list[int], cash: float = 100.0) -> pd.DataFrame:
    dates = [pd.Timestamp(AS_OF) + pd.Timedelta(days=o) for o in offsets]
    return pd.DataFrame({'expected_date': dates, 'expected_cash': [cash] * len(offsets)})


def test_week_boundaries() -> None:
    w = weekly_forecast(_events([1, 7, 8, 14, 15]), AS_OF, 13).set_index('week')
    # days 1-7 -> week 1, 8-14 -> week 2, 15-21 -> week 3
    assert w.loc['1', 'invoice_count'] == 2
    assert w.loc['2', 'invoice_count'] == 2
    assert w.loc['3', 'invoice_count'] == 1
    assert w.loc['1', 'week_start'] == date(2025, 4, 16)
    assert w.loc['1', 'week_end'] == date(2025, 4, 22)


def test_beyond_horizon_row_and_totals() -> None:
    w = weekly_forecast(_events([91, 92, 200]), AS_OF, 13)
    # day 91 is the last day of week 13; day 92 is beyond
    assert w.iloc[12]['invoice_count'] == 1
    assert w.iloc[-1]['week'] == 'beyond horizon'
    assert w.iloc[-1]['invoice_count'] == 2
    assert w['expected_cash'].sum() == pytest.approx(300.0)
    assert w.iloc[-1]['cumulative'] == pytest.approx(300.0)


def test_fixture_forecast(fixture_result: Any) -> None:
    ev = fixture_result.invoice_forecast().set_index('invoice_id')
    # INV-1: 6000 * 0.75 = 4500 on 2025-05-06; INV-2: 5000 * 0.98 = 4900 on 2025-04-19 + 10;
    # INV-6: 4000 * 0.98 = 3920 on 2025-04-20 + 10
    assert ev.loc['INV-1', 'expected_cash'] == pytest.approx(4500)
    assert ev.loc['INV-1', 'expected_date'] == pd.Timestamp('2025-05-06')
    assert ev.loc['INV-2', 'expected_date'] == pd.Timestamp('2025-04-29')
    assert ev.loc['INV-2', 'expected_cash'] == pytest.approx(4900)
    assert ev.loc['INV-6', 'expected_cash'] == pytest.approx(3920)
    w = fixture_result.forecast().set_index('week')
    # INV-2 is 14 days out (week 2); INV-1 21 days out and INV-6 15 days out (week 3)
    assert w.loc['2', 'expected_cash'] == pytest.approx(4900)
    assert w.loc['3', 'expected_cash'] == pytest.approx(8420)
    assert w['expected_cash'].sum() == pytest.approx(13320)


def test_uncollectable_risk(fixture_result: Any) -> None:
    # 6000*0.25 + 5000*0.02 + 4000*0.02 = 1500 + 100 + 80
    assert uncollectable_risk(fixture_result.ledger) == pytest.approx(1680)
    assert fixture_result.uncollectable_risk() == pytest.approx(1680)


def test_scenarios(fixture_tables: Any) -> None:
    res = analyze(*fixture_tables)
    pess = res.invoice_forecast('pessimistic').set_index('invoice_id')
    # INV-1: 2025-05-06 + 10 = 05-16; 6000 * 0.75 * 0.9 = 4050
    assert pess.loc['INV-1', 'expected_date'] == pd.Timestamp('2025-05-16')
    assert pess.loc['INV-1', 'expected_cash'] == pytest.approx(4050)
    opt = res.invoice_forecast('optimistic').set_index('invoice_id')
    # Current bucket: 0.98 * 1.05 = 1.029 capped at 1.0
    assert opt.loc['INV-2', 'probability'] == 1.0
    assert opt.loc['INV-1', 'probability'] == pytest.approx(0.7875)
    # INV-2 base 04-29, shifted -5 = 04-24
    assert opt.loc['INV-2', 'expected_date'] == pd.Timestamp('2025-04-24')


def test_optimistic_shift_clamped_to_next_day() -> None:
    inv = make_invoices([('A', 'C', '2025-04-16', '2025-04-17', 100.0), ('B', 'C', '2025-04-01', '2025-04-02', 10.0)])
    cfg = Config(as_of=AS_OF, scenarios=(Scenario('base', 0, 1.0), Scenario('opt', -5, 1.05)))
    ev = analyze(inv, make_payments([]), cfg).invoice_forecast('opt')
    assert ev['expected_date'].min() >= pd.Timestamp('2025-04-16')
