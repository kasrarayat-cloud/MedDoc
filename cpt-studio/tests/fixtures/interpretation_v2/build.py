"""The failure-class, borderline, checklist and refutation fixtures of design v2 (docs/gemini-migration/FINAL-V2.md 9.5;
step 6c of 8.1): the builder that writes ``documents/<case>.txt`` and ``answers/<case>.json`` from the cases in
cases_s4.py, cases_checklist.py and cases_refutation.py, and ``MANIFEST.json``. TEXT-ONLY and SYNTHETIC: every
document is written for these fixtures (fictional clinicians, no patient), and each is checked, as written and
whitespace-stripped, against the acceptance owner's DEV-EXCLUSION hashes (hashes only; the acceptance set itself is
never opened). Run it from cpt-studio/ with the project's settings::

    DJANGO_SETTINGS_MODULE=cptstudio.settings python -c "import django; django.setup(); \\
        from tests.fixtures.interpretation_v2 import build; build.write()"

tests/v2/test_failure_classes.py asserts that the committed files equal what this builder writes (so the two cannot
drift), then runs each case's variants through the pipeline: extract_read, the checks, claims, appraise_read, settle,
store.row_v2, store.textfree_v2, facts.effective and engine/assess.

**A case** (9.5's table): one document; pass 1's RIGHT filing and the class's attested or constructed MISFILING; and
three pass-2 answers, each a rule over the claim set's facts (the request's claim ids are assigned by claims.py's seeded
order, which may change until the first recording, DECISIONS D202, so an answer names facts, never claim ids):
- (i) correct: the right filing, every real claim supported and attached, every control rejected (a faithful reading);
- (ii) caught: the misfiling, the claims of the misfiled facts (``caught``) contradicted - or qualified - and their
  controls supported (a faithful reading of a wrong claim), every other claim faithful; for an omission, pass 2 lists
  the act or statement no card describes (``unlisted_ii``);
- (iii) shared misreading: the misfiling, every claim supported and every control rejected - pass 2 shares pass 1's
  error. Its outcome is RECORDED in RESIDUALS.json as a residual and never counted as a pass (9.5). A case whose shared
  misreading is not (ii)'s misfiling gives (iii) a filing of its own (``shared``): an omission pass 2 has no claim to
  contradict, kept only as (iii) (DECISIONS D241: GI Note #8's tattoo filed with no place and no lesion), with the facts
  it leaves out (``shared_omits``: established under (i), absent under (iii)).
A NAMED residual (``named``) is an outcome a ruling keeps as built and names beside a variant's documented outcome (D244:
Q-N8b, the tattoo denial at the bed of a saline lift read as a contradiction), or one an open design question leaves
there: it is asserted as built, so a change is seen, recorded in RESIDUALS.json, and never counted as a pass.
The expected outcomes of (i) and (ii) are written here from the design (4.3, 4.4, 4.6-4.8, Appendix C) and the rulings
(D180-D252), each with its reason; they are never copied from what the engine returns."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from tests.fixtures.interpretation_v2.dsl import DOS, Note

HERE = Path(__file__).resolve().parent
APP = HERE.parents[2]
DEV_EXCLUSION = APP / 'docs' / 'gemini-migration' / 'acceptance-a1' / 'DEV-EXCLUSION.sha256'
VARIANTS = ('i', 'ii', 'iii')
STATUSES = {'R': 'ready', 'H': 'needs_clarification', 'X': 'excluded'}


@dataclass
class Case:
    """One fixture case (module docstring). ``codes``: the proposal provider's selected codes, each (code, words): its
    evidence the unit holding ``words``, or with ``exact`` set the words themselves (a citation C-10 can read).
    ``expect``: per variant, code -> (status, item fact or None, item kind or None, reason). ``caught``: the misfiled
    facts, 'attribute@object/index', whose claims (ii) contradicts. ``variants``: the variants this case has (9.5: the
    checklist and refutation cases (i) and (ii), (iii) where the finding names a shared misreading). ``shared``: (iii)'s
    own filing when its shared misreading is not (ii)'s misfiling, and ``shared_omits`` the facts it leaves out (module
    docstring). ``named``: per variant, the named residuals beside its documented outcome, each (id, where, fact,
    subject, naming): where 'service' (a service question) or a code (one of its held facts), naming the ruling that
    keeps it or the open question that leaves it."""
    id: str
    kind: str
    refs: tuple
    title: str
    text: str
    build: Callable[[Note, bool], dict]
    codes: tuple
    expect: dict
    caught: tuple = ()
    checked: tuple = ()
    variants: tuple = VARIANTS
    ii_verdict: str = 'contradicts'
    ii_qualifiers: tuple = ()
    ii_rules: tuple = ()
    unlisted: tuple = ()
    unlisted_ii: tuple = ()
    member: tuple | None = ('office', 'established')
    date_of_service: str | None = DOS
    considerations: dict = field(default_factory=dict)
    services: dict = field(default_factory=dict)
    acts: dict = field(default_factory=dict)
    subjects: dict = field(default_factory=dict)
    held: dict = field(default_factory=dict)
    answers: tuple = ()
    listed: dict = field(default_factory=dict)
    known: dict = field(default_factory=dict)
    header: dict = field(default_factory=dict)
    source: str = ''
    settled: dict = field(default_factory=dict)
    provenance: str = 'synthetic: written for this fixture'
    note: str = ''
    shared: Callable[[Note], dict[str, Any]] | None = None
    shared_omits: tuple[str, ...] = ()
    named: dict[str, tuple[tuple[str, str, str, str, str], ...]] = field(default_factory=dict)


def exclusion_hashes() -> set:
    with open(DEV_EXCLUSION, encoding='ascii') as handle:
        return {line.strip() for line in handle if line.strip()}


def sha256(data: str) -> str:
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


def pass2(case: Case) -> dict:
    """The three pass-2 answers of a case, as rules over the claim set (module docstring)."""
    faithful = {'default': 'faithful', 'verdicts': [], 'unlisted': [dict(entry) for entry in case.unlisted]}
    caught = {'default': 'faithful', 'verdicts': [], 'unlisted': [dict(entry) for entry in case.unlisted]
              + [dict(entry) for entry in case.unlisted_ii]}
    for key in case.caught:
        caught['verdicts'].append({'fact': key, 'role': 'claim', 'verdict': case.ii_verdict,
                                   'qualifiers': list(case.ii_qualifiers)})
        caught['verdicts'].append({'fact': key, 'role': 'control', 'verdict': 'supports', 'qualifiers': []})
    caught['verdicts'] += [dict(rule) for rule in case.ii_rules]
    out = {'i': faithful, 'ii': caught, 'iii': faithful}
    return {variant: out[variant] for variant in case.variants}


def known_entry(pinned: tuple) -> dict:
    """A known defect's pin: (status, item, request) or (status, item, request, considerations) - what the engine gives
    TODAY, never the expectation (the case's ``expect`` keeps the design's; tests/v2/test_failure_classes.py's
    KnownDefectTests asserts that one, red until the request is repaired)."""
    status, item, request, *rest = pinned
    entry = {'status': STATUSES[status], 'item': item, 'request': request}
    if rest:
        entry['considerations'] = list(rest[0])
    return entry


def expected(case: Case) -> dict:
    out: dict = {}
    for variant, codes in case.expect.items():
        out[variant] = {code: {'status': STATUSES[status], 'item': item, 'item_kind': kind, 'why': why}
                        for code, (status, item, kind, why) in codes.items()}
    return out


def named_entries(case: Case) -> dict[str, list[dict[str, str]]]:
    """A case's named residuals, per variant (Case.named), as the answers file writes them."""
    return {variant: [{'id': rid, 'where': where, 'fact': fact, 'subject': subject, 'naming': naming}
                      for rid, where, fact, subject, naming in entries]
            for variant, entries in case.named.items()}


