"""Explicit partial-coverage recovery for a protected consent destination; never automatic correctness."""
from core import import_binding
from core.models import Job, MappingConfirmation, Reservation, TemplateVersion, Usage
from core.security import private_path


def consent_issue(case, version, slot):
    coverage = version.import_manifest['coverage']
    case.assertTrue(coverage['block_generation'])
    case.assertFalse(coverage['automatic_complete'])
    issues = coverage['selected_engine_issues']
    case.assertEqual([(i['code'], i['part'], i['slot']) for i in issues],
                     [('human_signing_action', 'word/document.xml', slot)])
    consent = next(f for f in version.fields if f['label'] == 'Consent obtained')
    case.assertTrue(consent['write_protected'])
    expected_slot = slot
    if consent['kind'] == 'checkbox':
        expected_slot += '/glyphs'
        case.assertEqual(consent['locator']['target'], {'type': 'checkboxes', 'boxes': [{
            'kind': 'glyph', 'part': 'word/document.xml', 'slot': expected_slot, 'glyph': 0}]})
    case.assertEqual((consent['locator']['part'], consent['locator']['slot']),
                     ('word/document.xml', expected_slot))
    return issues[0]


def assert_unreviewed_consent_refused(case, template, version, slot):
    consent_issue(case, version, slot)
    original = private_path(template.original_path).read_bytes()
    before = (version.fields, version.document_backend, version.import_manifest)
    response = case.client.post(f'/templates/{template.pk}/', {
        'action': 'v3_confirm', 'mapping_version': version.pk, 'checked_every_field': 'on'})
    case.assertContains(response, 'This import has unmapped answer areas', status_code=400)
    response = case.client.post(f'/templates/{template.pk}/', {
        'action': 'v3_coverage', 'mapping_version': version.pk})
    case.assertContains(response, 'explicitly exclude every listed area', status_code=400)
    version.refresh_from_db()
    case.assertEqual((version.fields, version.document_backend, version.import_manifest), before)
    case.assertEqual(template.versions.count(), 1)
    for model in (MappingConfirmation, Job, Reservation, Usage):
        case.assertFalse(model.objects.exists(), model.__name__)
    case.assertEqual(private_path(template.original_path).read_bytes(), original)


def review_protected_consent(case, template, version, slot):
    issue = consent_issue(case, version, slot)
    original = private_path(template.original_path).read_bytes()
    response = case.client.post(f'/templates/{template.pk}/', {
        'action': 'v3_coverage', 'mapping_version': version.pk, 'exclude_' + issue['id']: 'on'})
    case.assertEqual(response.status_code, 302, response.content.decode())
    reviewed = case.latest(template)
    case.assertEqual(reviewed.number, version.number + 1)
    case.assertEqual((reviewed.fields, reviewed.document_backend, reviewed.import_manifest),
                     (version.fields, version.document_backend, version.import_manifest))
    case.assertEqual(reviewed.corrections['coverage_review'], [{
        'id': issue['id'], 'disposition': 'leave_unchanged',
        'source_sha256': template.sha256, 'reviewed_by': str(case.user.pk)}])
    case.assertTrue(import_binding.coverage_reviewed(reviewed))
    case.assertFalse(reviewed.import_manifest['coverage']['automatic_complete'])
    case.assertIsNone(TemplateVersion.objects.get(pk=version.pk).confirmed)
    case.assertEqual(private_path(template.original_path).read_bytes(), original)
    return reviewed
