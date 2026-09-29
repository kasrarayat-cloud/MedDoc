"""Per-change degradation and per-slot reference presentation in the compact mapping wire. Pure synthetic metadata.

An individually invalid change is NOT adopted and never refuses the rest of the proposal: a replacement leaves its
field with an uncertain verdict and no target, an addition is dropped, and each is recorded (change index, the wire
array, the field, the proposed slot, the reason). Envelope violations still refuse the whole response.
"""
import copy
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from documents.mapping_limits import MAX_MAPPING_LABEL
from core import mapping_assistance, mapping_wire as wire


def payload(count=3, fields=2):
    body = {'slots': [{'slot': f'word/document.xml#body/p[{n}]', 'text': '🏥 Plan: rest', 'heading': 'Clinical form',
                       'row_label': 'Plan', 'options': ['Yes', 'No']} for n in range(count)],
            'fields': [{'key': f'f{n}', 'label': 'Plan', 'kind': 'text', 'slots': [f'word/document.xml#body/p[{n}]'],
                        'options': []} for n in range(fields)]}
    body['text_refs'] = wire.catalog(body)
    return body


def ref(body, sid, role=0, index=0):
    return body['text_refs'].index([sid, role, index])


def change(body, fid, sid, **kw):
    """'Plan' from slot `sid`'s own text: [fid, sid, text, ref, 2, 6, -1]."""
    row = [fid, sid, 0, ref(body, sid), 2, 6, -1]
    for name, value in kw.items():
        row[{'kind': 2, 'ref': 3, 'start': 4, 'end': 5, 'glyph': 6}[name]] = value
    return row


def replacing(body, fid, *changes, verdict=True):
    answer = wire.fixture(body)
    if verdict:
        answer['f']['k'].remove(fid); answer['f']['r'].append(fid)
    answer['x'] = [list(c) for c in changes]
    return answer


