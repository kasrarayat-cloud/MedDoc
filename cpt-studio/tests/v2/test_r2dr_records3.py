"""Repair round r2d, builder records3 (DECISIONS D301 RBRX-1). TEXT-ONLY and SYNTHETIC: the notes below are written
here (no real patient), and nothing is sent.

RBRX-1 - whenever findings are made for an inventory version recorded before a reading changed, every check
AMENDMENT-2 4.3.3 changed reads as that label was recorded: under gemini-inventory@2 the K rules (D297 R2RX-1) and L1 -
the relation sides L1 judges (a supported relation alone; a contradicted one, pass 1's own contradiction, states no
value), the dates it reads into an act's relation (a supported date's words alone) and the condition on which an act
with no relation of its own judges the occasion it inherits (a supported date alone) - each through
consistency._Reading (D193's clause, as recorded). gemini-inventory@3 (the current path, the default) reads every
relation and date a slot states or offers, as before. So a recording made under gemini-inventory@2 re-settles, and its
pass-2 request rebuilds, as the recorded tree made them.

- R2DRRecordedL1ReadingTests: for each of the three readings, inputs the rule must change (gemini-inventory@2 as
  recorded; @3 and no label as before) and boundaries it must leave alone (a supported relation or date is read under
  both labels; a denial under neither).
- R2DRRecordedL1PinTests: GRID - every state of the act's date slot (silent, supported, negated, contradicted) against
  every state of its own date relation and of the occasion it inherits - checked for gemini-inventory@2 equals the
  RECORDED tree's Checked (0a5f3283b, the tree gemini-inventory@2 produced: RECORDED_FIXTURE, written there by
  ``write_recorded``, the fixture's owning function, which refuses a tree whose checks take a label): L1's findings and
  literals in full, and the whole Checked's findings, failed links, literals, K8 groups and reference date by sha256.
  gemini-inventory@3 only adds L1 findings to the recorded ones. And K_GRIDS - K2's existence arm, K6, K7 and K8, which
  AMENDMENT-2 changed only through the merged view of an overfilled slot, on single written facts in every state -
  checked for either label equals the recorded tree's whole Checked.
- R2DRRecordedRowsTests: the row tests/v2/test_failure_classes.pipeline writes at the recorded labels (its checks made
  for gemini-inventory@2, a faithful pass 2) equals the recorded tree's row, claim set and code outcomes - for a
  colonoscopy whose snare act's date is pass 1's own contradiction (45385 READY, as recorded) and the controls, and for
  the GRID note's change inputs.
- R2DRRecordedRequestTests: the dormant (Gemini) adapter's pass-2 request, built from the RECORDED tree's pass-1 request
  and answer with the checks made for gemini-inventory@2, is the request the recorded tree built (its canonical
  sha256); the request the checks make for gemini-inventory@3 differs on the act-date input and not on the control.

Each GRID answer is read under gemini-events@2 (extract_read's default, the recorded pass-1 label: an overfilled slot
is refused whole there) and checked by contract/checks.check, the orchestration settle and claims read."""
from __future__ import annotations

import copy
import hashlib
import inspect
import itertools
import json
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from studio import interpretation
from studio.interpretation.contract import checks, geometry, jsonschema
from studio.interpretation.contract import extract_read as xr
from studio.interpretation.contract import extract_schema as xs

INV2 = interpretation.INVENTORY_VERSION_V2
INV3 = getattr(interpretation, 'INVENTORY_VERSION_V3', 'gemini-inventory@3')  # the recorded tree names no @3
RECORDED_FIXTURE = (Path(__file__).resolve().parents[1] / 'fixtures' / 'interpretation_v2' / 'r2dr_records3'
                    / 'recorded_l1.json')
MISMATCH = 'literal_mismatch'
ON, EARLIER, LATER = 'on_date_of_service', 'earlier_date', 'later_date'

# --- the synthetic EGD note and its answer ---------------------------------------------------------------------------

R2DR_EGD = ('SYNTHETIC EGD REPORT\n'                                                                       # S1
            'Date of service: 05/20/2031\n'                                                                  # S2
            'Findings: The gastroscope was advanced to the duodenum.\n'                                      # S3
            'A 5 mm polyp in the gastric antrum was removed with a cold snare on 05/20/2031 (listed 03/01/2031).\n'
            'A clip was placed at the polypectomy site.\n'                                                   # S5
            'The prior EGD was on 03/01/2031.\n')                                                            # S6
DOS_WORDS, PRIOR_WORDS = '05/20/2031', '03/01/2031'  # S4 states both; S6 states the prior date alone
DOS, PRIOR = '2031-05-20', '2031-03-01'


def src(unit: str, words: str = '', link: str = 'statement') -> dict:
    return {'units': [unit], 'words': words, 'link': link}


def fact(value: str, *sources: dict, state: str = 'supported') -> dict:
    return {'state': state, 'value': value, 'qualifiers': [], 'sources': list(sources), 'options': []}


