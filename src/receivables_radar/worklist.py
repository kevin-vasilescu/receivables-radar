'''Collections worklist.'''

from __future__ import annotations

import pandas as pd

from receivables_radar.config import Config

ACTIONS = {
    1: 'Friendly reminder',
    2: 'Phone call and firm reminder',
    3: 'Escalate to account manager, payment plan',
    4: 'Final notice, consider hold on new orders / legal review',
}


def priority_score(outstanding: float, days_past_due: int) -> float:
    '''Collections priority of an overdue invoice.

    Args:
        outstanding: Outstanding amount.
        days_past_due: Days past due.

    Returns:
        outstanding * (1 + days_past_due / 30).
    '''
    return outstanding * (1.0 + days_past_due / 30.0)


def invoice_worklist(ledger: pd.DataFrame) -> pd.DataFrame:
    '''Overdue invoices with priority scores.

    Args:
        ledger: Ledger frame.

    Returns:
        Overdue invoices sorted by priority_score descending.
    '''
    od = ledger[(ledger['outstanding'] > 0) & (ledger['days_past_due'] > 0)].copy()
    od['priority_score'] = od['outstanding'] * (1.0 + od['days_past_due'] / 30.0)
    cols = [
        'invoice_id', 'customer_id', 'customer_name', 'due_date', 'outstanding', 'days_past_due', 'bucket',
        'partially_paid', 'priority_score',
    ]
    return od[cols].sort_values(['priority_score', 'invoice_id'], ascending=[False, True]).reset_index(drop=True)


def customer_worklist(ledger: pd.DataFrame, behavior: pd.DataFrame, config: Config | None = None) -> pd.DataFrame:
    '''Customer-level collections worklist.

    Args:
        ledger: Ledger frame.
        behavior: Customer behaviour frame.
        config: Settings (bucket labels).

    Returns:
        One row per customer with overdue invoices: customer_id, customer_name, total_overdue,
        oldest_days_past_due, invoice_count, risk_tier, priority_score, suggested_action.
        Sorted by priority_score descending, then customer_id.
    '''
    cfg = config or Config()
    inv = invoice_worklist(ledger)
    cols = [
        'customer_id', 'customer_name', 'total_overdue', 'oldest_days_past_due', 'invoice_count', 'risk_tier',
        'priority_score', 'suggested_action',
    ]
    if inv.empty:
        return pd.DataFrame(columns=cols)
    rank = {b: i for i, b in enumerate(cfg.buckets)}
    inv['rank'] = inv['bucket'].map(rank)
    g = inv.groupby(['customer_id', 'customer_name'], as_index=False).agg(
        total_overdue=('outstanding', 'sum'),
        oldest_days_past_due=('days_past_due', 'max'),
        invoice_count=('invoice_id', 'count'),
        priority_score=('priority_score', 'sum'),
        worst=('rank', 'max'),
    )
    g['suggested_action'] = g['worst'].map(ACTIONS)
    g['total_overdue'] = g['total_overdue'].round(2)
    g = g.merge(behavior[['customer_id', 'risk_tier']], on='customer_id', how='left')
    return g[cols].sort_values(['priority_score', 'customer_id'], ascending=[False, True]).reset_index(drop=True)
