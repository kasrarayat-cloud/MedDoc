"""The mapping-review screen must say WHERE each answer goes.

`template_detail.html` rendered `{% firstof field.location field.kind %}` and no code has
ever set `location`, so the "Location" column showed the literal word "text" on every row —
on the one screen whose stated purpose is "Review where each answer belongs."

The description is display-only on purpose: `documents.engine.validate_mapping` compares the
stored field list against a fresh inspection with `fields != mapping (⚠️ SUPERSEDED: `validate_mapping` now compares STRUCTURE — key, kind, locator and the rest — and excludes only `label`, which the mapping-review rename gate owns instead.)`, so adding a key to the
field dict would invalidate every mapping version already saved.

Isolated synthetic DB; no provider request.
"""
import json

from django.test import TestCase, override_settings

from core import field_location
from core.tests.test_billing_boundary import BoundaryFixture
from core.tests.test_billing_policy import STORAGES


class Describe(TestCase):
    def test_each_locator_shape_gets_a_distinct_human_description(self):
        placeholder = field_location.describe(
            {'locator': {'paragraph': 4, 'start': 9, 'end': 27, 'token': '{{Patient name}}'}})
        cell = field_location.describe({'locator': {'cell': 2}})
        tab = field_location.describe({'locator': {'tab_form': {
            'grouping': 'label', 'anchors': [{'part': 'word/document.xml', 'paragraph': 11, 'run': 1}]}}})

        self.assertIn('Paragraph 5', placeholder)          # 1-based for a human
        self.assertIn('{{Patient name}}', placeholder)
        self.assertIn('table', cell.lower())
        self.assertIn('Body paragraph 12', tab)
        self.assertEqual(len({placeholder, cell, tab}), 3, 'Each shape must read differently.')

    def test_several_physical_blanks_for_one_question_are_counted(self):
        anchors = [{'part': 'word/document.xml', 'paragraph': 17, 'run': 0},
                   {'part': 'word/document.xml', 'paragraph': 18, 'run': 0},
                   {'part': 'word/document.xml', 'paragraph': 19, 'run': 0}]
        text = field_location.describe({'locator': {'tab_form': {'grouping': 'label', 'anchors': anchors}}})
        self.assertIn('2 more line(s)', text,
                      'A logical question over several blanks must say so, or the count looks wrong.')

    def test_header_and_footer_parts_are_named_not_shown_as_filenames(self):
        for part, expected in [('word/header1.xml', 'Header'), ('word/footer1.xml', 'Footer')]:
            text = field_location.describe({'locator': {'tab_form': {'anchors': [{'part': part, 'paragraph': 0}]}}})
            self.assertIn(expected, text)
            self.assertNotIn('.xml', text)

    def test_an_unknown_locator_does_not_crash_or_invent_a_place(self):
        self.assertEqual(field_location.describe({'locator': {}}), 'Original form field')
        self.assertEqual(field_location.describe({}), 'Original form field')


@override_settings(AI_MODE='fixture', ADMIN_SITE=False, STORAGES=STORAGES)
class MappingReviewScreen(BoundaryFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)

    def test_the_review_table_shows_a_location_and_not_the_word_text(self):
        version = self.encounter.template_version
        response = self.client.get(f'/templates/{version.template.pk}/')
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()

        self.assertIn('Where the answer goes', body)
        self.assertEqual(len(response.context['field_rows']), len(version.fields))
        for row in response.context['field_rows']:
            self.assertTrue(row['location'].strip())
            self.assertNotEqual(row['location'], 'text',
                                'The old column rendered field.kind, which is "text" for every field.')

    def test_the_label_editor_is_given_the_same_locations(self):
        version = self.encounter.template_version
        response = self.client.get(f'/templates/{version.template.pk}/')
        self.assertEqual(response.context['field_locations'],
                         [row['location'] for row in response.context['field_rows']])
        self.assertIn('id="mapping-locations"', response.content.decode())

    def test_upload_offers_only_supported_file_types_in_the_picker(self):
        response = self.client.get('/templates/upload/')
        body = response.content.decode()
        self.assertIn('accept=', body)
        self.assertIn('.docx', body)
        self.assertIn('.pdf', body)


