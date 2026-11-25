'''Deterministic synthetic data generator.'''

from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

END_DATE = date(2025, 12, 31)
_NAMES = [
    'Acme', 'Borealis', 'Cobalt', 'Delta', 'Evergreen', 'Fjord', 'Granite', 'Harbor', 'Indigo', 'Juniper', 'Keystone',
    'Lumen', 'Meridian', 'Nimbus', 'Orchid', 'Pinnacle', 'Quartz', 'Redwood', 'Summit', 'Tundra', 'Umbra', 'Vertex',
    'Willow', 'Xenon', 'Yarrow', 'Zenith',
]
_SUFFIX = ['Ltd', 'GmbH', 'Supply Co', 'Studios', 'Partners', 'Logistics', 'Foods', 'Labs']
_ARCHETYPES = ['reliable', 'slightly_late', 'chronic_late', 'partial', 'disputed']
_WEIGHTS = [0.35, 0.25, 0.15, 0.15, 0.10]


def generate(customers: int = 60, months: int = 18, seed: int = 42) -> tuple[pd.DataFrame, pd.DataFrame]:
    '''Generate synthetic invoices and payments.

    Archetypes: reliable early payers, slightly late payers, chronic late payers, partial payers
    (2-3 installments), disputed accounts that never pay, and a few big customers that create
    concentration risk. Data ends on 2025-12-31 and is fully determined by the arguments.

    Args:
        customers: Number of customers.
        months: Months of invoicing history.
        seed: Random seed.

    Returns:
        Tuple of invoices and payments frames in CSV column layout.
    '''
    rng = random.Random(seed)
    start = END_DATE - timedelta(days=int(months * 30.4))
    big = set(range(max(1, customers // 20)))
    inv_rows: list[dict[str, object]] = []
    pay_rows: list[dict[str, object]] = []
    for c in range(customers):
        cid = f'C{c + 1:03d}'
        name = f'{rng.choice(_NAMES)} {rng.choice(_SUFFIX)} {c + 1}'
        arche = rng.choices(_ARCHETYPES, _WEIGHTS)[0]
        terms = rng.choice([15, 30, 30, 45, 60])
        scale = rng.uniform(8, 20) if c in big else rng.uniform(0.3, 2.5)
        day = start + timedelta(days=rng.randint(0, 20))
        while day <= END_DATE:
            amount = round(rng.uniform(800, 4000) * scale, 2)
            iid = f'INV-{len(inv_rows) + 1:05d}'
            due = day + timedelta(days=terms)
            inv_rows.append(
                {
                    'invoice_id': iid,
                    'customer_id': cid,
                    'customer_name': name,
                    'invoice_date': day,
                    'due_date': due,
                    'amount': amount,
                    'currency': 'USD',
                }
            )
            for pay_date, part in _payments(rng, arche, due, amount):
                if pay_date <= END_DATE:
                    pay_rows.append({'invoice_id': iid, 'payment_date': pay_date, 'amount': part})
            day += timedelta(days=rng.randint(24, 38))
    pay_rows.sort(key=lambda r: (str(r['payment_date']), str(r['invoice_id'])))
    for i, r in enumerate(pay_rows, start=1):
        r['payment_id'] = f'PAY-{i:05d}'
    invoices = pd.DataFrame(inv_rows)
    payments = pd.DataFrame(pay_rows, columns=['payment_id', 'invoice_id', 'payment_date', 'amount'])
    return invoices, payments


def _payments(rng: random.Random, arche: str, due: date, amount: float) -> list[tuple[date, float]]:
    if arche == 'disputed':
        return []
    if arche == 'reliable':
        return [(due + timedelta(days=rng.randint(-5, 1)), amount)]
    if arche == 'slightly_late':
        return [(due + timedelta(days=rng.randint(3, 15)), amount)]
    if arche == 'chronic_late':
        if rng.random() < 0.15:
            return []
        return [(due + timedelta(days=rng.randint(30, 80)), amount)]
    n = rng.choice([2, 3])
    first = round(amount * rng.uniform(0.3, 0.5), 2)
    parts = [first]
    if n == 3:
        parts.append(round((amount - first) * rng.uniform(0.4, 0.6), 2))
    parts.append(round(amount - sum(parts), 2))
    out = []
    when = due + timedelta(days=rng.randint(0, 10))
    for p in parts:
        out.append((when, p))
        when += timedelta(days=rng.randint(15, 35))
    return out


def write_sample(out_dir: str | Path, customers: int = 60, months: int = 18, seed: int = 42) -> tuple[Path, Path]:
    '''Generate sample data and write invoices.csv and payments.csv.

    Args:
        out_dir: Destination directory (created if missing).
        customers: Number of customers.
        months: Months of history.
        seed: Random seed.

    Returns:
        Paths of the two files.
    '''
    folder = Path(out_dir)
    folder.mkdir(parents=True, exist_ok=True)
    inv, pay = generate(customers, months, seed)
    ip, pp = folder / 'invoices.csv', folder / 'payments.csv'
    inv.to_csv(ip, index=False, lineterminator='\n')
    pay.to_csv(pp, index=False, lineterminator='\n')
    return ip, pp
