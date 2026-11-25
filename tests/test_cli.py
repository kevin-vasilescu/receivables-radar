import builtins
import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from receivables_radar import __version__
from receivables_radar.cli import app

from .conftest import FIXTURES

runner = CliRunner()
INV = str(FIXTURES / 'invoices.csv')
PAY = str(FIXTURES / 'payments.csv')


def test_version() -> None:
    r = runner.invoke(app, ['--version'])
    assert r.exit_code == 0 and __version__ in r.output


def test_analyze_summary_and_formats(tmp_path: Path) -> None:
    r = runner.invoke(app, ['analyze', INV, PAY, '--top', '3'])
    assert r.exit_code == 0
    assert '15,000.00' in r.output and 'CEI 62.50%' in r.output and 'Acme Ltd' in r.output
    for fmt, name in [('md', 'r.md'), ('html', 'r.html'), ('json', 'r.json')]:
        out = tmp_path / name
        r = runner.invoke(app, ['analyze', INV, PAY, '--format', fmt, '--out', str(out)])
        assert r.exit_code == 0 and out.stat().st_size > 0
    json.loads((tmp_path / 'r.json').read_text(encoding='utf-8'))
    r = runner.invoke(app, ['analyze', INV, PAY, '--format', 'csv', '--out', str(tmp_path / 'csv')])
    assert r.exit_code == 0
    assert {p.name for p in (tmp_path / 'csv').iterdir()} == {'kpis.csv', 'aging.csv', 'ledger.csv', 'customers.csv', 'worklist.csv', 'forecast.csv'}


def test_as_of_option() -> None:
    r = runner.invoke(app, ['analyze', INV, PAY, '--as-of', '2025-03-15'])
    assert r.exit_code == 0 and 'as of 2025-03-15' in r.output


def test_xlsx_written(tmp_path: Path) -> None:
    pytest.importorskip('openpyxl')
    out = tmp_path / 'r.xlsx'
    assert runner.invoke(app, ['analyze', INV, PAY, '--format', 'xlsx', '--out', str(out)]).exit_code == 0
    assert out.exists()


def test_xlsx_missing_openpyxl(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    real = builtins.__import__

    def fake(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == 'openpyxl' or name.startswith('openpyxl.'):
            raise ImportError('simulated')
        return real(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', fake)
    r = runner.invoke(app, ['analyze', INV, PAY, '--format', 'xlsx', '--out', str(tmp_path / 'r.xlsx')])
    assert r.exit_code == 1
    assert 'receivables-radar[excel]' in r.output


def test_forecast_variants(tmp_path: Path) -> None:
    r = runner.invoke(app, ['forecast', INV, PAY, '--weeks', '4', '--scenario', 'base'])
    assert r.exit_code == 0 and 'Scenario: base' in r.output and 'pessimistic' not in r.output
    out = tmp_path / 'f.csv'
    assert runner.invoke(app, ['forecast', INV, PAY, '--format', 'csv', '--out', str(out)]).exit_code == 0
    assert 'scenario' in out.read_text(encoding='utf-8').splitlines()[0]
    r = runner.invoke(app, ['forecast', INV, PAY, '--format', 'json'])
    assert r.exit_code == 0 and json.loads(r.output)


def test_dunning_writes_files(tmp_path: Path) -> None:
    out = tmp_path / 'd'
    r = runner.invoke(app, ['dunning', INV, PAY, '--out', str(out), '--company-name', 'Me', '--contact', 'x@y.test'])
    assert r.exit_code == 0
    assert (out / 'ACME.txt').exists()
    idx = (out / 'dunning_index.csv').read_text(encoding='utf-8').splitlines()
    assert idx[0].startswith('customer_id,customer_name,file')
    assert idx[1].startswith('ACME,Acme Ltd,ACME.txt,6000.00,45,MEDIUM')


def test_validate_ok_and_failure(tmp_path: Path) -> None:
    r = runner.invoke(app, ['validate', INV, PAY])
    assert r.exit_code == 0 and '0 error(s)' in r.output
    bad = tmp_path / 'bad.csv'
    bad.write_text('invoice_id,customer_id,invoice_date,due_date,amount\nA,C,xx,2025-01-01,5\n', encoding='utf-8')
    r = runner.invoke(app, ['validate', str(bad), PAY])
    assert r.exit_code == 1 and 'invoices row 2' in r.output


def test_data_error_is_friendly(tmp_path: Path) -> None:
    r = runner.invoke(app, ['analyze', str(tmp_path / 'missing.csv'), PAY])
    assert r.exit_code == 1
    assert 'Data error' in r.output
    assert 'Traceback' not in r.output


def test_usage_errors_exit_2() -> None:
    assert runner.invoke(app, ['analyze']).exit_code == 2
    assert runner.invoke(app, ['analyze', INV, PAY, '--format', 'pdf']).exit_code == 2
    assert runner.invoke(app, ['analyze', INV, PAY, '--as-of', 'yesterday']).exit_code == 2
    assert runner.invoke(app, ['forecast', INV, PAY, '--scenario', 'wild']).exit_code == 2


def test_sample_command(tmp_path: Path) -> None:
    out = tmp_path / 's'
    r = runner.invoke(app, ['sample', '--customers', '10', '--months', '6', '--out', str(out)])
    assert r.exit_code == 0
    assert (out / 'invoices.csv').exists() and (out / 'payments.csv').exists()
    assert runner.invoke(app, ['analyze', str(out / 'invoices.csv'), str(out / 'payments.csv')]).exit_code == 0
