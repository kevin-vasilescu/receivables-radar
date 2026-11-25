from typing import Any

import pytest

from receivables_radar import analyze
from receivables_radar.dunning import draft_filenames, safe_filename, template_for

from .conftest import make_invoices, make_payments


@pytest.mark.parametrize(('days', 'name'), [(1, 'friendly'), (30, 'friendly'), (31, 'firm'), (60, 'firm'), (61, 'final'), (200, 'final')])
def test_template_choice(days: int, name: str) -> None:
    assert template_for(days) == name


def test_fixture_draft(fixture_result: Any) -> None:
    drafts = fixture_result.dunning_drafts(company_name='Acme Collections', contact='ar@example.test')
    assert list(drafts) == ['ACME']
    text = drafts['ACME']
    assert 'INV-1' in text and '2025-03-01' in text and '45 days past due' in text
    assert '6,000.00' in text
    assert 'Acme Collections' in text and 'ar@example.test' in text
    assert 'INV-2' not in text
    assert 'significantly past their due date' in text


def test_min_days_filter(fixture_result: Any) -> None:
    assert fixture_result.dunning_drafts(min_days_past_due=46) == {}


@pytest.mark.parametrize('name', ['A/B', 'Acme: Ltd', 'Zo\u00eb M\u00fcller GmbH', '\u682a\u5f0f\u4f1a\u793e', 'CON', '..', 'a' * 300, 'x\\y*?'])
def test_safe_filename(name: str) -> None:
    out = safe_filename(name)
    assert out
    assert len(out) <= 82
    assert not set(out) & set('/\\:*?"<>| ')
    assert out not in {'.', '..'}
    assert out.lower() != 'con'


def test_filename_collisions() -> None:
    names = draft_filenames({'a/b': '', 'a:b': '', 'A_B': ''})
    assert len({n.lower() for n in names.values()}) == 3


def test_tone_by_bucket() -> None:
    inv = make_invoices(
        [('A', 'C1', '2025-01-01', '2025-01-10', 10.0), ('Z', 'C3', '2025-03-01', '2025-03-05', 1.0)]
    )
    d = analyze(inv, make_payments([])).dunning_drafts()
    # as_of = 2025-03-01: C1 is 50 days past due -> firm
    assert 'significantly' in d['C1']
