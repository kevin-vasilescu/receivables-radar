'''Customer payment behaviour and risk scoring.'''

from __future__ import annotations

import numpy as np
import pandas as pd

from receivables_radar.config import Config


def risk_score(overdue_share: float, avg_days_late: float, on_time_rate: float | None, oldest_days_past_due: float) -> float:
    '''Customer risk score from 0 to 100.

    A None on_time_rate is treated as 0.5.

    Args:
        overdue_share: Customer overdue outstanding over total outstanding.
        avg_days_late: Amount-weighted mean lateness of settled invoices.
        on_time_rate: Share of settled invoices paid on or before the due date.
        oldest_days_past_due: Oldest open overdue invoice, in days.

    Returns:
        The score, clamped to [0, 100].
    '''
    on_time = 0.5 if on_time_rate is None else on_time_rate
    score = 100.0 * (
        0.4 * overdue_share
        + 0.3 * min(avg_days_late / 60.0, 1.0)
        + 0.2 * (1.0 - on_time)
        + 0.1 * min(oldest_days_past_due / 90.0, 1.0)
    )
    return float(min(max(score, 0.0), 100.0))


def risk_tier(score: float) -> str:
    '''Map a risk score to a tier.

    Args:
        score: Risk score in [0, 100].

    Returns:
        LOW (<25), MEDIUM (<50), HIGH (<75) or SEVERE.
    '''
    if score < 25:
        return 'LOW'
    if score < 50:
        return 'MEDIUM'
    if score < 75:
        return 'HIGH'
    return 'SEVERE'


def customer_behavior(ledger: pd.DataFrame, config: Config | None = None) -> pd.DataFrame:
    '''Build per-customer behaviour metrics and risk scores.

    Args:
        ledger: Ledger frame from compute_ledger.
        config: Settings (min_history).

    Returns:
        One row per customer, sorted by customer_id, with outstanding, overdue_outstanding,
        oldest_days_past_due, settled_count, typical_delay_days, history_quality, avg_days_late,
        on_time_rate, risk_score and risk_tier.
    '''
    cfg = config or Config()
    settled = ledger[ledger['status'] == 'PAID'].copy()
    settled['days_late'] = (settled['settle_date'] - settled['due_date']).dt.days
    port_n = len(settled)
    port_median = float(settled['days_late'].median()) if port_n else 0.0
    port_ok = port_n >= cfg.min_history

    rows = []
    for (cid, name), led in ledger.groupby(['customer_id', 'customer_name'], sort=True):
        s = settled[settled['customer_id'] == cid]
        n = len(s)
        outstanding = float(led['outstanding'].sum())
        over = led[led['days_past_due'] > 0]
        overdue_out = float(over['outstanding'].sum())
        oldest = int(over['days_past_due'].max()) if len(over) else 0
        if n >= cfg.min_history:
            delay, quality = float(s['days_late'].median()), 'own'
        elif port_ok:
            delay, quality = port_median, 'portfolio'
        else:
            delay, quality = 0.0, 'none'
        if n:
            late = s['days_late'].clip(lower=0).to_numpy(dtype=float)
            avg_late = float(np.average(late, weights=s['amount'].to_numpy(dtype=float)))
            on_time: float | None = float((s['days_late'] <= 0).sum()) / n
        else:
            avg_late, on_time = 0.0, None
        share = overdue_out / outstanding if outstanding > 0 else 0.0
        score = risk_score(share, avg_late, on_time, oldest)
        rows.append(
            {
                'customer_id': cid,
                'customer_name': name,
                'outstanding': round(outstanding, 2),
                'overdue_outstanding': round(overdue_out, 2),
                'oldest_days_past_due': oldest,
                'settled_count': n,
                'typical_delay_days': delay,
                'history_quality': quality,
                'avg_days_late': avg_late,
                'on_time_rate': on_time,
                'risk_score': score,
                'risk_tier': risk_tier(score),
            }
        )
    cols = [
        'customer_id', 'customer_name', 'outstanding', 'overdue_outstanding', 'oldest_days_past_due', 'settled_count',
        'typical_delay_days', 'history_quality', 'avg_days_late', 'on_time_rate', 'risk_score', 'risk_tier',
    ]
    return pd.DataFrame(rows, columns=cols)
