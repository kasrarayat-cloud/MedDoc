"""H3: the second, independent review of the truth tables, and the judge that reads a tree's observations against them.

THE TRUTH TABLES ARE PROVISIONAL AUTHOR EXPECTATIONS. NO QUALIFIED GI CODER HAS REVIEWED THEM. The second review below is
a separate pass by the harness's author with its own rules (a coder's questions, asked of each kind of document), not an
independent coder: every cell it disputes becomes MAY and is never judged, and every table records that no coder has
reviewed it (``review.coder_reviewed`` is False).

A cell is MUST (a safety property: one violation blocks), SHOULD (a reading the round asks for; ratcheted, never
blocking on its own) or MAY (careful coders could differ: never judged).
"""
from __future__ import annotations

import collections

REVIEW_PASS = 'gi4-truth-review@1'
CODER_NOTE = ('Provisional author expectations. No qualified GI coder has reviewed these truth tables; the second review '
              'is a separate pass by the same author, and every cell it disputes is MAY (never judged).')
NOT_TODAY = ('negated', 'historical', 'planned', 'cancelled')
FAMILIES = ('gi.egd', 'gi.colonoscopy', 'gi.flex_sig', 'gi.eus', 'gi.ercp', 'gi.office_em')
POSITIVE = ('performed', 'incomplete')


def _review_rules(doc: dict) -> dict:
    """{cell name: reason} for every cell the second review disputes (a coder's question about this kind of document)."""
    kind, axes, truth = doc['kind'], doc['axes'], doc['truth']
    disputed = {}
    for c in truth['cells']:
        name = c['cell']
        if name == 'date.own-read[out]':
            disputed[name] = ('whether a date label outside the installed vocabulary is sent without a question is the '
                              "owner's PD2 decision, not a reading")
        if name == 'date.answer-held[F]' and truth.get('own_label') == 'none':
            disputed[name] = ('the document labels no date of service of its own: refusing every member date would '
                              'leave the encounter without one; coders differ on what a member may supply')
    if kind == 'around' and axes.get('signed') == 'on_procedure_day':
        for name in ('date.send', 'date.answer-held[N]'):
            disputed[name] = ('the note is signed on the planned day: it may have been written on that day, so its own '
                              'date may be the planned one')
    if kind == 'seeded' and axes.get('seed_of') == 'h4-02':
        for family in ('gi.egd', 'gi.flex_sig'):
            disputed[f'extent.read[{family}]'] = ('an extent stated only in a grid: whether it makes the examination '
                                                  'complete is an open coder question (synthesis E)')
    if kind == 'em' and axes.get('mode') == 'addendum_time':
        disputed['em.time-read'] = 'a time written under an addendum dated another day (the judge: arguable)'
    if kind == 'procedure' and axes.get('insertion') == 'absent' and axes.get('head') == 'headless':
        disputed[f"status.performed[{axes['family']}]"] = 'no insertion, landmark or act is stated'
    return disputed


def _independent_allowed(doc: dict):
    """The review's own reading of which member answers may be taken (None where it reads none independently)."""
    kind, axes, truth = doc['kind'], doc['axes'], doc['truth']
    answers = truth['answers']
    if kind == 'procedure':
        return sorted({answers['D']} | ({answers['L']} if axes['ledger'] == 'differ' else set()))
    if kind in ('em', 'bidirectional', 'records', 'around'):
        return [answers['D']]
    return None


def review(doc: dict) -> dict:
    """The document with its truth table reviewed: disputed cells set to MAY (their author level kept)."""
    truth = doc['truth']
    disputed = _review_rules(doc)
    allowed = _independent_allowed(doc)
    if allowed is not None and sorted(allowed) != sorted(truth['allowed_answers']):
        disputed['date.send'] = f'the review reads the allowed answers as {allowed}, the author as ' \
                                f'{truth["allowed_answers"]}'
    cells = []
    for c in truth['cells']:
        if c['cell'] in disputed and c['level'] != 'MAY':
            c = dict(c, level='MAY', author_level=c['level'], disputed=disputed[c['cell']])
        cells.append(c)
    out = dict(doc)
    out['truth'] = dict(truth, cells=cells, review={
        'pass': REVIEW_PASS, 'coder_reviewed': False, 'note': CODER_NOTE,
        'disputed': sorted(c['cell'] for c in cells if c.get('disputed'))})
    return out


def table_counts(docs) -> dict:
    """Documents and cells per level (MAY split into author-MAY and review-disputed)."""
    counts = collections.Counter()
    kinds = collections.Counter()
    for doc in docs:
        kinds[doc['kind']] += 1
        for c in doc['truth']['cells']:
            counts[c['level']] += 1
            if c.get('disputed'):
                counts['MAY (disputed by the review)'] += 1
    return {'documents': sum(kinds.values()), 'by_kind': dict(sorted(kinds.items())), 'cells': dict(sorted(counts.items()))}


# --- judging observations --------------------------------------------------------------------------------------------

def _f(obs, family):
    return (obs.get('routing') or {}).get(family)


def _services(obs, family):
    return [s for s in obs.get('inventory') or () if s['family'] == family]


def _sends_ok(sends, allowed):
    return sends in ('DATELESS', 'HELD', None) or sends in allowed


