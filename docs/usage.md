# Usage

## Commands

```
ar-radar sample --out DIR [--customers 60] [--months 18] [--seed 42]
ar-radar validate INVOICES PAYMENTS [--currency CODE]
ar-radar analyze INVOICES PAYMENTS [--as-of YYYY-MM-DD] [--currency CODE] [--format md|html|json|csv|xlsx] [--out PATH] [--top N]
ar-radar forecast INVOICES PAYMENTS [--weeks 13] [--scenario base|pessimistic|optimistic|all] [--format md|json|csv] [--out PATH]
ar-radar dunning INVOICES PAYMENTS --out DIR [--company-name NAME] [--contact TEXT] [--min-days-past-due N]
ar-radar --version
```

Exit codes: 0 success, 1 validation or data error, 2 usage error.

## Input files

invoices.csv columns: invoice_id, customer_id, customer_name (optional), invoice_date, due_date, amount, currency (optional). Dates are YYYY-MM-DD.

payments.csv columns: payment_id (optional), invoice_id, payment_date, amount. The file may have only the header row.

## JSON schema (`analyze --format json`)

Top-level keys, in order: meta, warnings, kpis, aging, top_customers, customers, risk_tiers, forecast, worklist.

- meta: as_of, currency, invoice_count, payment_count.
- kpis: total_outstanding, overdue_outstanding, overdue_share, credit_balance_total, billed_in_window, beginning_ar, current_ar, dso, bpdso, add, cei, uncollectable_risk. Undefined values are null.
- aging rows: bucket, amount, invoice_count, share.
- customers rows: customer_id, customer_name, outstanding, overdue_outstanding, oldest_days_past_due, settled_count, typical_delay_days, history_quality, avg_days_late, on_time_rate, risk_score, risk_tier.
- forecast: an object keyed by scenario; each value is a list of rows with week, week_start, week_end, expected_cash, cumulative, invoice_count. The last row has week equal to beyond horizon and null dates.
- worklist rows: customer_id, customer_name, total_overdue, oldest_days_past_due, invoice_count, risk_tier, priority_score, suggested_action.

## CSV output

`analyze --format csv --out DIR` writes kpis.csv, aging.csv, ledger.csv, customers.csv, worklist.csv and forecast.csv. `forecast --format csv` writes one file with an extra scenario column.

## Python API

```python
from receivables_radar import analyze, load_invoices, load_payments, Config

invoices = load_invoices('invoices.csv')
payments = load_payments('payments.csv', invoices)
result = analyze(invoices, payments, Config())
print(result.kpis()['dso'])
print(result.worklist().head())
```
