'''Command line interface.'''

from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path
from typing import Annotated, Optional

import pandas as pd
import typer

from receivables_radar import __version__
from receivables_radar.analysis import AnalysisResult, analyze, records
from receivables_radar.config import Config
from receivables_radar.dunning import draft_filenames
from receivables_radar.io import check_files, load_all
from receivables_radar.models import DataError
from receivables_radar.report.markdown import money, num, pct
from receivables_radar.sample_data import write_sample

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help='Turn invoice and payment exports into aging, DSO, risk, a cash forecast and a collections worklist.',
)

FORMATS = {'md', 'html', 'json', 'csv', 'xlsx'}


def _version(value: bool) -> None:
    if value:
        typer.echo(f'ar-radar {__version__}')
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[Optional[bool], typer.Option('--version', callback=_version, is_eager=True, help='Show the version and exit.')] = None,
) -> None:
    '''Receivables Radar.'''


def _fail(message: str) -> typer.Exit:
    typer.echo(message, err=True)
    return typer.Exit(1)


def _parse_date(value: str | None) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise typer.BadParameter(f'{value!r} is not a YYYY-MM-DD date') from None


def _run(inv: Path, pay: Path, as_of: str | None, currency: str | None, weeks: int | None = None) -> AnalysisResult:
    cfg = Config(as_of=_parse_date(as_of), forecast_weeks=weeks or 13)
    try:
        invoices, payments, issues = load_all(inv, pay, currency)
        for issue in issues:
            typer.echo(str(issue), err=True)
        return analyze(invoices, payments, cfg)
    except DataError as exc:
        raise _fail('Data error:\n' + '\n'.join(f'  {p}' for p in exc.problems)) from exc


def _all_forecasts(res: AnalysisResult, scenario: str = 'all') -> pd.DataFrame:
    names = [s.name for s in res.config.scenarios] if scenario == 'all' else [scenario]
    return pd.concat([res.forecast(n).assign(scenario=n) for n in names], ignore_index=True)


