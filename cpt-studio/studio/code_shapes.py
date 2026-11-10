"""The code-shape helpers that consumers outside the legacy reader call, re-homed (Gemini migration; design/
ADJUDICATION.md R-2 and P-8, FINAL.md 8.3) so that there is one implementation of each, outside the legacy reader's
modules: the act and service-kind labels (from studio/validation/reconcile.py), the member answers that close a
documented service's question (from studio/validation/review_view.py), and the rules by which a code is listed - the
proposal provider's (1 to MAX_LISTED_CODE characters) and a model participant's (a CPT or HCPCS code's shape) - with the
participant's count and sentence (from studio/validation/engine.py).

reconcile.py, review_view.py and engine.py import every name here back, so each of their names is this module's own
object (identity, not a copy) and every existing importer - answers, customer_api, serializers, review, the reports and
the legacy modules themselves - keeps working unchanged. The code below is moved verbatim (tests/
test_readers_dispatch.py pins each definition's source to its text in the legacy module at 070fa0a75, which is the
rollback image's). Its code objects live in this file, so the legacy-call sentinel's deny set (computed from the code
objects of the denied files, interpretation/sentinel.py) does not hold them: a new-path consumer that calls one runs no
code of the legacy reader (D17). They read labels, answers and code values only - never a document's text.
"""
from __future__ import annotations

from typing import Mapping

from studio.validation import checks

# --- act and service-kind labels (moved from studio/validation/reconcile.py) ------------------------------------------

ACT_LABELS = {
    'biopsy': 'forceps biopsy', 'hot_biopsy': 'hot forceps removal', 'snare': 'snare removal', 'emr': 'endoscopic '
    'mucosal resection', 'esd': 'endoscopic submucosal dissection', 'ablation': 'ablation', 'bleeding_control':
    'bleeding control', 'clip': 'clip placement', 'tattoo': 'submucosal tattoo', 'injection': 'submucosal injection',
    'band_ligation': 'band ligation', 'dilation': 'dilation', 'stent': 'stent placement', 'foreign_body':
    'foreign-body removal', 'sphincterotomy': 'sphincterotomy', 'stone_extraction': 'stone removal', 'lithotripsy':
    'lithotripsy', 'cholangioscopy': 'cholangioscopy', 'cannulation': 'cannulation', 'peg': 'gastrostomy (PEG) '
    'placement', 'tube_replacement': 'feeding-tube replacement', 'tube_placement': 'tube placement', 'specimen': 'specimen collection',
    'myotomy': 'myotomy', 'decompression': 'decompression', 'fundoplication': 'transoral fundoplication',
    'capsule_study': 'capsule study', 'manometry': 'manometry', 'ph_monitoring': 'pH / impedance monitoring',
    'rectal_sensation': 'rectal sensation and compliance testing', 'moderate_sedation': 'moderate sedation',
    'fna': 'fine-needle aspiration or biopsy', 'eus_exam': 'endosonographic examination', 'em_visit': 'office visit',
    'drainage': 'drainage', 'stent_removal': 'stent removal', 'stent_exchange': 'stent exchange',
    'pressure_measurement': 'pressure measurement', 'balloon_expulsion': 'balloon expulsion test',
}
SERVICE_LABELS = {'egd': 'upper endoscopy', 'esophagoscopy': 'esophagoscopy', 'poem': 'peroral endoscopic myotomy',
                  'colonoscopy': 'colonoscopy', 'flex_sig': 'flexible sigmoidoscopy', 'eus': 'endoscopic ultrasound',
                  'ercp': 'ERCP', 'enteroscopy': 'enteroscopy', 'capsule': 'capsule endoscopy',
                  'manometry': 'manometry', 'ph_study': 'pH / impedance study', 'anorectal_testing':
                  'anorectal testing', 'feeding_tube': 'feeding-tube procedure', 'office_em': 'office / outpatient '
                  'visit'}


def act_label(kind: str) -> str:
    return ACT_LABELS.get(kind, kind.replace('_', ' '))


def kind_label(kind: str) -> str:
    """A service kind's label, as service_label words a documented service's own kind."""
    return SERVICE_LABELS.get(kind, kind.replace('_', ' '))


# --- the member answers that close a documented service's question (moved from studio/validation/review_view.py) ------

UNAVAILABLE_ANSWERS = ('not_documented', 'cannot_confirm')


def _field(answer, name):
    return answer.get(name) if isinstance(answer, Mapping) else getattr(answer, name, None)


def service_answers(answers) -> set:
    """{(family, fact)} of the current member answers given for a documented service (no code): they close that
    question and change nothing else."""
    return {(str(_field(answer, 'family') or ''), str(_field(answer, 'fact') or '')) for answer in answers or ()
            if not _field(answer, 'code') and _field(answer, 'value') in UNAVAILABLE_ANSWERS}


# --- the code shapes: which code is listed, and a participant's codes that are not (moved from engine.py) ------------

MAX_LISTED_CODE = 10  # what a stored proposal code holds; codes are never truncated


def _listable(code) -> bool:
    return isinstance(code, str) and 0 < len(code) <= MAX_LISTED_CODE


def participant_listable(code) -> bool:
    """Whether the engine reads a model participant's ``code`` at all: only in a code's shape, a CPT code's or an HCPCS
    Level II code's (participants.peer.code_shaped, the one rule by which a peer request and the owner's trace show a
    code as given; refutation round 4, the session's D9). Any other code a participant gives is counted, as the proposal
    provider's codes that cannot be listed are, and never listed: no proposal, alternative, position or summary names
    it, so it reaches neither the reconciliation, the reference retrieval (recorded for proposals only), the page nor
    the reports (shapes-1: 'W/LES(S)' passed _listable, the proposal provider's rule of 1 to MAX_LISTED_CODE characters,
    and reached all of them as a participant's alternative). The proposal provider's own rule is I1's and does not
    change."""
    from studio.participants.peer import code_shaped  # local: the peer module's rule (it imports the HTTP layer)

    return code_shaped(code)


def participant_unlisted_count(entries) -> int:
    """How many of a model participant's code entries - a reading's codes, or a peer review's additional codes - the
    engine does not read (participant_listable): every entry, a value given twice counted twice, as the proposal
    provider's codes that cannot be listed are counted one per code its answer returned. The one count of them
    (refutation round 5, the session's D13): _Harness states it in participants.summary, and a participant row states it
    re-read from the frozen reading (review.unlisted_count) - the row had counted the assessment's record of the reading,
    which keeps one entry per code value, so '45385-59' given twice was 2 in the summary and 1 on the row."""
    return sum(1 for item in entries if not participant_listable(item.code))


def participant_unlisted_codes(count: int, who: str = 'It') -> str:
    """The sentence for codes a model participant gave that the engine does not read (participant_listable): counted,
    never named or truncated. The proposal provider's (checks.unlisted_codes: "empty, or longer than 10 characters") is
    not true of a participant's 'W/LES(S)', 8 characters in no code's shape."""
    pronoun = 'It is' if count == 1 else 'They are'
    return (f'{who} returned {checks.plural(count, "code")} that cannot be listed: not in the shape of a CPT code '
            '(four digits, then a digit or a capital letter) or of an HCPCS Level II code (a capital letter, then four '
            f'digits). {pronoun} not shown and never truncated.')