def contradicted(options: list, *sources: dict) -> dict:
    """Pass 1's own contradiction: ``options`` (value, its source) and the fact's own ``sources``."""
    return {'state': 'contradicted', 'value': '', 'qualifiers': [], 'sources': list(sources),
            'options': [{'value': value, 'sources': [source]} for value, source in options]}


def relation(spec: str, source: dict) -> list:
    """A date relation slot from a spec: '' silent, 'v' supported, '-v' negated, 'a|b' pass 1's own contradiction -
    every fact and side cited at ``source``."""
    if spec == '':
        return []
    if '|' in spec:
        return [contradicted([(value, source) for value in spec.split('|')], source)]
    if spec.startswith('-'):
        return [fact(spec[1:], source, state='negated')]
    return [fact(spec, source)]


# the act's date slot, in every state it can take: the date of service's date (S4's words), the prior date (S6's),
# the prior date denied, and pass 1's own contradiction of the two - its sides in S4 and S6, either order, or both in S4
# (the fact's own source the whole of S4, which states both)
_DOS_SIDE, _PRIOR_SIDE, _PRIOR_IN_S4 = src('S4', DOS_WORDS), src('S6', PRIOR_WORDS), src('S4', PRIOR_WORDS)
DATES = {
    '': [],
    'dos': [fact(DOS, _DOS_SIDE)],
    'prior': [fact(PRIOR, _PRIOR_SIDE)],
    '-prior': [fact(PRIOR, _PRIOR_SIDE, state='negated')],
    'dos|prior': [contradicted([(DOS, _DOS_SIDE), (PRIOR, _PRIOR_SIDE)], src('S4'))],
    'prior|dos': [contradicted([(PRIOR, _PRIOR_SIDE), (DOS, _DOS_SIDE)], src('S4'))],
    'dos|prior@S4': [contradicted([(DOS, _DOS_SIDE), (PRIOR, _PRIOR_IN_S4)], src('S4'))],
}


def section(id: str, start: dict, owner: dict, **slots) -> dict:
    item = {'id': id, 'start': start, 'end': [], 'owner': owner, 'role': [], 'occasion': [], 'performer': [],
            'performer_person': []}
    item.update(slots)
    return item


def event(id: str, unit: str, kind: str, kind_words: str, status_words: str, **fields) -> dict:
    item = {'id': id, 'anchor': {'units': [unit], 'kind_words': kind_words, 'status_words': status_words},
            'restatements': [], 'kind': fact(kind, src(unit, kind_words)), 'other_class': [],
            'status': fact('performed', src(unit, status_words)), 'session': [fact('X1', src(unit))],
            'date_relation': [], 'date': [], 'performer': [], 'performer_person': [],
            'target': {'lesion': [], 'structure': [], 'places': [], 'anatomy': [], 'duct': []},
            'technique': {'device': [], 'route': []}, 'purpose': [], 'cause': [], 'cause_event': [], 'part_of': [],
            'part_relation': [], 'yield': [], 'access_outcome': [],
            'scope': {'breadth': [], 'targets': [], 'segment': [], 'covers': [], 'excepts': []},
            'visit': {'basis': [], 'separately_identifiable': []}}
    item.update(fields)
    return item


def listed(spec: str, source: dict) -> list:
    """A list from a spec: '' none, else each comma-separated spec one fact (``relation``)."""
    return [] if spec == '' else [relation(part, source)[0] for part in spec.split(',')]


def answer(e2_date: str = '', e2_rel: str = '', n1_occ: str = ON, *, n1_role: str = 'findings',
           n1_owner: str = 'documenting_clinician', n1_link: str = 'statement', n1_performer: str = '',
           reached: str = '', device: str = '', e2_places: str = '', e2_session: str = 'X1') -> dict:
    """R2DR_EGD's pass-1 answer: one EGD session X1 whose examination E1 is told in the Findings part N1, and the snare
    E2 (S4) in N1, whose date slot is ``e2_date`` (a DATES key), its own date relation ``e2_rel`` (cited at S4's date of
    service words) and N1's occasion ``n1_occ`` (cited at S2, the date of service line) - the occasion E2 inherits when
    its own relation is silent. The K slots (K_GRIDS): N1's role, its owner (a FACT), the link its occasion and its
    performer are cited with and its performer; X1's reached points and device_reached; E2's places and its session.
    Their defaults give GRID's answers."""
    frame = 'document_frame'
    clinician = fact('documenting_clinician', src('S1', link=frame))
    e2 = event('E2', 'S4', 'snare', 'cold snare', 'was removed', session=relation(e2_session, src('S4')),
               date=copy.deepcopy(DATES[e2_date]), date_relation=relation(e2_rel, src('S4', DOS_WORDS)))
    e2['target']['places'] = listed(e2_places, src('S4'))
    return {
        'encounter': {'date_of_service': {'state': 'stated', 'value': DOS, 'sources': [src('S2', DOS_WORDS, frame)],
                                          'options': []},
                      'other_dates': [], 'documenting_clinician': []},
        'people': [],
        'sections': [
            section('N0', {'units': [], 'words': '', 'link': 'section'}, clinician,
                    role=[fact('header', src('S1', link='section'))],
                    occasion=[fact(ON, src('S2', DOS_WORDS, frame))]),
            section('N1', src('S3', 'Findings:', 'section'), relation(n1_owner, src('S1', link=frame))[0],
                    role=relation(n1_role, src('S3', 'Findings:', 'section')),
                    occasion=relation(n1_occ, src('S2', link=n1_link)),
                    performer=relation(n1_performer, src('S3', link=n1_link)))],
        'sessions': [{'id': 'X1', 'examination': [fact('E1', src('S3'))],
                      'kind': fact('egd', src('S1', 'EGD', frame)), 'encounter': [], 'tract': [], 'approach': [],
                      'through': [], 'reached': listed(reached, src('S3')), 'device_reached': listed(device, src('S3')),
                      'reached_anatomy': [], 'completion': [], 'stations': [], 'part_of_session': []}],
        'anatomy': [], 'lesions': [],
        'events': [event('E1', 'S3', 'examination', 'gastroscope', 'was advanced'), e2],
        'doubts': [],
    }


