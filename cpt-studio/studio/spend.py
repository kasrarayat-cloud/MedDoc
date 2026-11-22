"""What a coding run cost, as the operator console reads it (owner direction 2026-11-22, DECISIONS D395; refutation r2,
figures-1): one reading for every console page - the Encounters list, an encounter's rounds and the Spending page - so a
run never shows two different money figures.

A run's known cost is its priced usage once it settled (succeeded or failed); a run that sent nothing, was cancelled, or
was refused by the API before answering cost nothing. Every other run - still being sent, of unknown outcome, or settled
with usage that cannot be priced - has no known cost and counts apart, at the worst case it was reserved at. That is
studio.jobs._held_cost's own reading of a run against the per-document ceiling, with its two parts kept apart (the tests
hold the two readers to each other), apart from one choice for display: a reserved figure that is not a finite,
non-negative amount reads as the whole ceiling, where _held_cost would pass it on.

Nothing here writes, and nothing on the coding path reads this module.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from . import jobs, models

Run = models.ProviderRun
SETTLED = (Run.SUCCEEDED, Run.FAILED)


def reserve(run) -> Decimal:
    """The worst case a run with no known cost counts at: the amount it was reserved at (scope worst_usd), or the whole
    per-document ceiling when nothing readable says what it could cost."""
    try:
        value = Decimal(str((run.scope or {})['worst_usd']))
    except (KeyError, TypeError, InvalidOperation):
        return jobs.ceiling_usd()
    return value if value.is_finite() and value >= 0 else jobs.ceiling_usd()


def run_spend(run):
    """(cost, None) when the run's cost is known, else (None, its worst case)."""
    if run.state in (Run.NOT_SENT, Run.CANCELLED) or (run.state in SETTLED and not run.sent):
        return Decimal(0), None
    if run.state in SETTLED:
        priced = jobs.run_cost(run)
        if priced is not None:
            return priced, None
        if run.state == Run.FAILED and (run.http_status or 0) >= 400 and not run.usage:
            return Decimal(0), None
    return None, reserve(run)
