"""CMS reference passages: the bundled data files, their import and load_passages (HARNESS.md 5).

The data files are the curated passages themselves; these tests hold them to their schema and to the curation the
harness needs. That every passage is verbatim in its PDF is proved by ops/verify_passages.py against the publishers'
files, which CI does not have (tests/test_passages_verify.py tests that script on a synthetic PDF).
"""
import copy
import hashlib
import io
import json
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from django.core.management import CommandError, call_command
from django.db import IntegrityError
from django.test import SimpleTestCase, TestCase

from studio.models import PassageSource, ReferencePassage, ReferenceSource
from studio.reference.passages import (CODE_THEN_DESCRIPTION, DATA_DIR, EXCLUDED_FIELDS, PASSAGE_FIELDS,
                                       SOURCE_FIELDS, TOPICS, PassageImportError, bundled_files, import_data_file,
                                       load_passages, parse_data, read_data_file)

PFS_DOC, NCCI, CLAIMS = ('cms-pfs-rvu26d-documentation', 'cms-ncci-policy-manual-2026-ch6',
                         'cms-claims-manual-100-04-ch12')
TAIL = 'Verbatim CMS text; passages that quote a CPT code description are not imported.'
# The sources as the harness pins them: (kind, release, window, file sha256, url).
PINNED = {
    PFS_DOC: ('cms-pfs-documentation', 'RVU26D', ('2026-10-01', '2026-12-31'),
              '8aba8efb62e86a804bd8791ecefeef254da94de37a2391156de1415ce6a7e278',
              'https://www.cms.gov/files/zip/rvu26d-updated-08-26-2026.zip'),
    NCCI: ('cms-ncci-policy-manual', 'Revision Date (Medicare): 1/1/2026', ('2026-01-01', '2026-12-31'),
           'c1d2dc0d9ccc8890a50059124ce65e1930bc4ff02c99183ee65b46951b72aabf',
           'https://www.cms.gov/files/document/06-chapter6-ncci-medicare-policy-manual-2026-final.pdf'),
    CLAIMS: ('cms-claims-manual', 'Rev. 13753; Issued: 05-07-26', ('2026-05-07', '2026-12-31'),
             '71689eed983a6ef4a5a5d9313655ea732ff0329adf03b85183e9755f025e74a8',
             'https://www.cms.gov/regulations-and-guidance/guidance/manuals/downloads/clm104c12.pdf'),
}
# The literal guard of the task: a five-digit code followed by an opening parenthesis.
FIVE_DIGITS_THEN_PARENTHESIS = re.compile(r'[0-9]{5}\s*\(')


def document(key) -> dict:
    return json.loads((DATA_DIR / f'{key}.json').read_text(encoding='utf-8'))


def strings(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)
    elif isinstance(value, str):
        yield value


def file_passages(paths=None) -> list[dict]:
    """The bundled data files in load_passages' shape, read without the database."""
    found = []
    for path in paths or bundled_files():
        data = read_data_file(path)
        source = data.source
        for passage in data.passages:
            found.append({'source_key': source['key'], 'kind': source['kind'], 'source_title': source['title'],
                          'release': source['release'], 'effective_start': source['effective_start'].isoformat(),
                          'effective_end': source['effective_end'].isoformat(), 'source_sha256': source['sha256'],
                          'url': source['url'], **{name: passage[name] for name in PASSAGE_FIELDS},
                          'sha256': passage['sha256']})
    return sorted(found, key=lambda p: (p['source_key'], p['passage_key']))


