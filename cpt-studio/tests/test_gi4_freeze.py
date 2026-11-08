"""GI round 4 harness, H2: the request-side freeze (ops/gi4/freeze.py), pinned against installed 80df1831d168.

A request is the document's text plus one "Date of service" line, so the date it carries is the only interpretation it
sends. (a) Every cue pattern context.py and sections.py read is byte-identical to installed (tests/fixtures/gi4/pins/
cues.json); a pattern may only be ADDED, and only when a package declaration names it (tests/fixtures/gi4/declarations/).
(b)-(d) Over the CI corpus (the regression texts, a slice of the generated corpus and seeded families, the repository's
own test texts) the layout, the date channel in every member state, every request's bytes and the mention counts equal
installed's (pins/freeze.json). The classifier and the gate are pinned on hand-made records: NEW-SEND and NEW-TAKE always
fail, and any other movement fails unless declared.

The owner's decision of 2026-11-07 (the date forms; declarations/dates-owner-ruling-20261107.json, repaired after the
first refutation) is the one movement of the request side a declaration may name: (a) only the constants it names
change, each to the sha256 it pins, and the notes it rewords are exactly the installed texts and the head's; (b)-(d) a
CI text moves only where the ruling's own text-by-text acceptance (freeze._ruled_acceptor) explains every movement
against the installed reading's record of that text - kept in the declaration and checked against the pinned digest, so
it is the installed record and no other: a NEW-SEND only of a date quoted in a decided form where the base sent none, a
NEW-HELD only of an answer contradicting that date, a NEW-TAKE only of an answer equal to it, SEND->ASK never. Without
the declaration, and from any other date form, the gate still fails.
"""
import collections
import hashlib
import json
import re
from pathlib import Path

from django.test import SimpleTestCase

from ops.gi4 import freeze, observe, pins

FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'gi4'
CUES = json.loads((FIXTURES / 'pins' / 'cues.json').read_text())
DIGESTS = json.loads((FIXTURES / 'pins' / 'freeze.json').read_text())
DECLARED = sorted({name for path in (FIXTURES / 'declarations').glob('*.json')
                   for name in json.loads(path.read_text()).get('cues_added', ())})
RULING = json.loads((FIXTURES / 'declarations' / 'dates-owner-ruling-20261107.json').read_text())


class CuePatternFreezeTests(SimpleTestCase):
    def test_every_pattern_the_request_side_reads_is_unchanged(self):
        # the owner's ruling of 2026-11-07 names the constants it changes, each pinned to its new sha256; no other moves
        now = freeze.cue_inventory()
        moved = freeze.compare_cues(CUES['cues'], now)
        named = RULING['owner_ruling']['changed_cues']
        self.assertEqual([k for k in moved['changed'] if named.get(k) != now[k]], [],
                         'a constant context.py or sections.py reads changed that the owner ruling does not name so')
        self.assertEqual(moved['removed'], [])
        self.assertEqual(sorted(set(moved['added']) - set(DECLARED)), [], 'an added pattern no declaration names')
        cues = dict(moved, added=[])
        self.assertEqual(freeze.gate(cues, collections.Counter(), RULING), [])
        self.assertTrue(freeze.gate(cues, collections.Counter(), {}) if moved['changed'] else True,
                        'without the declaration a changed constant fails the gate')

    def test_the_reworded_notes_are_the_installed_texts_and_the_heads(self):
        # each [installed text, head text] pair the ruling's FACT-CHANGED acceptance applies (freeze._reworded): the
        # installed text hashes to the installed cue pin of a note constant, and the head text IS that constant now
        from studio.gi import context
        pairs = RULING['owner_ruling']['note_rewordings']
        self.assertEqual(len(pairs), 3)
        for old, new in pairs:
            name = next(k for k in ('FORM_DATE_NOTE', 'WIDE_DATE_NOTE', 'WIDE_DATE_QUOTE_NOTE')
                        if freeze._sha(freeze._canon(old)) == CUES['cues'][f'context.{k}'])
            with self.subTest(name=name):
                self.assertEqual(getattr(context, name), new)
                self.assertEqual(RULING['owner_ruling']['changed_cues'][f'context.{name}'],
                                 freeze._sha(freeze._canon(new)))
        self.assertNotIn('14 Oct 2026', context.FORM_DATE_NOTE)
        self.assertNotIn('Exam date', context.WIDE_DATE_NOTE + context.WIDE_DATE_QUOTE_NOTE)

    def test_the_inventory_reads_cues_and_module_constants(self):
        now = freeze.cue_inventory()
        self.assertGreater(len([k for k in now if k.startswith('cues.')]), 20)
        self.assertIn('context.SERVICE_DATE', now)
        self.assertIn('sections.HEADINGS', now)
        self.assertIn('cues.PROCEDURE_TITLE', now)

    def test_a_pattern_change_is_seen_flags_included(self):
        a = freeze._canon(re.compile('date', re.I))
        self.assertNotEqual(a, freeze._canon(re.compile('date')))
        self.assertNotEqual(a, freeze._canon(re.compile('dates', re.I)))
        self.assertEqual(freeze._canon(frozenset({'b', 'a'})), freeze._canon(frozenset({'a', 'b'})))
        self.assertIsNone(freeze._canon(object()))


