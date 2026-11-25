'''Invariant checks shared by the Hypothesis tests.'''

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from receivables_radar import Config, analyze

from .conftest import make_invoices, make_payments

BASE = date(2024, 1, 1)


def build(inv_specs: list[tuple[int, int, int, int]], pay_specs: list[tuple[int, int, int]]) -> tuple[pd.DataFrame, pd.DataFrame]:
    '''Inputs are (customer, invoice day, terms days, cents) and (invoice index, day, cents).'''
    inv = make_invoices(
        [
            (f'I{i}', f'C{c}', (BASE + timedelta(days=d)).isoformat(), (BASE + timedelta(days=d + t)).isoformat(), cents / 100)
            for i, (c, d, t, cents) in enumerate(inv_specs)
        ]
    )
    pay = make_payments(
        [(f'P{j}', f'I{i % len(inv_specs)}', (BASE + timedelta(days=d)).isoformat(), cents / 100) for j, (i, d, cents) in enumerate(pay_specs)]
    )
    return inv, pay


def check_all(inv: pd.DataFrame, pay: pd.DataFrame) -> None:
    res = analyze(inv, pay)
    led = res.ledger
    total = float(led['outstanding'].sum())
    assert (led['outstanding'] >= 0).all()
    assert abs(float(res.aging()['amount'].sum()) - total) < 0.01
    ev = res.invoice_forecast()
    assert ((ev['probability'] >= 0) & (ev['probability'] <= 1)).all()
    assert (ev['expected_cash'] <= ev['outstanding'] + 1e-9).all()
    for s in res.config.scenarios:
        scen = res.invoice_forecast(s.name)
        assert abs(float(res.forecast(s.name)['expected_cash'].sum()) - float(scen['expected_cash'].sum())) < 1e-6
        assert (scen['probability'] <= 1.0).all()
    c = res.customers()
    assert ((c['risk_score'] >= 0) & (c['risk_score'] <= 100)).all()
    assert res.to_json() == analyze(inv, pay).to_json()
    shuffled = analyze(inv.sample(frac=1, random_state=1).reset_index(drop=True), pay.sample(frac=1, random_state=2).reset_index(drop=True))
    assert shuffled.to_json() == res.to_json()


def check_extra_payment_never_increases(inv: pd.DataFrame, pay: pd.DataFrame, extra_cents: int) -> None:
    cfg = Config(as_of=BASE + timedelta(days=400))
    before = analyze(inv, pay, cfg)
    extra = make_payments([('PX', 'I0', (BASE + timedelta(days=10)).isoformat(), extra_cents / 100)])
    after = analyze(inv, pd.concat([pay, extra], ignore_index=True), cfg)
    b = before.ledger.set_index('invoice_id')['outstanding']
    a = after.ledger.set_index('invoice_id')['outstanding']
    assert (a <= b + 1e-9).all()