RELATIONS = ('', ON, EARLIER, LATER, f'-{ON}', f'-{EARLIER}', f'{ON}|{EARLIER}', f'{EARLIER}|{LATER}')
# every state of each slot L1's three readings read, each against each: the act's date x its own relation x the
# occasion it inherits
GRID = {'e2_date': tuple(DATES), 'e2_rel': RELATIONS, 'n1_occ': RELATIONS}


# The K rules AMENDMENT-2 4.3.3 changed only through the merged view of an overfilled slot - K2's existence arm, K6, K7
# and K8 (K1's other rules read a supported value alone, _value, as recorded) - on single written facts in every state
# their slots take: under gemini-inventory@2 as the recorded tree read them, and alike under both labels.
K_GRIDS = {
    'k7_frame': {'n1_role': ('findings', 'history', 'findings|history', '-history'),
                 'n1_owner': ('documenting_clinician', 'outside_record', 'documenting_clinician|outside_record'),
                 'n1_link': ('statement', 'document_frame', 'placing'), 'n1_performer': ('', 'documenting_team')},
    'k6_k8_places': {'reached': ('', 'duodenum', '-duodenum', 'stomach,-duodenum'),
                     'device': ('', 'duodenum', '-duodenum'),
                     'e2_places': ('', 'stomach', 'stomach,-stomach', 'gastric_antrum,-stomach',
                                   '-gastric_antrum,stomach')},
    'k2_existence': {'e2_session': ('X1', 'X9', '-X9', 'X1|X9', '')},
}


def _product(grid: dict) -> dict[str, dict[str, str]]:
    names = list(grid)
    return {'/'.join(f'{name}={value}' for name, value in zip(names, values)): dict(zip(names, values))
            for values in itertools.product(*(grid[name] for name in names))}


def cases() -> dict[str, dict[str, str]]:
    """Every case of GRID, by id ('<slot>=<spec>/...'), in a fixed order."""
    return _product(GRID)


def k_cases() -> dict[str, dict[str, str]]:
    """Every case of K_GRIDS, by id ('<grid>/<slot>=<spec>/...'), in a fixed order."""
    return {f'{name}/{case_id}': spec for name, grid in K_GRIDS.items() for case_id, spec in _product(grid).items()}


def grid_sha256() -> str:
    digest = hashlib.sha256(R2DR_EGD.encode('utf-8'))
    for case_id, spec in cases().items():
        digest.update(case_id.encode('utf-8') + b'\0' + json.dumps(answer(**spec), sort_keys=True).encode('utf-8'))
    return digest.hexdigest()


def read(value: dict, text: str = R2DR_EGD) -> xr.ReadAnswer:
    """``value`` read as the recorded pass-1 label reads it (extract_read's default, gemini-events@2), under the
    computed LOCAL_SCHEMA_2 pin."""
    with mock.patch.object(interpretation, 'LOCAL_SCHEMA_SHA256_V2', jsonschema.sha256_of(xs.LOCAL_SCHEMA_2)):
        found = xr.read(json.dumps(value), len(geometry.Layout.of(text).units))
    if not isinstance(found, xr.ReadAnswer):
        raise AssertionError(f'refused: {getattr(found, "reason", found)}')
    return found


def labelled() -> bool:
    """Whether this tree's checks take a label (the recorded tree's have one rule and take none)."""
    return 'inventory_version' in inspect.signature(checks.check).parameters


def check_for(value: dict, inventory_version: str | None, text: str = R2DR_EGD):
    """checks.check over ``value`` read under gemini-events@2, made for ``inventory_version`` (None: no label named)."""
    named = {} if inventory_version is None or not labelled() else {'inventory_version': inventory_version}
    return checks.check(text, (), read(value, text), **named)


def _key(key) -> list:
    return [str(key.family.value), key.object, str(key.attribute.value), key.index]