class CorpusFreezeTests(SimpleTestCase):
    def test_layout_date_channel_requests_and_mentions_equal_installed(self):
        docs = pins.ci_corpus()
        now = pins.freeze_digests(docs, observe._modules())
        self.assertEqual(len(now), DIGESTS['texts'])
        moved = sorted(k for k in DIGESTS['digests'] if now.get(k) != DIGESTS['digests'][k])
        base = RULING['owner_ruling']['ci_base_records']
        self.assertEqual([k for k in moved if k not in base], [], 'texts whose request side moved against installed '
                                                                   '(run python -m ops.gi4.freeze for the classes)')
        self.assertEqual(sorted(base), moved, 'the declaration keeps the installed record of exactly the moved texts')
        by_id, m = {doc['id']: doc for doc in docs}, observe._modules()
        texts, heads = {}, {}
        for k in moved:  # the installed record, proved by its pinned digest, against the head's record of the same text
            self.assertEqual(hashlib.sha256(json.dumps(base[k], sort_keys=True).encode()).hexdigest(),
                             DIGESTS['digests'][k], f'{k}: the declared record is not the installed one')
            texts[k] = by_id[k]['text']
            heads[k] = observe.text_record(m, texts[k], by_id[k].get('truth'))
            m['jobs'].release_routing_caches()
        accept = freeze._ruled_acceptor({k: base[k] for k in moved}, heads, texts, RULING)
        counts, examples = freeze.classify({k: base[k] for k in moved}, heads, accept)
        none = {'changed': [], 'removed': [], 'added': [], 'head': {}}
        self.assertEqual(freeze.gate(none, counts, RULING), [], examples)
        self.assertTrue(all(cls.endswith(freeze.RULED) for cls in counts), counts)
        self.assertTrue(freeze.gate(none, freeze.classify({k: base[k] for k in moved}, heads)[0], {}),
                        'without the declaration the same movement fails the gate')


def _rec(sends='2026-10-19', taken=False, held=False, request='r1', layout='L', fact=None, mentions=(1, 1),
         answer=None, label='none'):
    return {'layout': layout, 'fact': fact or ['document', '2026-10-19', [], ''], 'mentions': list(mentions),
            'states': {label: {'answer': answer, 'sends': sends, 'taken': taken, 'held': held, 'request': request}}}


