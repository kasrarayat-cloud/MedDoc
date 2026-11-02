"""The participants' CMS tool executor (HARNESS.md 11.2, 12.2; studio/reference/tools.py).

Synthetic reference rows in the layout the PFS and MUE importers store (tests/test_reference.py), and the bundled,
sha256-pinned passage data files imported as an installation imports them. Every test runs behind the participant
suites' network guard (tests/test_participants_support.py): the executor never reaches the network.
"""
import hashlib
import json
from datetime import date, datetime, timezone
from unittest import mock

from django.conf import settings

from studio.models import PassageSource, ReferenceCodeFact, ReferencePassage, ReferenceSource
from studio.participants import loop, prompt
from studio.reference import passages as reference_passages
from studio.reference import tools
from tests.test_participants_support import OfflineDatabaseTestCase

RETRIEVED = datetime(2026, 10, 23, 20, 59, tzinfo=timezone.utc)
PFS_KEY, MUE_KEY = 'cms-pfs-rvu26d', 'cms-mue-practitioner-2026q4'
DAY = '2026-10-21'
# Synthetic rows (test data, not CMS's): two endoscopic codes of base 45378, an office visit, a modifier-only code.
PFS_ROWS = {
    '45378': {'status': 'A', 'global_days': '000', 'mult_proc': '2', 'endo_base': None, 'pctc': '0'},
    '45385': {'status': 'A', 'global_days': '000', 'mult_proc': '3', 'endo_base': '45378', 'pctc': '0'},
    '99213': {'status': 'A', 'global_days': 'XXX', 'mult_proc': '0', 'endo_base': None, 'pctc': '0'},
}
MUE_ROWS = {'45385': {'value': 1, 'mai': {'indicator': 2, 'label': 'Date of Service Edit: Policy'},
                      'rationale': 'Anatomic Consideration'}}
PFS_FIELDS = ('status', 'global_days', 'mult_proc', 'endo_base', 'pctc')


def source(key, kind, release, start='2026-10-01', end='2026-12-31'):
    return ReferenceSource.objects.create(
        key=key, kind=kind, publisher='CMS', title=f'Synthetic {key}', release=release,
        url='https://www.cms.gov/synthetic', sha256=hashlib.sha256(key.encode()).hexdigest(), retrieved_at=RETRIEVED,
        effective_start=date.fromisoformat(start), effective_end=date.fromisoformat(end),
        license_note='CPT codes are copyright the American Medical Association.', scope_note='synthetic')


def install_store():
    pfs = source(PFS_KEY, 'cms-pfs', 'RVU26D')
    mue = source(MUE_KEY, 'cms-mue-practitioner', '2026-Q4')
    for code, facts in PFS_ROWS.items():
        ReferenceCodeFact.objects.create(source=pfs, code=code, facts=facts)
    ReferenceCodeFact.objects.create(source=pfs, code='86153', modifier='26', facts={'status': 'A'})
    for code, facts in MUE_ROWS.items():
        ReferenceCodeFact.objects.create(source=mue, code=code, facts=facts)
    return pfs, mue


def install_passages():
    for path in reference_passages.bundled_files():
        reference_passages.import_data_file(path)


def facts_call(codes, day=DAY):
    return {'codes': list(codes), 'date_of_service': day}