def render(case: Case) -> dict:
    note = Note(case.text, **case.header)
    filings = {'correct': case.build(note, False)}
    if any(variant in case.variants for variant in ('ii', 'iii')):
        filings['misfiled'] = case.build(note, True)
    if case.shared is not None:
        if 'iii' not in case.variants:
            raise ValueError(f'{case.id}: a shared filing without a variant (iii)')
        filings['shared'] = case.shared(note)
    extra: dict[str, Any] = {}
    if case.shared is not None:
        extra['shared_omits'] = list(case.shared_omits)
    if case.named:
        extra['named'] = named_entries(case)
    proposals = []
    for code, words, *exact in case.codes:
        if exact and exact[0]:
            start, end = note.at(words)
        else:
            unit = note.unit(note.u(words))
            start, end = unit.start, unit.end
        proposals.append({'code': code, 'start': start, 'end': end})
    return {'case': case.id, 'kind': case.kind, 'refs': list(case.refs), 'title': case.title,
            'document': f'documents/{case.id}.txt', 'document_sha256': sha256(case.text),
            'date_of_service': case.header.get('dos', case.date_of_service),
            'member': list(case.member) if case.member else None,
            'pass1': filings, 'pass2': pass2(case), 'proposals': proposals, 'caught': list(case.caught),
            'checked': list(case.checked),
            'settled': case.settled, 'expect': expected(case), 'variants': list(case.variants),
            'considerations': {variant: {code: list(values) for code, values in codes.items()}
                               for variant, codes in case.considerations.items()},
            'services': {variant: [list(item) for item in items] for variant, items in case.services.items()},
            'acts': {variant: {code: list(acts) for code, acts in codes.items()} for variant, codes in case.acts.items()},
            'subjects': {variant: dict(codes) for variant, codes in case.subjects.items()},
            'held': {variant: {code: list(facts) for code, facts in codes.items()} for variant, codes in case.held.items()},
            'answers': [dict(answer) for answer in case.answers],
            'listed': {variant: [[reason, list(events), mark] for reason, events, mark in items]
                       for variant, items in case.listed.items()},
            'known': {variant: {code: known_entry(pinned) for code, pinned in codes.items()}
                      for variant, codes in case.known.items()},
            'provenance': case.provenance, 'note': case.note, **extra}


