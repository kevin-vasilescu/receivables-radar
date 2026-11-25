import json
import re
from pathlib import Path
from typing import Any

import pytest

from receivables_radar import Config, analyze

from .conftest import make_invoices, make_payments


def test_json_schema(fixture_result: Any) -> None:
    data = json.loads(fixture_result.to_json())
    assert list(data) == ['meta', 'warnings', 'kpis', 'aging', 'top_customers', 'customers', 'risk_tiers', 'forecast', 'worklist']
    assert data['meta']['as_of'] == '2025-04-15'
    assert set(data['forecast']) == {'base', 'pessimistic', 'optimistic'}
    assert len(data['forecast']['base']) == 14
    assert data['kpis']['cei'] == pytest.approx(62.5)


def test_json_has_no_nan_when_empty() -> None:
    inv = make_invoices([('A', 'C', '2025-01-01', '2025-02-01', 100.0)])
    pay = make_payments([('P', 'A', '2025-01-05', 100.0)])
    text = analyze(inv, pay).to_json()
    assert 'NaN' not in text and 'Infinity' not in text
    assert json.loads(text)['kpis']['overdue_share'] is None


def test_markdown_sections(fixture_result: Any) -> None:
    md = fixture_result.to_markdown()
    for heading in ['## Key figures', '## Aging', '## Top customers by outstanding', '## Risk tiers', '## 13-week cash forecast', '## Collections worklist (top 25)']:
        assert heading in md
    assert '62.50' in md
    assert 'pessimistic' in md and 'beyond horizon' in md


def test_html_self_contained(fixture_result: Any) -> None:
    html = fixture_result.to_html()
    assert '<svg' in html and 'badge' in html
    assert '<script' not in html
    assert not re.search(r'https?://', html)
    assert 'Acme Ltd' in html


def test_html_escapes_names() -> None:
    inv = make_invoices([('A', 'C', '2025-01-01', '2025-01-05', 100.0)])
    inv['customer_name'] = '<b>Evil</b> & Co'
    html = analyze(inv, make_payments([])).to_html()
    assert '<b>Evil</b>' not in html
    assert '&lt;b&gt;Evil' in html


def test_empty_state_html() -> None:
    inv = make_invoices([('A', 'C', '2025-01-01', '2025-02-01', 100.0)])
    pay = make_payments([('P', 'A', '2025-01-05', 100.0)])
    assert 'Nothing outstanding' in analyze(inv, pay).to_html()


def test_excel_workbook(fixture_result: Any, tmp_path: Path) -> None:
    openpyxl = pytest.importorskip('openpyxl')
    path = tmp_path / 'r.xlsx'
    fixture_result.to_excel(path)
    wb = openpyxl.load_workbook(path)
    assert wb.sheetnames == ['Summary', 'Ledger', 'Customers', 'Forecast', 'Worklist']
    assert wb['Ledger'].freeze_panes == 'A2'
    assert wb['Ledger'].max_row == 7


def test_custom_config_weeks(fixture_tables: Any) -> None:
    res = analyze(*fixture_tables, Config(forecast_weeks=4, currency_code='EUR'))
    assert len(res.forecast()) == 5
    assert 'EUR' in res.to_markdown()


def test_unknown_scenario(fixture_result: Any) -> None:
    with pytest.raises(KeyError):
        fixture_result.forecast('nope')
