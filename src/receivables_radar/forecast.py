'''Cash forecast from expected collection dates.'''

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from receivables_radar.config import Config, Scenario

BEYOND = 'beyond horizon'


def expected_date(due_date: date, as_of: date, bucket: str, typical_delay_days: float, config: Config | None = None) -> date:
    '''Expected collection date of one open invoice (base case).

    Args:
        due_date: Invoice due date.
        as_of: Reporting date.
        bucket: Aging bucket of the invoice.
        typical_delay_days: Customer's typical payment delay.
        config: Settings (overdue wait days).

    Returns:
        For Current invoices max(as_of + 1, due_date + round(delay)); for overdue invoices
        as_of + overdue_wait_days[bucket].
    '''
    cfg = config or Config()
    if bucket == 'Current':
        return max(as_of + timedelta(days=1), due_date + timedelta(days=round(typical_delay_days)))
    return as_of + timedelta(days=cfg.overdue_wait_days[bucket])


def invoice_forecast(
    ledger: pd.DataFrame, behavior: pd.DataFrame, as_of: date, scenario: Scenario, config: Config | None = None
) -> pd.DataFrame:
    '''Expected cash per open invoice under a scenario.

    The scenario delay shift is applied to the base expected date and the result is
    never earlier than as_of + 1 day.

    Args:
        ledger: Ledger frame.
        behavior: Customer behaviour frame.
        as_of: Reporting date.
        scenario: Scenario to apply.
        config: Settings.

    Returns:
        Columns invoice_id, customer_id, outstanding, bucket, expected_date, probability, expected_cash.
    '''
    cfg = config or Config()
    open_ = ledger[ledger['outstanding'] > 0]
    delay = behavior.set_index('customer_id')['typical_delay_days']
    floor = as_of + timedelta(days=1)
    dates: list[date] = []
    for r in open_.itertuples():
        base = expected_date(r.due_date.date(), as_of, str(r.bucket), float(delay.get(r.customer_id, 0.0)), cfg)
        dates.append(max(floor, base + timedelta(days=scenario.delay_shift)))
    out = pd.DataFrame(
        {
            'invoice_id': open_['invoice_id'].to_numpy(),
            'customer_id': open_['customer_id'].to_numpy(),
            'outstanding': open_['outstanding'].to_numpy(),
            'bucket': open_['bucket'].to_numpy(),
            'expected_date': pd.to_datetime(pd.Series(dates, dtype='object')).to_numpy(),
        }
    )
    prob = out['bucket'].map(cfg.bucket_probabilities).astype(float)
    out['probability'] = (prob * scenario.probability_multiplier).clip(upper=1.0)
    out['expected_cash'] = out['outstanding'] * out['probability']
    return out.sort_values(['expected_date', 'invoice_id'], kind='stable').reset_index(drop=True)


def weekly_forecast(events: pd.DataFrame, as_of: date, weeks: int = 13) -> pd.DataFrame:
    '''Aggregate invoice forecasts into weekly rows.

    Week 1 covers as_of + 1 to as_of + 7. Later events fall in a final beyond-horizon row.

    Args:
        events: Output of invoice_forecast.
        as_of: Reporting date.
        weeks: Number of weekly rows.

    Returns:
        Columns week, week_start, week_end, expected_cash, cumulative, invoice_count.
    '''
    offset = (events['expected_date'] - pd.Timestamp(as_of)).dt.days
    wk = (offset - 1) // 7 + 1
    rows = []
    cum = 0.0
    for w in range(1, weeks + 1):
        sel = events[wk == w]
        cash = float(sel['expected_cash'].sum())
        cum += cash
        rows.append(
            {
                'week': str(w),
                'week_start': as_of + timedelta(days=7 * (w - 1) + 1),
                'week_end': as_of + timedelta(days=7 * w),
                'expected_cash': cash,
                'cumulative': cum,
                'invoice_count': len(sel),
            }
        )
    sel = events[wk > weeks]
    cash = float(sel['expected_cash'].sum())
    rows.append(
        {'week': BEYOND, 'week_start': None, 'week_end': None, 'expected_cash': cash, 'cumulative': cum + cash, 'invoice_count': len(sel)}
    )
    return pd.DataFrame(rows)


def uncollectable_risk(ledger: pd.DataFrame, config: Config | None = None) -> float:
    '''Expected uncollectable amount, sum(outstanding * (1 - probability)).

    Args:
        ledger: Ledger frame.
        config: Settings (bucket probabilities).

    Returns:
        The risk amount in currency units.
    '''
    cfg = config or Config()
    open_ = ledger[ledger['outstanding'] > 0]
    prob = open_['bucket'].map(cfg.bucket_probabilities).astype(float)
    return float((open_['outstanding'] * (1.0 - prob)).sum())