def _write_csv_bundle(res: AnalysisResult, folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    frames = {
        'kpis': pd.DataFrame([res.kpis()]),
        'aging': res.aging(),
        'ledger': res.ledger,
        'customers': res.customers(),
        'worklist': res.worklist(),
        'forecast': _all_forecasts(res),
    }
    for name, df in frames.items():
        df.to_csv(folder / f'{name}.csv', index=False, lineterminator='\n')


def _emit(res: AnalysisResult, fmt: str, out: Path) -> None:
    try:
        if fmt == 'md':
            out.write_text(res.to_markdown(), encoding='utf-8', newline='\n')
        elif fmt == 'html':
            out.write_text(res.to_html(), encoding='utf-8', newline='\n')
        elif fmt == 'json':
            out.write_text(res.to_json(), encoding='utf-8', newline='\n')
        elif fmt == 'csv':
            _write_csv_bundle(res, out)
        else:
            try:
                res.to_excel(out)
            except ImportError:
                raise _fail("XLSX output needs openpyxl. Install it with: pip install 'receivables-radar[excel]'") from None
    except OSError as exc:
        raise _fail(f'Cannot write {out}: {exc}') from exc


@app.command('analyze')
def analyze_cmd(
    invoices: Annotated[Path, typer.Argument(help='Invoices CSV.')],
    payments: Annotated[Path, typer.Argument(help='Payments CSV.')],
    as_of: Annotated[Optional[str], typer.Option(help='Reporting date YYYY-MM-DD (default: latest date in data).')] = None,
    currency: Annotated[Optional[str], typer.Option(help='Currency to select if the file mixes currencies.')] = None,
    fmt: Annotated[str, typer.Option('--format', help='md, html, json, csv or xlsx.')] = 'md',
    out: Annotated[Optional[Path], typer.Option(help='Write the full report here (a directory for csv).')] = None,
    top: Annotated[int, typer.Option(min=1, help='Customers to chase in the summary.')] = 10,
) -> None:
    '''Print a summary and optionally write a full report.'''
    if fmt not in FORMATS:
        raise typer.BadParameter(f'format must be one of {sorted(FORMATS)}')
    res = _run(invoices, payments, as_of, currency)
    k = res.kpis()
    cur = res.config.currency_code
    total, overdue = money(k['total_outstanding']), money(k['overdue_outstanding'])
    typer.echo(f'Receivables Radar - as of {res.as_of} ({res.invoice_count} invoices, {res.payment_count} payments)')
    for w in res.warnings:
        typer.echo(f'warning: {w}')
    typer.echo(f'\nTotal outstanding : {total} {cur}')
    typer.echo(f'Overdue           : {overdue} {cur} ({pct(k["overdue_share"])})')
    typer.echo(f'DSO {num(k["dso"])}  BPDSO {num(k["bpdso"])}  ADD {num(k["add"])}  CEI {num(k["cei"], 2)}%')
    typer.echo('\nAging')
    for r in res.aging().itertuples():
        typer.echo(f'  {r.bucket:<8}{money(r.amount):>16}{r.invoice_count:>6} inv{pct(r.share):>9}')
    typer.echo('\nBase-case cash, next 4 weeks')
    for r in res.forecast('base').head(4).itertuples():
        typer.echo(f'  week {r.week:<3} {money(r.expected_cash):>16}')
    typer.echo(f'\nTop {top} customers to chase')
    for r in res.worklist().head(top).itertuples():
        typer.echo(f'  {r.customer_name[:28]:<28}{money(r.total_overdue):>14}  {r.risk_tier:<7} {r.suggested_action}')
    if out is not None:
        _emit(res, fmt, out)
        typer.echo(f'\nReport written to {out}')


def _forecast_text(df: pd.DataFrame) -> str:
    lines = []
    for name, grp in df.groupby('scenario', sort=False):
        lines += [f'Scenario: {name}', f'{"week":<16}{"expected cash":>16}{"cumulative":>16}{"invoices":>10}']
        lines += [f'{r.week:<16}{money(r.expected_cash):>16}{money(r.cumulative):>16}{r.invoice_count:>10}' for r in grp.itertuples()]
        lines.append('')
    return '\n'.join(lines)


@app.command()
def forecast(
    invoices: Annotated[Path, typer.Argument(help='Invoices CSV.')],
    payments: Annotated[Path, typer.Argument(help='Payments CSV.')],
    weeks: Annotated[int, typer.Option(min=1, max=104, help='Forecast weeks.')] = 13,
    scenario: Annotated[str, typer.Option(help='base, pessimistic, optimistic or all.')] = 'all',
    as_of: Annotated[Optional[str], typer.Option(help='Reporting date YYYY-MM-DD.')] = None,
    currency: Annotated[Optional[str], typer.Option(help='Currency selector.')] = None,
    fmt: Annotated[str, typer.Option('--format', help='md, json or csv.')] = 'md',
    out: Annotated[Optional[Path], typer.Option(help='Write the forecast to this file.')] = None,
) -> None:
    '''Print or write the weekly cash forecast.'''
    if fmt not in {'md', 'json', 'csv'}:
        raise typer.BadParameter('format must be md, json or csv')
    res = _run(invoices, payments, as_of, currency, weeks)
    names = {s.name for s in res.config.scenarios}
    if scenario != 'all' and scenario not in names:
        raise typer.BadParameter(f'scenario must be one of {sorted(names)} or all')
    df = _all_forecasts(res, scenario)
    if fmt == 'csv':
        text = df.to_csv(index=False, lineterminator='\n')
    elif fmt == 'json':
        text = json.dumps(records(df), indent=2, allow_nan=False)
    else:
        text = _forecast_text(df)
    if out is None:
        typer.echo(text)
        return
    try:
        out.write_text(text, encoding='utf-8', newline='\n')
    except OSError as exc:
        raise _fail(f'Cannot write {out}: {exc}') from exc
    typer.echo(f'Forecast written to {out}')


@app.command()
def dunning(
    invoices: Annotated[Path, typer.Argument(help='Invoices CSV.')],
    payments: Annotated[Path, typer.Argument(help='Payments CSV.')],
    out: Annotated[Path, typer.Option(help='Output directory.')],
    company_name: Annotated[str, typer.Option(help='Sender name.')] = 'Accounts Receivable',
    contact: Annotated[str, typer.Option(help='Contact text for the drafts.')] = '',
    min_days_past_due: Annotated[int, typer.Option(min=1, help='Minimum days past due to include.')] = 1,
    as_of: Annotated[Optional[str], typer.Option(help='Reporting date YYYY-MM-DD.')] = None,
    currency: Annotated[Optional[str], typer.Option(help='Currency selector.')] = None,
) -> None:
    '''Write one plain-text draft per customer (nothing is sent).'''
    res = _run(invoices, payments, as_of, currency)
    drafts = res.dunning_drafts(company_name, contact, min_days_past_due)
    names = draft_filenames(drafts)
    wl = res.worklist().set_index('customer_id')
    try:
        out.mkdir(parents=True, exist_ok=True)
        for cid, text in drafts.items():
            (out / names[cid]).write_text(text, encoding='utf-8', newline='\n')
        with (out / 'dunning_index.csv').open('w', encoding='utf-8', newline='') as fh:
            w = csv.writer(fh, lineterminator='\n')
            w.writerow(['customer_id', 'customer_name', 'file', 'total_overdue', 'oldest_days_past_due', 'risk_tier'])
            for cid in drafts:
                r = wl.loc[cid]
                w.writerow([cid, r['customer_name'], names[cid], f'{r["total_overdue"]:.2f}', int(r['oldest_days_past_due']), r['risk_tier']])
    except OSError as exc:
        raise _fail(f'Cannot write to {out}: {exc}') from exc
    typer.echo(f'Wrote {len(drafts)} draft(s) and dunning_index.csv to {out}')


@app.command()
def validate(
    invoices: Annotated[Path, typer.Argument(help='Invoices CSV.')],
    payments: Annotated[Path, typer.Argument(help='Payments CSV.')],
    currency: Annotated[Optional[str], typer.Option(help='Currency selector.')] = None,
) -> None:
    '''Validate both files and list problems with row numbers.'''
    issues = check_files(invoices, payments, currency)
    for i in issues:
        typer.echo(str(i))
    errors = sum(i.severity == 'error' for i in issues)
    typer.echo(f'{errors} error(s), {len(issues) - errors} warning(s)')
    if errors:
        raise typer.Exit(1)


@app.command()
def sample(
    out: Annotated[Path, typer.Option(help='Output directory.')],
    customers: Annotated[int, typer.Option(min=1, help='Number of customers.')] = 60,
    months: Annotated[int, typer.Option(min=1, help='Months of history.')] = 18,
    seed: Annotated[int, typer.Option(help='Random seed.')] = 42,
) -> None:
    '''Generate synthetic invoices.csv and payments.csv.'''
    try:
        ip, pp = write_sample(out, customers, months, seed)
    except OSError as exc:
        raise _fail(f'Cannot write to {out}: {exc}') from exc
    typer.echo(f'Wrote {ip} and {pp}')
