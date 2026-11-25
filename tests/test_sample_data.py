from pathlib import Path

from receivables_radar import analyze
from receivables_radar.io import load_all
from receivables_radar.sample_data import generate, write_sample


def test_deterministic_by_seed() -> None:
    a1, b1 = generate(20, 6, 7)
    a2, b2 = generate(20, 6, 7)
    assert a1.equals(a2) and b1.equals(b2)
    a3, _ = generate(20, 6, 8)
    assert not a1.equals(a3)


def test_written_files_load_and_analyze(tmp_path: Path) -> None:
    ip, pp = write_sample(tmp_path / 'out', customers=30, months=12, seed=1)
    inv, pay, issues = load_all(ip, pp)
    assert not [i for i in issues if i.severity == 'error']
    res = analyze(inv, pay)
    assert res.kpis()['total_outstanding'] > 0
    assert (res.ledger['credit_balance'] == 0).all()


def test_archetypes_present() -> None:
    inv, pay = generate(60, 18, 42)
    assert inv['customer_id'].nunique() == 60
    counts = pay.groupby('invoice_id').size()
    assert (counts >= 2).any()
    assert set(inv['invoice_id']) - set(pay['invoice_id'])