class PerChangeDegradation(SimpleTestCase):
    def assertRejectedReplacement(self, body, answer, reason, fid=0, index=0, slot=None):
        expanded, _ = wire.expand(body, answer)
        field = expanded['fields'][fid]
        self.assertEqual((field['key'], field['verdict'], field['target']), (f'f{fid}', 'uncertain', None))
        rows = [r for r in expanded['rejected'] if r['key'] == f'f{fid}']
        self.assertTrue(rows, expanded['rejected'])
        self.assertTrue(any(reason in r['reason'] for r in rows), rows)
        row = next(r for r in rows if reason in r['reason'])
        self.assertEqual((row['type'], row['change']), ('replacement', index))
        if index is not None:
            self.assertEqual(row['wire'], answer['x'][index])
        if slot is not None:
            self.assertEqual(row['slot'], slot)
        # Every other field keeps its verdict; nothing invalid became a target or an addition.
        self.assertTrue(all(f['verdict'] == 'keep' for n, f in enumerate(expanded['fields']) if n != fid))
        self.assertTrue(all(f['target'] is None for f in expanded['fields']))
        return expanded

    def test_each_invalid_replacement_class_keeps_the_field_uncertain_and_records_why(self):
        body = payload(); long_body = payload()
        long_body['slots'][0]['text'] = 'Q' * (MAX_MAPPING_LABEL + 1); long_body['text_refs'] = wire.catalog(long_body)
        slot = body['slots'][0]['slot']
        cases = [
            ('foreign text reference', body, change(body, 0, 0, ref=ref(body, 1)), 'Source text belongs to another destination.', slot),
            ('unknown text reference', body, change(body, 0, 0, ref=len(body['text_refs'])), 'Unknown source text reference.', slot),
            ('negative start', body, change(body, 0, 0, start=-1), 'Invalid Unicode source span', slot),
            ('end beyond text', body, change(body, 0, 0, end=999), 'Invalid Unicode source span', slot),
            ('empty span', body, change(body, 0, 0, end=2), 'Invalid Unicode source span', slot),
            ('label beyond the limit', long_body, change(long_body, 0, 0, start=0, end=MAX_MAPPING_LABEL + 1),
             'Invalid Unicode source span', slot),
            ('unknown slot ID', body, change(body, 0, 0) [:1] + [len(body['slots'])] + change(body, 0, 0)[2:],
             'Unknown mapping change destination, kind or glyph.', ''),
            ('unknown kind code', body, change(body, 0, 0, kind=len(wire.KINDS)), 'Unknown mapping change destination, kind or glyph.', slot),
            ('glyph beyond the limit', body, change(body, 0, 0, glyph=200), 'Unknown mapping change destination, kind or glyph.', slot),
            ('target not mapped to its field', body, change(body, 0, 1), 'Replacement target belongs to another field destination.',
             body['slots'][1]['slot']),
            ('another field\'s prior label', body, change(body, 0, 0, ref=ref(body, 1, 4), start=0, end=4),
             'Prior label does not own this replacement destination.', slot),
            ('foreign option reference', body, change(body, 0, 0) + [ref(body, 1, 3, 0), 0, 3],
             'Source text belongs to another destination.', slot),
            ('invalid option span', body, change(body, 0, 0) + [ref(body, 0, 3, 0), 0, 9], 'Invalid Unicode source span', slot),
        ]
        for name, source, bad, reason, where in cases:
            with self.subTest(name):
                self.assertRejectedReplacement(source, replacing(source, 0, bad), reason, slot=where)

    def test_ownership_classes_hold_the_field_without_refusing_the_proposal(self):
        body = payload()
        # A change for a field whose verdict is keep: not adopted, and the field is held.
        self.assertRejectedReplacement(body, replacing(body, 0, change(body, 0, 0), verdict=False),
                                       'Replacement does not uniquely own a replace verdict.')
        # Two changes for one field: neither is adopted.
        answer = replacing(body, 0, change(body, 0, 0), change(body, 0, 0))
        expanded = self.assertRejectedReplacement(body, answer, 'Replacement does not uniquely own a replace verdict.')
        self.assertEqual(sorted(r['change'] for r in expanded['rejected']), [0, 1])
        # A replace verdict with no change: held, recorded, nothing refused.
        expanded = self.assertRejectedReplacement(body, replacing(body, 0), 'A replacement verdict lacks its bound change.',
                                                  index=None, slot='')
        self.assertEqual(expanded['rejected'][0]['wire'], None)

    def test_invalid_additions_are_dropped_and_recorded_while_valid_changes_are_adopted(self):
        body = payload()
        bad = [change(body, -1, 2, ref=ref(body, 1)),                                     # foreign reference
               change(body, -1, 2, ref=ref(body, 0, 4), start=0, end=4),                  # a prior label as an addition
               change(body, -1, 2, end=999)]                                              # invalid span
        answer = replacing(body, 1, change(body, 1, 1), *bad, change(body, -1, 2))
        expanded, _ = wire.expand(body, answer)
        self.assertEqual(expanded['fields'][1]['verdict'], 'replace')
        self.assertEqual(expanded['fields'][1]['target']['label'], 'Plan')
        self.assertEqual(len(expanded['additions']), 1)
        # Each adopted change also names the WHOLE printed text its label quotes (the place rule reads that wording).
        self.assertEqual(expanded['sources'], {'fields': {'f1': 0}, 'additions': [4],
                                               'quoted': {0: body['slots'][1]['text'], 4: body['slots'][2]['text']}})
        self.assertEqual([(r['change'], r['type'], r['key'], r['slot']) for r in expanded['rejected']],
                         [(n, 'addition', '', body['slots'][2]['slot']) for n in (1, 2, 3)])
        self.assertEqual([r['wire'] for r in expanded['rejected']], bad)

    def test_the_rejection_record_reaches_validate_proposal_unchanged(self):
        # validate_proposal consumes 'rejected' and 'sources' before the strict proposal schema (extra='forbid').
        body = payload()
        expanded, _ = wire.expand(body, replacing(body, 0, change(body, 0, 0, ref=ref(body, 1))))
        with self.assertRaises(ValueError):
            mapping_assistance.Proposal.model_validate(expanded)
        mapping_assistance.Proposal.model_validate({k: v for k, v in expanded.items() if k not in ('rejected', 'sources')})

    def test_envelope_violations_still_refuse_the_whole_response(self):
        body = payload(); good = replacing(body, 0, change(body, 0, 0))
        wire.expand(body, good)
        candidates = []
        bad = copy.deepcopy(good); bad['f']['k'] = []; candidates.append(('incomplete field partition', body, bad))
        bad = copy.deepcopy(good); bad['s']['u'] = bad['s']['u'] + [0]; candidates.append(('duplicate slot', body, bad))
        bad = copy.deepcopy(good); bad['extra'] = 1; candidates.append(('schema member', body, bad))
        bad = copy.deepcopy(good); bad['x'][0][1] = True; candidates.append(('schema strict int', body, bad))
        bad = copy.deepcopy(good); bad['x'][0] = bad['x'][0] + [0]; candidates.append(('incomplete option triple', body, bad))
        bad = copy.deepcopy(good); bad['x'][0][0] = len(body['fields']); candidates.append(('invented field', body, bad))
        tampered = copy.deepcopy(body); tampered['text_refs'][0][0] = 1; candidates.append(('catalog mismatch', tampered, good))
        many = copy.deepcopy(good)
        for _ in range(4):
            many['x'].append(change(body, -1, 2) + [ref(body, 2, 3, 0), 0, 3] * 100)
        many['x'][0].extend([ref(body, 0, 3, 0), 0, 3]); candidates.append(('option capacity', body, many))
        for name, source, answer in candidates:
            with self.subTest(name), self.assertRaises((ValidationError, ValueError)):
                wire.expand(source, answer)


