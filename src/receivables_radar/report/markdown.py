'''Markdown report.'''

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from receivables_radar.analysis import AnalysisResult


def money(value: float | None) -> str:
    '''Format an amount with thousands separators, or n/a.'''
    return 'n/a' if value is None or pd.isna(value) else f'{value:,.2f}'


def pct(value: float | None) -> str:
    '''Format a ratio (0.25) as a percentage (25.0%), or n/a.'''
    return 'n/a' if value is None or pd.isna(value) else f'{value * 100:.1f}%'


def num(value: float | None, digits: int = 1) -> str:
    '''Format a plain number, or n/a.'''
    return 'n/a' if value is None or pd.isna(value) else f'{value:.{digits}f}'


def table(headers: list[str], rows: list[list[str]]) -> str:
    '''Render a Markdown table from headers and string cells.'''
    lines = ['| ' + ' | '.join(headers) + ' |', '|' + '|'.join('---' for _ in headers) + '|']
    lines += ['| ' + ' | '.join(c.replace('|', '/') for c in r) + ' |' for r in rows]
    return '\n'.join(lines)


def render_markdown(res: AnalysisResult) -> str:
    '''Render the full Markdown report.

    Args:
        res: Analysis result.

    Returns:
        Markdown document text.
    '''
    k = res.kpis()
    out = [
        '# Receivables Radar report',
        '',
        f'- As of: {res.as_of.isoformat()}',
        f'- Currency: {res.config.currency_code}',
        f'- Invoices: {res.invoice_count}',
        f'- Payments: {res.payment_count}',
        '',
    ]
    if res.warnings:
        out += ['## Warnings', ''] + [f'- {w}' for w in res.warnings] + ['']
    figures = [
        ['Total outstanding', money(k['total_outstanding'])],
        ['Overdue outstanding', money(k['overdue_outstanding'])],
        ['Overdue share', pct(k['overdue_share'])],
        ['Credit balances (overpayments)', money(k['credit_balance_total'])],
        ['DSO (days)', num(k['dso'])],
        ['Best possible DSO (days)', num(k['bpdso'])],
        ['Average days delinquent', num(k['add'])],
        ['CEI (%)', num(k['cei'], 2)],
        ['Uncollectable risk', money(res.uncollectable_risk())],
    ]
    out += ['## Key figures', '', table(['Metric', 'Value'], figures), '']
    aging = [[r.bucket, money(r.amount), str(r.invoice_count), pct(r.share)] for r in res.aging().itertuples()]
    out += ['## Aging', '', table(['Bucket', 'Amount', 'Invoices', 'Share'], aging), '']
    top = [[r.customer_name, money(r.outstanding), pct(r.share)] for r in res.top_customers().itertuples()]
    out += ['## Top customers by outstanding', '', table(['Customer', 'Outstanding', 'Share'], top), '']
    tiers = [[r.risk_tier, str(r.customers), money(r.outstanding)] for r in res.risk_tiers().itertuples()]
    out += ['## Risk tiers', '', table(['Tier', 'Customers', 'Outstanding'], tiers), '']
    names = [s.name for s in res.config.scenarios]
    fc = {n: res.forecast(n) for n in names}
    rows = []
    for i in range(len(fc[names[0]])):
        first = fc[names[0]].iloc[i]
        label = str(first['week'])
        if first['week_start'] is not None:
            label = f'{label} ({first["week_start"]:%Y-%m-%d})'
        rows.append([label] + [money(fc[n].iloc[i]['expected_cash']) for n in names])
    out += [f'## {res.config.forecast_weeks}-week cash forecast', '', table(['Week'] + names, rows), '']
    wl = [
        [r.customer_name, money(r.total_overdue), str(r.oldest_days_past_due), str(r.invoice_count), r.risk_tier, money(r.priority_score), r.suggested_action]
        for r in res.worklist().head(25).itertuples()
    ]
    heads = ['Customer', 'Overdue', 'Oldest (days)', 'Invoices', 'Risk', 'Priority', 'Action']
    out += ['## Collections worklist (top 25)', '', table(heads, wl), '']
    return '\n'.join(out)
