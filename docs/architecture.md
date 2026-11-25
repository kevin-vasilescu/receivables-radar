# Architecture

## Data flow

```
invoices.csv, payments.csv
   -> io.py + validation.py   (typed, cleaned tables plus row-numbered issues)
   -> ledger.py               (paid, outstanding, bucket, status, settle_date as of a date)
   -> aging.py / kpis.py / behavior.py
   -> forecast.py / worklist.py / dunning.py
   -> analysis.py             (AnalysisResult facade)
   -> report/ (markdown, html, excel, charts)  and cli.py
```

## Modules

| Module | Responsibility |
|---|---|
| config.py | Frozen `Config` and `Scenario` dataclasses with all defaults |
| models.py | `DataError`, `Issue`, status constants |
| io.py | Reading CSV files; the only module that touches input files |
| validation.py | Pure checks on raw tables; returns cleaned tables and issues |
| ledger.py | `compute_ledger`, `assign_bucket` |
| aging.py | Aging table per bucket |
| kpis.py | `dso`, `best_possible_dso`, `cei`, portfolio KPIs, top customers |
| behavior.py | Per-customer delay, on-time rate, `risk_score`, `risk_tier` |
| forecast.py | `expected_date`, per-invoice forecast, `weekly_forecast` |
| worklist.py | `priority_score`, invoice and customer worklists |
| dunning.py | Jinja drafts, file name sanitising |
| analysis.py | `analyze()` and `AnalysisResult` |
| sample_data.py | Deterministic synthetic data |
| report/ | Markdown, self-contained HTML with inline SVG, XLSX |
| cli.py | Typer commands, exit codes, friendly errors |

## Principles

- Math lives in small pure functions that tests call directly.
- I/O happens only in `io.py`, `cli.py` and the report writers.
- Every sum that feeds an output runs over data in a canonical sort order, so results do not depend on input row order.
- Division by zero yields `None`, never `inf` or `NaN`.