class DuplicateLabels(TestCase):
    """Two answers that read as the same question must be pointed at, not left to chance."""

    def test_rows_mark_every_field_sharing_a_label(self):
        fields = [{'key': 'a', 'label': 'FINDINGS — 1', 'locator': {'cell': 0}},
                  {'key': 'b', 'label': 'FINDINGS — 1', 'locator': {'cell': 1}},
                  {'key': 'c', 'label': 'FINDINGS — 2', 'locator': {'cell': 2}}]
        marked = [row['duplicate'] for row in field_location.rows(fields)]
        self.assertEqual(marked, [True, True, False],
                         'Both halves of a collision are marked; a unique label is not.')

    def test_no_field_is_marked_when_every_label_is_unique(self):
        fields = [{'key': 'a', 'label': 'Indication', 'locator': {'cell': 0}},
                  {'key': 'b', 'label': 'Plan', 'locator': {'cell': 1}}]
        self.assertEqual([row['duplicate'] for row in field_location.rows(fields)], [False, False])

    def test_the_importer_reports_the_collision_as_an_inspection_warning(self):
        """Reported through warnings, which validate_mapping does not compare.

        Putting it in the field dict would refuse every mapping version already saved —
        measured directly in documents/test_unmapped_areas.py's sibling assertion.
        """
        from documents.engine import duplicate_label_note
        note = duplicate_label_note([{'label': 'FINDINGS — 1'}, {'label': 'FINDINGS — 1'},
                                     {'label': 'FINDINGS — 2'}])
        self.assertEqual(len(note), 1)
        self.assertIn('"FINDINGS — 1" (2x)', note[0])
        self.assertIn('bold text rather than a Word heading', note[0],
                      'The note must name the cause a doctor can actually act on.')
        self.assertEqual(duplicate_label_note([{'label': 'A'}, {'label': 'B'}]), [],
                         'A clean form collects no note.')


@override_settings(STORAGES=STORAGES)
class ASignatureQuestionKeepsItsSignatureLabel(BoundaryFixture, TestCase):
    """⚠️ THE TWO HALVES OF ONE CHANGE CANCELLED EACH OTHER.

    `structure()` deliberately excludes the label so a RENAMED mapping still fills, and the
    signature check reads that same editable label — so renaming `Electronically signed by` to
    `Attending physician` turned the identity check OFF for generation and finalization alike.
    Measured: "Dr Someone Else" accepted as the signature of a different clinician, by way of
    one ordinary label edit on the mapping-review screen.
    """

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        from core.models import TemplateVersion
        latest = self.encounter.template_version
        # A mapping version is append-only, so the signature label arrives as a NEW version
        # rather than an edit. Asserted, not assumed: a qualified Word backend refuses every
        # rename for its own reason and would pass the test below without the guard existing.
        self.assertFalse(latest.document_backend)
        fields = [dict(field) for field in latest.fields]
        fields[0]['label'] = 'Electronically signed by'
        from core.import_binding import for_mapping
        self.version = TemplateVersion.objects.create(
            template=latest.template, number=latest.number + 1, fields=fields,
            review_requirements=latest.review_requirements,
            document_backend=latest.document_backend,
            import_manifest=for_mapping(latest.import_manifest, fields), created_by=self.user)
        self.key = fields[0]['key']

    def rename(self, label):
        labels = {f['key']: f['label'] for f in self.version.fields}
        labels[self.key] = label
        before = self.version.template.versions.count()
        response = self.client.post(f'/templates/{self.version.template.pk}/',
                                    {'mapping_version': self.version.pk,
                                     'labels': json.dumps(labels)}, follow=True)
        return response, before, self.version.template.versions.count()

    def test_renaming_it_to_an_ordinary_question_is_refused_and_saves_nothing(self):
        response, before, after = self.rename('Attending physician')
        self.assertContains(response, 'signature question keeps a signature label')
        self.assertEqual(before, after)

    def test_renaming_it_to_another_signature_spelling_is_allowed(self):
        """The control. A guard that refused every rename would pass the test above for free."""
        response, before, after = self.rename('Signed by (MD)')
        self.assertNotContains(response, 'signature question keeps a signature label')
        self.assertEqual(after, before + 1)
