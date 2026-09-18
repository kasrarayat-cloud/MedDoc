"""A check that cannot exercise its own condition must report MISSING COVERAGE, never success.

Four checks written on 2026-09-18 passed because of what was ABSENT from their inputs rather than
because the thing they watched was true. One of them — the migration proof, whose every fixture
encounter was a draft — reached production and the activation then failed against the live database.

The shape is always the same: an assertion that is correct, sitting behind an input that never
reaches it. A test like that does not merely fail to catch the defect; it reports that the defect is
absent, which is worse than having no test, because somebody acts on the green.

So the precondition stops being an assumption and becomes a declared, failing assertion:

    from exercised import requires_input

    requires_input(Encounter.objects.filter(status='finalized').exists(),
                   'a finalized encounter, or the immutability guard is never reached')

This module deliberately has no imports and no dependency on Django or unittest, so the same call
works in the Django suite, in the plain-unittest ops suite, and in an operational script.
"""


class MissingCoverage(AssertionError):
    """Raised when a check's required input is absent, so its result would be meaningless."""


def requires_input(condition, what):
    """Assert the INPUT a check needs, before asserting the behaviour it watches.

    `what` names the missing input and why its absence empties the check — it is read by whoever
    meets the failure, so it says what to add, not merely that something is wrong.
    """
    if not condition:
        raise MissingCoverage(
            'MISSING COVERAGE: ' + what + '. The assertions below cannot fail without it, so a pass '
            'here would report that a defect is absent when nothing looked for it.')
    return True


def requires_distinct(values, what, minimum=2):
    """A probe whose inputs are all the same answers nothing; require real variety.

    The activator's surface-agreement check was written `any(x is None) or all(x is not None)`, true
    for every input. A test that only ever feeds it uniform inputs cannot expose that.
    """
    distinct = {repr(value) for value in values}
    if len(distinct) < minimum:
        raise MissingCoverage(
            'MISSING COVERAGE: ' + what + '. Only ' + str(len(distinct)) + ' distinct input(s) were '
            'exercised, so the check was never asked to DISCRIMINATE and could pass while being a '
            'tautology.')
    return True