def all_cases() -> list:
    from tests.fixtures.interpretation_v2 import cases_checklist, cases_refutation, cases_s4
    cases = list(cases_s4.CASES) + list(cases_checklist.CASES) + list(cases_refutation.CASES)
    ids = [case.id for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate case ids')
    return cases


def dumps(data: Any) -> str:
    return json.dumps(data, indent=1, sort_keys=True, ensure_ascii=True) + '\n'


def files() -> dict:
    """Every file the builder writes, path -> text."""
    excluded = exclusion_hashes()
    out: dict = {}
    manifest = []
    for case in all_cases():
        rendered = render(case)
        out[f'documents/{case.id}.txt'] = case.text
        out[f'answers/{case.id}.json'] = dumps(rendered)
        checks = {'as_written': sha256(case.text) not in excluded,
                  'whitespace_stripped': sha256(case.text.strip()) not in excluded}
        manifest.append({'case': case.id, 'kind': case.kind, 'refs': list(case.refs), 'title': case.title,
                         'document_sha256': sha256(case.text), 'answers_sha256': sha256(out[f'answers/{case.id}.json']),
                         'variants': list(case.variants), 'provenance': case.provenance,
                         'not_on_exclusion_list': checks})
    out['MANIFEST.json'] = dumps({'fixtures': 'interpretation_v2', 'design': 'FINAL-V2 9.5', 'cases': manifest,
                                  'exclusion_list_entries': len(excluded)})
    return out


def write() -> None:
    for name, text in files().items():
        path = HERE / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
