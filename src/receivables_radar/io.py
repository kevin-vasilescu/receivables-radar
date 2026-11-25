'''CSV loading.'''

from __future__ import annotations

from pathlib import Path

import pandas as pd

from receivables_radar.models import DataError, Issue
from receivables_radar.validation import raise_on_errors, validate_invoices, validate_payments


def _read(path: str | Path) -> pd.DataFrame:
    p = Path(path)
    if not p.is_file():
        raise DataError([f'file not found: {p}'])
    try:
        return pd.read_csv(p, dtype=str, keep_default_na=False, na_values=[''], encoding='utf-8-sig')
    except pd.errors.EmptyDataError:
        return pd.DataFrame()
    except (pd.errors.ParserError, UnicodeDecodeError) as exc:
        raise DataError([f'cannot read {p}: {exc}']) from exc


def _read_payments(path: str | Path) -> pd.DataFrame:
    raw = _read(path)
    if len(raw.columns) == 0:
        raise DataError(['payments: file is empty; expected a header row'])
    return raw


def load_invoices(path: str | Path, currency: str | None = None) -> pd.DataFrame:
    '''Load and validate an invoices CSV.

    Args:
        path: CSV file path.
        currency: Currency to select if the file mixes currencies.

    Returns:
        Cleaned invoices with typed columns.

    Raises:
        DataError: If the file is missing or has validation errors.
    '''
    df, issues = validate_invoices(_read(path), currency)
    raise_on_errors(issues)
    return df.reset_index(drop=True)


def load_payments(path: str | Path, invoices: pd.DataFrame | None = None) -> pd.DataFrame:
    '''Load and validate a payments CSV.

    Args:
        path: CSV file path.
        invoices: Cleaned invoices used to drop unknown references. When omitted no cross-checks are applied.

    Returns:
        Cleaned payments with typed columns.

    Raises:
        DataError: If the file is missing or has validation errors.
    '''
    df, issues = validate_payments(_read_payments(path), invoices)
    raise_on_errors(issues)
    return df


def load_all(
    invoices_path: str | Path, payments_path: str | Path, currency: str | None = None
) -> tuple[pd.DataFrame, pd.DataFrame, list[Issue]]:
    '''Load both files and cross-validate them.

    Args:
        invoices_path: Invoices CSV path.
        payments_path: Payments CSV path.
        currency: Optional currency selector.

    Returns:
        Cleaned invoices, cleaned payments and the load-time warnings.

    Raises:
        DataError: If either file has errors.
    '''
    inv = load_invoices(invoices_path, currency)
    pay, issues = validate_payments(_read_payments(payments_path), inv)
    raise_on_errors(issues)
    return inv, pay, issues


def check_files(invoices_path: str | Path, payments_path: str | Path, currency: str | None = None) -> list[Issue]:
    '''Validate both files and return every issue without raising.

    Args:
        invoices_path: Invoices CSV path.
        payments_path: Payments CSV path.
        currency: Optional currency selector.

    Returns:
        All errors and warnings found.
    '''
    try:
        inv_raw = _read(invoices_path)
        pay_raw = _read_payments(payments_path)
    except DataError as exc:
        return [Issue('error', 'files', None, p) for p in exc.problems]
    inv, issues = validate_invoices(inv_raw, currency)
    has_errors = any(i.severity == 'error' for i in issues)
    _, pay_issues = validate_payments(pay_raw, None if has_errors else inv)
    if has_errors:
        pay_issues = [i for i in pay_issues if i.severity == 'error']
    return issues + pay_issues
