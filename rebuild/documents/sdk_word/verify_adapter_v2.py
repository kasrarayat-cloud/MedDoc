"""Actual sandbox and SDK qualification of reviewed WM v2 clinical variants."""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
import zipfile

from synthetic_fixture import build_fixture
from verify_adapter import ORIGINAL_SHA, NS, header_semantics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('original', 'runtime', 'manifest', 'output'):
        parser.add_argument('--'+name, required=True, type=Path)
    parser.add_argument('--manifest-sha', required=True)
    args = parser.parse_args()
    os.umask(0o077)
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    original = args.original.read_bytes()
    assert hashlib.sha256(original).hexdigest() == ORIGINAL_SHA
    launcher = Path(__file__).resolve().parents[1]/'sdk_sandbox.py'
    checks, serial = [], 0

    def check(name, condition):
        checks.append({'name': name, 'pass': bool(condition)})
        print(json.dumps(checks[-1]), flush=True)
        (args.output/'verification.json').write_text(json.dumps({'checks': checks, 'total': len(checks), 'all_pass': all(c['pass'] for c in checks), 'runtime_manifest_sha256': args.manifest_sha}, indent=2))
        assert condition, name

    def call(request, *, raw=None, altered=None):
        nonlocal serial
        serial += 1
        workspace = args.output/f'case-{serial:03d}'
        workspace.mkdir(mode=0o700)
        (workspace/'input.docx').write_bytes(original if altered is None else altered)
        (workspace/'request.json').write_text(json.dumps(request) if raw is None else raw)
        start = time.monotonic()
        result = subprocess.run([sys.executable, str(launcher), '--qualification', '--runtime', str(args.runtime), '--manifest', str(args.manifest), '--manifest-sha', args.manifest_sha, '--workspace', str(workspace)], capture_output=True, text=True, timeout=30, env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','QUILLMD_WORD_QUALIFICATION':'1'})
        if not result.stdout.strip():
            raise AssertionError('Sandbox failed before response: '+result.stderr[:300])
        payload = json.loads(result.stdout)
        (workspace/'result.json').write_text(json.dumps({'returncode':result.returncode,'duration_seconds':time.monotonic()-start,'result':payload},indent=2))
        return payload, workspace

    def refuse(name, request, code=None, **kwargs):
        result, workspace = call(request, **kwargs)
        check(name, result.get('code') == code if code else bool(result.get('code')))
        check(name+'_no_export', not (workspace/'output.docx').exists())

    inspect, _ = call({'operation':'inspect'})
    (args.output/'inspect.json').write_text(json.dumps(inspect,indent=2))
    check('v2_canonical_90_fields_14_requirements', inspect.get('backend') == 'wm-iov-foss-v2' and len(inspect['fields'])==90 and len(inspect['review_requirements'])==14)
    check('all_source_labels_unique_including_requirements', len({x['label'].casefold() for x in inspect['fields']+inspect['review_requirements']})==104)
    cases = {}
    for scenario in ('positive','absent','no_prior','asymptomatic','long'):
        request, resolved = build_fixture(inspect, lambda r:call(r)[0], scenario=scenario)
        result, workspace = call(request)
        check(scenario+'_actual_export', result.get('field_count')==90 and (workspace/'output.docx').exists())
        cases[scenario]=(request,resolved,workspace)
        (args.output/(scenario+'-fill-request.json')).write_text(json.dumps(request,indent=2))
        (args.output/(scenario+'-resolved.json')).write_text(json.dumps(resolved,indent=2))
        with zipfile.ZipFile(workspace/'output.docx') as z, zipfile.ZipFile(args.original) as old:
            doc=ET.fromstring(z.read('word/document.xml'))
            controls=doc.findall('.//w:sdt',NS)
            oldcontrols=ET.fromstring(old.read('word/document.xml')).findall('.//w:sdt',NS)
            def identities(rows):
                return [(r.find('w:sdtPr/w:id',NS).attrib, [x.attrib for x in r.findall('w:sdtPr/w:dropDownList/w:listItem',NS)]) for r in rows]
            check(scenario+'_all28_control_ids_and_original_options_preserved', len(controls)==28 and identities(controls)==identities(oldcontrols))
            ps=doc.find('w:body',NS).findall('w:p',NS)
            text=''.join(doc.itertext())
            check(scenario+'_actual_signer_and_timestamp', 'INTERPRETING PHYSICIAN: Synthetic Doctor' in text and '2026-09-17T12:34:56Z' in text and 'Maged S. Mikhail, MD, RPVI, RVT' not in ''.join(ps[46].itertext()))
            check(scenario+'_original_questions_and_layout_structure', len(ps)==48 and len(doc.findall('.//w:p',NS))==133 and ''.join(ps[18].itertext())=='TECHNIQUE' and ''.join(ps[21].itertext())=='FINDINGS')
            check(scenario+'_headers_media_semantics', all(header_semantics(z.read(name))==header_semantics(old.read(name)) if name.startswith('word/header') else z.read(name)==old.read(name) for name in old.namelist() if name.startswith('word/header') or name.startswith('word/media/')))
            check(scenario+'_all_resolved_statements_visible', all(r['text'] in text for r in resolved['review_requirements'] if r['kind']!='signature'))
            check(scenario+'_no_placeholder_or_duplicate_is', 'Choose an item.' not in text and 'is is absent' not in text)
            check(scenario+'_every_supported_answer_complete', all(a['text'] in text or (f['kind']=='measurement' and a['text'].removesuffix(' '+f['locator']['unit']) in text) for f in inspect['fields'] if (a:=request['answers'][f['key']])['text']))
            if scenario=='positive': check('positive_replaces_both_fixed_negatives', 'No saphenous reflux in right' not in text and 'No saphenous reflux in left' not in text)
            if scenario=='no_prior': check('no_prior_preserves_empty_controls_and_explicit_side_claims', 'No previous treatment in the right lower extremity.' in text and 'No previous treatment in the left lower extremity.' in text and 'was found to have had previous treatment' not in text)
            if scenario=='asymptomatic': check('no_symptoms_clean_visible_indication', ''.join(ps[15].itertext())=='CLINICAL INDICATIONS: Asymptomatic')
            if scenario=='long': check('full_long_answer_without_truncation', request['answers']['patient_name']['text'] in text)
    good,resolved,_=cases['positive']
    (args.output/'successful-fill-request.json').write_text(json.dumps(good,indent=2))
    (args.output/'resolved.json').write_text(json.dumps(resolved,indent=2))
    # Exact independently discovered cross-side proof: right evidence cannot
    # support the identical left statement or override its explicit negative.
    bad=deepcopy(good)
    bad['reviewed_requirements']['claim_27']['evidence']=deepcopy(bad['reviewed_requirements']['claim_23']['evidence'])
    bad['trusted_context']['notes']+='\nPrewritten statement: Left previous treatment: No previous treatment in the left lower extremity.'
    refuse('right_evidence_cannot_support_left_treatment',bad,'unsupported_assertion')
    bad=deepcopy(good)
    r=next(r for r in resolved['review_requirements'] if r['key']=='claim_23')
    start=len(bad['trusted_context']['notes'])+1
    bad['trusted_context']['notes']+='\n'+r['text']
    bad['reviewed_requirements']['claim_23']['evidence']=[{'quote':r['text'],'start':start,'end':start+len(r['text'])}]
    refuse('bare_statement_is_not_side_bound_evidence',bad,'unsupported_assertion')
    bad=deepcopy(good);bad['trusted_context']['notes']+='\nPrewritten statement: Right saphenous reflux finding: No saphenous reflux in right lower extremity.'
    refuse('conflicting_explicit_own_label_cannot_be_ignored',bad,'unsupported_assertion')
    bad=deepcopy(good);bad['claim_variants']['claim_32']='negative'
    refuse('positive_selection_with_negative_variant_rejected',bad,'template_conflict')
    bad=deepcopy(good);bad['claim_variants']['claim_23']='none'
    refuse('no_prior_variant_cannot_hide_supported_treatment_fields',bad,'template_conflict')
    bad=deepcopy(good);bad['answers']['sdt_1706206184']['text']='and is absent.'
    refuse('same_vein_cannot_be_absent_and_reflux_positive',bad,'template_conflict')
    bad=deepcopy(cases['no_prior'][0]);bad['answers']['sdt_-770853925']['text']='Previous vein treatment'
    refuse('prior_indication_cannot_conflict_with_bilateral_none',bad,'template_conflict')
    bad=deepcopy(cases['absent'][0]);bad['answers']['measurement_1_2']['text']='700 ms'
    refuse('global_negative_cannot_ignore_template_positive_duration',bad,'template_conflict')
    bad=deepcopy(cases['absent'][0]);bad['claim_variants']['claim_30']='not_assessed'
    for key in ('sdt_-892962961','sdt_-213273323'):
        bad['answers'][key].update(text='',status='missing',evidence=[])
    refuse('not_assessed_side_cannot_hide_recorded_measurements',bad,'template_conflict')
    bad=deepcopy(good);bad['claim_variants']['claim_32']='arbitrary freeform finding'
    refuse('unknown_variant_rejected',bad,'invalid_variant')
    bad=deepcopy(good);del bad['claim_variants']['claim_32']
    refuse('every_changed_variant_requires_explicit_review',bad,'review_required')
    bad=deepcopy(good);bad['trusted_context']['signer_name']='Different Synthetic Clinician'
    refuse('changed_actual_signer_invalidates_visible_review_hash',bad,'stale_review')
    bad=deepcopy(good);bad['reviewed_requirements']['claim_11']['evidence']=deepcopy(bad['reviewed_requirements']['claim_23']['evidence'])
    refuse('clinician_identity_cannot_come_from_notes',bad,'identity_evidence_forbidden')
    bad=deepcopy(good);bad['answers']['measurement_11_1']['evidence']=deepcopy(bad['answers']['measurement_12_1']['evidence'])
    refuse('tributary_evidence_not_transferable',bad,'unsupported_answer')
    bad=deepcopy(good);bad['answers']['measurement_11_1'].update(text='',status='missing',evidence=[])
    refuse('documented_measurement_cannot_be_silently_omitted',bad,'missing_documented_answer')
    bad=deepcopy(good);bad['answers']['measurement_11_1']['text']='3 cm'
    refuse('wrong_measurement_unit_rejected',bad,'invalid_measurement')
    bad=deepcopy(good);bad['answers']['patient_name']['text']='x'*20001
    refuse('oversize_is_refused_not_truncated',bad,'invalid_answer')
    bad=deepcopy(good);bad['answers']['patient_name']['revision']=6
    refuse('stale_source_review_rejected',bad,'stale_review')
    bad=deepcopy(good);bad['mapping_digest']='0'*64
    refuse('stale_mapping_rejected',bad,'stale_mapping')
    refuse('unknown_original_refused_before_sdk',{'operation':'inspect'},'unsupported_original',altered=original+b'x')
    refuse('duplicate_request_keys_refused',{},'duplicate_property',raw='{"operation":"inspect","operation":"fill"}')
    # Match core full-label normalization exactly, including internal colons.
    spaced=deepcopy(good);field=inspect['fields'][0];value=spaced['answers'][field['key']]['text']
    old=field['label']+': '+value;new='  '+field['label'].lower()+':  '+value
    spaced['trusted_context']['notes']=spaced['trusted_context']['notes'].replace(old,new,1)
    # Recompute every original span after the two added spaces; then bind this
    # field to its exact value span rather than a normalized invented quotation.
    for group in ('answers','reviewed_requirements'):
        for item in spaced[group].values():
            for e in item['evidence']:
                if e['quote']==old: e['quote']=value
                start=spaced['trusted_context']['notes'].index(e['quote']);e.update(start=start,end=start+len(e['quote']))
    result,_=call(spaced);check('normalized_complete_own_label_matches_core',result.get('field_count')==90)
    check('original_upload_unchanged',hashlib.sha256(args.original.read_bytes()).hexdigest()==ORIGINAL_SHA)
    print(json.dumps({'total':len(checks),'all_pass':True}))


if __name__=='__main__': main()
