# Decisions

Each entry: context, decision, consequence.

## Default as_of
Context: the spec says the latest date across both files. Decision: use the latest `invoice_date` and `payment_date`; due dates are ignored because a future due date is not an observed event. Consequence: as_of never moves ahead of real activity.

## Rounding of the expected delay
Context: `round(typical_delay_days)` for a median such as 2.5. Decision: Python `round` (half to even). Consequence: deterministic, documented.

## Scenario shifts and the next-day floor
Context: the optimistic scenario shifts dates by -5 days. Decision: after shifting, a date is never earlier than as_of + 1 day. Consequence: no forecast cash lands in the past.

## Portfolio history threshold
Context: customers with fewer than min_history settled invoices use the portfolio median. Decision: the portfolio median is trusted only if the portfolio has at least min_history settled invoices; otherwise delay is 0 and history_quality is `none`, with a warning. Consequence: a tiny portfolio never drives the forecast.

## CSV output format
Context: one CSV cannot hold several tables. Decision: `analyze --format csv --out DIR` writes kpis, aging, ledger, customers, worklist and forecast CSV files into a directory; `forecast --format csv` writes one file with a scenario column. Consequence: stable, flat schemas.

## Float tolerance
Context: payments are floats. Decision: amounts below half a cent are treated as zero and money is rounded to 2 decimals. Consequence: a 0.001 residue does not keep an invoice open.

## Overdue Current boundary
Context: an invoice due on as_of. Decision: days_past_due is 0 and the bucket is Current. Consequence: matches the spec.

## Tooling in CI
Context: this repository was created from a session without a local terminal, so ruff and mypy could not be run before the first push. Decision: CI runs ruff check (rules E and F) and mypy as separate steps, and mypy is allowed to fail until it is verified green. Consequence: tests are the blocking gate; tighten later.