class PerSlotPresentation(SimpleTestCase):
    def test_each_slot_and_field_lists_its_own_catalog_positions_and_the_catalog_is_unchanged(self):
        body = payload(4, 2); body['slots'][1]['text'] = ''; body['slots'][2]['options'] = []
        body['slots'][3].update(text='', heading='', row_label='', options=[])     # a slot with no text reference
        body['text_refs'] = wire.catalog(body); before = copy.deepcopy(body['text_refs'])
        wire.present(body)
        self.assertEqual(body['text_refs'], before); self.assertEqual(wire.catalog(body), before)
        for sid, row in enumerate(body['slots'][:3]):
            # A compact list of the slot's own catalog positions, in catalog order (text, heading, row_label, options).
            expected = [n for n, (owner, role, _) in enumerate(before) if owner == sid and role != 4]
            self.assertEqual(row['refs'], expected)
            self.assertTrue(all(before[position][0] == sid for position in row['refs']))
        self.assertEqual([before[n][1] for n in body['slots'][1]['refs']], [1, 2, 3, 3])      # no text role
        self.assertEqual([before[n][1] for n in body['slots'][2]['refs']], [0, 1, 2])         # no options
        self.assertNotIn('refs', body['slots'][3])                                            # empty lists are omitted
        self.assertEqual([f['label_ref'] for f in body['fields']], [before.index([n, 4, 0]) for n in range(2)])

    def test_presented_and_legacy_requests_expand_identically_and_a_wrong_presentation_refuses(self):
        legacy = payload(); presented = wire.present(copy.deepcopy(legacy))
        answer = replacing(legacy, 0, change(legacy, 0, 0), change(legacy, -1, 2, ref=ref(legacy, 1)))
        self.assertEqual(wire.expand(legacy, copy.deepcopy(answer)), wire.expand(presented, copy.deepcopy(answer)))
        for name, mutate in [('a slot lists another slot\'s ID', lambda b: b['slots'][0]['refs'].__setitem__(0, ref(b, 1))),
                             ('a slot lists one ID too many', lambda b: b['slots'][0]['refs'].append(ref(b, 1))),
                             ('an empty list is sent', lambda b: b['slots'][0].update(refs=[])),
                             ('a field lists another label', lambda b: b['fields'][0].update(label_ref=ref(b, 1, 4))),
                             ('one slot is not presented', lambda b: b['slots'][2].pop('refs')),
                             ('one field is not presented', lambda b: b['fields'][1].pop('label_ref'))]:
            bad = copy.deepcopy(presented); mutate(bad)
            with self.subTest(name), self.assertRaises(ValidationError):
                wire.expand(bad, copy.deepcopy(answer))

    def test_the_instructions_name_the_per_slot_lists_and_the_separate_numbering(self):
        for words in ('refs', 'label_ref', 'target slot', 'never a slot ID', 'text_refs order'):
            self.assertIn(words, wire.INSTRUCTIONS)
        self.assertIn(wire.INSTRUCTIONS, mapping_assistance.SYSTEM)
        # The unpresented request keeps the v3 prompt, which never names the presentation it does not carry.
        self.assertTrue(wire.INSTRUCTIONS.startswith(wire.INSTRUCTIONS_V3))
        self.assertTrue(mapping_assistance.SYSTEM_V3.endswith(wire.INSTRUCTIONS_V3))
        for words in ('refs', 'label_ref'):
            self.assertNotIn(words, wire.INSTRUCTIONS_V3.replace('text_refs', ''))
