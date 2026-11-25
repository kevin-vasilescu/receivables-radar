'''Configuration for an analysis run.'''

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class Scenario:
    '''A forecast scenario.

    Attributes:
        name: Scenario identifier.
        delay_shift: Days added to every expected collection date.
        probability_multiplier: Factor applied to collection probabilities.
    '''

    name: str
    delay_shift: int
    probability_multiplier: float


def _default_scenarios() -> tuple[Scenario, ...]:
    return (
        Scenario('base', 0, 1.0),
        Scenario('pessimistic', 10, 0.9),
        Scenario('optimistic', -5, 1.05),
    )


@dataclass(frozen=True)
class Config:
    '''Analysis settings.

    Attributes:
        as_of: Reporting date. None means the latest date in the data.
        bucket_edges: Upper edges of the 1-30, 31-60 and 61-90 buckets.
        bucket_probabilities: Probability of eventual collection per bucket.
        overdue_wait_days: Days from as_of until expected collection per overdue bucket.
        dso_window_days: Window used for DSO, BPDSO and CEI.
        min_history: Settled invoices needed to trust a customer's own history.
        forecast_weeks: Number of weekly forecast rows.
        scenarios: Forecast scenarios.
        currency_code: Display currency.
    '''

    as_of: date | None = None
    bucket_edges: tuple[int, int, int] = (30, 60, 90)
    bucket_probabilities: dict[str, float] = field(
        default_factory=lambda: {'Current': 0.98, '1-30': 0.90, '31-60': 0.75, '61-90': 0.50, '90+': 0.20}
    )
    overdue_wait_days: dict[str, int] = field(default_factory=lambda: {'1-30': 14, '31-60': 21, '61-90': 30, '90+': 45})
    dso_window_days: int = 90
    min_history: int = 3
    forecast_weeks: int = 13
    scenarios: tuple[Scenario, ...] = field(default_factory=_default_scenarios)
    currency_code: str = 'USD'

    @property
    def buckets(self) -> list[str]:
        '''Ordered bucket labels derived from the edges.'''
        a, b, c = self.bucket_edges
        return ['Current', f'1-{a}', f'{a + 1}-{b}', f'{b + 1}-{c}', f'{c}+']

    def scenario(self, name: str) -> Scenario:
        '''Look up a scenario by name.

        Args:
            name: Scenario name.

        Returns:
            The matching scenario.

        Raises:
            KeyError: If no scenario has that name.
        '''
        for s in self.scenarios:
            if s.name == name:
                return s
        raise KeyError(f'unknown scenario: {name}')