class ClassifierAndGateTests(SimpleTestCase):
    def classes(self, base, head):
        counts, _ = freeze.classify({'t': base}, {'t': head})
        return {k: v for k, v in counts.items() if v}

    def test_movements(self):
        self.assertEqual(self.classes(_rec(), _rec()), {})
        self.assertEqual(self.classes(_rec('DATELESS', request='r0'), _rec('2026-10-19')),
                         {'NEW-SEND': 1})
        self.assertEqual(self.classes(_rec('2026-10-18', request='r0'), _rec('2026-10-19')), {'NEW-SEND': 1})
        self.assertEqual(self.classes(_rec('HELD', held=True, request=None, answer='1998-01-01', label='far'),
                                      _rec('1998-01-01', taken=True, answer='1998-01-01', label='far')),
                         {'NEW-SEND': 1, 'NEW-TAKE': 1})
        self.assertEqual(self.classes(_rec('1998-01-01', taken=True, answer='1998-01-01', label='far'),
                                      _rec('HELD', held=True, request=None, answer='1998-01-01', label='far')),
                         {'NEW-HELD': 1})
        self.assertEqual(self.classes(_rec(), _rec('DATELESS', request='r0')), {'SEND->ASK': 1})
        self.assertEqual(self.classes(_rec(), _rec(request='r2')), {'REQUEST-CHANGED': 1})
        self.assertEqual(self.classes(_rec(), _rec(layout='M')), {'LAYOUT-CHANGED': 1})
        self.assertEqual(self.classes(_rec(), _rec(mentions=(2, 1))), {'MENTIONS-CHANGED': 1})

    def test_the_gate(self):
        cues = {'changed': [], 'removed': [], 'added': []}
        self.assertEqual(freeze.gate(cues, collections.Counter(), {}), [])
        self.assertTrue(freeze.gate(cues, collections.Counter({'NEW-SEND': 1}), {'movements': {'NEW-SEND': 9}}))
        self.assertTrue(freeze.gate(cues, collections.Counter({'NEW-TAKE': 1}), {'movements': {'NEW-TAKE': 9}}))
        self.assertTrue(freeze.gate(cues, collections.Counter({'NEW-HELD': 2}), {'movements': {'NEW-HELD': 1}}))
        self.assertEqual(freeze.gate(cues, collections.Counter({'NEW-HELD': 2}), {'movements': {'NEW-HELD': 2}}), [])
        self.assertTrue(freeze.gate(dict(cues, changed=['cues.X']), collections.Counter(), {}))
        self.assertTrue(freeze.gate(dict(cues, added=['sections.Y']), collections.Counter(), {}))
        self.assertEqual(freeze.gate(dict(cues, added=['sections.Y']), collections.Counter(),
                                     {'cues_added': ['sections.Y']}), [])


# --- the owner's ruling of 2026-11-07 (the date forms), on hand-made records ------------------------------------------

def _ruling(**flags):
    return {'owner_ruling': dict({'id': freeze.DATE_FORMS_RULING, 'changed_cues': {}, 'new_send_forms': True,
                                  'new_held_forms': True, 'new_take_forms': True}, **flags)}


def _doc(line, origin='document', value='2026-11-09', states=None, lead='SYNTHETIC\n', note=''):
    """A text whose service-date fact quotes ``line`` (its only evidence), and a record of it."""
    text = lead + line + '\nPROCEDURE NOTE: Colonoscopy\n'
    start = text.index(line)
    return text, {'layout': 'L', 'fact': [origin, value, [[start, start + len(line)]], note], 'mentions': [1, 1],
                  'states': states or {'none': {'answer': None, 'sends': value or 'DATELESS', 'taken': False,
                                                'held': False, 'request': 'r1'}}}


def _st(sends, answer=None, taken=False, held=False):
    return {'answer': answer, 'sends': sends, 'taken': taken, 'held': held, 'request': None if held else 'r-' + sends}


def _pair(line, base_states, head_states, head_fact=('document', '2026-11-09'), base_fact=None, lead='SYNTHETIC\n'):
    text, base = _doc(line, *(base_fact or head_fact), base_states, lead)
    _, head = _doc(line, *head_fact, head_states, lead)
    return text, base, head


def _ruled(line, base_states, head_states, head_fact=('document', '2026-11-09'), flags=None, lead='SYNTHETIC\n'):
    """The movement classes under the ruling (both records carry the head's fact: no FACT-CHANGED)."""
    text, base, head = _pair(line, base_states, head_states, head_fact, lead=lead)
    accept = freeze._ruled_acceptor({'t': base}, {'t': head}, {'t': text}, _ruling(**(flags or {})))
    counts, _ = freeze.classify({'t': base}, {'t': head}, accept)
    return {k: v for k, v in counts.items() if v}


def _sent(day='2026-11-09', **states):
    """A newly sent text's states: the base sent no date ('none' DATELESS), the head sends ``day``."""
    base = {'none': _st('DATELESS')}
    head = {'none': _st(day)}
    for label, (b, h) in states.items():
        base[label], head[label] = b, h
    return base, head


R = freeze.RULED