def l1_part(checked) -> dict:
    """L1's part of a Checked: each key L1 found literal_mismatch on, each key's stored literals (as stored, in order)
    and the reference date."""
    return {'mismatch': sorted(_key(key) for key, reasons in checked.findings.items()
                               if any(str(reason.value) == MISMATCH for reason in reasons)),
            'literals': sorted([*_key(key), [[item.value, str(item.precision.value)] for item in found]]
                               for key, found in checked.literals.items()),
            'document_date': str(checked.document_date)}


def whole_sha256(checked) -> str:
    """The sha256 of what the checks found: every finding, failed link, stored literal, K8 group and the reference date
    (canonical JSON)."""
    def source(item) -> list:
        return [list(item.units), item.words, str(item.link.value)]
    whole = {'findings': sorted([*_key(key), sorted(str(reason.value) for reason in reasons)]
                                for key, reasons in checked.findings.items()),
             'failed_links': sorted([*_key(key), [source(item) for item in found]]
                                    for key, found in checked.failed_links.items()),
             'joined': [[[_key(key) for key in supported], [_key(key) for key in negated]]
                        for supported, negated in checked.joined],
             **l1_part(checked)}
    return hashlib.sha256(json.dumps(whole, sort_keys=True).encode('utf-8')).hexdigest()


def at(checked, attribute: str, object_id: str = 'E2', family: str = 'events') -> tuple[bool, set, list]:
    """(whether L1 stored literals at that key, its L1 reasons, the literals stored there)."""
    for key, found in checked.literals.items():
        if _key(key)[:3] == [family, object_id, attribute]:
            reasons = {str(reason.value) for reason in checked.findings.get(key, ()) if str(reason.value) == MISMATCH}
            return True, reasons, [item.value for item in found]
    reasons = {str(reason.value) for key, found in checked.findings.items() if _key(key)[:3] == [family, object_id,
                                                                                                attribute]
               for reason in found if str(reason.value) == MISMATCH}
    return False, reasons, []


# --- a colonoscopy whose snare act's date pass 1 contradicts (the r2b refutation's RBRX-1 input) ---------------------

COLON = ('SYNTHETIC COLONOSCOPY REPORT\n'                                                                  # S1
         'Date of service: 04/22/2031\n'                                                                   # S2
         'Endoscopist: Tamsin Orlo, MD (fictional)\n'                                                      # S3
         '\n'
         'Findings: The colonoscope was advanced to the cecum.\n'                                          # S4
         'A 5 mm sessile polyp in the descending colon was removed with a cold snare on 04/22/2031 '        # S5
         '(listed 03/01/2031).\n'
         'The prior colonoscopy was on 03/01/2031.\n')                                                     # S6
_SNARE = ('A 5 mm sessile polyp in the descending colon was removed with a cold snare on 04/22/2031 '
          '(listed 03/01/2031).')
_REACH = 'The colonoscope was advanced to the cecum.'
COLON_DATA = {'proposals': [{'code': '45385', 'start': COLON.index(_SNARE), 'end': COLON.index(_SNARE) + len(_SNARE)},
                            {'code': '45378', 'start': COLON.index(_REACH), 'end': COLON.index(_REACH) + len(_REACH)}],
              'member': None, 'date_of_service': '2031-04-22', 'answers': []}


def colon_answer(**e2: list) -> dict:
    """COLON's pass-1 answer (the replay tools' answer_a shape, units as this note cuts them: S4 the Findings line, S5
    the snare), the snare E2's slots ``e2`` set."""
    def unit(units, words='', link='statement'):
        return {'units': list(units), 'words': words, 'link': link}

    def one(value, *sources, state='supported'):
        return {'state': state, 'value': value, 'qualifiers': [], 'sources': list(sources), 'options': []}

    def act(id, units, kind_words, status_words, kind, **over):
        item = event(id, units[0], kind, kind_words, status_words)
        item['session'] = [one('X1', unit(units))]
        for name, value in over.items():
            if '__' in name:
                outer, inner = name.split('__')
                item[outer][inner] = value
            else:
                item[name] = value
        return item
    frame = 'document_frame'
    clinician = one('documenting_clinician', unit(['S3'], link=frame))
    value = {
        'encounter': {'date_of_service': {'state': 'stated', 'value': '2031-04-22',
                                          'sources': [unit(['S2'], '04/22/2031', frame)], 'options': []},
                      'other_dates': [], 'documenting_clinician': [one('P1', unit(['S3'], 'Tamsin Orlo', frame))]},
        'people': [{'id': 'P1', 'name': unit(['S3'], 'Tamsin Orlo'),
                    'role': one('documenting_clinician', unit(['S3'], 'Endoscopist'))}],
        'sections': [
            section('N0', unit([], '', 'section'), clinician, role=[one('header', unit(['S1'], '', 'frame'))],
                    occasion=[one(ON, unit(['S2'], link=frame))], performer=[one('documenting_team', unit(['S3'],
                                                                                                       link=frame))]),
            section('N1', unit(['S4'], 'Findings:', 'section'), clinician,
                    role=[one('findings', unit(['S4'], 'Findings:', 'section'))],
                    occasion=[one(ON, unit(['S2'], link=frame))],
                    performer=[one('documenting_team', unit(['S3'], link=frame))])],
        'sessions': [{'id': 'X1', 'examination': [one('E1', unit(['S4']))],
                      'kind': one('colonoscopy', unit(['S4'], 'colonoscope')),
                      'encounter': [one('this_encounter', unit(['S2'], link=frame))], 'tract': [], 'approach': [],
                      'through': [], 'reached': [one('cecum', unit(['S4'], 'advanced to the cecum'))],
                      'device_reached': [], 'reached_anatomy': [], 'completion': [], 'stations': [],
                      'part_of_session': []}],
        'anatomy': [],
        'lesions': [{'id': 'L1', 'description': unit(['S5'], 'A 5 mm sessile polyp'),
                     'multiplicity': [one('single', unit(['S5'], 'A 5 mm sessile polyp'))],
                     'places': [one('descending_colon', unit(['S5'], 'descending colon'))],
                     'distinct_from': [], 'same_as': []}],
        'events': [act('E1', ['S4'], 'colonoscope', 'was advanced', 'examination'),
                   act('E2', ['S5'], 'cold snare', 'was removed', 'snare',
                       target__lesion=[one('L1', unit(['S5'], 'A 5 mm sessile polyp'))],
                       target__places=[one('descending_colon', unit(['S5'], 'descending colon'))],
                       technique__device=[one('cold_snare', unit(['S5'], 'cold snare'))])],
        'doubts': []}
    value['events'][1].update(copy.deepcopy(e2))
    return value


