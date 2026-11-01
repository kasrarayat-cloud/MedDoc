"""retrieve(): the facts and CMS passages recorded for each proposed code (HARNESS.md 5), on the bundled curation.

The facts are synthetic rows in the layout the PFS and MUE importers store (tests/test_reference.py); the passages are
the bundled data files, read without the database in load_passages' shape.
"""
import hashlib
import json
import random
import re
from datetime import date, datetime, timezone

from django.test import SimpleTestCase

from studio.reference.passages import (CODE_THEN_DESCRIPTION, NO_DATE_NOTE, NOT_CONNECTED, passage_sha256,
                                       retrieve)
from studio.reference.store import UNKNOWN_DATE_NOTE, InMemoryReferenceLookup
from studio.types import CodeReference, ReferenceSourceInfo
from tests.test_passages import CLAIMS, NCCI, PFS_DOC, file_passages

PFS_KEY, MUE_KEY = 'cms-pfs-rvu26d', 'cms-mue-practitioner-2026q4'
DAY = date(2026, 10, 21)


def info(key, kind, release, start='2026-10-01', end='2026-12-31'):
    return ReferenceSourceInfo(key=key, kind=kind, publisher='CMS', title=key, release=release, url='https://x',
                               sha256=hashlib.sha256(key.encode()).hexdigest(), effective_start=start,
                               effective_end=end, license_note='', scope_note='')


def pfs(status, global_days, mult_proc, endo_base, pctc):
    return {'status': status, 'global_days': global_days, 'mult_proc': mult_proc, 'endo_base': endo_base,
            'pctc': pctc}


# Synthetic PFS rows: the endoscopic families of the reference fixture (bases 43235 and 45378, whose own indicator is
# 2 there) and a few codes for the code-number rules. Values are test data, not CMS's.
ROWS = {
    '43235': pfs('A', '000', '2', None, '0'), '43239': pfs('A', '000', '3', '43235', '0'),
    '45378': pfs('A', '000', '2', None, '0'), '45380': pfs('A', '000', '3', '45378', '0'),
    '45385': pfs('A', '000', '3', '45378', '0'), '99213': pfs('A', 'XXX', '0', None, '0'),
    '76000': pfs('A', 'XXX', '0', None, '1'), '43753': pfs('A', 'XXX', '0', None, '0'),
    '43450': pfs('A', '000', '2', None, '0'), '46221': pfs('A', '010', '2', None, '0'),
    '93010': pfs('A', 'XXX', '0', None, '2'),
}
MUE_ROW = {'value': 1, 'mai': {'indicator': 2, 'label': 'Date of Service Edit: Policy'},
           'rationale': 'Anatomic Consideration'}


def lookup(release='RVU26D', start='2026-10-01', end='2026-12-31', pfs_key=PFS_KEY):
    return InMemoryReferenceLookup(
        [info(pfs_key, 'cms-pfs', release, start, end), info(MUE_KEY, 'cms-mue-practitioner', '2026-Q4')],
        {pfs_key: {(code, ''): row for code, row in ROWS.items()}, MUE_KEY: {('45385', ''): MUE_ROW}})


PASSAGES = file_passages()


def run(codes, day=DAY, reference=None, passages=None):
    return {entry['code']: entry for entry in retrieve(codes, day, reference or lookup(),
                                                       PASSAGES if passages is None else passages)}


def keys(entry, topic=None):
    return [(p['source_key'], p['passage_key']) for p in entry['passages'] if topic is None or p['topic'] == topic]


def rules(entry):
    """{(topic, value)} of the endoscopy rules retrieved for one code."""
    return {(p['topic'], p['topic_value']) for p in entry['passages']
            if p['topic'] in ('ncci.endoscopy', 'claims.multiple_endoscopy')}


PFS_45385 = [(PFS_DOC, 'status-A'), (PFS_DOC, 'global-000'), (PFS_DOC, 'mult-proc-3-part-1'),
             (PFS_DOC, 'mult-proc-3-part-2'), (PFS_DOC, 'endo-base'), (PFS_DOC, 'pctc-0')]
