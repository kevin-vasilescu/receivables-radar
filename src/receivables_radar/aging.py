'''Aging table.'''

from __future__ import annotations

import pandas as pd

from receivables_radar.config import Config


def aging_table(ledger: pd.DataFrame, config: Config | None = None) -> pd.DataFrame:
    '''Summarise outstanding amounts per aging bucket.

    Args:
        ledger: Output of compute_ledger.
        config: Settings (bucket labels).

    Returns:
        One row per bucket with amount, invoice_count and share (None when nothing is outstanding).
    '''
    cfg = config or Config()
    open_ = ledger[ledger['outstanding'] > 0]
    amount = open_.groupby('bucket')['outstanding'].sum().reindex(cfg.buckets, fill_value=0.0)
    count = open_.groupby('bucket')['invoice_id'].count().reindex(cfg.buckets, fill_value=0)
    total = float(amount.sum())
    share = [float(a) / total if total > 0 else None for a in amount]
    return pd.DataFrame(
        {
            'bucket': cfg.buckets,
            'amount': amount.round(2).to_numpy(),
            'invoice_count': count.to_numpy(),
            'share': pd.Series(share, dtype=object),
        }
    )
