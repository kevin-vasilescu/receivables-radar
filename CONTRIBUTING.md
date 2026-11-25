# Contributing

1. Fork and create a virtual environment: `python -m venv .venv`.
2. Install: `pip install -e ".[dev]"` and `pre-commit install`.
3. Run `make lint typecheck test` before opening a pull request.
4. For any formula change, add a test whose expected value is calculated by hand (show the arithmetic in a comment) and update docs/formulas.md.
5. Use Conventional Commit messages (feat, fix, docs, test, ci, chore).

Never attach real customer data to issues; use `ar-radar sample` to build a reproduction.
