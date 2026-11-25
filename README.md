# receivables-radar

Turn invoice and payment exports into aging, DSO, customer risk, a 13-week cash forecast and a prioritized collections worklist in one command.

[![CI](https://github.com/kevin-vasilescu/receivables-radar/actions/workflows/ci.yml/badge.svg)](https://github.com/kevin-vasilescu/receivables-radar/actions/workflows/ci.yml)
[![CodeQL](https://github.com/kevin-vasilescu/receivables-radar/actions/workflows/codeql.yml/badge.svg)](https://github.com/kevin-vasilescu/receivables-radar/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)

## Why this exists

Founders, bookkeepers and collections teams can export invoices and payments as CSV from almost any accounting tool, but turning those files into "who owes what, who pays when, who to chase first" usually means a spreadsheet rebuilt every month. This tool does it deterministically, offline, in one command.

## Features

- Aging buckets, overdue share and top-customer concentration.
- DSO, best possible DSO, average days delinquent and CEI.
- Customer payment behavior and a 0-100 risk score with tiers.
- 13-week cash forecast with base, pessimistic and optimistic scenarios.
- Prioritized collections worklist and plain-text dunning drafts (nothing is ever sent).
- Reports as Markdown, self-contained HTML (inline SVG, no external requests), JSON, CSV and XLSX.

## Installation

```
pip install git+https://github.com/kevin-vasilescu/receivables-radar.git
pip install "receivables-radar[excel] @ git+https://github.com/kevin-vasilescu/receivables-radar.git"
```

From source: `git clone https://github.com/kevin-vasilescu/receivables-radar && cd receivables-radar && pip install -e .`

## 60-second quickstart

```
ar-radar sample --out ./data
ar-radar analyze ./data/invoices.csv ./data/payments.csv --format html --out report.html
ar-radar forecast ./data/invoices.csv ./data/payments.csv --scenario base
ar-radar dunning ./data/invoices.csv ./data/payments.csv --out ./drafts
```

Captured output of `ar-radar analyze` on the default sample (60 customers, 18 months, seed 42; 1067 invoices, 1118 payments), top-10 list shortened here:

```
Receivables Radar - as of 2025-12-31 (1067 invoices, 1118 payments)

Total outstanding : 507,686.66 USD
Overdue           : 282,484.21 USD (55.6%)
DSO 56.1  BPDSO 24.9  ADD 31.2  CEI 73.35%

Aging
  Current       225,202.45    65 inv    44.4%
  1-30           78,874.40    15 inv    15.5%
  31-60          39,475.34    11 inv     7.8%
  61-90          17,524.23     6 inv     3.5%
  90+           146,610.24    46 inv    28.9%

Base-case cash, next 4 weeks
  week 1          17,905.59
  week 2          90,129.37
  week 3          64,462.92
  week 4          55,191.36

Top 10 customers to chase
  Lumen Foods 27                   76,245.98  HIGH    Final notice, consider hold on new orders / legal review
  Juniper Labs 41                  38,822.75  HIGH    Final notice, consider hold on new orders / legal review
  ...
```

Those figures come from the first working build of the code; the sample generator is deterministic, so the same command should reproduce them. Treat any difference as a bug.

## Python API

```python
from receivables_radar import analyze, load_invoices, load_payments, Config

invoices = load_invoices('invoices.csv')
payments = load_payments('payments.csv', invoices)
result = analyze(invoices, payments, Config())
print(result.kpis())
print(result.forecast('pessimistic'))
print(result.worklist().head(10))
```

## CLI reference

| Command | Purpose |
|---|---|
| `ar-radar analyze INVOICES PAYMENTS` | Summary plus full report (`--format md,html,json,csv,xlsx --out PATH`) |
| `ar-radar forecast INVOICES PAYMENTS` | Weekly cash forecast (`--weeks`, `--scenario`) |
| `ar-radar dunning INVOICES PAYMENTS --out DIR` | One draft per customer plus dunning_index.csv |
| `ar-radar validate INVOICES PAYMENTS` | Row-numbered errors and warnings |
| `ar-radar sample --out DIR` | Deterministic synthetic data |

See [docs/usage.md](docs/usage.md) for options, exit codes and output schemas.

## Input format

- invoices.csv: invoice_id, customer_id, customer_name (optional), invoice_date, due_date, amount, currency (optional).
- payments.csv: payment_id (optional), invoice_id, payment_date, amount. Partial payments are allowed and the file may be header-only.

## How the metrics work

Every formula, with a worked example, is in [docs/formulas.md](docs/formulas.md). The default as-of date is the latest invoice or payment date in the data, so results are reproducible. Design decisions are in [docs/decisions.md](docs/decisions.md).

## Performance

`benchmarks/bench.py` times `analyze()` on 200,000 synthetic invoices. No timing numbers are published here yet because the benchmark has not been run on a documented machine. Run it locally and open a pull request with your results.

## Development

```
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
make test
```

## Limitations

- Collection probabilities and wait times are heuristic defaults; tune them per business through `Config`.
- One currency per run.
- No interest, late fees or credit notes beyond overpayment tracking.
- Not a substitute for accounting advice.
- The first commit of this repository was produced without a local toolchain: ruff, mypy and the Hypothesis tests had not been run locally before the push. See CHANGELOG and decisions.

## Roadmap

- Golden-file regression tests.
- Per-customer probability calibration from history.
- Credit note support.
- Multi-currency with explicit rates.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

MIT, see [LICENSE](LICENSE).
