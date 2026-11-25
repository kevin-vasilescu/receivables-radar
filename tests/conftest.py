from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from receivables_radar import analyze
from receivables_radar.io import load_all

FIXTURES = Path(__file__).parent / 'fixtures'


def make_invoices(rows: list[tuple[str, str, str, str, float]]) -> pd.DataFrame:
    '''Rows are (invoice_id, customer_id, invoice_date, due_date, amount).'''
    df = pd.DataFrame(rows, columns=['invoice_id', 'customer_id', 'invoice_date', 'due_date', 'amount'])
    df['customer_name'] = df['customer_id']
    df['invoice_date'] = pd.to_datetime(df['invoice_date'])
    df['due_date'] = pd.to_datetime(df['due_date'])
    return df


def make_payments(rows: list[tuple[str, str, str, float]]) -> pd.DataFrame:
    '''Rows are (payment_id, invoice_id, payment_date, amount).'''
    df = pd.DataFrame(rows, columns=['payment_id', 'invoice_id', 'payment_date', 'amount'])
    df['payment_date'] = pd.to_datetime(df['payment_date'])
    return df


@pytest.fixture
def fixture_tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    inv, pay, _ = load_all(FIXTURES / 'invoices.csv', FIXTURES / 'payments.csv')
    return inv, pay


@pytest.fixture
def fixture_result(fixture_tables: tuple[pd.DataFrame, pd.DataFrame]) -> Any:
    return analyze(*fixture_tables)


@pytest.fixture
def worked() -> tuple[pd.DataFrame, pd.DataFrame, date]:
    inv = make_invoices([('INV-1', 'ACME', '2025-02-01', '2025-03-01', 10000.0)])
    pay = make_payments([('P1', 'INV-1', '2025-03-10', 4000.0)])
    return inv, pay, date(2025, 4, 15)
