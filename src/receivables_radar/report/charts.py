'''Inline SVG charts.'''

from __future__ import annotations

from html import escape

import pandas as pd

BUCKET_COLORS = ['#2e7d32', '#9ccc65', '#fbc02d', '#f57c00', '#c62828']


def aging_bar(aging: pd.DataFrame, width: int = 720, height: int = 56) -> str:
    '''Stacked horizontal bar of outstanding per bucket.

    Args:
        aging: Output of aging_table.
        width: SVG width in pixels.
        height: Bar height in pixels.

    Returns:
        SVG markup, or an empty-state paragraph when nothing is outstanding.
    '''
    total = float(aging['amount'].sum())
    if total <= 0:
        return '<p class="muted">Nothing outstanding.</p>'
    x = 0.0
    parts = [f'<svg viewBox="0 0 {width} {height + 40}" role="img" aria-label="Aging distribution" class="chart">']
    for i, r in enumerate(aging.itertuples()):
        w = width * float(r.amount) / total
        if w <= 0:
            continue
        label = escape(str(r.bucket))
        parts.append(
            f'<rect x="{x:.1f}" y="0" width="{w:.1f}" height="{height}" fill="{BUCKET_COLORS[i % 5]}"><title>{label}: {r.amount:,.2f}</title></rect>'
        )
        if w > 60:
            parts.append(f'<text x="{x + w / 2:.1f}" y="{height / 2 + 5}" text-anchor="middle" fill="#fff" font-size="13">{label}</text>')
        x += w
    for i, b in enumerate(aging['bucket']):
        lx = 10 + i * 140
        parts.append(
            f'<rect x="{lx}" y="{height + 14}" width="12" height="12" fill="{BUCKET_COLORS[i % 5]}"/>'
            f'<text x="{lx + 18}" y="{height + 25}" font-size="12" fill="#444">{escape(str(b))}</text>'
        )
    parts.append('</svg>')
    return ''.join(parts)


def forecast_bars(weekly: pd.DataFrame, width: int = 720, height: int = 220) -> str:
    '''Bar chart of expected cash per forecast week.

    Args:
        weekly: Output of weekly_forecast.
        width: SVG width in pixels.
        height: SVG height in pixels.

    Returns:
        SVG markup, or an empty-state paragraph when there is no expected cash.
    '''
    data = weekly[weekly['week_start'].notna()]
    peak = float(data['expected_cash'].max()) if len(data) else 0.0
    if peak <= 0:
        return '<p class="muted">No expected cash in the forecast horizon.</p>'
    left, bottom, top = 10, 30, 20
    slot = (width - left) / len(data)
    plot = height - bottom - top
    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Weekly expected cash" class="chart">']
    for i, r in enumerate(data.itertuples()):
        h = plot * float(r.expected_cash) / peak
        x = left + i * slot + slot * 0.12
        y = height - bottom - h
        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{slot * 0.76:.1f}" height="{h:.1f}" fill="#1565c0"><title>Week {r.week}: {r.expected_cash:,.2f}</title></rect>'
        )
        parts.append(f'<text x="{x + slot * 0.38:.1f}" y="{height - 12}" text-anchor="middle" font-size="11" fill="#444">{escape(str(r.week))}</text>')
    parts.append(f'<text x="{left}" y="14" font-size="12" fill="#444">Peak week: {peak:,.0f}</text>')
    parts.append('</svg>')
    return ''.join(parts)