RULE_1, RULE_2, RULE_4, RULE_7, RULE_16 = (('ncci.endoscopy', n) for n in ('1', '2', '4', '7', '16'))
ITEM_13, ITEM_14 = ('claims.multiple_endoscopy', '13'), ('claims.multiple_endoscopy', '14')


class ShapeTests(SimpleTestCase):
    def test_one_entry_per_code_sorted_and_unique(self):
        entries = retrieve(['45385', '43239', '45385', '99213'], DAY, lookup(), PASSAGES)
        self.assertEqual([e['code'] for e in entries], ['43239', '45385', '99213'])
        self.assertEqual(retrieve([], DAY, lookup(), PASSAGES), [])

    def test_the_entry_fact_and_passage_shapes(self):
        entry = run(['45385'])['45385']
        self.assertEqual(list(entry), ['code', 'service_date', 'facts', 'passages', 'lookups', 'notes'])
        self.assertEqual(entry['service_date'], '2026-10-21')
        self.assertEqual([f['field'] for f in entry['facts']],
                         ['pfs.status', 'pfs.global_days', 'pfs.mult_proc', 'pfs.endo_base', 'pfs.pctc', 'mue.value',
                          'mue.mai', 'mue.rationale'])
        status, endo, mai = entry['facts'][0], entry['facts'][3], entry['facts'][6]
        pfs_source = lookup().sources()[1]
        self.assertEqual(status, {'source_key': PFS_KEY, 'release': 'RVU26D', 'effective': ['2026-10-01', '2026-12-31'],
                                  'sha256': pfs_source.sha256, 'field': 'pfs.status', 'value': 'A', 'kind': 'cms-pfs',
                                  'label': 'PFS status code'})
        self.assertEqual(endo['value'], '45378')
        self.assertEqual((mai['source_key'], mai['release'], mai['value']), (MUE_KEY, '2026-Q4', MUE_ROW['mai']))
        for passage in entry['passages']:
            self.assertEqual(list(passage), ['source_key', 'release', 'passage_key', 'section', 'page', 'topic',
                                             'topic_value', 'sha256', 'text'])
            self.assertEqual(passage['sha256'], passage_sha256(passage['text']))
        json.dumps(entry)  # the trace is JSON data as it stands

    def test_a_code_that_lacks_facts_says_so(self):
        entry = run(['45999'])['45999']
        self.assertEqual((entry['facts'], entry['passages']), ([], []))
        self.assertEqual(entry['notes'], ['45999 is not listed in RVU26D.', '45999 is not listed in 2026-Q4.',
                                          '45999 has no PFS facts for 2026-10-21; no PFS definition was retrieved for '
                                          'it.'])
        self.assertEqual(entry['lookups'], [f'reference lookup 45999 on 2026-10-21: {PFS_KEY}, {MUE_KEY}'])

    def test_codes_and_dates_are_checked(self):
        with self.assertRaises(TypeError):
            retrieve('45385', DAY, lookup(), PASSAGES)
        for bad in ([45385], ['']):
            with self.assertRaises(ValueError):
                retrieve(bad, DAY, lookup(), PASSAGES)
        with self.assertRaises(TypeError):
            retrieve(['45385'], datetime(2026, 10, 21, tzinfo=timezone.utc), lookup(), PASSAGES)

    def test_inconsistent_inputs_are_refused(self):
        tampered = [dict(p, text=p['text'] + ' ') if p['passage_key'] == 'status-A' else p for p in PASSAGES]
        with self.assertRaisesRegex(ValueError, 'status-A does not match its sha256'):
            retrieve(['45385'], DAY, lookup(), tampered)
        split = [dict(p, release='RVU26C') if p['passage_key'] == 'global-000' else p for p in PASSAGES]
        with self.assertRaisesRegex(ValueError, f'passages of {PFS_DOC} disagree'):
            retrieve(['45385'], DAY, lookup(), split)

        class Unlisted:
            def sources(self):
                return ()

            def lookup(self, code, service_date):
                return CodeReference(code=code, pfs=dict(ROWS[code], source_key='elsewhere'))

        with self.assertRaisesRegex(ValueError, "names source 'elsewhere'"):
            retrieve(['45385'], DAY, Unlisted(), PASSAGES)

    def test_retrieval_is_deterministic(self):
        codes = ['45385', '43239', '45380', '43235', '76000', '43450', '99213', '45999']
        first = retrieve(codes, DAY, lookup(), PASSAGES)
        shuffled_codes, shuffled_passages = codes[:], PASSAGES[:]
        random.Random(20261101).shuffle(shuffled_codes)
        random.Random(20261102).shuffle(shuffled_passages)
        second = retrieve(shuffled_codes, DAY, lookup(), shuffled_passages)
        self.assertEqual(json.dumps(first), json.dumps(second))
        self.assertEqual(json.dumps(first), json.dumps(retrieve(codes, DAY, lookup(), PASSAGES)))

    def test_nothing_retrieved_carries_a_description_form(self):
        entries = retrieve(list(ROWS), DAY, lookup(), PASSAGES)
        texts = [p['text'] for e in entries for p in e['passages']]
        self.assertGreater(len(texts), 40)
        self.assertEqual([t for t in texts if CODE_THEN_DESCRIPTION.search(t) or re.search(r'[0-9]{5}\s*\(', t)], [])
        # nor does any line of the trace CPT Studio writes itself
        written = [line for e in entries for line in e['lookups'] + e['notes']]
        written += [line for e in retrieve(list(ROWS), None, lookup(), PASSAGES) for line in e['lookups'] + e['notes']]
        self.assertEqual([line for line in written if CODE_THEN_DESCRIPTION.search(line)], [])

    def test_the_not_connected_sources_are_named_as_the_api_reports_them(self):
        self.assertEqual(NOT_CONNECTED, ('NCCI procedure-to-procedure edits (AMA licence agreement not accepted)',
                                         'AMA CPT descriptors and guidelines (no licence)', 'Payer policies'))


