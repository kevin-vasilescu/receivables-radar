"""Time analyze() on 200k synthetic invoices. Run: python benchmarks/bench.py"""

from __future__ import annotations

import platform
import time
from datetime import date, timedelta

import numpy as np
import pandas as pd

from receivables_radar import analyze

N = 200_000


def build(n: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(42)
    base = pd.Timestamp(date(2024, 1, 1))
    inv_date = base + pd.to_timedelta(rng.integers(0, 700, n), unit='D')
    due = inv_date + pd.to_timedelta(rng.choice([15, 30, 45, 60], n), unit='D')
    cust = rng.integers(0, 5000, n)
    inv = pd.DataFrame(
        {
            'invoice_id': [f'I{i}' for i in range(n)],
            'customer_id': [f'C{c}' for c in cust],
            'customer_name': [f'C{c}' for c in cust],
            'invoice_date': inv_date,
            'due_date': due,
            'amount': np.round(rng.uniform(100, 5000, n), 2),
        }
    )
    paid = rng.random(n) < 0.85
    idx = np.flatnonzero(paid)
    pay = pd.DataFrame(
        {
            'payment_id': [f'P{i}' for i in idx],
            'invoice_id': inv.loc[idx, 'invoice_id'].to_numpy(),
            'payment_date': due.iloc[idx] + pd.to_timedelta(rng.integers(-5, 60, len(idx)), unit='D'),
            'amount': inv.loc[idx, 'amount'].to_numpy(),
        }
    )
    return inv, pay


def main() -> None:
    inv, pay = build(N)
    start = time.perf_counter()
    res = analyze(inv, pay)
    res.kpis()
    res.forecast()
    res.worklist()
    elapsed = time.perf_counter() - start
    print(f'machine: {platform.platform()} / Python {platform.python_version()} / pandas {pd.__version__}')
    print(f'invoices: {N}, payments: {len(pay)}, as_of: {res.as_of}')
    print(f'analyze + kpis + forecast + worklist: {elapsed:.2f} s')
    print(f'unused horizon: {timedelta(days=0)}')


if __name__ == '__main__':
    main()