class OwnerRulingGateTests(SimpleTestCase):
    """The H2 gate taught the owner's ruling of 2026-11-07 and nothing more: the decided forms are recognised by the
    freeze's own patterns (a label the ruling added only in the document's head); a NEW-SEND passes only of a date one of
    them states where the base sent none; a NEW-HELD only of an answer contradicting that newly sent date, a NEW-TAKE
    only of an answer equal to it; SEND->ASK never."""

    DECIDED = ('Date of service: 9 November 2026', 'DOS: 16-Nov-2026', 'Procedure date: 9th Nov. 2026',
               'Date of service: Monday, November 9, 2026', 'Service date: Mon 09-Nov-2026',
               'Date of procedure: Mon., 11/09/2026', 'Date of Operation: 11/09/2026', 'Exam date: November 9, 2026',
               'EXAMINATION DATE: 11/09/2026', 'date of operation: 2026-11-09', 'Exam date: Mon 9 Nov 2026')
    NOT_DECIDED = ('Date of service: 11/09/2026', 'DOS: 2026-11-09', 'Procedure date: November 9, 2026',
                   'Date of service: 11-09-2026', 'Date of service: 11.09.2026', 'Date of service: 11/09/26',
                   'Date of service: 09/11/2026', 'Date of service: Tuesday, November 9, 2026', 'Date: 9 November 2026',
                   'Admission date: 9 November 2026', 'Date of birth: 9 November 2026', 'Referral date: 16-Nov-2026',
                   'Date of service: Monday', 'Date of service: Monday, 11/09/26', 'Date of exam: 11/09/2026',
                   'Operation date: 11/09/2026', 'Date/Time of Operation: 11/09/2026', 'Exam day: 11/09/2026')

    def test_the_decided_forms_are_recognised_and_no_other(self):
        for line in self.DECIDED:
            with self.subTest(line=line):
                forms = freeze.ruled_forms(line)
                self.assertEqual([f[1] for f in forms], ['2026-11-09'] if '16' not in line else ['2026-11-16'], forms)
        for line in self.NOT_DECIDED:
            with self.subTest(line=line):
                self.assertEqual(freeze.ruled_forms(line), [])
        # a label the ruling added is a decided form whatever its value - its date only when it reads one - and only in
        # the document's head: beyond it, it is no form at all (nor is its weekday or day-first date)
        self.assertEqual([f[:2] for f in freeze.ruled_forms('Exam date: 11/09/26')], [('label', None)])
        for line in ('Exam date: 11/09/2026', 'Date of Operation: Monday, November 9, 2026', 'Exam date: 9 Nov 2026'):
            self.assertEqual(freeze.ruled_forms(line, head=False), [], line)
        self.assertEqual([f[0] for f in freeze.ruled_forms('Date of service: 9 Nov 2026', head=False)], ['dayfirst'])

    def test_a_label_the_ruling_added_counts_only_where_the_ruling_reads_it(self):
        line = 'Exam date: 11/09/2026'  # the label's line is the (lines + 1)th non-empty line
        for blanks, lines, ok in ((0, 10, True), (5, 11, True), (0, 12, False), (3, 12, False), (0, 30, False)):
            lead = 'L\n' * lines + '\n' * blanks
            with self.subTest(lines=lines, blanks=blanks):
                counts = _ruled(line, *_sent(), lead=lead)
                self.assertEqual(counts, {'NEW-SEND' + R: 1} if ok else {'NEW-SEND': 1})
        self.assertEqual(freeze._head_bound('a\n\nb\n'), 5)  # fewer lines: the whole text
        text = ''.join(f'L{i}\n\n' for i in range(20))
        self.assertEqual(freeze._head_bound(text), text.index('L11') + 3)
        # the head ends at the first section heading after the first two lines (the installed sections module's
        # layout); a title of a note written around a procedure; a label inside another field's sentence
        for lead, ok in (('SYNTHETIC\nColonoscopy Report\n', True), ('SYNTHETIC\nColonoscopy Report\nIndication: '
                         'screening.\n', False), ('SYNTHETIC\nEndoscopy booking\n', False),
                         ('SYNTHETIC\nInformed consent\n', False), ('SYNTHETIC\nPatient: A. Synthetic    ', True),
                         ('SYNTHETIC\nInterval events: right hemicolectomy. ', False), ('SYNTHETIC\n- ', True)):
            with self.subTest(lead=lead):
                counts = _ruled(line, *_sent(), lead=lead)
                self.assertEqual(counts, {'NEW-SEND' + R: 1} if ok else {'NEW-SEND': 1})
        # a weekday or day-first form under an installed label counts wherever it stands (the head rule is the labels')
        self.assertEqual(_ruled('Date of service: 9 Nov 2026', *_sent(),
                                lead='SYNTHETIC\nColonoscopy Report\nIndication: screening.\n'), {'NEW-SEND' + R: 1})

    def test_a_new_send_from_a_decided_form_is_accepted(self):
        for line in self.DECIDED:
            day = '2026-11-16' if '16' in line else '2026-11-09'
            with self.subTest(line=line):
                self.assertEqual(_ruled(line, *_sent(day), ('document', day)), {'NEW-SEND' + R: 1})
                text, base, head = _pair(line, {'none': _st('DATELESS')}, {'none': _st(day)}, ('document', day),
                                         ('missing', None))
                self.assertTrue(freeze.gate({'changed': [], 'removed': [], 'added': []},
                                            freeze.classify({'t': base}, {'t': head})[0], {}),
                                'without the declaration the same movement fails')

    def test_a_new_send_from_any_other_form_is_refused(self):
        for line in self.NOT_DECIDED:
            with self.subTest(line=line):
                counts = _ruled(line, *_sent())
                self.assertEqual(counts, {'NEW-SEND': 1})
                self.assertTrue(freeze.gate({'changed': [], 'removed': [], 'added': []}, collections.Counter(counts),
                                            _ruling()))
        # a decided form whose date is not the date sent, a base that sent a date, a fact not the document's one date
        self.assertEqual(_ruled('DOS: 16-Nov-2026', *_sent()), {'NEW-SEND': 1})
        self.assertEqual(_ruled('DOS: 9 Nov 2026', {'none': _st('2026-11-08')}, {'none': _st('2026-11-09')}),
                         {'NEW-SEND': 1})
        self.assertEqual(_ruled('DOS: 9 Nov 2026', *_sent(), ('missing', None)), {'NEW-SEND': 1})
        # and a declaration that does not name new sends accepts none
        self.assertEqual(_ruled('DOS: 9 Nov 2026', *_sent(), flags={'new_send_forms': False}), {'NEW-SEND': 1})

    def test_new_held_only_where_the_answer_contradicts_the_newly_sent_date(self):
        line = 'Exam date: 11/09/2026'
        far = (_st('1998-01-01', '1998-01-01', taken=True), _st('HELD', '1998-01-01', held=True))
        self.assertEqual(_ruled(line, *_sent(far=far)), {'NEW-SEND' + R: 1, 'NEW-HELD' + R: 1})
        self.assertEqual(_ruled(line, *_sent(far=far), flags={'new_held_forms': False}),
                         {'NEW-SEND' + R: 1, 'NEW-HELD': 1})
        # the sent date's own answer held: no contradiction, refused
        same = (_st('2026-11-09', '2026-11-09', taken=True), _st('HELD', '2026-11-09', held=True))
        self.assertEqual(_ruled(line, *_sent(doc=same)), {'NEW-SEND' + R: 1, 'NEW-HELD': 1})
        # no newly sent date - the head asks (a conflict, or no date), or the base already sent one: refused
        for fact in (('conflict', None), ('missing', None)):
            base, head = _sent(far=far)
            head['none'] = _st('DATELESS')
            self.assertEqual(_ruled(line, base, head, fact), {'NEW-HELD': 1}, fact)
        base, head = _sent(far=far)
        base['none'] = _st('2026-11-09')
        self.assertEqual(_ruled(line, base, head), {'NEW-HELD': 1})
        # and an installed form's newly sent date explains nothing
        self.assertEqual(_ruled('Date of service: 11/09/2026', *_sent(far=far)), {'NEW-SEND': 1, 'NEW-HELD': 1})

    def test_new_take_only_where_the_answer_equals_the_newly_sent_date(self):
        line = 'Date of Operation: 11/09/2026'
        take = (_st('HELD', '2026-11-09', held=True), _st('2026-11-09', '2026-11-09', taken=True))
        self.assertEqual(_ruled(line, *_sent(**{'answer:D': take})), {'NEW-SEND' + R: 2, 'NEW-TAKE' + R: 1})
        self.assertEqual(_ruled(line, *_sent(**{'answer:D': take}), flags={'new_take_forms': False}),
                         {'NEW-SEND' + R: 2, 'NEW-TAKE': 1})
        other = (_st('HELD', '2026-11-10', held=True), _st('2026-11-10', '2026-11-10', taken=True))
        self.assertEqual(_ruled(line, *_sent(**{'answer:D': other})), {'NEW-SEND' + R: 1, 'NEW-SEND': 1,
                                                                        'NEW-TAKE': 1})
        # a conflict that takes a decided form's date (the first design's shape) is no newly sent date: refused
        base, head = _sent(**{'answer:D': take})
        head['none'] = _st('DATELESS')
        self.assertEqual(_ruled(line, base, head, ('conflict', None)), {'NEW-SEND': 1, 'NEW-TAKE': 1})

    def test_a_changed_fact_is_accepted_only_beside_a_decided_form_or_as_a_declared_rewording(self):
        for line, ruled in (('Date of service: 9 November 2026', True), ('Date of service: 11/09/2026', False),
                            ('Exam date: 11/09/26', True), ('Date: 9 November 2026', False)):
            text, base = _doc(line, 'missing', None)
            _, head = _doc(line, 'document', '2026-11-09', base['states'])
            accept = freeze._ruled_acceptor({'t': base}, {'t': head}, {'t': text}, _ruling())
            counts = {k: v for k, v in freeze.classify({'t': base}, {'t': head}, accept)[0].items() if v}
            with self.subTest(line=line):
                self.assertEqual(counts, {'FACT-CHANGED' + (R if ruled else ''): 1})
        old, new = 'An old note.', 'A new note.'
        line = 'Date of service: 11/09/2026'
        for base_note, head_note, value, ok in ((old, new, None, True), ('X. ' + old, 'X. ' + new, None, True),
                                                (old, 'Another note.', None, False), (old, new, '2026-11-09', False)):
            text, base = _doc(line, 'missing', None, note=base_note)
            _, head = _doc(line, 'missing' if value is None else 'document', value, base['states'], note=head_note)
            accept = freeze._ruled_acceptor({'t': base}, {'t': head}, {'t': text},
                                            _ruling(note_rewordings=[[old, new]]))
            counts = {k: v for k, v in freeze.classify({'t': base}, {'t': head}, accept)[0].items() if v}
            with self.subTest(base_note=base_note, head_note=head_note, value=value):
                self.assertEqual(counts.get('FACT-CHANGED' + R, 0), int(ok), counts)
                self.assertEqual(counts.get('FACT-CHANGED', 0), int(not ok), counts)

    def test_send_to_ask_is_never_accepted(self):
        for line in ('Date of service: 9 November 2026', 'Exam date: 11/09/2026'):
            counts = _ruled(line, {'none': _st('2026-11-09')}, {'none': _st('DATELESS')}, ('missing', None))
            self.assertEqual(counts, {'SEND->ASK': 1}, line)
        declared = dict(_ruling(), movements={'NEW-HELD': 9, 'SEND->ASK': 9, 'NEW-TAKE': 9, 'NEW-SEND': 9})
        none = {'changed': [], 'removed': [], 'added': []}
        for cls in ('NEW-HELD', 'SEND->ASK', 'NEW-TAKE', 'NEW-SEND'):  # unaccepted, they fail whatever a count declares
            self.assertTrue(freeze.gate(none, collections.Counter({cls: 1}), declared), cls)
        self.assertEqual(freeze.gate(none, collections.Counter({'NEW-HELD' + R: 3}), declared), [])

    def test_the_ruling_names_its_constants_and_its_id(self):
        none = {'changed': [], 'removed': [], 'added': []}
        changed = dict(none, changed=['context.SERVICE_DATE'], head={'context.SERVICE_DATE': 'abc'})
        self.assertTrue(freeze.gate(changed, collections.Counter(), {}))
        self.assertTrue(freeze.gate(changed, collections.Counter(), _ruling()))
        self.assertTrue(freeze.gate(changed, collections.Counter(),
                                    _ruling(changed_cues={'context.SERVICE_DATE': 'abd'})))
        self.assertEqual(freeze.gate(changed, collections.Counter(),
                                     _ruling(changed_cues={'context.SERVICE_DATE': 'abc'})), [])
        self.assertTrue(freeze.gate(dict(changed, removed=['context.X']), collections.Counter(),
                                    _ruling(changed_cues={'context.SERVICE_DATE': 'abc'})))
        unknown = {'owner_ruling': {'id': 'another decision', 'changed_cues': {'context.SERVICE_DATE': 'abc'}}}
        self.assertTrue(freeze.gate(changed, collections.Counter(), unknown))
        self.assertTrue(freeze.gate(none, collections.Counter({'NEW-SEND' + R: 1}), unknown))

    def test_the_declaration_names_this_ruling(self):
        ruling = RULING['owner_ruling']
        self.assertEqual(ruling['id'], freeze.DATE_FORMS_RULING)
        self.assertTrue(set(ruling['changed_cues']) <= {k for k in freeze.cue_inventory() if k.startswith('context.')})
        self.assertEqual(RULING.get('movements'), {})
        self.assertTrue(ruling['new_send_forms'] and ruling['new_held_forms'] and ruling['new_take_forms'])
