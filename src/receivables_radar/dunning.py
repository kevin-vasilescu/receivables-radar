'''Dunning email drafts (never sent).'''

from __future__ import annotations

import re
import unicodedata

import pandas as pd
from jinja2 import Environment, PackageLoader, StrictUndefined

from receivables_radar.config import Config

_ENV = Environment(
    loader=PackageLoader('receivables_radar', 'report/templates'),
    undefined=StrictUndefined,
    keep_trailing_newline=True,
    autoescape=False,  # plain-text output
)
_RESERVED = {'con', 'prn', 'aux', 'nul', *(f'com{i}' for i in range(1, 10)), *(f'lpt{i}' for i in range(1, 10))}


def template_for(worst_days_past_due: int) -> str:
    '''Pick the template name for the oldest overdue invoice.

    Args:
        worst_days_past_due: Days past due of the oldest invoice.

    Returns:
        friendly (1-30), firm (31-60) or final (61+).
    '''
    if worst_days_past_due <= 30:
        return 'friendly'
    if worst_days_past_due <= 60:
        return 'firm'
    return 'final'


def safe_filename(name: str, fallback: str = 'customer') -> str:
    '''Make a string safe as a file name on Windows, macOS and Linux.

    Args:
        name: Arbitrary text such as a customer id.
        fallback: Used when nothing usable remains.

    Returns:
        ASCII file stem of at most 80 characters.
    '''
    ascii_ = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii')
    stem = re.sub(r'[^A-Za-z0-9._-]+', '_', ascii_).strip('._-')[:80].strip('._-')
    if not stem:
        return fallback
    return f'_{stem}' if stem.lower() in _RESERVED else stem


def build_drafts(
    ledger: pd.DataFrame,
    config: Config | None = None,
    company_name: str = 'Accounts Receivable',
    contact: str = '',
    min_days_past_due: int = 1,
) -> dict[str, str]:
    '''Render one plain-text draft per customer with overdue invoices.

    Args:
        ledger: Ledger frame.
        config: Settings (currency code).
        company_name: Sender name for the sign-off.
        contact: Contact text added to the draft.
        min_days_past_due: Only include invoices at least this many days late.

    Returns:
        Mapping of customer_id to draft text, sorted by customer_id.
    '''
    cfg = config or Config()
    od = ledger[(ledger['outstanding'] > 0) & (ledger['days_past_due'] >= max(1, min_days_past_due))]
    drafts: dict[str, str] = {}
    for cid, grp in od.sort_values(['customer_id', 'due_date', 'invoice_id']).groupby('customer_id', sort=True):
        invoices = [
            {
                'invoice_id': r.invoice_id,
                'due_date': r.due_date.date().isoformat(),
                'days_past_due': int(r.days_past_due),
                'outstanding': f'{r.outstanding:,.2f}',
            }
            for r in grp.itertuples()
        ]
        tpl = _ENV.get_template(f'dunning_{template_for(int(grp["days_past_due"].max()))}.txt.j2')
        drafts[str(cid)] = tpl.render(
            customer_name=grp['customer_name'].iloc[0],
            invoices=invoices,
            total=f'{grp["outstanding"].sum():,.2f}',
            currency=cfg.currency_code,
            company_name=company_name,
            contact=contact,
        )
    return drafts


def draft_filenames(drafts: dict[str, str]) -> dict[str, str]:
    '''Unique, sanitised file names for drafts.

    Args:
        drafts: Mapping of customer_id to text.

    Returns:
        Mapping of customer_id to a .txt name; collisions get _2, _3 suffixes (case-insensitive).
    '''
    used: set[str] = set()
    out: dict[str, str] = {}
    for cid in drafts:
        base = safe_filename(cid)
        name, n = base, 1
        while name.lower() in used:
            n += 1
            name = f'{base}_{n}'
        used.add(name.lower())
        out[cid] = f'{name}.txt'
    return out
