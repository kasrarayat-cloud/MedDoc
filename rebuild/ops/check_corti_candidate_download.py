"""Read-only comparison of actual downloads with the isolated persisted approval."""
import hashlib
import json
from pathlib import Path
import sys
from zipfile import ZipFile

import django
django.setup()
from django.conf import settings
from lxml import etree
from core.coding_export import eligible_codes, W, TAG
from core.models import CodingRun, Encounter, Job
from core.security import private_path


def main():
    if settings.SETTINGS_MODULE != 'ops.corti_candidate_settings' or settings.CORTI_CODING_MODE != 'replay':
        raise RuntimeError('Only the isolated replay candidate may be inspected.')
    downloads, destination = map(Path, sys.argv[1:])
    installed = json.loads((settings.STATE_DIR / 'installation.json').read_text())
    encounter = Encounter.objects.get(pk=installed['encounter_id'])
    run, decision, codes = eligible_codes(encounter)
    assert [(r['system'], r['code']) for r in codes] == [('ICD-10-CM', 'R12')]
    assert run.result['original_verdict'] == 'FAIL_RESPONSE_QUALITY_WITH_SELECTED_CODES_PASS'
    assert sum(len(r['evidence_spans']) for r in run.result['suggestions']) == 7
    assert CodingRun.objects.count() == 1 and len(run.requests) == 1
    assert all(r['simulated'] and not r['sent'] for r in run.requests)
    assert Job.objects.count() == 0  # No clinical generation during export.
    original = downloads / 'synthetic-original.docx'
    variant = downloads / 'synthetic-with-codes.docx'
    assert original.read_bytes() == private_path(encounter.export_path).read_bytes()
    assert hashlib.sha256(original.read_bytes()).hexdigest() == encounter.export_sha256
    with ZipFile(original) as source, ZipFile(variant) as coded:
        assert source.namelist() == coded.namelist()
        for name in source.namelist():
            if name != 'word/document.xml':
                assert source.read(name) == coded.read(name), name
        old, new = source.read('word/document.xml'), coded.read('word/document.xml')
        assert new.startswith(old[:old.rindex(b'<w:sectPr')])
        root = etree.fromstring(new)
        appendix = root.xpath('//w:sdt[w:sdtPr/w:tag/@w:val="' + TAG + '"]', namespaces={'w': W})
        assert len(appendix) == 1
        text = appendix[0].xpath('.//w:t/text()', namespaces={'w': W})
        assert text == ['Diagnosis and procedure codes', 'ICD-10-CM', 'R12 — Heartburn']
    report = dict(verdict='PASS', scope='Read-only persisted decision versus actual browser downloads',
        encounter_id=str(encounter.pk), run_id=str(run.pk), decision_id=str(decision.pk),
        revision=encounter.revision, input_digest=run.input_digest, selection_digest=decision.selection_digest,
        codes=codes, appendix_text=text, evidence_spans=7, coding_runs=1, simulated_attempts=1,
        provider_calls=0, generation_jobs=0, original_clinical_xml_prefix_unchanged=True,
        all_other_zip_members_unchanged=True, original_sha256=encounter.export_sha256,
        variant_sha256=hashlib.sha256(variant.read_bytes()).hexdigest(),
        original_provider_response_sha256=run.requests[0]['response_sha256'],
        original_verdict=run.result['original_verdict'])
    with destination.open('x') as handle:
        destination.chmod(0o600)
        json.dump(report, handle, indent=2)
    print(json.dumps({'verdict':report['verdict'], 'output':str(destination)}))


if __name__ == '__main__':
    main()