def _colon_date(prior_unit: str, prior_words: str = '03/01/2031') -> list:
    return [{'state': 'contradicted', 'value': '', 'qualifiers': [],
             'sources': [{'units': ['S5'], 'words': '', 'link': 'statement'}],
             'options': [{'value': '2031-04-22', 'sources': [{'units': ['S5'], 'words': '04/22/2031',
                                                              'link': 'statement'}]},
                         {'value': '2031-03-01', 'sources': [{'units': [prior_unit], 'words': prior_words,
                                                              'link': 'statement'}]}]}]


def colon_cases() -> dict[str, dict]:
    """The colonoscopy inputs: two controls, the snare act's date pass 1's own contradiction (its prior side in S6 or
    in its own sentence), inheriting N1's occasion or with an own relation."""
    supported = [{'state': 'supported', 'value': '2031-04-22', 'qualifiers': [],
                  'sources': [{'units': ['S5'], 'words': '04/22/2031', 'link': 'statement'}], 'options': []}]
    own = [{'state': 'supported', 'value': ON, 'qualifiers': [],
            'sources': [{'units': ['S5'], 'words': '04/22/2031', 'link': 'statement'}], 'options': []}]
    return {'control: no act date': colon_answer(),
            'control: the act date supported': colon_answer(date=supported),
            'act date contradicted, inherits N1': colon_answer(date=_colon_date('S6')),
            'act date contradicted, own relation': colon_answer(date=_colon_date('S6'), date_relation=own),
            'act date contradicted in its own sentence, inherits N1': colon_answer(date=_colon_date('S5'))}


# the GRID note's inputs whose row the pin also reads (each a change input of one reading, and the control)
GRID_ROWS = {'control': {}, 'relation sides: N1 occasion contradicted': {'n1_occ': f'{ON}|{EARLIER}'},
             'dates read: own relation, date contradicted': {'e2_rel': ON, 'e2_date': 'dos|prior'},
             'inherited occasion: date contradicted': {'e2_date': 'dos|prior'}}
GRID_DATA = {'proposals': [{'code': '43251', 'start': R2DR_EGD.index('A 5 mm polyp'),
                            'end': R2DR_EGD.index('\n', R2DR_EGD.index('A 5 mm polyp'))}],
             'member': None, 'date_of_service': DOS, 'answers': []}


def recorded_row(text: str, value: dict, data: dict) -> dict:
    """The row tests/v2/test_failure_classes.pipeline writes for ``value`` (its sha256, labels, claim count and code
    outcomes): in a labelled tree its checks are made for gemini-inventory@2; in the recorded tree for its one rule."""
    import tests.v2.test_failure_classes as FC
    from studio.interpretation import store
    seen = {}
    real = store.row_v2

    def spy(**kwargs):
        seen['fields'] = real(**kwargs)
        return seen['fields']
    with mock.patch.object(store, 'row_v2', spy):
        run = FC.pipeline(text, value, {'default': 'faithful', 'verdicts': [], 'unlisted': []}, data)
    fields = seen['fields']
    return {'sha256': fields['sha256'], 'labels': [fields['interpretation_version'], fields['inventory_version']],
            'claims': len(run.claim_set.claims),
            'outcomes': {code: item['status'] for code, item in sorted(FC.outcomes(run.assessment).items())}}


