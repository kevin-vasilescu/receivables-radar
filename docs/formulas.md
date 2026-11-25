# Formulas

All formulas are implemented as small pure functions and tested against the hand-calculated values below.

## Invoice ledger (`compute_ledger`)

- paid = sum of payments dated on or before as_of; outstanding = max(0, amount - paid); credit_balance = max(0, paid - amount).
- days_past_due = max(0, as_of - due_date) when outstanding > 0, else 0.
- Buckets (`assign_bucket`): 0 is Current, 1-30, 31-60, 61-90, 91 or more is 90+.
- Status: PAID (outstanding 0), OVERDUE (outstanding > 0 and days_past_due > 0), PARTIAL (0 < paid and not overdue), OPEN. A partial and overdue invoice is OVERDUE with partially_paid True.
- settle_date: payments sorted by date then payment_id; the date at which the cumulative total first reaches the amount.

Worked example: INV-1, amount 10000, due 2025-03-01, payment 4000 on 2025-03-10, as_of 2025-04-15. Outstanding is 10000 - 4000 = 6000. Days past due is 31 (to April 1) + 14 = 45, so the bucket is 31-60 and the status is OVERDUE.

## Collections priority (`priority_score`)

priority = outstanding x (1 + days_past_due / 30). Example: 6000 x (1 + 45/30) = 6000 x 2.5 = 15000. A customer's priority is the sum over its overdue invoices.

## Portfolio KPIs

- DSO = ending_AR / billed_in_window x window_days, where billed_in_window sums invoices dated in (as_of - window, as_of].
- BPDSO = current_AR / billed_in_window x window_days.
- ADD = DSO - BPDSO.
- CEI = (beginning_AR + billed - ending_AR) / (beginning_AR + billed - current_AR) x 100, with beginning_AR computed as of as_of - window.

A zero denominator returns None (null in JSON, n/a in text).

Worked example: ending_AR 60000, billed 180000, window 90, current_AR 40000, beginning_AR 50000. DSO = 60000 / 180000 x 90 = 30.0. BPDSO = 40000 / 180000 x 90 = 20.0. ADD = 10.0. CEI = 170000 / 190000 = 89.47%.

## Customer behavior (settled invoices only)

- days_late = settle_date - due_date (negative means early).
- typical_delay_days = median days_late (own history if at least min_history settled invoices, else the portfolio median if the portfolio has at least min_history, else 0).
- avg_days_late = amount-weighted mean of max(days_late, 0).
- on_time_rate = count(days_late <= 0) / count(settled); None is treated as 0.5 in the score.

## Risk score (`risk_score`)

score = 100 x (0.4 x overdue_share + 0.3 x min(avg_days_late / 60, 1) + 0.2 x (1 - on_time_rate) + 0.1 x min(oldest_days_past_due / 90, 1)).

Example: 100 x (0.4 x 0.5 + 0.3 x 0.5 + 0.2 x 0.4 + 0.1 x 0.5) = 100 x (0.20 + 0.15 + 0.08 + 0.05) = 48.0, tier MEDIUM. Tiers: LOW below 25, MEDIUM below 50, HIGH below 75, SEVERE otherwise.

## Cash forecast

- Not yet due: expected_date = max(as_of + 1, due_date + round(typical_delay_days)).
- Overdue: expected_date = as_of + overdue_wait_days[bucket] (14, 21, 30, 45).
- probability by bucket: 0.98, 0.90, 0.75, 0.50, 0.20; expected_cash = outstanding x probability.
- Week w covers as_of + 7(w-1) + 1 through as_of + 7w; later dates go to the beyond horizon row.
- Scenario: shift expected_date by delay_shift (never earlier than as_of + 1) and multiply probability, capped at 1.0.
- uncollectable_risk = sum(outstanding x (1 - probability)).

Worked example: INV-1 above has probability 0.75, so expected cash is 6000 x 0.75 = 4500, expected on 2025-04-15 + 21 = 2025-05-06, which is 21 days out and therefore week 3.
