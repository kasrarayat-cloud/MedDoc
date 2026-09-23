"""The qualified Word form's wording/answer conflicts are named: which statement, which answers.

Offline. The live adapter strings are exercised in CI by WMDocumentWorkflow (Word runtime); here the
adapter's `conflicts` are the exact strings from WmVariants.cs / WmAdapter.cs, fed through a patched
`documents.resolve_template`, so no Word runtime and no provider is involved.
"""
import hashlib
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings

from core.models import Encounter, TemplateVersion
from core.security import private_path
from core.wm_conflicts import ADAPTER_SOURCES, GENERAL, PREFIXED, WHOLE, WmConflicts, describe
from .test_security import SyntheticFixture
from .test_workflow import TEST_SETTINGS

ROOT = Path(__file__).resolve().parents[2]
FIELDS = [
    {'key': 'sdt_-213273323', 'label': 'Right impression: reflux or absence', 'kind': 'choice', 'locator': {'sdt_id': '1'},
     'options': ['reflux positive.', 'is absent.']},
    {'key': 'sdt_-892962961', 'label': 'Right impression: vein', 'kind': 'choice', 'locator': {'sdt_id': '2'}, 'options': ['GSV']},
    {'key': 'measurement_1_1', 'label': 'Right GSV at the SFJ: diameter (mm)', 'kind': 'measurement',
     'locator': {'row': 1, 'column': 1, 'unit': 'mm'}},
    {'key': 'measurement_1_2', 'label': 'Right GSV at the SFJ: reflux time (ms)', 'kind': 'measurement',
     'locator': {'row': 1, 'column': 2, 'unit': 'ms'}},
    {'key': 'measurement_2_2', 'label': 'Right GSV mid-thigh: reflux time (ms)', 'kind': 'measurement',
     'locator': {'row': 2, 'column': 2, 'unit': 'ms'}},
    {'key': 'location_11', 'label': 'Right tributary row 11: anatomical location', 'kind': 'text', 'locator': {'row': 11}},
    {'key': 'measurement_15_2', 'label': 'Left GSV at the SFJ: reflux time (ms)', 'kind': 'measurement',
     'locator': {'row': 15, 'column': 2, 'unit': 'ms'}},
]


def requirement(claim, label, variants):
    return {'key': claim, 'label': 'Prewritten statement: ' + label, 'kind': 'assertion', 'default_variant': variants[0]['id'],
            'variants': variants}


def variant(identifier, label, required=(), empty=()):
    return {'id': identifier, 'label': label, 'text_template': '', 'required_control_keys': list(required),
            'empty_control_keys': list(empty)}


REQUIREMENTS = [
    requirement('claim_30', 'Right impression', [variant('selected', 'Documented right vein and finding',
                                                         required=['sdt_-892962961', 'sdt_-213273323']),
                                                 variant('not_assessed', 'Right saphenous veins explicitly not assessed',
                                                         empty=['sdt_-892962961', 'sdt_-213273323'])]),
    requirement('claim_32', 'Right saphenous reflux finding', [variant('negative', 'Documented no right saphenous reflux'),
                                                               variant('positive', 'Documented positive right saphenous reflux'),
                                                               variant('not_assessed', 'Right saphenous reflux explicitly not assessed')]),
]
VERSION = SimpleNamespace(fields=FIELDS, review_requirements=REQUIREMENTS)


def sent(**texts):
    return {field['key']: {'text': texts.get(field['key'], ''), 'status': 'supported' if texts.get(field['key']) else 'missing'}
            for field in FIELDS}


class TheTranscriptionIsPinnedToTheAdapter(SimpleTestCase):
    def test_both_adapter_sources_are_the_ones_the_table_was_copied_from(self):
        """If either C# file changes, a rule may have changed: revisit core/wm_conflicts.py, then re-pin."""
        for relative, expected in ADAPTER_SOURCES.items():
            with self.subTest(source=relative):
                self.assertEqual(hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(), expected)

    def test_every_known_string_is_verbatim_in_the_adapter(self):
        source = ''.join((ROOT / relative).read_text() for relative in ADAPTER_SOURCES)
        for text in list(PREFIXED) + list(WHOLE):
            with self.subTest(text=text):
                self.assertIn('"' + text + '"' if text in WHOLE else ': ' + text + '"', source)