class PfsDefinitionTests(SimpleTestCase):
    def test_a_codes_own_values_select_their_definitions(self):
        entry = run(['45385'])['45385']
        self.assertEqual(keys(entry), PFS_45385)
        self.assertEqual(entry['lookups'][1:], [
            f'passages pfs.status=A in {PFS_DOC}: 1', f'passages pfs.global_days=000 in {PFS_DOC}: 1',
            f'passages pfs.mult_proc=3 in {PFS_DOC}: 2',
            f'passages pfs.endo_base in {PFS_DOC} (45385 names the endoscopic base 45378): 1',
            f'passages pfs.pctc=0 in {PFS_DOC}: 1'])
        self.assertEqual(entry['notes'], [])
        office = run(['99213'])['99213']
        self.assertEqual(keys(office), [(PFS_DOC, 'status-A'), (PFS_DOC, 'global-XXX'), (PFS_DOC, 'mult-proc-0'),
                                        (PFS_DOC, 'pctc-0')])

    def test_a_value_without_a_passage_is_noted(self):
        entry = run(['93010'])['93010']
        self.assertNotIn((PFS_DOC, 'pctc-2'), keys(entry))
        self.assertIn(f'{PFS_DOC} has no passage for pfs.pctc=2.', entry['notes'])
        self.assertIn(f'passages pfs.pctc=2 in {PFS_DOC}: 0', entry['lookups'])

    def test_definitions_come_only_from_the_release_of_the_facts(self):
        other = lookup(release='RVU26X', pfs_key='cms-pfs-rvu26x')
        entry = run(['45385'], reference=other)['45385']
        self.assertEqual(keys(entry), [])
        self.assertIn(f'The CMS PFS file documentation covering 2026-10-21 ({PFS_DOC}) is release RVU26D, not RVU26X '
                      'of the facts; its definitions were not used.', entry['notes'])