class BundledDataFileTests(SimpleTestCase):
    def test_the_three_sources_are_the_pinned_files(self):
        self.assertEqual([path.name for path in bundled_files()], sorted(f'{key}.json' for key in PINNED))
        for key, (kind, release, window, sha, url) in PINNED.items():
            with self.subTest(key):
                source = document(key)['source']
                self.assertEqual(list(source), list(SOURCE_FIELDS))
                self.assertEqual((source['key'], source['kind'], source['release']), (key, kind, release))
                self.assertEqual((source['effective_start'], source['effective_end']), window)
                self.assertEqual((source['sha256'], source['url']), (sha, url))
                self.assertEqual(source['retrieved_at'], '2026-11-01T21:30:00Z')
                self.assertEqual(source['publisher'], 'Centers for Medicare & Medicaid Services (CMS)')

    def test_every_file_passes_the_importers_own_checks(self):
        for path in bundled_files():
            with self.subTest(path.name):
                data = read_data_file(path)
                self.assertLessEqual(data.source['effective_start'], data.source['effective_end'])
                self.assertTrue(re.fullmatch(r'[0-9a-f]{64}', data.source['sha256']))

    def test_the_layout_is_exact(self):
        for key in PINNED:
            with self.subTest(key):
                content = document(key)
                self.assertEqual(list(content), ['source', 'passages', 'excluded'])
                self.assertTrue(all(list(p) == list(PASSAGE_FIELDS) for p in content['passages']))
                self.assertTrue(all(list(e) == list(EXCLUDED_FIELDS) for e in content['excluded']))
                keys = [p['passage_key'] for p in content['passages']]
                self.assertEqual(len(keys), len(set(keys)))
                self.assertTrue(all(TOPICS[p['topic']] == content['source']['kind'] for p in content['passages']))
                for passage in content['passages']:
                    self.assertEqual(' '.join(passage['text'].split()), passage['text'])

    def test_no_text_quotes_a_code_description(self):
        for key in PINNED:
            with self.subTest(key):
                content = document(key)
                for passage in content['passages']:
                    self.assertIsNone(FIVE_DIGITS_THEN_PARENTHESIS.search(passage['text']), passage['passage_key'])
                # and the importer's wider guard (a code then '(' or '--') finds nothing anywhere in the file
                self.assertEqual([s for s in strings(content) if CODE_THEN_DESCRIPTION.search(s)], [])

    def test_the_license_notes_quote_the_files_own_notices(self):
        for key in PINNED:
            with self.subTest(key):
                self.assertTrue(document(key)['source']['license_note'].endswith(TAIL))
        for key, year in ((PFS_DOC, '2026'), (NCCI, '2025')):
            note = document(key)['source']['license_note']
            self.assertRegex(note, rf'^Notice in the file: "[^"]*copyright {year} American Medical Association\.')
        self.assertTrue(document(CLAIMS)['source']['license_note'].startswith(
            'The file carries no copyright or licence notice.'))

    def test_the_pfs_documentation_defines_every_value_the_harness_reads(self):
        passages = document(PFS_DOC)['passages']
        values = {}
        for passage in passages:
            values.setdefault(passage['topic'], set()).add(passage['topic_value'])
        self.assertEqual(values['pfs.status'], set('ABCDEFGHIJMNPRTX'))
        self.assertEqual(values['pfs.global_days'], {'000', '010', '090', 'XXX', 'YYY', 'ZZZ', 'MMM'})
        self.assertEqual(values['pfs.mult_proc'], set('01234567') | {'9'})
        self.assertEqual(values['pfs.endo_base'], {''})
        self.assertEqual(values['pfs.pctc'], set('01456789'))
        excluded = {(e['topic'], e['topic_value']) for e in document(PFS_DOC)['excluded']}
        self.assertEqual(excluded, {('pfs.pctc', '2'), ('pfs.pctc', '3')})
        three = [p for p in passages if p['topic'] == 'pfs.mult_proc' and p['topic_value'] == '3']
        self.assertEqual([p['passage_key'] for p in three], ['mult-proc-3-part-1', 'mult-proc-3-part-2'])
        self.assertIn('The base procedure for each code with this indicator is identified in the Endobase field',
                      three[0]['text'])
        self.assertTrue(three[0]['text'].endswith('If an endoscopic procedure is reported with'))
        self.assertTrue(three[1]['text'].startswith('only its base procedure, do not pay separately for the base '
                                                    'procedure.'))

    def test_every_ncci_endoscopy_rule_is_imported_or_listed_as_excluded(self):
        content = document(NCCI)
        imported = {p['topic_value'] for p in content['passages']}
        excluded = {e['topic_value'] for e in content['excluded']}
        self.assertEqual(imported | excluded, {str(n) for n in range(1, 17)})
        self.assertEqual(excluded, {'9', '11'})
        self.assertEqual(imported & excluded, set())
        for item in content['excluded']:
            self.assertIn('Quotes', item['reason'])
            self.assertTrue(item['anchor'].startswith(f'{item["topic_value"]}. '))
        for passage in content['passages']:
            if '-part-' not in passage['passage_key'] or passage['passage_key'].endswith('-part-1'):
                self.assertTrue(passage['text'].startswith(f'{passage["topic_value"]}. '), passage['passage_key'])

    def test_a_cut_passages_parts_are_consecutive_pages_in_key_order(self):
        for key in PINNED:
            parts = {}
            for passage in document(key)['passages']:
                if '-part-' in passage['passage_key']:
                    parts.setdefault((passage['topic'], passage['topic_value']), []).append(passage)
            for (topic, value), found in parts.items():
                with self.subTest(key=key, topic=topic, value=value):
                    self.assertEqual([p['passage_key'] for p in found], sorted(p['passage_key'] for p in found))
                    pages = [int(p['page']) for p in found]
                    self.assertEqual(pages, list(range(pages[0], pages[0] + len(pages))))
        self.assertEqual(sum(1 for key in PINNED for p in document(key)['passages'] if '-part-' in p['passage_key']),
                         6)

    def test_the_claims_manual_gives_items_13_and_14(self):
        content = document(CLAIMS)
        self.assertEqual([(p['passage_key'], p['topic_value']) for p in content['passages']],
                         [('item-13', '13'), ('item-13-example', '13'), ('item-13-note', '13'), ('item-14', '14')])
        example = content['passages'][1]['text']
        self.assertEqual(sorted(set(re.findall(r'[0-9]{5}', example))), ['45378', '45380', '45385'])
        self.assertEqual(len(content['excluded']), 1)
        self.assertEqual(content['passages'][3]['page'], '98-99')