def evaluate(c: dict, doc: dict, obs: dict) -> bool:
    """Whether observation ``obs`` meets cell ``c`` of ``doc``'s truth table."""
    name, truth = c['cell'], doc['truth']
    head, _, arg = name.partition('[')
    arg = arg.rstrip(']')
    answers = obs.get('answers') or {}
    if head == 'date.send':
        allowed = c['expect']['allowed']
        return _sends_ok(obs['sent_initial'], allowed) and all(_sends_ok(a['sends'], allowed) for a in answers.values())
    if head == 'date.no-send-before-answer':
        return obs['sent_initial'] in ('DATELESS', 'HELD', None)
    if head == 'date.answer-held':
        return arg not in answers or not answers[arg]['taken']
    if head == 'date.answer-own-taken':
        return obs['sent_initial'] == truth['date'] or bool((answers.get('D') or {}).get('taken'))
    if head == 'date.own-read':
        return obs['sent_initial'] == truth['date']
    act = ''
    family = arg
    if head.startswith('act.'):
        family, act = arg.rsplit('.', 1)
    if arg and family not in FAMILIES:  # a cell naming no family would pass vacuously
        raise KeyError(f'cell {name} names no known family')
    f = _f(obs, family)
    if head == 'status.not-denied':
        return (f is None or f['status'] not in NOT_TODAY) and all(
            s['status'] not in NOT_TODAY for s in _services(obs, family))
    if head == 'status.performed':
        return f is not None and f['status'] == 'performed'
    if head == 'status.not-performed':
        return (f is None or (f['status'] not in POSITIVE and not set(f['mentions']) & set(POSITIVE))) and all(
            s['status'] not in POSITIVE for s in _services(obs, family))
    extent = ((f or {}).get('facts') or {}).get('extent')
    if head == 'extent.read':
        return bool(extent) and extent[1] == 'document' and any(t in str(extent[0]).lower() for t in c['expect'])
    if head == 'extent.never-false-incomplete':
        return not (extent and str(extent[0]).startswith('incomplete'))
    if head in ('act.not-another-occurrence', 'act.today-read', 'act.no-phantom'):
        done = any(a[0] == act and a[1] == 'performed' for s in _services(obs, family) for a in s['acts'])
        return done if head == 'act.today-read' else not done
    if head == 'binding.lower-not-on-upper':
        regions = set(truth.get('lower_regions') or ())
        return not any(x[2] in regions for s in _services(obs, 'gi.egd') for x in s['acts'] + s['lesions'])
    em = _f(obs, 'gi.office_em')
    facts = (em or {}).get('facts') or {}
    if head == 'em.time-not-another-occurrence':
        return str((facts.get('time_minutes') or [''])[0]) != c['expect']
    if head == 'em.not-office-basis':
        return not (em and em['status'] == 'performed' and 'em_basis' in facts)
    if head == 'em.time-read':
        return str((facts.get('time_minutes') or [''])[0]) == c['expect']
    if head == 'em.mdm-read':
        return str((facts.get('mdm_level') or [''])[0]) == c['expect']
    if head == 'em.no-level-from-shared-decision':
        return 'mdm_level' not in facts
    raise KeyError(f'no judge for cell {name}')


def judge(docs: dict, observations: dict) -> dict:
    """{doc id: [(cell, level, ok)]} for every MUST and SHOULD cell (MAY cells are never judged)."""
    out = {}
    for doc_id, doc in docs.items():
        obs = observations.get(doc_id)
        rows = []
        for c in doc['truth']['cells']:
            if c['level'] == 'MAY':
                continue
            if obs is None or 'error' in obs:
                rows.append((c['cell'], c['level'], False))
                continue
            rows.append((c['cell'], c['level'], evaluate(c, doc, obs)))
        out[doc_id] = rows
    return out


def rates(judged: dict, docs: dict) -> dict:
    """Pass counts per (level, property) and per (kind, level)."""
    by_prop = collections.defaultdict(lambda: [0, 0])
    by_kind = collections.defaultdict(lambda: [0, 0])
    for doc_id, rows in judged.items():
        for name, level, ok in rows:
            prop = name.split('[')[0]
            by_prop[(level, prop)][0] += ok
            by_prop[(level, prop)][1] += 1
            by_kind[(docs[doc_id]['kind'], level)][0] += ok
            by_kind[(docs[doc_id]['kind'], level)][1] += 1
    return {'by_property': {f'{lv} {p}': v for (lv, p), v in sorted(by_prop.items())},
            'by_kind': {f'{k} {lv}': v for (k, lv), v in sorted(by_kind.items())}}


def differential(base: dict, head: dict) -> dict:
    """Per property: fixed / regressed / both-fail counts (MUST regressions are the gate)."""
    out = collections.defaultdict(collections.Counter)
    examples = collections.defaultdict(list)
    for doc_id, rows in base.items():
        head_rows = {(n, i): ok for i, (n, _, ok) in enumerate(head.get(doc_id, []))}
        for i, (name, level, ok) in enumerate(rows):
            other = head_rows.get((name, i))
            if other is None:
                continue
            key = f'{level} {name.split("[")[0]}'
            verdict = 'both-pass' if ok and other else 'both-fail' if not ok and not other else (
                'fixed' if other else 'regressed')
            out[key][verdict] += 1
            if verdict in ('regressed', 'fixed') and len(examples[(key, verdict)]) < 3:
                examples[(key, verdict)].append(doc_id)
    return {'counts': {k: dict(v) for k, v in sorted(out.items())},
            'examples': {f'{k} {v}': ids for (k, v), ids in sorted(examples.items())}}
