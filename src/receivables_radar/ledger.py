'''Invoice ledger: outstanding amounts, buckets and status.'''

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from receivables_radar.config import Config
from receivables_radar.models import OPEN, OVERDUE, PAID, PARTIAL

EPS = 0.005


def assign_bucket(days_past_due: int, edges: tuple[int, int, int] = (30, 60, 90)) -> str:
    '''Map days past due to an aging bucket label.

    Args:
        days_past_due: Non-negative days past due.
        edges: Upper edges of the three middle buckets (inclusive).

    Returns:
        Current, 1-30, 31-60, 61-90 or 90+ for the default edges.
    '''
    labels = Config(bucket_edges=edges).buckets
    if days_past_due <= 0:
        return labels[0]
    for idx, edge in enumerate(edges, start=1):
        if days_past_due <= edge:
            return labels[idx]
    return labels[4]


def _settle_dates(inv: pd.DataFrame, pay: pd.DataFrame) -> pd.Series:
    '''Date on which cumulative payments first reached the invoice amount.'''
    if pay.empty:
        return pd.Series(pd.NaT, index=inv['invoice_id'], dtype='datetime64[ns]')
    p = pay.sort_values(['payment_date', 'payment_id'], kind='stable').copy()
    p['cum'] = p.groupby('invoice_id')['amount'].cumsum()
    p = p.join(inv.set_index('invoice_id')['amount'].rename('inv_amount'), on='invoice_id')
    hit = p[p['cum'] >= p['inv_amount'] - EPS]
    first = hit.groupby('invoice_id')['payment_date'].min()
    return first.reindex(inv['invoice_id'])


def compute_ledger(invoices: pd.DataFrame, payments: pd.DataFrame, as_of: date, config: Config | None = None) -> pd.DataFrame:
    '''Compute the invoice ledger as of a date.

    Invoices and payments dated after as_of are ignored.

    Args:
        invoices: Cleaned invoices.
        payments: Cleaned payments.
        as_of: Reporting date.
        config: Settings (bucket edges).

    Returns:
        One row per invoice with paid, outstanding, credit_balance, days_past_due,
        bucket, status, partially_paid and settle_date.
    '''
    cfg = config or Config()
    stamp = pd.Timestamp(as_of)
    inv = invoices[invoices['invoice_date'] <= stamp].copy()
    pay = payments[payments['payment_date'] <= stamp].sort_values(
        ['payment_date', 'payment_id', 'invoice_id', 'amount'], kind='stable'
    )
    paid = pay.groupby('invoice_id')['amount'].sum()
    inv['paid'] = inv['invoice_id'].map(paid).fillna(0.0).astype(float)
    inv['outstanding'] = (inv['amount'] - inv['paid']).clip(lower=0.0).round(2)
    inv['credit_balance'] = (inv['paid'] - inv['amount']).clip(lower=0.0).round(2)
    inv.loc[inv['outstanding'] < EPS, 'outstanding'] = 0.0
    inv.loc[inv['credit_balance'] < EPS, 'credit_balance'] = 0.0
    late = (stamp - inv['due_date']).dt.days.clip(lower=0)
    inv['days_past_due'] = late.where(inv['outstanding'] > 0, 0).astype(int)
    edges = cfg.bucket_edges
    idx = np.select(
        [
            inv['days_past_due'] <= 0,
            inv['days_past_due'] <= edges[0],
            inv['days_past_due'] <= edges[1],
            inv['days_past_due'] <= edges[2],
        ],
        [0, 1, 2, 3],
        default=4,
    )
    inv['bucket'] = np.array(cfg.buckets, dtype=object)[idx]
    owes = inv['outstanding'] > 0
    overdue = owes & (inv['days_past_due'] > 0)
    inv['status'] = np.select([~owes, overdue, inv['paid'] > 0], [PAID, OVERDUE, PARTIAL], default=OPEN)
    inv['partially_paid'] = owes & (inv['paid'] > 0)
    settle = _settle_dates(inv, pay)
    inv['settle_date'] = inv['invoice_id'].map(settle)
    inv.loc[owes, 'settle_date'] = pd.NaT
    cols = [
        'invoice_id', 'customer_id', 'customer_name', 'invoice_date', 'due_date', 'amount', 'paid',
        'outstanding', 'credit_balance', 'days_past_due', 'bucket', 'status', 'partially_paid', 'settle_date',
    ]
    return inv[cols].sort_values('invoice_id', kind='stable').reset_index(drop=True)
