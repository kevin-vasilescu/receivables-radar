'''Shared types.'''

from __future__ import annotations

from dataclasses import dataclass


class DataError(Exception):
    '''Raised when input data is invalid.'''

    def __init__(self, problems: list[str]) -> None:
        super().__init__('\n'.join(problems))
        self.problems = problems


@dataclass(frozen=True)
class Issue:
    '''A validation finding.

    Attributes:
        severity: error or warning.
        file: Name of the input (invoices or payments).
        row: 1-based file row including the header, or None.
        message: Human-readable description.
    '''

    severity: str
    file: str
    row: int | None
    message: str

    def __str__(self) -> str:
        where = f'{self.file}' + (f' row {self.row}' if self.row else '')
        return f'{self.severity.upper()}: {where}: {self.message}'


PAID, PARTIAL, OPEN, OVERDUE = 'PAID', 'PARTIAL', 'OPEN', 'OVERDUE'
