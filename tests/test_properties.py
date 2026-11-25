from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from .properties import build, check_all, check_extra_payment_never_increases

inv_st = st.lists(
    st.tuples(st.integers(0, 3), st.integers(0, 200), st.integers(0, 90), st.integers(1, 1_000_000)),
    min_size=1,
    max_size=12,
)
pay_st = st.lists(st.tuples(st.integers(0, 50), st.integers(0, 300), st.integers(1, 1_000_000)), max_size=20)


@settings(max_examples=60, deadline=None)
@given(inv_st, pay_st)
def test_invariants(inv_specs: Any, pay_specs: Any) -> None:
    inv, pay = build(inv_specs, pay_specs)
    check_all(inv, pay)


@settings(max_examples=40, deadline=None)
@given(inv_st, pay_st, st.integers(1, 1_000_000))
def test_extra_payment_never_increases_outstanding(inv_specs: Any, pay_specs: Any, extra: int) -> None:
    inv, pay = build(inv_specs, pay_specs)
    check_extra_payment_never_increases(inv, pay, extra)