def recorded_request(value: dict, inventory_version: str | None) -> dict:
    """The dormant (Gemini) adapter's two requests for COLON and ``value`` - pass 1's, and pass 2's built from it and a
    synthetic stored answer (``value`` in a Gemini envelope) with the checks made for ``inventory_version`` - as a
    recorded Gemini case-run's pass1/pass2 request sha256 name them (the replay tools' paste: one page per span)."""
    from studio import jobs
    from studio.ingest.extract import extract_paste
    from studio.interpretation import adapter
    from studio.types import PageSpan
    result = extract_paste(COLON, limits=jobs._limits())
    spans = sorted(result.pages, key=lambda span: span.start)
    tiled: list = []
    for index, span in enumerate(spans):
        end = spans[index + 1].start if index + 1 < len(spans) else len(result.text)
        tiled.append(PageSpan(page=span.page, start=tiled[-1].end if tiled else 0, end=end))
    text, pages = result.text, tuple(tiled)
    first = adapter.build_extraction_request(text, pages, 'paste')
    body = json.dumps({'candidates': [{'content': {'parts': [{'text': json.dumps(value)}], 'role': 'model'},
                                       'finishReason': 'STOP', 'index': 0}],
                       'usageMetadata': {'promptTokenCount': 31000, 'candidatesTokenCount': 2100,
                                         'totalTokenCount': 33100},
                       'modelVersion': adapter.MODEL, 'responseId': 'synthetic-r2dr-0001'}).encode()
    named = {} if inventory_version is None or not labelled() else {'inventory_version': inventory_version}
    second = adapter.build_appraisal_request(text, pages, 'paste', first, body,
                                             check=lambda t, p, a: checks.check(t, p, a, **named).findings)
    return {'pass1_sha256': first.canonical_sha256, 'pass2_sha256': second.request.canonical_sha256,
            'claims': len(second.built.claim_set.claims)}


def write_recorded(path: Path = RECORDED_FIXTURE) -> None:
    """RECORDED_FIXTURE's owning function: what the RECORDED tree makes - for every case of GRID, L1's part of its
    Checked and the whole Checked's sha256; for every case of K_GRIDS, the whole Checked's sha256; for each colonoscopy
    input and each GRID_ROWS input, the row its recorded
    labels' writer makes; for each colonoscopy input, the dormant adapter's two requests. Run it in the tree
    gemini-inventory@2 produced (0a5f3283b), whose checks have one rule and take no label: it refuses a tree whose
    checks.check takes ``inventory_version``."""
    if labelled():
        raise RuntimeError('The recorded outputs are written in the recorded tree, whose checks take no label.')
    consistency = Path(inspect.getfile(checks)).with_name('consistency.py')
    grid = {}
    for case_id, spec in cases().items():
        checked = check_for(answer(**spec), None)
        grid[case_id] = {'l1': l1_part(checked), 'whole_sha256': whole_sha256(checked)}
    out = {'grid_sha256': grid_sha256(),
           'recorded_consistency_sha256': hashlib.sha256(consistency.read_bytes()).hexdigest(),
           'cases': grid,
           'k_cases': {case_id: whole_sha256(check_for(answer(**spec), None)) for case_id, spec in k_cases().items()},
           'rows': {**{name: recorded_row(COLON, value, COLON_DATA) for name, value in colon_cases().items()},
                    **{name: recorded_row(R2DR_EGD, answer(**spec), GRID_DATA) for name, spec in GRID_ROWS.items()}},
           'requests': {name: recorded_request(value, None) for name, value in colon_cases().items()}}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=0, sort_keys=True) + '\n', encoding='utf-8')


def recorded() -> dict:
    return json.loads(RECORDED_FIXTURE.read_text(encoding='utf-8'))


# --- RBRX-1: L1's three readings under gemini-inventory@2 ------------------------------------------------------------

