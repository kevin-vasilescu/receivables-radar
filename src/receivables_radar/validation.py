'''Validation of invoice and payment tables.'''

from __future__ import annotations

import pandas as pd

from receivables_radar.models import DataError, Issue

INVOICE_REQUIRED = ['invoice_id', 'customer_id', 'invoice_date', 'due_date', 'amount']
PAYMENT_REQUIRED = ['invoice_id', 'payment_date', 'amount']


def _dates(raw: pd.Series, name: str, file: str, issues: list[Issue]) -> pd.Series:
    parsed = pd.to_datetime(raw, format='%Y-%m-%d', errors='coerce')
    for i in parsed.index[parsed.isna()]:
        issues.append(Issue('error', file, int(i) + 2, f'unparsable {name} {raw[i]!r}, expected YYYY-MM-DD'))
    return parsed


def _amounts(raw: pd.Series, file: str, issues: list[Issue]) -> pd.Series:
    num = pd.to_numeric(raw, errors='coerce')
    bad = num.isna() | (num <= 0) | (num == float('inf'))
    for i in num.index[bad]:
        issues.append(Issue('error', file, int(i) + 2, f'amount must be a positive number, got {raw[i]!r}'))
    return num.astype(float)


def _missing_columns(df: pd.DataFrame, required: list[str], file: str) -> list[Issue]:
    return [Issue('error', file, 1, f'missing required column {c!r}') for c in required if c not in df.columns]


def validate_invoices(raw: pd.DataFrame, currency: str | None = None) -> tuple[pd.DataFrame, list[Issue]]:
    '''Validate and normalise a raw invoices table.

    Args:
        raw: Table read with all columns as strings.
        currency: Currency code to select when the file mixes currencies.

    Returns:
        The cleaned table and the list of issues found.
    '''
    issues = _missing_columns(raw, INVOICE_REQUIRED, 'invoices')
    if issues:
        return raw, issues
    if raw.empty:
        return raw, [Issue('error', 'invoices', None, 'file has no data rows')]
    df = raw.copy()
    for col in ('invoice_id', 'customer_id'):
        df[col] = df[col].fillna('').str.strip()
        for i in df.index[df[col] == '']:
            issues.append(Issue('error', 'invoices', int(i) + 2, f'empty {col}'))
    dup = df['invoice_id'].ne('') & df['invoice_id'].duplicated(keep='first')
    for i in df.index[dup]:
        issues.append(Issue('error', 'invoices', int(i) + 2, f'duplicate invoice_id {df.at[i, "invoice_id"]!r}'))
    df['invoice_date'] = _dates(df['invoice_date'], 'invoice_date', 'invoices', issues)
    df['due_date'] = _dates(df['due_date'], 'due_date', 'invoices', issues)
    for i in df.index[df['due_date'] < df['invoice_date']]:
        issues.append(Issue('error', 'invoices', int(i) + 2, 'due_date is before invoice_date'))
    df['amount'] = _amounts(df['amount'], 'invoices', issues)
    if 'customer_name' not in df.columns:
        df['customer_name'] = df['customer_id']
    name = df['customer_name'].fillna('').str.strip()
    df['customer_name'] = name.where(name != '', df['customer_id'])
    if 'currency' in df.columns:
        cur = df['currency'].fillna('').str.strip().str.upper()
        present = sorted(set(cur[cur != '']))
        if len(present) > 1 and currency is None:
            issues.append(Issue('error', 'invoices', None, f'mixed currencies {present}; choose one with --currency'))
        elif currency is not None and present:
            code = currency.upper()
            if code not in present:
                issues.append(Issue('error', 'invoices', None, f'currency {code} not found in {present}'))
            else:
                df = df[cur == code].copy()
    return df, issues


def validate_payments(raw: pd.DataFrame, invoices: pd.DataFrame | None) -> tuple[pd.DataFrame, list[Issue]]:
    '''Validate and normalise a raw payments table against cleaned invoices.

    Args:
        raw: Table read with all columns as strings.
        invoices: Cleaned invoices table, or None to skip cross-checks.

    Returns:
        The cleaned payments (unknown invoices and duplicate payment ids removed) and the issues.
    '''
    issues = _missing_columns(raw, PAYMENT_REQUIRED, 'payments')
    if issues:
        return raw, issues
    df = raw.copy()
    if 'payment_id' not in df.columns:
        df['payment_id'] = ''
    df['payment_id'] = df['payment_id'].fillna('').str.strip()
    df['invoice_id'] = df['invoice_id'].fillna('').str.strip()
    df['payment_date'] = _dates(df['payment_date'], 'payment_date', 'payments', issues)
    df['amount'] = _amounts(df['amount'], 'payments', issues)
    if issues:
        return df, issues
    dup = df['payment_id'].ne('') & df['payment_id'].duplicated(keep='first')
    for i in df.index[dup]:
        issues.append(Issue('warning', 'payments', int(i) + 2, f'duplicate payment_id {df.at[i, "payment_id"]!r} dropped'))
    df = df[~dup]
    if invoices is None:
        return df.reset_index(drop=True), issues
    known = df['invoice_id'].isin(set(invoices['invoice_id']))
    for i in df.index[~known]:
        issues.append(Issue('warning', 'payments', int(i) + 2, f'unknown invoice_id {df.at[i, "invoice_id"]!r} ignored'))
    df = df[known]
    inv_date = invoices.set_index('invoice_id')['invoice_date']
    for i in df.index[df['payment_date'] < df['invoice_id'].map(inv_date)]:
        issues.append(Issue('warning', 'payments', int(i) + 2, 'payment dated before its invoice date'))
    return df.reset_index(drop=True), issues


def raise_on_errors(issues: list[Issue]) -> None:
    '''Raise DataError if any issue is an error.

    Args:
        issues: Findings from validation.

    Raises:
        DataError: If at least one issue has severity error.
    '''
    errors = [str(i) for i in issues if i.severity == 'error']
    if errors:
        raise DataError(errors)
