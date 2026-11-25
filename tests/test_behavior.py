from typing import Any

import pytest

from receivables_radar import analyze
from receivables_radar.behavior import risk_score, risk_tier

from .conftest import make_invoices, make_payments


def test_worked_risk_example() -> None:
    # 100 * (0.4*0.5 + 0.3*(30/60) + 0.2*(1-0.6) + 0.1*(45/90)) = 100 * (0.20 + 0.15 + 0.08 + 0.05) = 48
    score = risk_score(0.5, 30, 0.6, 45)
    assert score == pytest.approx(48.0)
    assert risk_tier(score) == 'MEDIUM'


def test_none_on_time_rate_is_half() -> None:
    assert risk_score(0, 0, None, 0) == pytest.approx(10.0)


def test_caps() -> None:
    assert risk_score(1, 600, 0.0, 900) == pytest.approx(100.0)


@pytest.mark.parametrize(
    ('score', 'tier'),
    [(0, 'LOW'), (24.99, 'LOW'), (25, 'MEDIUM'), (49.99, 'MEDIUM'), (50, 'HIGH'), (74.99, 'HIGH'), (75, 'SEVERE'), (100, 'SEVERE')],
)
def test_tier_boundaries(score: float, tier: str) -> None:
    assert risk_tier(score) == tier


def test_fixture_behavior(fixture_result: Any) -> None:
    c = fixture_result.customers().set_index('customer_id')
    # BETA settled days_late = 0, 10, 15 -> median 10; own history (3 >= min_history)
    assert c.loc['BETA', 'typical_delay_days'] == 10
    assert c.loc['BETA', 'history_quality'] == 'own'
    # amount-weighted late = (0*2000 + 10*3000 + 15*1000) / 6000 = 7.5; on_time = 1/3
    assert c.loc['BETA', 'avg_days_late'] == pytest.approx(7.5)
    assert c.loc['BETA', 'on_time_rate'] == pytest.approx(1 / 3)
    # score = 100 * (0 + 0.3*7.5/60 + 0.2*(2/3) + 0) = 17.0833
    assert c.loc['BETA', 'risk_score'] == pytest.approx(17.0833, abs=1e-3)
    assert c.loc['BETA', 'risk_tier'] == 'LOW'
    # ACME has no settled invoices: portfolio median 10 is used
    assert c.loc['ACME', 'history_quality'] == 'portfolio'
    assert c.loc['ACME', 'typical_delay_days'] == 10
    # score = 100 * (0.4*6/11 + 0 + 0.2*0.5 + 0.1*45/90) = 36.8182
    assert c.loc['ACME', 'risk_score'] == pytest.approx(36.8182, abs=1e-3)
    assert c.loc['ACME', 'risk_tier'] == 'MEDIUM'


def test_no_settled_invoices_anywhere() -> None:
    inv = make_invoices([('A', 'C', '2025-01-01', '2025-02-01', 100.0)])
    res = analyze(inv, make_payments([]))
    row = res.customers().iloc[0]
    assert row['history_quality'] == 'none'
    assert row['typical_delay_days'] == 0
    assert any('zero payment delay' in w for w in res.warnings)
