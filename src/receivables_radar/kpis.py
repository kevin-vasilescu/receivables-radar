'''Portfolio KPIs: DSO, BPDSO, ADD, CEI and concentration.'''

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from receivables_radar.config import Config
from receivables_radar.ledger import compute_ledger


def _div(num: float, den: float) -> float | None:
    return None if den == 0 else num / den


def dso(ending_ar: float, billed: float, window_days: int) -> float | None:
    '''Days sales outstanding (count method).

    Args:
        ending_ar: Total outstanding at as_of.
        billed: Invoiced amount inside the window.
        window_days: Window length in days.

    Returns:
        ending_ar / billed * window_days, or None if billed is 0.
    '''
    ratio = _div(ending_ar, billed)
    return None if ratio is None else ratio * window_days


def best_possible_dso(current_ar: float, billed: float, window_days: int) -> float | None:
    '''Best possible DSO using only Current-bucket receivables.

    Args:
        current_ar: Outstanding on Current-bucket invoices.
        billed: Invoiced amount inside the window.
        window_days: Window length in days.

    Returns:
        current_ar / billed * window_days, or None if billed is 0.
    '''
    return dso(current_ar, billed, window_days)


def average_days_delinquent(dso_value: float | None, bpdso_value: float | None) -> float | None:
    '''Average days delinquent, DSO - BPDSO.

    Args:
        dso_value: DSO or None.
        bpdso_value: BPDSO or None.

    Returns:
        The difference, or None if either input is None.
    '''
    if dso_value is None or bpdso_value is None:
        return None
    return dso_value - bpdso_value


def cei(beginning_ar: float, billed: float, ending_ar: float, current_ar: float) -> float | None:
    '''Collection effectiveness index in percent.

    Args:
        beginning_ar: Outstanding at the start of the window.
        billed: Invoiced amount inside the window.
        ending_ar: Total outstanding at as_of.
        current_ar: Outstanding on Current-bucket invoices.

    Returns:
        The index in percent, or None if the denominator is 0.
    '''
    ratio = _div(beginning_ar + billed - ending_ar, beginning_ar + billed - current_ar)
    return None if ratio is None else ratio * 100.0


def compute_kpis(
    invoices: pd.DataFrame, payments: pd.DataFrame, ledger: pd.DataFrame, as_of: date, config: Config | None = None
) -> dict[str, float | None]:
    '''Compute portfolio KPIs.

    Args:
        invoices: Cleaned invoices.
        payments: Cleaned payments.
        ledger: Ledger as of as_of.
        as_of: Reporting date.
        config: Settings.

    Returns:
        Mapping with total_outstanding, overdue_outstanding, overdue_share, credit_balance_total,
        billed_in_window, beginning_ar, current_ar, dso, bpdso, add and cei.
    '''
    cfg = config or Config()
    total = round(float(ledger['outstanding'].sum()), 2)
    overdue = round(float(ledger.loc[ledger['days_past_due'] > 0, 'outstanding'].sum()), 2)
    current = round(float(ledger.loc[ledger['bucket'] == 'Current', 'outstanding'].sum()), 2)
    start = as_of - timedelta(days=cfg.dso_window_days)
    in_window = (invoices['invoice_date'] > pd.Timestamp(start)) & (invoices['invoice_date'] <= pd.Timestamp(as_of))
    billed = round(float(invoices.loc[in_window, 'amount'].sum()), 2)
    beginning = round(float(compute_ledger(invoices, payments, start, cfg)['outstanding'].sum()), 2)
    d = dso(total, billed, cfg.dso_window_days)
    b = best_possible_dso(current, billed, cfg.dso_window_days)
    return {
        'total_outstanding': total,
        'overdue_outstanding': overdue,
        'overdue_share': _div(overdue, total),
        'credit_balance_total': round(float(ledger['credit_balance'].sum()), 2),
        'billed_in_window': billed,
        'beginning_ar': beginning,
        'current_ar': current,
        'dso': d,
        'bpdso': b,
        'add': average_days_delinquent(d, b),
        'cei': cei(beginning, billed, total, current),
    }


def top_customers(ledger: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    '''Top customers by outstanding with their share of the total.

    Args:
        ledger: Ledger frame.
        n: Number of customers.

    Returns:
        Columns customer_id, customer_name, outstanding, share. Ties are broken by customer_id.
    '''
    g = ledger.groupby(['customer_id', 'customer_name'], as_index=False)['outstanding'].sum()
    total = float(g['outstanding'].sum())
    g = g[g['outstanding'] > 0].sort_values(['outstanding', 'customer_id'], ascending=[False, True])
    g['share'] = g['outstanding'] / total if total > 0 else None
    return g.head(n).reset_index(drop=True)