def refusal(test, mutate, message, key=NCCI):
    content = document(key)
    mutate(content)
    with test.assertRaisesRegex(PassageImportError, message):
        parse_data(content, 'mutated.json')


class ParseRefusalTests(SimpleTestCase):
    def test_the_layout_is_refused_when_it_differs(self):
        cases = {
            'extra member': (lambda d: d.update(notes=[]), 'exactly the members'),
            'no excluded': (lambda d: d.pop('excluded'), 'exactly the members'),
            'extra source field': (lambda d: d['source'].update(edition='x'), 'exactly the fields'),
            'missing passage field': (lambda d: d['passages'][0].pop('page'), 'exactly the fields'),
            'non-string value': (lambda d: d['passages'][0].update(page=5), 'must be a string'),
            'empty passages': (lambda d: d.update(passages=[]), 'non-empty list'),
            'excluded not a list': (lambda d: d.update(excluded={}), 'must be a list'),
        }
        for label, (mutate, message) in cases.items():
            with self.subTest(label):
                refusal(self, mutate, message)

    def test_source_metadata_is_validated(self):
        cases = {
            'kind': ({'kind': 'cms-pfs'}, 'is not one of'),
            'key': ({'key': 'NCCI Chapter 6'}, 'lower-case letters'),
            'sha256': ({'sha256': 'C1D2' * 16}, '64 lower-case hexadecimal'),
            'url': ({'url': 'http://www.cms.gov/x.pdf'}, 'https://'),
            'naive time': ({'retrieved_at': '2026-11-01T21:30:00'}, 'no UTC offset'),
            'not a time': ({'retrieved_at': 'yesterday'}, 'not an ISO-8601'),
            'date form': ({'effective_end': '2026-12-31T00:00:00'}, 'not a YYYY-MM-DD date'),
            'compact date': ({'effective_start': '20260101'}, 'not a YYYY-MM-DD date'),
            'window order': ({'effective_start': '2027-01-01'}, 'after the effective end'),
            'empty note': ({'scope_note': ' '}, 'scope_note is empty'),
            'long release': ({'release': 'R' * 61}, 'longer than 60'),
        }
        for label, (override, message) in cases.items():
            with self.subTest(label):
                refusal(self, lambda d, o=override: d['source'].update(o), message)

    def test_passages_are_validated(self):
        cases = {
            'topic of another kind': ({'topic': 'pfs.status'}, 'is not one a cms-ncci-policy-manual source states'),
            'unknown topic': ({'topic': 'ncci.ptp'}, 'is not one'),
            'empty value': ({'topic_value': ''}, 'does not fit topic'),
            'page': ({'page': 'VI-5'}, 'page number or a range'),
            'reversed range': ({'page': '7-6'}, 'N < M'),
            'one-page range': ({'page': '6-6'}, 'N < M'),
            'key': ({'passage_key': 'rule 01'}, 'passage_key must be'),
            'whitespace': ({'text': '1. Per CPT  Professional codebook instructions.'}, 'collapsed'),
            'edge whitespace': ({'text': ' 1. Per CPT Professional codebook instructions.'}, 'collapsed'),
            'control character': ({'text': '1. Per\x00CPT'}, 'control character'),
            'lone surrogate': ({'text': '1. Per \ud800 CPT'}, 'lone surrogate'),
            'too long': ({'text': 'x' * 4001}, '1 to 4000 characters'),
            'empty section': ({'section': ''}, 'section is empty'),
        }
        for label, (override, message) in cases.items():
            with self.subTest(label):
                refusal(self, lambda d, o=override: d['passages'][0].update(o), message)

    def test_a_field_topic_takes_no_value(self):
        def give_the_field_a_value(content):
            [field] = [p for p in content['passages'] if p['topic'] == 'pfs.endo_base']
            field['topic_value'] = '45378'

        refusal(self, give_the_field_a_value, 'does not fit topic', key=PFS_DOC)

    def test_duplicates_are_refused(self):
        refusal(self, lambda d: d['passages'][1].update(passage_key=d['passages'][0]['passage_key']), 'appears twice')
        refusal(self, lambda d: d['passages'][1].update(text=d['passages'][0]['text']), "repeats another passage")

    def test_a_code_followed_by_a_description_form_is_refused_anywhere(self):
        # synthetic shapes only: a code number, then '(' or '--' and placeholder words
        cases = {
            'passage text': lambda d: d['passages'][0].update(text='CPT code 99999 (SYNTHETIC WORDS) is cited.'),
            'double dash': lambda d: d['passages'][0].update(text='CPT code 99999--SYNTHETIC WORDS is cited.'),
            'category III form': lambda d: d['passages'][0].update(text='Code 0999T (SYNTHETIC) is cited.'),
            'excluded anchor': lambda d: d['excluded'][0].update(anchor='9. Code 99999 (SYNTHETIC)'),
            'excluded reason': lambda d: d['excluded'][0].update(reason='99999 (SYNTHETIC WORDS)'),
            'source note': lambda d: d['source'].update(scope_note='99999 -- SYNTHETIC WORDS'),
        }
        for label, mutate in cases.items():
            with self.subTest(label):
                refusal(self, mutate, 'form of a quoted code description')
        # a code followed by ')' or ':' as the manuals list them is not that form
        content = document(NCCI)
        content['passages'][0]['text'] = '1. Synthetic (e.g., CPT code 99999) and 99999: are listed.'
        parse_data(content, 'listed.json')

    def test_excluded_items_need_a_topic_of_the_source_an_anchor_and_a_reason(self):
        refusal(self, lambda d: d['excluded'][0].update(reason=''), 'an anchor and a reason')
        refusal(self, lambda d: d['excluded'][0].update(topic='pfs.pctc'), 'a topic of this source')
        refusal(self, lambda d: d['excluded'][0].update(page='six'), 'page number')

    def test_a_passage_may_not_hold_what_is_listed_as_left_out(self):
        # as if rule 8's end anchor had run on into the excluded rule 9
        def run_on(content):
            [rule_8] = [p for p in content['passages'] if p['passage_key'] == 'rule-08']
            rule_8['text'] += ' ' + content['excluded'][0]['anchor']

        refusal(self, run_on, "passage 'rule-08' holds the text it says is left out")