class EachConflictNamesItsStatementAndAnswers(SimpleTestCase):
    def row(self, conflict, answers, variants=None):
        rows = describe([conflict], VERSION, answers, variants or {'claim_30': 'selected', 'claim_32': 'negative'})
        self.assertEqual(len(rows), 1)
        return rows[0]

    def test_positive_reflux_with_the_no_reflux_wording(self):
        row = self.row('claim_32: positive selected reflux requires the reviewed positive statement.',
                       sent(**{'sdt_-213273323': 'reflux positive.'}))
        self.assertEqual(row['statements'], [('Prewritten statement: Right saphenous reflux finding',
                                              'Documented no right saphenous reflux')])
        self.assertEqual(row['answers'], [('Right impression: reflux or absence', 'reflux positive.')])
        self.assertIn('positive-reflux wording', row['explanation'])

    def test_a_required_answer_names_only_what_is_missing(self):
        row = self.row('claim_30: selected statement needs a documented answer for every required control.',
                       sent(**{'sdt_-213273323': 'reflux positive.'}))
        self.assertEqual(row['answers'], [('Right impression: vein', '')])
        self.assertEqual(row['statements'][0][1], 'Documented right vein and finding')

    def test_reflux_over_500_names_the_sides_given_reflux_times_but_never_quotes_a_measurement(self):
        row = self.row("claim_32: a recorded reflux duration exceeds this template's explicit 500 ms positive criterion.",
                       sent(measurement_1_2='700 ms', measurement_15_2='900 ms'))
        self.assertEqual(row['answers'], [('Right GSV at the SFJ: reflux time (ms)', '')])
        self.assertNotIn('700', str(row))

    def test_reflux_over_500_names_only_the_times_over_500(self):
        row = self.row("claim_32: a recorded reflux duration exceeds this template's explicit 500 ms positive criterion.",
                       sent(measurement_1_2='650 ms', measurement_2_2='100 ms'))
        self.assertEqual([label for label, _ in row['answers']], ['Right GSV at the SFJ: reflux time (ms)'])

    def test_a_not_assessed_side_names_its_documented_rows_only(self):
        row = self.row('claim_30: a non-assessed side cannot contain documented measurements or locations.',
                       sent(measurement_1_1='3.2 mm', location_11='lateral calf', measurement_15_2='400 ms'),
                       {'claim_30': 'not_assessed', 'claim_32': 'negative'})
        self.assertEqual([label for label, _ in row['answers']],
                         ['Right GSV at the SFJ: diameter (mm)', 'Right tributary row 11: anatomical location'])
        self.assertEqual(row['statements'][0][1], 'Right saphenous veins explicitly not assessed')

    def test_an_unknown_string_or_a_missing_statement_keeps_the_general_sentence(self):
        for conflict in ('claim_32: some future rule.', 'claim_99: positive selected reflux requires the reviewed positive statement.',
                         'Something else entirely.'):
            with self.subTest(conflict=conflict):
                self.assertEqual(self.row(conflict, sent())['explanation'], GENERAL)

    def test_the_error_message_itself_stays_general(self):
        error = WmConflicts(describe(['claim_32: positive selected reflux requires the reviewed positive statement.'],
                                     VERSION, sent(**{'sdt_-213273323': 'reflux positive.'}), {'claim_32': 'negative'}))
        self.assertEqual(error.messages, [GENERAL])
        self.assertNotIn('reflux positive.', ' '.join(error.messages))


@override_settings(**TEST_SETTINGS)
class ThePageListsEachConflictAndTheCookieCarriesNone(SyntheticFixture, TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(); self.addCleanup(directory.cleanup)
        override = override_settings(MEDIA_ROOT=Path(directory.name)); override.enable(); self.addCleanup(override.disable)
        self.user, _, self.department, self.patient, self.template, self.encounter, blob = self.make_scope('wm-conflicts')
        path = private_path(self.template.original_path); path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(blob)
        version = TemplateVersion.objects.create(template=self.template, number=2, fields=FIELDS, review_requirements=REQUIREMENTS,
                                                 document_backend={'backend': 'synthetic-qualified', 'mapping_digest': 'd' * 64},
                                                 created_by=self.user)
        self.encounter.template_version = version; self.encounter.answers = {}
        self.encounter.save(update_fields=['template_version', 'answers'])
        self.client.force_login(self.user)
        self.resolve = {'backend': 'synthetic-qualified', 'mapping_digest': 'd' * 64, 'sha256': self.template.sha256,
                        'conflicts': ['claim_32: positive selected reflux requires the reviewed positive statement.'],
                        'review_requirements': REQUIREMENTS}

    def patched(self):
        return (patch('documents.resolve_template', return_value=self.resolve),
                patch('core.views.wm_review.sdk_answers', return_value=sent(**{'sdt_-213273323': 'reflux positive.'})))

    def test_the_document_page_names_the_statement_the_wording_and_the_answer(self):
        first, second = self.patched()
        with first, second:
            page = self.client.get(f'/encounters/{self.encounter.pk}/')
        self.assertContains(page, '<li data-wm-conflict>', count=1)
        self.assertContains(page, '<strong>Prewritten statement: Right saphenous reflux finding</strong> '
                                  '(chosen wording: Documented no right saphenous reflux)')
        self.assertContains(page, 'answers: Right impression: reflux or absence (&ldquo;reflux positive.&rdquo;).')

    def test_what_every_flash_site_receives_is_the_general_sentence(self):
        """save_answers and finalize flash `error_message(exc)`; for a named conflict that is GENERAL only. (A WM
        save cannot be driven offline here: it first requires the qualified original's identity.)"""
        from core.views import error_message
        rows = describe(['claim_32: positive selected reflux requires the reviewed positive statement.'], VERSION,
                        sent(**{'sdt_-213273323': 'reflux positive.'}), {'claim_32': 'negative'})
        self.assertEqual(error_message(WmConflicts(rows)), GENERAL)