class R2DRRecordedL1ReadingTests(SimpleTestCase):
    """DECISIONS D301 RBRX-1: L1 reads each of its three readings as gemini-inventory@2 was recorded - inputs it must
    change (@2 as recorded; @3 and no label as AMENDMENT-2 4.3.3 built them) and boundaries it leaves alone."""

    def assertL1(self, spec: dict, where: str, *, recorded: tuple, current: tuple, object_id: str = 'E2',
                 family: str = 'events') -> None:
        """(literals stored at the key, literal_mismatch there) for gemini-inventory@2, @3 and no label."""
        for label, want in ((INV2, recorded), (INV3, current), (None, current)):
            stored, reasons, _ = at(check_for(answer(**spec), label), where, object_id, family)
            self.assertEqual((stored, MISMATCH in reasons), want, f'{label or "no label"} on {family}/{object_id}/'
                                                                  f'{where} for {spec}')

    def test_the_relation_sides_l1_judges_are_the_labels(self):
        """A contradicted occasion or relation states no value under gemini-inventory@2: L1 judges a supported relation
        alone (the 03/01-free date of service words make its earlier_date side fail under @3)."""
        for spec in ({'n1_occ': f'{ON}|{EARLIER}'}, {'n1_occ': f'{EARLIER}|{LATER}'}):
            with self.subTest(**spec):
                self.assertL1(spec, 'occasion', recorded=(True, False), current=(True, True), object_id='N1',
                              family='sections')
        for spec in ({'e2_rel': f'{ON}|{EARLIER}'}, {'e2_rel': f'{EARLIER}|{LATER}'}):
            with self.subTest(**spec):
                self.assertL1(spec, 'date_relation', recorded=(True, False), current=(True, True))
        for spec, fails in (({'n1_occ': EARLIER}, True), ({'n1_occ': ON}, False), ({'n1_occ': f'-{EARLIER}'}, False)):
            with self.subTest(boundary=spec):  # a supported relation is judged, a denial is not, under both labels
                self.assertL1(spec, 'occasion', recorded=(True, fails), current=(True, fails), object_id='N1',
                              family='sections')

    def test_the_dates_read_into_an_acts_relation_are_the_labels(self):
        """An act's own relation (on the date of service, its own words holding it) is read with a supported date's
        words alone under gemini-inventory@2: a contradicted date's sides are no evidence there."""
        for date in ('dos|prior', 'prior|dos', 'dos|prior@S4'):
            with self.subTest(e2_date=date):
                self.assertL1({'e2_rel': ON, 'e2_date': date}, 'date_relation', recorded=(True, False),
                              current=(True, True))
                checked = check_for(answer(e2_rel=ON, e2_date=date), INV2)
                self.assertEqual(at(checked, 'date_relation')[2], [DOS])  # the relation's own words alone
        for date, fails in (('prior', True), ('dos', False), ('-prior', False), ('', False)):
            with self.subTest(boundary=date):  # a supported date is read under both labels, a denial under neither
                self.assertL1({'e2_rel': ON, 'e2_date': date}, 'date_relation', recorded=(True, fails),
                              current=(True, fails))

    def test_an_act_judges_its_inherited_occasion_on_a_supported_date_alone_under_the_recorded_label(self):
        """An act with no relation of its own judges the occasion it inherits (N1's, on the date of service) only when
        gemini-inventory@2 reads a date in its slot: a supported one. A contradicted date makes no inherited key."""
        for date in ('dos|prior', 'prior|dos', 'dos|prior@S4'):
            with self.subTest(e2_date=date):
                self.assertL1({'e2_date': date}, 'date_relation', recorded=(False, False), current=(True, True))
        for date, want in (('prior', (True, True)), ('dos', (True, False)), ('-prior', (False, False)),
                           ('', (False, False))):
            with self.subTest(boundary=date):
                self.assertL1({'e2_date': date}, 'date_relation', recorded=want, current=want)

    def test_the_label_chooses_one_reading_for_the_k_rules_and_l1(self):
        from studio.interpretation.contract import consistency as cs
        self.assertIs(cs._reading(INV2), cs._RECORDED)
        self.assertEqual((cs._RECORDED.members, cs._RECORDED.dates), (cs._supported, cs._dates_supported))
        self.assertEqual((cs._OFFERED.members, cs._OFFERED.dates), (cs._offered, cs._dates_read))
        for label in (INV3, 'gemini-inventory@1', 'gemini-inventory@4', ''):
            with self.subTest(label=label):
                self.assertIs(cs._reading(label), cs._OFFERED)


# --- the pin: GRID against the recorded tree's Checked ---------------------------------------------------------------

