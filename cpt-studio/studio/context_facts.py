"""Stored context facts: the predicates every reader asks of one, and the note texts they read.

Re-homed from studio/gi/context.py (Gemini migration, FINAL.md sections 3.1 and 4.4) so that there is one
implementation, outside the legacy reader. studio/gi/context.py imports every name here back, so each of its names is
this module's own object (identity, not a copy), and every existing importer - jobs, progress, answers, checks, review,
reports, serializers, reconcile, engine and ops.install - keeps working unchanged. The code below is moved verbatim.

These read a fact's origin and the note it keeps, never a document's text: a call to one is a call to a stored-fact
utility, never into the legacy reader (D17). is_member_conflict, charge_date_problem and charge_date_own take a Fact or
a stored context fact (a mapping); documented_values reads a Fact's attributes. The writers their docstrings name
(_fact, _charge_block_asks, merge_user_values) stay in studio/gi/context.py. This module imports nothing from studio.gi.
"""
from __future__ import annotations

import re
from typing import Optional

# The sixth refutation's dates-n6-1 and n6-3 to n6-6: this sentence says only what is true of the document whatever the
# guards decided. It quotes the region's first line rather than calling it the last heading (a billing heading outside
# the closed class may follow it, and a guard may take a ledger row for one), each stated line whole rather than up to its
# date ("10/04/2026 through 10/06/2026", "(cancelled)", "entered in error"), and says the date "is read from" its line, not
# that it is the document's own (the installed reading may have taken a planned procedure's date) or that the lines state
# a date of service (a filing deadline's label reads as one).
CHARGE_DATE_NOTE = ("The lines from {heading} to the document's end state {block}, while {value} is read from {own}. Those "
                    "lines may record this encounter or another occurrence, so the date is asked; a member's answer is "
                    'taken only when it is {value}.')
_CHARGE_NOTE_HEAD = CHARGE_DATE_NOTE.split('{', 1)[0]
# GI round 4 (D1, D2; package PD): the same question where a wide or worded own label states another day than the date
# the installed reading sends - read and answered by the same readers (charge_date_problem, charge_date_own,
# charge_question_day), so a member's answer is taken only when it is that date, and every reader reads that date
WIDE_DATE_ASK_NOTE = ('The document also states {wide}, while {value} is read from {own}. Those lines may record this '
                      "encounter or another occurrence, so the date is asked; a member's answer is taken only when it "
                      'is {value}.')
_WIDE_NOTE_HEAD = WIDE_DATE_ASK_NOTE.split('{', 1)[0]
_CHARGE_NOTE_REST = '. Those lines may record this encounter or another occurrence'
_CHARGE_NOTE_OWN = re.compile(r', while (\d{4}-\d{2}-\d{2}) is read from ')


def charge_date_problem(fact) -> Optional[str]:
    """What a date question the note's closing charge block asks (_charge_block_asks) states as its problem: the note's
    first sentence, naming what the block's lines state as theirs and the date the installed reading reads - or None for
    any other fact. Every reader that words that question or labels it asks here, where its note is written
    (checks._date_problem, reports, review, serializers).
    ``fact`` is a Fact or a stored context fact (a mapping); the last marker is the note's own, whatever a quote holds."""
    get = fact.get if isinstance(fact, dict) else (lambda name, default=None: getattr(fact, name, default))
    note = str(get('note', '') or '')
    if get('origin') != 'conflict' or not note.startswith((_CHARGE_NOTE_HEAD, _WIDE_NOTE_HEAD)) \
            or _CHARGE_NOTE_REST not in note:  # GI round 4 (package PD): a wide or worded label's question too
        return None
    return note[:note.rindex(_CHARGE_NOTE_REST)]


def charge_date_own(fact) -> Optional[str]:
    """The document's own date (ISO) that a date question the note's closing charge block asks keeps in its note - the
    date the installed reading sends, the only member's answer it takes (merge_user_values) - or None for any other fact.
    The last match is the note's own, whatever a quote before it holds."""
    problem = charge_date_problem(fact)
    found = list(_CHARGE_NOTE_OWN.finditer(problem)) if problem else []
    return found[-1].group(1) if found else None


DOCUMENT_CONFLICT_NOTE = 'Conflicting documented values: '


def documented_values(fact) -> tuple[str, ...]:
    """The values a document-internal conflict lists (its note, written by _fact), or () for any other fact."""
    note = str(getattr(fact, 'note', '') or '')
    if getattr(fact, 'origin', None) != 'conflict' or not note.startswith(DOCUMENT_CONFLICT_NOTE) or not note.endswith('.'):
        return ()
    return tuple(v for v in note[len(DOCUMENT_CONFLICT_NOTE):-1].split(', ') if v)


USER_CONFLICT_NOTE = ('Encounter metadata entered by a workspace member gives {user}; the document gives {document}. '
                      'Both are kept and neither is used until they agree: correct the metadata, clear it, or add an '
                      'addendum to the document.')
_USER_CONFLICT_PREFIX = USER_CONFLICT_NOTE.split('{', 1)[0]
# GI round 2 (the occurrence investigation's R4 (ii)): a member's date equal to a date this reader reads in the document
# as another occurrence's or another document's, or as possibly one (_ElsewhereSpan: fr-di:3, df-d:4), and never as
# this encounter's, is held as before - but USER_CONFLICT_NOTE said 'the document gives “Date of service: 10/14/2026”.
# Both are kept and neither is used until they agree', as if the two dates differed. This note says why it is held. It
# speaks of what this service READS, never of everything the document states: the same day may also be written in a
# form it does not read ("Date of service: 11/04/26" beside "Next procedure date: 11/04/2026"). It opens with
# USER_CONFLICT_NOTE's prefix, by which every reader - and a rollback to 2b82889f - knows a member conflict.
USER_ELSEWHERE_NOTE = (_USER_CONFLICT_PREFIX + "{user}; this service reads that date in the document as another "
                       "occurrence's or another document's date, or as possibly one ({document}), and not as this "
                       "encounter's date of service. Both are kept and neither is used: correct the metadata, clear it, "
                       'or add an addendum to the document.')
# Fix round (dates lens, F1): a member's date equal to an own labelled date that states the document's date of birth
# (_BirthSpan) - held, and said to be so, never as if it were another occurrence's date. Same prefix.
USER_BIRTH_NOTE = (_USER_CONFLICT_PREFIX + "{user}; the document gives that date as the patient's date of birth, and "
                   "this service does not read the date-of-service label stating it ({document}) as this encounter's "
                   'date of service. Both are kept and neither is used: correct the metadata, clear it, or add an '
                   'addendum to the document.')


def is_member_conflict(fact) -> bool:
    """Whether ``fact`` is a member's encounter metadata that differs from the document's single value
    (merge_user_values), as opposed to values that conflict within the document itself. Every reader that words a
    conflict asks this one question, so a member's value is never described as conflicting documentation. ``fact`` is
    a Fact or a stored context fact (a mapping)."""
    if fact is None:
        return False
    get = fact.get if isinstance(fact, dict) else (lambda name, default=None: getattr(fact, name, default))
    return get('origin') == 'conflict' and str(get('note', '') or '').startswith(_USER_CONFLICT_PREFIX)
