'''XLSX report (optional excel extra).'''

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

if TYPE_CHECKING:
    from receivables_radar.analysis import AnalysisResult


def _cell(v: Any) -> Any:
    if isinstance(v, pd.Timestamp):
        return v.date()
    if v is pd.NaT or v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    return v.item() if hasattr(v, 'item') else v


def _sheet(ws: Any, df: pd.DataFrame, money_cols: set[str], pct_cols: set[str]) -> None:
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    ws.append(list(df.columns))
    for row in df.itertuples(index=False):
        ws.append([_cell(v) for v in row])
    for c in ws[1]:
        c.font = Font(bold=True, color='FFFFFF')
        c.fill = PatternFill('solid', fgColor='1F3A5F')
        c.alignment = Alignment(horizontal='center')
    ws.freeze_panes = 'A2'
    for i, name in enumerate(df.columns, start=1):
        letter = get_column_letter(i)
        width = max([len(str(name))] + [len(str(_cell(v))) for v in df[name].head(200)]) + 2
        ws.column_dimensions[letter].width = min(max(width, 10), 48)
        fmt = '#,##0.00' if name in money_cols else '0.0%' if name in pct_cols else None
        if fmt:
            for cell in ws[letter][1:]:
                cell.number_format = fmt


def write_excel(res: AnalysisResult, path: Path) -> None:
    '''Write the workbook with sheets Summary, Ledger, Customers, Forecast and Worklist.

    Args:
        res: Analysis result.
        path: Destination file.

    Raises:
        ImportError: If openpyxl is not installed.
    '''
    from openpyxl import Workbook

    wb = Workbook()
    summary = wb.active
    if summary is None:
        raise RuntimeError('workbook has no active sheet')
    summary.title = 'Summary'
    k = {**res.kpis(), 'uncollectable_risk': res.uncollectable_risk()}
    meta = pd.DataFrame({'metric': ['as_of', 'currency', *k], 'value': [res.as_of.isoformat(), res.config.currency_code, *k.values()]})
    _sheet(summary, meta, set(), set())
    summary.column_dimensions['B'].width = 18
    money = {'amount', 'paid', 'outstanding', 'credit_balance', 'total_overdue', 'priority_score', 'overdue_outstanding', 'expected_cash', 'cumulative'}
    pct = {'share', 'on_time_rate'}
    fc = pd.concat([res.forecast(s.name).assign(scenario=s.name) for s in res.config.scenarios], ignore_index=True)
    sheets = [('Ledger', res.ledger), ('Customers', res.customers()), ('Forecast', fc), ('Worklist', res.worklist())]
    for title, df in sheets:
        _sheet(wb.create_sheet(title), df, money, pct)
    wb.save(path)