class Base(OfflineDatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.pfs, self.mue = install_store()
        install_passages()
        self.execute = tools.executor(None)

    def entry(self, result, code):
        return next(item for item in result['codes'] if item['code'] == code)


class CodeFactsTests(Base):
    def test_the_facts_of_each_code_with_their_source_and_refs(self):
        result, refs = self.execute('cms_code_facts', facts_call(['45385', '99213']))
        self.assertEqual((result['tool'], result['date_of_service'], result['releases']),
                         ('cms_code_facts', DAY, f'the release covering {DAY}'))
        entry = self.entry(result, '45385')
        pfs, mue = entry['sources']
        self.assertEqual({name: pfs[name] for name in ('source_key', 'kind', 'release', 'effective_start',
                                                        'effective_end', 'sha256')},
                         {'source_key': PFS_KEY, 'kind': 'cms-pfs', 'release': 'RVU26D',
                          'effective_start': '2026-10-01', 'effective_end': '2026-12-31', 'sha256': self.pfs.sha256})
        self.assertEqual([(fact['field'], fact['value']) for fact in pfs['facts']],
                         [(field, PFS_ROWS['45385'][field]) for field in PFS_FIELDS])
        self.assertEqual([fact['label'] for fact in pfs['facts']],
                         ['PFS status code', 'PFS global surgery days', 'PFS multiple procedure indicator',
                          'PFS endoscopic base code', 'PFS PC/TC indicator'])
        self.assertEqual([(fact['field'], fact['value']) for fact in mue['facts']],
                         [('value', 1), ('mai', {'indicator': 2, 'label': 'Date of Service Edit: Policy'}),
                          ('rationale', 'Anatomic Consideration')])
        self.assertEqual((mue['source_key'], mue['release']), (MUE_KEY, '2026-Q4'))
        self.assertEqual(entry['notes'], [])
        # 99213 has a PFS row and no MUE row: CPT Studio says so in its own sentence
        self.assertEqual(self.entry(result, '99213')['notes'], ['99213 is not listed in 2026-Q4.'])
        expected = ([f'fact:{PFS_KEY}:45385:{field}' for field in PFS_FIELDS]
                    + [f'fact:{MUE_KEY}:45385:{field}' for field in ('value', 'mai', 'rationale')]
                    + [f'fact:{PFS_KEY}:99213:{field}' for field in PFS_FIELDS])
        self.assertEqual(refs, expected)
        # every fact carries its own ref, and the refs are exactly the facts returned
        self.assertEqual([fact['ref'] for item in result['codes'] for src in item['sources'] for fact in src['facts']],
                         refs)

    def test_codes_are_deduplicated_sorted_and_the_order_given_changes_nothing(self):
        once = self.execute('cms_code_facts', facts_call(['99213', '45385']))
        again = self.execute('cms_code_facts', facts_call(['45385', '99213', '45385', '99213']))
        self.assertEqual(once, again)
        self.assertEqual([item['code'] for item in once[0]['codes']], ['45385', '99213'])

    def test_a_code_no_source_lists_and_a_modifier_only_code_say_so(self):
        result, refs = self.execute('cms_code_facts', facts_call(['45999', '86153']))
        self.assertEqual(self.entry(result, '45999'), {
            'code': '45999', 'sources': [],
            'notes': ['45999 is not listed in RVU26D.', '45999 is not listed in 2026-Q4.']})
        self.assertEqual(self.entry(result, '86153')['notes'],
                         ['86153 is listed in RVU26D only with modifier(s) 26; it has no unmodified row.',
                          '86153 is not listed in 2026-Q4.'])
        self.assertEqual(refs, [])

    def test_no_source_for_the_date_says_so_for_each_kind(self):
        result, refs = self.execute('cms_code_facts', facts_call(['45385'], '2027-02-01'))
        self.assertEqual(self.entry(result, '45385'), {
            'code': '45385', 'sources': [],
            'notes': ['45385: no installed CMS Physician Fee Schedule source covers 2027-02-01.',
                      '45385: no installed CMS practitioner MUE source covers 2027-02-01.']})
        self.assertEqual(refs, [])

    def test_every_release_held_when_the_date_is_empty(self):
        later = source('cms-pfs-rvu27a', 'cms-pfs', 'RVU27A', '2027-01-01', '2027-03-31')
        ReferenceCodeFact.objects.create(source=later, code='45385', facts=dict(PFS_ROWS['45385'], mult_proc='9'))
        result, refs = self.execute('cms_code_facts', facts_call(['45385'], ''))
        self.assertEqual((result['date_of_service'], result['releases']), ('', 'every release held'))
        entry = self.entry(result, '45385')
        self.assertEqual([(src['source_key'], src['release']) for src in entry['sources']],
                         [(PFS_KEY, 'RVU26D'), ('cms-pfs-rvu27a', 'RVU27A'), (MUE_KEY, '2026-Q4')])
        self.assertEqual([fact['value'] for src in entry['sources'][:2] for fact in src['facts']
                          if fact['field'] == 'mult_proc'], ['3', '9'])
        self.assertIn('fact:cms-pfs-rvu27a:45385:mult_proc', refs)
        self.assertIn(f'fact:{PFS_KEY}:45385:mult_proc', refs)
        # a dated call reads only the release covering the date
        dated, _ = self.execute('cms_code_facts', facts_call(['45385'], '2027-02-01'))
        self.assertEqual([src['source_key'] for src in self.entry(dated, '45385')['sources']], ['cms-pfs-rvu27a'])

    def test_two_sources_of_one_kind_covering_the_date_are_not_used(self):
        overlap = source('cms-pfs-overlap', 'cms-pfs', 'RVU26X', '2026-12-01', '2027-02-28')
        ReferenceCodeFact.objects.create(source=overlap, code='45385', facts={'status': 'X'})
        result, refs = self.execute('cms_code_facts', facts_call(['45385'], '2026-12-15'))
        entry = self.entry(result, '45385')
        self.assertEqual([src['source_key'] for src in entry['sources']], [MUE_KEY])
        self.assertEqual(entry['notes'], ['45385: 2 installed CMS Physician Fee Schedule sources cover 2026-12-15 '
                                          '(cms-pfs-rvu26d, cms-pfs-overlap); none was used because the applicable '
                                          'release is ambiguous.'])  # in window order, as every source is listed
        self.assertTrue(all(ref.startswith(f'fact:{MUE_KEY}:') for ref in refs))

    def test_bad_arguments_are_cpt_studio_s_own_sentences(self):
        too_many = [f'{45300 + n}' for n in range(33)]
        cases = {
            'not an object': (['45385'], tools.NOT_AN_OBJECT),
            'a missing field': ({'codes': ['45385']}, 'The arguments must be exactly codes and date_of_service.'),
            'an extra field': ({**facts_call(['45385']), 'modifier': '26'},
                               'The arguments must be exactly codes and date_of_service.'),
            'codes not a list': ({'codes': '45385', 'date_of_service': DAY}, tools.CODES_LIST),
            'a code not a string': ({'codes': [45385], 'date_of_service': DAY}, tools.CODES_LIST),
            'no code': (facts_call([]), tools.NO_CODE),
            'more than 32': (facts_call(too_many), 'Give at most 32 different codes in one call; this call names 33.'),
            'a lower-case letter': (facts_call(['4538a']), tools.BAD_CODES.format(count=1, verb='is')),
            'four digits': (facts_call(['4538', '45385']), tools.BAD_CODES.format(count=1, verb='is')),
            'six characters': (facts_call(['453850', '45385 ']), tools.BAD_CODES.format(count=2, verb='are')),
            'non-ASCII digits': (facts_call(['٤٥٣٨٥']),
                                 tools.BAD_CODES.format(count=1, verb='is')),
            'a slash date': (facts_call(['45385'], '2026/10/21'), tools.BAD_DATE),
            'an impossible date': (facts_call(['45385'], '2026-13-01'), tools.BAD_DATE),
            'a date and time': (facts_call(['45385'], '2026-10-21T00:00'), tools.BAD_DATE),
            'a date not a string': (facts_call(['45385'], None), tools.BAD_DATE),
        }
        for label, (arguments, sentence) in cases.items():
            with self.subTest(label):
                self.assertEqual(self.execute('cms_code_facts', arguments), ({'error': sentence}, []))
        # 32 different codes are fine (duplicates are not counted twice)
        result, _ = self.execute('cms_code_facts', facts_call(too_many[:32] + too_many[:5]))
        self.assertEqual(len(result['codes']), 32)

    def test_an_unknown_tool(self):
        for name in ('cms_web_search', '', None, 'CMS_CODE_FACTS'):
            with self.subTest(name):
                self.assertEqual(self.execute(name, facts_call(['45385'])), ({'error': tools.UNKNOWN_TOOL}, []))

    def test_a_store_error_is_cpt_studio_s_sentence_and_is_logged(self):
        with mock.patch('studio.reference.tools.ReferenceSource.objects.filter', side_effect=RuntimeError('db down')), \
                self.assertLogs('studio.reference.tools', level='ERROR') as logged:
            self.assertEqual(self.execute('cms_code_facts', facts_call(['45385'])), ({'error': tools.STORE_ERROR}, []))
        self.assertIn('cms_code_facts failed', logged.output[0])


class PolicyPassagesTests(Base):
    def file_passages(self, topics):
        return sorted(((p['source_key'], p['passage_key']) for p in reference_passages.load_passages()
                       if p['topic'] in topics))

    def test_each_topic_returns_its_passages_verbatim_with_their_source_and_refs(self):
        for topic, passage_topics in tools.POLICY_TOPICS.items():
            with self.subTest(topic):
                result, refs = self.execute('cms_policy_passages', {'topic': topic, 'codes': ['45385', '45380']})
                self.assertEqual((result['tool'], result['topic'], result['codes'], result['notes']),
                                 ('cms_policy_passages', topic, ['45380', '45385'], []))
                self.assertEqual(sorted((p['source_key'], p['passage_key']) for p in result['passages']),
                                 self.file_passages(passage_topics))
                self.assertEqual(refs, [p['passage_key'] for p in result['passages']])
                self.assertEqual(len(set(refs)), len(refs))
                stored = {(row.source.key, row.passage_key): row for row in
                          ReferencePassage.objects.select_related('source')}
                for passage in result['passages']:
                    row = stored[(passage['source_key'], passage['passage_key'])]
                    self.assertEqual((passage['text'], passage['sha256'], passage['source_sha256']),
                                     (row.text, row.sha256, row.source.sha256))
                    self.assertEqual(hashlib.sha256(passage['text'].encode()).hexdigest(), passage['sha256'])
                    self.assertEqual((passage['release'], passage['effective_start'], passage['effective_end'],
                                      passage['section'], passage['page'], passage['kind']),
                                     (row.source.release, row.source.effective_start.isoformat(),
                                      row.source.effective_end.isoformat(), row.section, row.page, row.source.kind))
                    self.assertEqual(passage['ref'], passage['passage_key'])

    def test_pfs_definitions_come_in_retrieval_order(self):
        result, _ = self.execute('cms_policy_passages', {'topic': 'pfs_indicator_definitions', 'codes': []})
        topics = [p['topic'] for p in result['passages']]
        self.assertEqual(list(dict.fromkeys(topics)),
                         ['pfs.status', 'pfs.global_days', 'pfs.mult_proc', 'pfs.endo_base', 'pfs.pctc'])
        self.assertEqual(topics, sorted(topics, key=list(dict.fromkeys(topics)).index))

    def test_a_hint_date_narrows_to_the_source_covering_it(self):
        hinted = tools.executor(None, service_date_hint=date(2026, 6, 1))
        result, refs = hinted('cms_policy_passages', {'topic': 'pfs_indicator_definitions', 'codes': []})
        self.assertEqual((result['passages'], refs), ([], []))
        self.assertEqual(result['notes'], ['No CMS PFS file documentation passage source covers 2026-06-01.'])
        result, refs = hinted('cms_policy_passages', {'topic': 'multiple_endoscopy_payment', 'codes': []})
        self.assertEqual({p['source_key'] for p in result['passages']}, {'cms-claims-manual-100-04-ch12'})
        with self.assertRaises(TypeError):
            tools.executor(None, service_date_hint=datetime(2026, 6, 1, tzinfo=timezone.utc))

    def test_no_passage_installed_says_so(self):
        ReferencePassage.objects.all().delete()
        PassageSource.objects.all().delete()
        result, refs = self.execute('cms_policy_passages', {'topic': 'ncci_endoscopy_rules', 'codes': ['45385']})
        self.assertEqual((result['passages'], refs, result['notes']),
                         ([], [], ['No CMS NCCI Policy Manual passages of this topic are installed.']))

    def test_bad_arguments(self):
        cases = {
            'an unknown topic': ({'topic': 'payer_policies', 'codes': []}, tools.BAD_TOPIC),
            'a missing field': ({'topic': 'ncci_endoscopy_rules'}, 'The arguments must be exactly topic and codes.'),
            'a bad code': ({'topic': 'ncci_endoscopy_rules', 'codes': ['4538']},
                           tools.BAD_CODES.format(count=1, verb='is')),
            'codes not a list': ({'topic': 'ncci_endoscopy_rules', 'codes': None}, tools.CODES_LIST),
        }
        for label, (arguments, sentence) in cases.items():
            with self.subTest(label):
                self.assertEqual(self.execute('cms_policy_passages', arguments), ({'error': sentence}, []))
        self.assertEqual(tools.BAD_TOPIC, 'topic must be one of pfs_indicator_definitions, ncci_endoscopy_rules or '
                                          'multiple_endoscopy_payment.')

    def test_a_stored_passage_shaped_like_a_descriptor_is_never_returned(self):
        # the import refuses such a text; a row written around it is refused here too (I9: never a descriptor)
        row = ReferencePassage.objects.filter(topic='ncci.endoscopy').first()
        text = 'Synthetic 45385 (a description-shaped text) inserted around the import.'
        ReferencePassage.objects.filter(pk=row.pk).update(text=text, sha256=hashlib.sha256(text.encode()).hexdigest())
        with self.assertLogs('studio.reference.tools', level='ERROR'):
            self.assertEqual(self.execute('cms_policy_passages', {'topic': 'ncci_endoscopy_rules', 'codes': []}),
                             ({'error': tools.DESCRIPTOR}, []))


class ContractTests(Base):
    def test_the_mapped_topics_are_the_tools_enumeration(self):
        self.assertEqual(tuple(tools.POLICY_TOPICS), tuple(prompt.POLICY_TOPICS))
        self.assertEqual(tools.TOOL_NAMES, tuple(tool['name'] for tool in prompt.TOOLS))
        for topics in tools.POLICY_TOPICS.values():
            self.assertTrue(set(topics) <= set(reference_passages.TOPICS))

    def test_results_are_json_and_deterministic(self):
        calls = [('cms_code_facts', facts_call(['45385', '99213', '45999'])),
                 ('cms_code_facts', facts_call(['45385'], '')),
                 ('cms_policy_passages', {'topic': 'pfs_indicator_definitions', 'codes': ['45385']})]
        for name, arguments in calls:
            with self.subTest(name):
                first = self.execute(name, json.loads(json.dumps(arguments)))
                second = tools.executor('another-workspace')(name, json.loads(json.dumps(arguments)))
                self.assertEqual(first, second)
                encoded = json.dumps(first[0], sort_keys=True, ensure_ascii=False, allow_nan=False)
                self.assertEqual(json.loads(encoded), first[0])
                self.assertLessEqual(len(encoded.encode()), settings.PARTICIPANT_MAX_TOOL_RESULT_BYTES)
                self.assertFalse(tools._has_descriptor_form(first[0]))

    def test_no_text_returned_names_a_code_followed_by_a_parenthesis(self):
        overlap = source('cms-pfs-overlap', 'cms-pfs', 'RVU26X', '2026-12-01', '2027-02-28')
        ReferenceCodeFact.objects.create(source=overlap, code='45385', facts={'status': 'X'})
        for name, arguments in (('cms_code_facts', facts_call(['45385', '86153', '45999'], '2026-12-15')),
                                ('cms_code_facts', facts_call(['45385'], '2028-01-01')),
                                ('cms_code_facts', facts_call(['45385', '86153'], '')),
                                ('cms_policy_passages', {'topic': 'ncci_endoscopy_rules', 'codes': ['45385']})):
            result, _ = self.execute(name, arguments)
            self.assertNotIn('error', result)
            self.assertFalse(tools._has_descriptor_form(result), result)

    def test_the_executor_never_truncates_and_the_loop_refuses_what_is_too_large(self):
        # 20 releases of one kind, every one listing 32 codes: the whole answer is returned, never cut
        codes = [f'{45300 + n}' for n in range(32)]
        for number in range(20):
            year = 2030 + number
            held = source(f'cms-pfs-r{number}', 'cms-pfs', f'R{number}', f'{year}-01-01', f'{year}-12-31')
            ReferenceCodeFact.objects.bulk_create([ReferenceCodeFact(source=held, code=code, facts=PFS_ROWS['45385'])
                                                   for code in codes])
        result, refs = self.execute('cms_code_facts', facts_call(codes, ''))
        self.assertEqual(len(refs), 20 * 32 * len(PFS_FIELDS))
        size = len(json.dumps(result, sort_keys=True, separators=(',', ':')).encode())
        self.assertGreater(size, settings.PARTICIPANT_MAX_TOOL_RESULT_BYTES)
        record, output = loop._execute(loop.Call('call_1', 'cms_code_facts', facts_call(codes, '')), self.execute,
                                       settings.PARTICIPANT_MAX_TOOL_RESULT_BYTES)
        self.assertEqual((record.result, record.refs), ({'error': loop.TOO_LARGE}, ()))
        self.assertEqual(json.loads(output), {'error': loop.TOO_LARGE})

    def test_through_the_loop_the_result_and_refs_are_recorded_as_given(self):
        arguments = facts_call(['45385'])
        record, output = loop._execute(loop.Call('call_1', 'cms_code_facts', arguments), self.execute,
                                       settings.PARTICIPANT_MAX_TOOL_RESULT_BYTES)
        result, refs = self.execute('cms_code_facts', arguments)
        self.assertEqual((record.tool, record.result, record.refs), ('cms_code_facts', result, tuple(refs)))
        self.assertEqual(json.loads(output), result)

    def test_retrieved_references_are_read_from_a_stored_result(self):
        result, refs = self.execute('cms_code_facts', facts_call(['45385']))
        found = tools.retrieved_references(result)
        self.assertEqual([item['ref'] for item in found], refs)
        self.assertEqual(found[0], {'ref': f'fact:{PFS_KEY}:45385:status', 'kind': 'cms-pfs', 'source_key': PFS_KEY,
                                    'release': 'RVU26D', 'effective_start': '2026-10-01',
                                    'effective_end': '2026-12-31'})
        self.assertEqual(found[-1]['source_key'], MUE_KEY)
        result, refs = self.execute('cms_policy_passages', {'topic': 'ncci_endoscopy_rules', 'codes': []})
        found = tools.retrieved_references(result)
        self.assertEqual([item['ref'] for item in found], refs)
        self.assertEqual({item['kind'] for item in found}, {'cms-ncci-policy-manual'})
        for bad in ({'error': tools.STORE_ERROR}, None, [], {'tool': 'other'}, {'tool': 'cms_code_facts', 'codes': 3}):
            self.assertEqual(tools.retrieved_references(bad), [])
