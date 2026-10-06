"""Prospective source-bound consent exclusion; original frozen cases stay unchanged."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

try:
    from . import provider_campaign as pc
except ImportError:
    import provider_campaign as pc

MANIFEST = Path(__file__).with_name('fixtures') / 'frozen-notes-consent-review-v1.json'
MANIFEST_SHA256 = '64aaa64aabc46ab5954df14e442025f96210707703254bda1589be9dfe3086a5'


def frozen(digest):
    root = Path(__file__).resolve().parents[2]
    raw, _, _, _ = pc.committed_file(MANIFEST, root, 'prospective notes mapping review')
    pc.committed_file(Path(__file__).resolve(), root, 'notes mapping review reader')
    pc.require(digest == MANIFEST_SHA256 == hashlib.sha256(raw).hexdigest(),
               'The declared notes review differs from its committed freeze.')
    return json.loads(raw)


def inputs_with_review(inputs, row):
    result = deepcopy(inputs)
    form = result['cases']['forms'][row['form']]
    pc.require(form['sha256'] == row['source_sha256'], 'The notes original differs from its review freeze.')
    fields = form['fields']
    found = [f for f in fields if f['key'] == row['field_key']]
    pc.require(len(found) == 1 and found[0]['label'] == row['label']
               and found[0]['kind'] == 'checkbox' and not found[0].get('write_protected'),
               'The original consent field differs from the preserved frozen mapping.')
    result['original_frozen_notes_fields'] = {row['form']: deepcopy(fields)}
    found[0].update(write_protected=True, review_reason=row['review_reason'])
    return result


def assert_reviewable(template, version, row, fields):
    pc.require(template.sha256 == row['source_sha256'] and version.fields == fields,
               'The current original or physical mapping differs from the prospective review.')
    coverage = version.import_manifest.get('coverage', {})
    issues = coverage.get('selected_engine_issues', [])
    pc.require(coverage.get('automatic_complete') is False and coverage.get('block_generation') is True
               and not coverage.get('comparison_unresolved') and not coverage.get('layout_quarantine')
               and len(issues) == 1,
               'The exact human-owned exclusion is the only permitted partial coverage.')
    issue = issues[0]
    pc.require(all(issue.get(k) == row[k] for k in ('part','slot'))
               and issue.get('id') == row['issue_id'] and issue.get('code') == 'human_signing_action',
               'The current exclusion differs from the prospectively reviewed physical consent destination.')


def review_mapping(client, template, version, row, fields):
    """One actual clinician review POST; no direct database edits or automatic completeness."""
    from core import import_binding
    from core.models import TemplateVersion
    from core.security import private_path
    before_fields, before_manifest = deepcopy(version.fields), deepcopy(version.import_manifest)
    original = private_path(template.original_path).read_bytes()
    pc.require(hashlib.sha256(original).hexdigest() == row['source_sha256'], 'The uploaded original changed.')
    assert_reviewable(template, version, row, fields)
    response = client.post(f'/templates/{template.pk}/', {
        'action':'v3_coverage', 'mapping_version':str(version.pk), 'exclude_'+row['issue_id']:'on'})
    pc.require(response.status_code == 302, 'The explicit consent exclusion review was refused; nothing sent.')
    reviewed = TemplateVersion.objects.filter(template=template).order_by('-number').first()
    version.refresh_from_db()
    pc.require(reviewed.pk != version.pk and version.fields == before_fields
               and version.import_manifest == before_manifest and reviewed.fields == before_fields
               and reviewed.import_manifest == before_manifest and import_binding.coverage_reviewed(reviewed),
               'The explicit review did not preserve the original immutable mapping and binding.')
    records = reviewed.corrections.get('coverage_review', [])
    pc.require(len(records) == 1 and records[0].get('id') == row['issue_id']
               and records[0].get('disposition') == row['disposition']
               and records[0].get('source_sha256') == row['source_sha256']
               and records[0].get('reviewed_by')
               and private_path(template.original_path).read_bytes() == original,
               'The exact consent exclusion or original bytes were not preserved.')
    return reviewed, {'manifest_sha256':MANIFEST_SHA256, 'original_version':str(version.pk),
        'reviewed_version':str(reviewed.pk), 'coverage_review':records, 'automatic_complete':False,
        'manual_mapping_review':True, 'corpus_qualification':False}