class R2DRRecordedL1PinTests(SimpleTestCase):
    """For every case of GRID, the Checked made for gemini-inventory@2 is the recorded tree's (RECORDED_FIXTURE)."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.recorded = recorded()
        cls.reads = {case_id: read(answer(**spec)) for case_id, spec in cases().items()}  # each case read once

    def checked(self, case_id: str, label: str):
        return checks.check(R2DR_EGD, (), self.reads[case_id], inventory_version=label)

    def test_the_fixture_is_the_recorded_trees_answer_to_this_grid(self):
        self.assertEqual(self.recorded['grid_sha256'], grid_sha256())
        self.assertEqual(sorted(self.recorded['cases']), sorted(cases()))
        self.assertEqual(self.recorded['recorded_consistency_sha256'],
                         '9e31e5a4c91ea19722562589a6666972d7694ac9f83c5647cf1205ec07841cc6')
        with self.assertRaises(RuntimeError):  # its owning function writes in the recorded tree alone
            write_recorded(Path('/nonexistent/recorded_l1.json'))

    def test_every_state_of_every_slot_l1_reads_is_in_the_grid(self):
        def state(spec: str) -> str:
            return ('silent' if spec == '' else 'contradicted' if '|' in spec else 'negated' if spec.startswith('-')
                    else 'supported')
        for name, specs in GRID.items():
            with self.subTest(slot=name):
                self.assertEqual({state(spec) for spec in specs}, {'silent', 'supported', 'negated', 'contradicted'})
        mismatching = sum(bool(item['l1']['mismatch']) for item in self.recorded['cases'].values())
        self.assertGreater(mismatching, 100)  # the recorded tree finds literal_mismatch on the grid: a reading

    def test_the_recorded_label_makes_the_recorded_trees_checked_on_every_case(self):
        differ = []
        for case_id in cases():
            checked = self.checked(case_id, INV2)
            want = self.recorded['cases'][case_id]
            if l1_part(checked) != want['l1'] or whole_sha256(checked) != want['whole_sha256']:
                differ.append((case_id, l1_part(checked), want['l1']))
        self.assertEqual(len(differ), 0, f'{len(differ)} of {len(cases())} cases differ; first: {differ[:3]}')

    def test_the_k_rules_amendment_2_changed_only_through_the_merged_view_read_as_recorded(self):
        """K2's existence arm, K6, K7 and K8 on single written facts in every state (K_GRIDS): the Checked made for
        gemini-inventory@2 is the recorded tree's - and, the boundary, the one made for gemini-inventory@3 too, for no
        answer read under gemini-events@2 holds the merged view through which alone AMENDMENT-2 changed them."""
        recorded_k = self.recorded['k_cases']
        self.assertEqual(sorted(recorded_k), sorted(k_cases()))
        differ: dict[str, list] = {INV2: [], INV3: []}
        for case_id, spec in k_cases().items():
            found = read(answer(**spec))
            for label in differ:
                if whole_sha256(checks.check(R2DR_EGD, (), found, inventory_version=label)) != recorded_k[case_id]:
                    differ[label].append(case_id)
        self.assertEqual(differ, {INV2: [], INV3: []})
        reasons = {str(reason.value) for spec in k_cases().values()
                   for found in check_for(answer(**spec), INV2).findings.values() for reason in found}
        self.assertLessEqual({'frame_role', 'instrument_conflict', 'session_inconsistent'}, reasons)  # each rule fires

    def test_the_current_reading_only_adds_l1_findings_to_the_recorded_ones(self):
        """The boundary: gemini-inventory@3 is left as it was - on the same grid it finds every L1 finding the recorded
        label finds (it only demotes more) and more on pass 1's own contradictions."""
        more = 0
        for case_id in cases():
            mine = {tuple(key) for key in l1_part(self.checked(case_id, INV3))['mismatch']}
            theirs = {tuple(key) for key in self.recorded['cases'][case_id]['l1']['mismatch']}
            with self.subTest(case=case_id):
                self.assertLessEqual(theirs, mine)
            more += mine > theirs
        self.assertGreater(more, 100)


# --- the row and the request a recording of gemini-inventory@2 makes --------------------------------------------------

class R2DRRecordedRowsTests(SimpleTestCase):
    """The row tests/v2/test_failure_classes.pipeline writes at the recorded labels is the recorded tree's - row sha256,
    claim count and code outcomes - on each colonoscopy input and each GRID_ROWS input."""

    def test_each_row_is_the_recorded_trees(self):
        rows = recorded()['rows']
        inputs = {**{name: (COLON, value, COLON_DATA) for name, value in colon_cases().items()},
                  **{name: (R2DR_EGD, answer(**spec), GRID_DATA) for name, spec in GRID_ROWS.items()}}
        self.assertEqual(sorted(rows), sorted(inputs))
        for name, (text, value, data) in inputs.items():
            with self.subTest(case=name):
                found = recorded_row(text, value, data)
                self.assertEqual(found['labels'], [interpretation.INTERPRETATION_PAIR, INV2])
                self.assertEqual(found, rows[name])

    def test_the_contradicted_act_date_leaves_the_snare_ready_as_recorded(self):
        """The input the r2b refutation moved READY -> held: recorded, the snare (45385) is READY on 35 claims."""
        rows = recorded()['rows']
        for name in ('act date contradicted, inherits N1', 'act date contradicted, own relation',
                     'act date contradicted in its own sentence, inherits N1'):
            with self.subTest(case=name):
                self.assertEqual(rows[name]['outcomes']['45385'], 'ready')
                self.assertEqual(recorded_row(COLON, colon_cases()[name], COLON_DATA)['outcomes']['45385'], 'ready')


class R2DRRecordedRequestTests(SimpleTestCase):
    """The pass-2 request a recording of gemini-inventory@2 was made with is the one its label rebuilds: the dormant
    adapter's request, with the checks made for gemini-inventory@2, is the recorded tree's (RECORDED_FIXTURE's
    requests, built by the recorded tree)."""

    def test_the_recorded_label_rebuilds_the_recorded_trees_requests(self):
        requests = recorded()['requests']
        self.assertEqual(sorted(requests), sorted(colon_cases()))
        for name, value in colon_cases().items():
            with self.subTest(case=name):
                self.assertEqual(recorded_request(value, INV2), requests[name])

    def test_the_current_label_builds_another_request_where_its_reading_differs(self):
        """The boundary: the checks made for gemini-inventory@3 build the recorded request on the controls and another
        (fewer claims: the act's date relation is not claimed) on the contradicted act date."""
        requests = recorded()['requests']
        for name, value in colon_cases().items():
            with self.subTest(case=name):
                same = recorded_request(value, INV3) == requests[name]
                self.assertEqual(same, name.startswith('control'))