class WindowTests(SimpleTestCase):
    def test_the_window_boundaries_are_inclusive(self):
        for day, applies in ((date(2026, 9, 30), False), (date(2026, 10, 1), True), (date(2026, 12, 31), True),
                             (date(2027, 1, 1), False)):
            with self.subTest(day=day):
                entry = run(['45385'], day=day)['45385']
                self.assertEqual(keys(entry) == PFS_45385, applies)
                if not applies:
                    self.assertEqual(entry['passages'], [])
                    self.assertIn(f'45385 has no PFS facts for {day.isoformat()}; no PFS definition was retrieved for '
                                  'it.', entry['notes'])

    def test_a_source_applies_only_inside_its_own_window(self):
        # Facts of a synthetic spring release, so that the rules can run in May: the NCCI chapter applies from
        # 2026-01-01, the claims chapter from its issue date 2026-05-07, the PFS documentation (RVU26D) not at all.
        spring = lookup(release='RVU26B', start='2026-04-01', end='2026-06-30', pfs_key='cms-pfs-rvu26b')
        before = run(['45380', '45385'], day=date(2026, 5, 6), reference=spring)['45385']
        self.assertEqual(rules(before), {RULE_2})
        self.assertIn('No CMS Claims Processing Manual passage source covers 2026-05-06.', before['notes'])
        self.assertIn('No CMS PFS file documentation passage source covers 2026-05-06.', before['notes'])
        on = run(['45380', '45385'], day=date(2026, 5, 7), reference=spring)['45385']
        self.assertEqual(rules(on), {RULE_2, ITEM_13})
        self.assertEqual(keys(on, 'claims.multiple_endoscopy'),
                         [(CLAIMS, 'item-13'), (CLAIMS, 'item-13-example'), (CLAIMS, 'item-13-note')])

    def test_no_service_date_applies_nothing_dated(self):
        entry = run(['45380', '45385'], day=None)['45385']
        self.assertEqual((entry['service_date'], entry['facts'], entry['passages']), (None, [], []))
        self.assertEqual(entry['notes'], [UNKNOWN_DATE_NOTE, NO_DATE_NOTE])
        self.assertEqual(entry['lookups'], ['reference lookup 45385 on an unknown date: no source applied'])

    def test_two_sources_of_one_kind_covering_the_date_are_not_used(self):
        copy = [dict(p, source_key='cms-ncci-copy', sha256=p['sha256']) for p in PASSAGES if p['source_key'] == NCCI]
        entry = run(['45380', '45385'], passages=PASSAGES + copy)['45385']
        self.assertEqual(rules(entry), {ITEM_13})
        self.assertIn(f'2 CMS NCCI Policy Manual passage sources cover 2026-10-21 (cms-ncci-copy, {NCCI}); none was '
                      'used because the applicable one is ambiguous.', entry['notes'])

    def test_with_no_passages_installed_only_the_facts_are_recorded(self):
        entry = run(['45385'], passages=[])['45385']
        self.assertEqual((len(entry['facts']), entry['passages']), (8, []))
        self.assertEqual(entry['notes'], ['No CMS PFS file documentation passage source covers 2026-10-21.'])


