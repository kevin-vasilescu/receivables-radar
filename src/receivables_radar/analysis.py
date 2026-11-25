'''Orchestration: from cleaned tables to an AnalysisResult.'''

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from receivables_radar import behavior, forecast, kpis, worklist
from receivables_radar.aging import aging_table
from receivables_radar.config import Config
from receivables_radar.dunning import build_drafts
from receivables_radar.ledger import compute_ledger
from receivables_radar.models import DataError


def records(df: pd.DataFrame) -> list[dict[str, Any]]:
    '''Convert a frame to JSON-safe records (ISO dates, None for NaN).

    Args:
        df: Any frame.

    Returns:
        List of row dictionaries.
    '''
    out: list[dict[str, Any]] = []
    for row in df.to_dict(orient='records'):
        clean: dict[str, Any] = {}
        for k, v in row.items():
            if isinstance(v, pd.Timestamp):
                v = v.date().isoformat()
            elif isinstance(v, date):
                v = v.isoformat()
            elif v is pd.NaT or v is None:
                v = None
            elif hasattr(v, 'item'):
                v = v.item()
            if isinstance(v, float) and not math.isfinite(v):
                v = None
            clean[str(k)] = v
        out.append(clean)
    return out


@dataclass
class AnalysisResult:
    '''Everything computed for one run.

    Attributes:
        config: Settings used, with as_of resolved.
        as_of: Reporting date.
        ledger: Invoice ledger frame.
        invoice_count: Invoices loaded.
        payment_count: Payments loaded.
        warnings: Human-readable warnings.
    '''

    config: Config
    as_of: date
    ledger: pd.DataFrame
    invoice_count: int
    payment_count: int
    warnings: list[str] = field(default_factory=list)
    _invoices: pd.DataFrame = field(repr=False, default_factory=pd.DataFrame)
    _payments: pd.DataFrame = field(repr=False, default_factory=pd.DataFrame)

    def aging(self) -> pd.DataFrame:
        '''Aging table (amount, invoice_count, share per bucket).'''
        return aging_table(self.ledger, self.config)

    def kpis(self) -> dict[str, float | None]:
        '''Portfolio KPIs, including DSO, BPDSO, ADD and CEI.'''
        return kpis.compute_kpis(self._invoices, self._payments, self.ledger, self.as_of, self.config)

    def top_customers(self, n: int = 10) -> pd.DataFrame:
        '''Top n customers by outstanding with share of total.'''
        return kpis.top_customers(self.ledger, n)

    def customers(self) -> pd.DataFrame:
        '''Per-customer behaviour and risk.'''
        return behavior.customer_behavior(self.ledger, self.config)

    def invoice_forecast(self, scenario: str = 'base') -> pd.DataFrame:
        '''Expected cash per open invoice under a scenario.'''
        return forecast.invoice_forecast(self.ledger, self.customers(), self.as_of, self.config.scenario(scenario), self.config)

    def forecast(self, scenario: str = 'base') -> pd.DataFrame:
        '''Weekly cash forecast, including the beyond-horizon row.'''
        return forecast.weekly_forecast(self.invoice_forecast(scenario), self.as_of, self.config.forecast_weeks)

    def uncollectable_risk(self) -> float:
        '''Expected uncollectable amount.'''
        return forecast.uncollectable_risk(self.ledger, self.config)

    def worklist(self) -> pd.DataFrame:
        '''Customer-level collections worklist.'''
        return worklist.customer_worklist(self.ledger, self.customers(), self.config)

    def invoice_worklist(self) -> pd.DataFrame:
        '''Overdue invoices by priority.'''
        return worklist.invoice_worklist(self.ledger)

    def dunning_drafts(self, company_name: str = 'Accounts Receivable', contact: str = '', min_days_past_due: int = 1) -> dict[str, str]:
        '''Plain-text dunning drafts keyed by customer_id.'''
        return build_drafts(self.ledger, self.config, company_name, contact, min_days_past_due)

    def risk_tiers(self) -> pd.DataFrame:
        '''Customer count and outstanding per risk tier.'''
        c = self.customers()
        g = c.groupby('risk_tier').agg(customers=('customer_id', 'count'), outstanding=('outstanding', 'sum'))
        return g.reindex(['LOW', 'MEDIUM', 'HIGH', 'SEVERE'], fill_value=0).reset_index()

    def to_dict(self) -> dict[str, Any]:
        '''Full machine-readable report.'''
        return {
            'meta': {
                'as_of': self.as_of.isoformat(),
                'currency': self.config.currency_code,
                'invoice_count': self.invoice_count,
                'payment_count': self.payment_count,
            },
            'warnings': list(self.warnings),
            'kpis': {**self.kpis(), 'uncollectable_risk': self.uncollectable_risk()},
            'aging': records(self.aging()),
            'top_customers': records(self.top_customers()),
            'customers': records(self.customers()),
            'risk_tiers': records(self.risk_tiers()),
            'forecast': {s.name: records(self.forecast(s.name)) for s in self.config.scenarios},
            'worklist': records(self.worklist()),
        }

    def to_json(self) -> str:
        '''Full report as a JSON string.'''
        return json.dumps(self.to_dict(), indent=2, allow_nan=False)

    def to_markdown(self) -> str:
        '''Full report as Markdown.'''
        from receivables_radar.report.markdown import render_markdown

        return render_markdown(self)

    def to_html(self) -> str:
        '''Full report as a single self-contained HTML document.'''
        from receivables_radar.report.html import render_html

        return render_html(self)

    def to_excel(self, path: str | Path) -> None:
        '''Write the report as an XLSX workbook (requires openpyxl).

        Args:
            path: Destination file.
        '''
        from receivables_radar.report.excel import write_excel

        write_excel(self, Path(path))


def analyze(invoices: pd.DataFrame, payments: pd.DataFrame, config: Config | None = None) -> AnalysisResult:
    '''Run the full analysis.

    Args:
        invoices: Cleaned invoices from load_invoices.
        payments: Cleaned payments from load_payments.
        config: Settings. as_of defaults to the latest invoice or payment date.

    Returns:
        The analysis result.

    Raises:
        DataError: If there are no invoices.
    '''
    cfg = config or Config()
    if invoices.empty:
        raise DataError(['invoices: no data rows'])
    latest_pay = payments['payment_date'].max() if len(payments) else pd.NaT
    as_of = cfg.as_of or max(d for d in [invoices['invoice_date'].max(), latest_pay] if pd.notna(d)).date()
    cfg = replace(cfg, as_of=as_of)
    warns: list[str] = []
    late_inv = int((invoices['invoice_date'] > pd.Timestamp(as_of)).sum())
    late_pay = int((payments['payment_date'] > pd.Timestamp(as_of)).sum()) if len(payments) else 0
    if late_inv:
        warns.append(f'{late_inv} invoice(s) dated after {as_of} were ignored')
    if late_pay:
        warns.append(f'{late_pay} payment(s) dated after {as_of} were ignored')
    ledger = compute_ledger(invoices, payments, as_of, cfg)
    over = int((ledger['credit_balance'] > 0).sum())
    if over:
        warns.append(f'{over} invoice(s) are overpaid; credit_balance is reported separately')
    settled = int((ledger['status'] == 'PAID').sum())
    if settled < cfg.min_history:
        warns.append(f'only {settled} settled invoice(s) (min_history {cfg.min_history}); forecast assumes zero payment delay')
    return AnalysisResult(cfg, as_of, ledger, len(invoices), len(payments), warns, invoices, payments)