class ReadDataFileTests(SimpleTestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.tmp = Path(directory.name)

    def write(self, data: bytes) -> Path:
        path = self.tmp / 'data.json'
        path.write_bytes(data)
        return path

    def test_json_is_read_strictly(self):
        text = (DATA_DIR / f'{NCCI}.json').read_text(encoding='utf-8')
        cases = {
            'repeated key': (text.replace('"excluded": [', '"excluded": [], "excluded": [', 1).encode(),
                             'repeats a key'),
            'NaN': (text.replace('"passages": [', '"nan": NaN, "passages": [', 1).encode(), 'NaN is not JSON data'),
            'not JSON': (b'{"source": ', 'not valid JSON'),
            'not UTF-8': (b'{"source": "\xff"}', 'not UTF-8'),
        }
        for label, (data, message) in cases.items():
            with self.subTest(label):
                with self.assertRaisesRegex(PassageImportError, message):
                    read_data_file(self.write(data))

    def test_size_and_presence_are_checked(self):
        with mock.patch('studio.reference.passages.MAX_DATA_BYTES', 100):
            with self.assertRaisesRegex(PassageImportError, 'larger than 100 bytes'):
                read_data_file(DATA_DIR / f'{NCCI}.json')
        with self.assertRaisesRegex(PassageImportError, 'not a readable file'):
            read_data_file(self.tmp / 'absent.json')


class ImportTests(TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.tmp = Path(directory.name)

    def variant(self, key, mutate, name='variant.json') -> Path:
        content = copy.deepcopy(document(key))
        mutate(content)
        path = self.tmp / name
        path.write_text(json.dumps(content, ensure_ascii=False), encoding='utf-8')
        return path

    def counts(self):
        return PassageSource.objects.count(), ReferencePassage.objects.count()

    def test_each_bundled_file_loads_its_source_and_passages(self):
        expected = {PFS_DOC: 42, NCCI: 16, CLAIMS: 4}
        for path in bundled_files():
            source, created = import_data_file(path)
            self.assertTrue(created)
            content = document(source.key)
            self.assertEqual(source.passage_count, expected[source.key])
            self.assertEqual(source.passages.count(), expected[source.key])
            for name in ('kind', 'publisher', 'title', 'release', 'url', 'sha256', 'license_note', 'scope_note'):
                self.assertEqual(getattr(source, name), content['source'][name])
            self.assertEqual(source.retrieved_at, datetime(2026, 11, 1, 21, 30, tzinfo=timezone.utc))
            self.assertEqual(source.effective_start.isoformat(), content['source']['effective_start'])
            stored = {row.passage_key: row for row in source.passages.all()}
            for passage in content['passages']:
                row = stored[passage['passage_key']]
                self.assertEqual([getattr(row, f) for f in PASSAGE_FIELDS], [passage[f] for f in PASSAGE_FIELDS])
                self.assertEqual(row.sha256, hashlib.sha256(passage['text'].encode('utf-8')).hexdigest())
        self.assertEqual(self.counts(), (3, 62))
        self.assertFalse(ReferenceSource.objects.exists())  # passages never add a reference-source entry

    def test_the_same_file_again_is_a_no_op(self):
        first, _ = import_data_file(DATA_DIR / f'{NCCI}.json')
        later = self.variant(NCCI, lambda d: d['source'].update(retrieved_at='2026-11-02T08:00:00+00:00'))
        for path in (DATA_DIR / f'{NCCI}.json', later):
            source, created = import_data_file(path)
            self.assertFalse(created)
            self.assertEqual(source.pk, first.pk)
        self.assertEqual(self.counts(), (1, 16))
        self.assertEqual(PassageSource.objects.get().retrieved_at, datetime(2026, 11, 1, 21, 30, tzinfo=timezone.utc))

    def test_anything_else_under_a_loaded_key_is_refused(self):
        import_data_file(DATA_DIR / f'{NCCI}.json')
        cases = {
            'a passage text': (lambda d: d['passages'][0].update(text=d['passages'][0]['text'][:-1]), 'passages'),
            'a passage page': (lambda d: d['passages'][0].update(page='4'), 'passages'),
            'a passage removed': (lambda d: d['passages'].pop(), 'passages'),
            'a passage added': (lambda d: d['passages'].append(dict(d['passages'][0], passage_key='rule-99',
                                                                     text='99. Synthetic.')), 'passages'),
            'the title': (lambda d: d['source'].update(title='Another title'), 'title'),
            'the window': (lambda d: d['source'].update(effective_end='2026-12-30'), 'effective_end'),
            'the scope note': (lambda d: d['source'].update(scope_note='Another note.'), 'scope_note'),
            'the file': (lambda d: d['source'].update(sha256='0' * 64), 'from a different file'),
        }
        before = list(ReferencePassage.objects.order_by('id').values_list('passage_key', 'text', 'sha256'))
        for label, (mutate, message) in cases.items():
            with self.subTest(label):
                with self.assertRaisesRegex(PassageImportError, message):
                    import_data_file(self.variant(NCCI, mutate))
        self.assertEqual(list(ReferencePassage.objects.order_by('id').values_list('passage_key', 'text', 'sha256')),
                         before)
        self.assertEqual(self.counts(), (1, 16))

    def test_the_same_file_under_another_key_is_refused(self):
        import_data_file(DATA_DIR / f'{NCCI}.json')
        with self.assertRaisesRegex(PassageImportError, f'already loaded as {NCCI}'):
            import_data_file(self.variant(NCCI, lambda d: d['source'].update(key='cms-ncci-copy')))
        self.assertEqual(self.counts(), (1, 16))

    def test_an_overlapping_window_of_one_kind_is_refused_and_a_disjoint_one_loads(self):
        import_data_file(DATA_DIR / f'{NCCI}.json')

        def another(start, end, key):
            return lambda d: d['source'].update(key=key, sha256='e' * 64, effective_start=start, effective_end=end)

        with self.assertRaisesRegex(PassageImportError, 'two passage sources of one kind may not cover the same date'):
            import_data_file(self.variant(NCCI, another('2026-12-31', '2027-12-31', 'cms-ncci-2027')))
        source, created = import_data_file(self.variant(NCCI, another('2027-01-01', '2027-12-31', 'cms-ncci-2027')))
        self.assertTrue(created)
        self.assertEqual(self.counts(), (2, 32))
        # another kind may share the window
        import_data_file(DATA_DIR / f'{CLAIMS}.json')
        self.assertEqual(self.counts(), (3, 36))

    def test_a_failure_part_way_writes_nothing(self):
        with mock.patch.object(ReferencePassage.objects, 'bulk_create', side_effect=IntegrityError('synthetic')):
            with self.assertRaises(IntegrityError):
                import_data_file(DATA_DIR / f'{NCCI}.json')
        self.assertEqual(self.counts(), (0, 0))

    def test_a_refused_file_writes_nothing(self):
        bad = self.variant(NCCI, lambda d: d['passages'][-1].update(text='16. Code 99999 (SYNTHETIC).'))
        with self.assertRaises(PassageImportError):
            import_data_file(bad)
        self.assertEqual(self.counts(), (0, 0))


class ImportCommandTests(TestCase):
    def run_command(self, path):
        out = io.StringIO()
        call_command('import_passages', '--data', str(path), stdout=out)
        return out.getvalue()

    def test_command_loads_once_then_reports_no_change(self):
        path = DATA_DIR / f'{CLAIMS}.json'
        self.assertEqual(self.run_command(path).strip(),
                         f'Loaded {CLAIMS}: 4 passages from Medicare Claims Processing Manual (Pub. 100-04), '
                         'Chapter 12: Physicians/Nonphysician Practitioners, effective 2026-05-07 to 2026-12-31, '
                         'sha256 '
                         f'{PINNED[CLAIMS][3]}.')
        self.assertEqual(self.run_command(path).strip(),
                         f'{CLAIMS} is already loaded with these 4 passages (sha256 {PINNED[CLAIMS][3]}); '
                         'nothing changed.')
        self.assertEqual(ReferencePassage.objects.count(), 4)

    def test_command_reports_refusals_as_command_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bad.json'
            path.write_text('{}', encoding='utf-8')
            with self.assertRaisesRegex(CommandError, 'exactly the members'):
                self.run_command(path)
            with self.assertRaisesRegex(CommandError, 'not a readable file'):
                self.run_command(Path(directory) / 'absent.json')
        self.assertFalse(PassageSource.objects.exists())


class LoadPassagesTests(TestCase):
    def test_load_passages_returns_every_passage_with_its_source(self):
        for path in bundled_files():
            import_data_file(path)
        loaded = load_passages()
        self.assertEqual(loaded, file_passages())
        self.assertEqual(len(loaded), 62)
        self.assertEqual(list(loaded[0]), ['source_key', 'kind', 'source_title', 'release', 'effective_start',
                                           'effective_end', 'source_sha256', 'url', 'passage_key', 'section', 'page',
                                           'topic', 'topic_value', 'text', 'sha256'])
        self.assertEqual([p['source_key'] for p in loaded], sorted(p['source_key'] for p in loaded))

    def test_a_passage_changed_after_import_is_refused(self):
        import_data_file(DATA_DIR / f'{NCCI}.json')
        ReferencePassage.objects.filter(passage_key='rule-01').update(text='1. Synthetic replacement.')
        with self.assertRaisesRegex(ValueError, f'{NCCI}/rule-01 does not match its sha256'):
            load_passages()

    def test_nothing_imported_loads_nothing(self):
        self.assertEqual(load_passages(), [])