class EndoscopyRuleTests(SimpleTestCase):
    def test_two_codes_naming_one_base(self):
        found = run(['45380', '45385'])
        for code in ('45380', '45385'):
            self.assertEqual(rules(found[code]), {RULE_2, ITEM_13})
        self.assertIn(f'passages ncci.endoscopy=2 in {NCCI} (45380, 45385 name the endoscopic base 45378): 1',
                      found['45380']['lookups'])
        self.assertIn(f'passages claims.multiple_endoscopy=13 in {CLAIMS} (45380, 45385 are one endoscopic family '
                      '(base 45378)): 3', found['45385']['lookups'])

    def test_a_code_with_its_own_base(self):
        found = run(['45378', '45385'])
        self.assertEqual(rules(found['45385']), {RULE_1, ITEM_13})
        self.assertEqual(rules(found['45378']), {RULE_1, ITEM_13})
        self.assertEqual(keys(found['45378'], 'ncci.endoscopy'), [(NCCI, 'rule-01')])
        self.assertNotIn((PFS_DOC, 'endo-base'), keys(found['45378']))  # the base names no base of its own

    def test_unrelated_endoscopies_and_other_surgery(self):
        found = run(['43239', '45385'])
        self.assertEqual(rules(found['43239']), {ITEM_14})
        self.assertEqual(rules(found['45385']), {ITEM_14})
        self.assertEqual(keys(found['45385'], 'claims.multiple_endoscopy'), [(CLAIMS, 'item-14')])
        # a base of another family (indicator 2) and a non-endoscopic procedure (indicator 2) are other surgery
        self.assertEqual(rules(run(['43235', '45385'])['43235']), {ITEM_14})
        self.assertEqual(rules(run(['46221', '45385'])['46221']), {ITEM_14})
        # indicator 0 is not ranked with other procedures
        self.assertEqual(rules(run(['99213', '45385'])['45385']), set())
        # a proposed base is one of its family's related endoscopies, so other surgery reaches it too
        found = run(['45378', '45385', '46221'])
        self.assertEqual(rules(found['45378']), {RULE_1, ITEM_13, ITEM_14})
        self.assertEqual(rules(found['45385']), {RULE_1, ITEM_13, ITEM_14})
        self.assertEqual(rules(found['46221']), {ITEM_14})
        self.assertIn(f'passages claims.multiple_endoscopy=14 in {CLAIMS} (46221 is not of one endoscopic family with '
                      '45378, 45385): 1', found['46221']['lookups'])

    def test_two_families_with_a_base_proposed(self):
        found = run(['43235', '43239', '45385'])
        self.assertEqual(rules(found['43239']), {RULE_1, ITEM_13, ITEM_14})
        self.assertEqual(rules(found['43235']), {RULE_1, ITEM_13, ITEM_14})
        self.assertEqual(rules(found['45385']), {ITEM_14})
        self.assertIn(f'passages claims.multiple_endoscopy=14 in {CLAIMS} (45385 is not of one endoscopic family with '
                      '43235, 43239): 1', found['45385']['lookups'])

    def test_one_endoscopy_alone_selects_no_rule(self):
        self.assertEqual(rules(run(['45385'])['45385']), set())

    def test_the_rules_naming_their_own_codes(self):
        found = run(['76000', '43753', '43239'])
        self.assertEqual(rules(found['76000']), {RULE_16})
        self.assertEqual(rules(found['43753']), {RULE_4})
        self.assertEqual(rules(found['43239']), set())
        self.assertIn(f'passages ncci.endoscopy=16 in {NCCI} (76000 is rule 16\'s code, with 43239, of multiple '
                      'procedure indicator 3): 1', found['76000']['lookups'])
        dilation = run(['43450', '43239'])['43450']
        self.assertEqual(rules(dilation), {RULE_7, ITEM_14})
        # without an endoscopy none of them applies
        self.assertEqual(rules(run(['76000', '43753', '43450'])['76000']), set())

    def test_rules_are_listed_in_topic_then_rule_order(self):
        entry = run(['43235', '43239', '45385', '76000'])['43239']
        topics = [(p['topic'], p['topic_value']) for p in entry['passages']]
        self.assertEqual(topics, sorted(topics, key=lambda t: (['pfs.status', 'pfs.global_days', 'pfs.mult_proc',
                                                                 'pfs.endo_base', 'pfs.pctc', 'ncci.endoscopy',
                                                                 'claims.multiple_endoscopy'].index(t[0]),
                                                                len(t[1]), t[1])))
        self.assertEqual(keys(entry, 'claims.multiple_endoscopy'),
                         [(CLAIMS, 'item-13'), (CLAIMS, 'item-13-example'), (CLAIMS, 'item-13-note'),
                          (CLAIMS, 'item-14')])
