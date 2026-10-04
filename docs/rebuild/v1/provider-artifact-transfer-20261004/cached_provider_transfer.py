"""Prospective fresh-route fixture replay; execute only through the protected QA wrapper after a root grant.

Old paid artifacts remain read-only. SDK requests are reconstructed and compared, never sent. All fresh
provider receipts are simulated, cost zero, and cannot qualify a new paid revision by themselves.
"""
from pathlib import Path
from types import SimpleNamespace
from decimal import Decimal
import ast
import hashlib
import importlib.util
import json
import os
import socket
import subprocess
import sys
from unittest.mock import patch

from transfer_inputs import GROUPS, PAID_SOURCE, load, semantic, sha

WT, HEAD, OUT, GROUP = Path(sys.argv[1]).resolve(), sys.argv[2], Path(sys.argv[3]).resolve(), sys.argv[4]
if GROUP not in GROUPS or len(HEAD) != 40:
    raise ValueError('A fixed packet and full frozen source identity are required.')
OUT.mkdir(mode=0o700, parents=True, exist_ok=False)


def git(*args):
    return subprocess.check_output(['git', *args], cwd=WT, text=True).strip()


def guarded_source():
    if git('rev-parse', 'HEAD') != HEAD or git('status', '--porcelain'):
        raise ValueError('The candidate must be the agreed clean frozen revision.')
    pins = json.loads((WT/'docs/rebuild/v1/qualified-provider-20261004-4/future-C-transfer-requirements.json').read_text())['guarded_source_inputs']
    modules = {'core/v3_field_relations.py': pins['ORDINARY_PRICED_SHA256'], **pins['BATCH_PRICED_MODULES'],
               **pins['ORDINARY_PRICED_DEPENDENCIES']}
    if len(modules) != 15 or len(pins['ORDINARY_PRICED_INPUTS']) != 4:
        raise ValueError('The complete fifteen-plus-four priced prerequisite is required.')
    hashes = {}
    for path, expected in modules.items():
        data = (WT/'rebuild'/path).read_bytes()
        paid = subprocess.check_output(['git', 'show', PAID_SOURCE+':rebuild/'+path], cwd=WT)
        digest = sha(ast.dump(ast.parse(data), include_attributes=False).encode())
        if digest != expected or digest != sha(ast.dump(ast.parse(paid), include_attributes=False).encode()):
            raise ValueError('Priced AST transfer differs: '+path)
        hashes[path] = sha(data)
    for path, expected in pins['ORDINARY_PRICED_INPUTS'].items():
        data = (WT/'rebuild'/path).read_bytes()
        if sha(data) != expected or data != subprocess.check_output(['git','show',PAID_SOURCE+':rebuild/'+path],cwd=WT):
            raise ValueError('Parser/package transfer differs: '+path)
        hashes[path] = sha(data)
    # These changes can affect admission/export even when every priced AST is equal.
    for path in ('core/import_binding.py','core/destination_roles.py','core/models.py','core/views.py',
                 'core/jobs.py','core/transcript_context.py','documents/word_v3.py','documents/service.py',
                 'documents/engine.py','documents/layout.py','ops/sonnet5_stages.py','quillmd/urls.py'):
        hashes[path] = sha((WT/'rebuild'/path).read_bytes())
    return hashes


BEFORE = guarded_source()
INPUTS = {attempt: load(attempt) for attempt in GROUPS[GROUP]}
sys.path.insert(0, str(WT/'rebuild'))
os.environ['DJANGO_SETTINGS_MODULE'] = 'quillmd.settings'
import django
django.setup()
from django.conf import settings
from django.test import TestCase, override_settings
from django.test.runner import DiscoverRunner
from django.core.files.uploadedfile import SimpleUploadedFile
from core import generation as g, v3_field_relations as r, transcript_context as tc
from core.jobs import run_one
from core.models import Encounter, Job, Usage, ProviderReceipt, Reservation, TranscriptReview, LedgerEntry, AuditEvent, MappingConfirmation
from core.security import private_path
from core.tests.test_word_v3_workflow import V3Fixture, V3
from core.tests.test_v3_supersession_floor import SONNET_55_DEFAULT
from ops import standing_qa_notes_review as nr, sonnet5_stages as stages
from documents.service import engine_fingerprint

if settings.AI_MODE != 'fixture' or not settings.DATABASES['default']['NAME'].startswith('quillmd_qa_sol_'):
    raise ValueError('Only the normal protected, isolated fixture QA database is permitted.')
spec=importlib.util.spec_from_file_location('closed_app_steps', WT/'docs/rebuild/v1/sonnet5-campaign/diagnostics/notes/app_path_steps.py')
steps=importlib.util.module_from_spec(spec); spec.loader.exec_module(steps)


def dump(folder, name, value):
    (folder/name).write_text(json.dumps(value, indent=2, default=str)+'\n')


@override_settings(**{**V3, **SONNET_55_DEFAULT, 'AI_MODE':'fixture', 'QUILLMD_AI_MODE':'fixture',
                     'QUILLMD_DEEPGRAM_SMART_FORMAT':'true', 'QUILLMD_DEEPGRAM_MIP_OPT_OUT':'true'})
class Transfer(V3Fixture, TestCase):
    def walk(self, attempt):
        retained = INPUTS[attempt]; folder = OUT/f'{attempt:03}'; folder.mkdir(mode=0o700)
        dump(folder, 'input-identity.json', {'paid_source':PAID_SOURCE, 'attempt':attempt,
             'evidence_sha256':retained['hashes'], 'current_source':HEAD,
             'current_engine_fingerprint':engine_fingerprint('v3'), 'cached_response_only':True})
        original = retained['original']
        template, version = self.uploaded(data=original, name=f'Closed artifact transfer {attempt:03}')
        self.assertEqual(template.sha256,sha(original))
        self.assertEqual(private_path(template.original_path).read_bytes(),original)
        self.assertEqual(version.fields, retained['fields'], 'Freshly inspected physical catalogue changed; do not copy old mapping')
        dump(folder,'fresh-import.json',{'template':str(template.pk),'version':str(version.pk),
             'source_sha256':template.sha256,'fields':version.fields,'manifest':version.import_manifest})
        if any(f.get('label')=='Consent obtained' and f.get('write_protected') for f in version.fields):
            freeze=nr.frozen(nr.MANIFEST_SHA256)
            version, review=nr.review_mapping(self.client,template,version,freeze,version.fields)
            dump(folder,'explicit-human-owned-coverage-review.json',review)
        version=self.confirm(template,version)
        self.assertTrue(version.confirmed)
        from core import import_binding
        import_binding.verify(version)
        dump(folder,'mapping-confirmation.json',{'version':str(version.pk),'confirmed':version.confirmed,
             'confirmation':list(MappingConfirmation.objects.filter(version=version).values())})
        self.assertEqual(self.new_encounter(version,notes='' if 'voice' in retained else retained['notes']).status_code,302)
        encounter=Encounter.objects.get(template_version=version); url=f'/encounters/{encounter.pk}/'
        if 'voice' in retained:
            voice=retained['voice']
            audio_name='soap-ankle-speech.wav' if attempt==17 else 'colonoscopy-speech.wav'
            audio=(voice['folder']/'case'/audio_name).read_bytes()
            def transcription(job, raw, key, submitted, params=None):
                self.assertEqual(key,'synthetic-offline-transfer-not-a-key')
                self.assertEqual(sha(raw),voice['request']['body_sha256'])
                self.assertEqual(params,voice['request']['params'])
                dump(folder,'fresh-transcription-submission.json',{'sha256':sha(raw),'submitted':submitted,'params':params,
                     'cached_response_sha256':sha((voice['folder']/'provider-response.json').read_bytes()),'simulated':True})
                return (voice['raw'],Decimal('0'),dict(submitted,duration_seconds=str(voice['response']['body_json']['metadata']['duration'])),
                    {'synthetic_cached_response':True},'synthetic-cached-deepgram',f'fixture-cached-asr-{attempt-1:03}',True)
            with patch.dict(os.environ,{'DEEPGRAM_API_KEY':'synthetic-offline-transfer-not-a-key',
                    'QUILLMD_DEEPGRAM_RATE_PER_MINUTE':'0.0043','QUILLMD_DEEPGRAM_RATE_PER_SECOND':''}):
                page=self.client.get(url)
                response=self.client.post(url+'voice/',{'audio':SimpleUploadedFile(audio_name,audio),
                    'consent':'on','usage_quote':page.context['usage_quote']})
                self.assertEqual(response.status_code,302)
                with patch('core.jobs.submit_transcription',side_effect=transcription): self.assertTrue(run_one())
            asr=Job.objects.get(kind='transcription',encounter=encounter)
            dump(folder,'fresh-ASR-worker-state.json',{'job':list(Job.objects.filter(pk=asr.pk).values()),'receipts':list(ProviderReceipt.objects.filter(job=asr).values()),'reservations':list(Reservation.objects.filter(job=asr).values()),'usage':list(Usage.objects.filter(job=asr).values())})
            self.assertEqual(asr.state,'succeeded',asr.error)
            raw_result=private_path(asr.result_path).read_bytes();(folder/'fresh-raw-transcription-result.json').write_bytes(raw_result)
            encounter.refresh_from_db()
            response=self.client.post(url+'notes/',{'revision':encounter.revision,'transcript_job':asr.pk,
                 'corrected_transcript':voice['reviewed'],'transcript_mode':'replace','transcript_reviewed':'on',
                 'transcript_patient_context':'on'})
            self.assertEqual(response.status_code,302)
            encounter.refresh_from_db();self.assertEqual(encounter.notes,retained['notes'])
            self.assertTrue(tc.current(encounter));self.assertEqual(TranscriptReview.objects.filter(job=asr).count(),1)
            dump(folder,'fresh-reviewed-source.json',{'rows':list(TranscriptReview.objects.filter(job=asr).values()),
                 'old_signed_token_copied':False,'explicit_frozen_edits':voice['edits']})
        page=self.client.get(url)
        self.assertEqual(page.status_code,200)
        response=self.client.post(url+'generate/',{'revision':encounter.revision,'usage_quote':page.context['usage_quote']})
        self.assertEqual(response.status_code,302)
        job=Job.objects.get(encounter=encounter,kind='generation')
        self.assertEqual(job.config['ordinary_field_contract'],r.CONTRACT)
        self.assertEqual(job.config['request_profile']['max_output_tokens'],20000)
        calls=[]
        def cached(notes,catalogue,compiled,config):
            calls.append(1)
            self.assertEqual(notes,retained['notes']);self.assertEqual(catalogue,retained['fields'])
            self.assertEqual(compiled['wire'],retained['request'],'SDK dictionary changed; no transfer inference')
            paid_audit=json.loads((retained['folder']/'audit-billing.json').read_text())
            rows=[row for row in paid_audit['rows'] if row['provider_resource_id']==retained['provider']['id']]
            self.assertEqual(len(rows),1)
            maximum=g.maximum_cost(notes,catalogue,{**config,'mode':'live'},
                   context_labels=[row['label'] for row in version.review_requirements],requirements=version.review_requirements)
            limit=(maximum*Decimal('1.5')).quantize(Decimal('0.000000000001'))
            self.assertEqual(config['pricing_version'],rows[0]['configured_pricing_fingerprint_at_enqueue'])
            self.assertEqual(limit,Decimal(rows[0]['customer_limit_usd']))
            dump(folder,'quote-prerequisite.json',{'current_offline_live_mode_maximum':str(maximum),
                 'current_customer_limit':str(limit),'retained_customer_limit':rows[0]['customer_limit_usd'],
                 'current_actual_job_mode':'fixture','actual_new_charge':'0','new_paid_usage':False,
                 'retained_usage_immutable_reference':rows[0]})
            provider=retained['provider']; response=SimpleNamespace(model=provider['model'],stop_reason=provider['stop_reason'],
                content=[SimpleNamespace(**block) for block in provider['content']])
            answers=r.validated({'anthropic_response':response,'ordinary_field_contract':r.CONTRACT,
                'notes':notes,'fields':compiled['asked'],'full_catalogue':catalogue,'context_labels':compiled['context'],
                'requested_model':g.SONNET_5_5,'patient_default_context':config.get('patient_default_context','')})
            dump(folder,'current-compiled-SDK.json',compiled['wire']);dump(folder,'cached-provider-output.json',provider)
            return answers
        with patch('core.relations_fixture.result',side_effect=cached):self.assertTrue(run_one())
        job.refresh_from_db();self.assertEqual(job.state,'succeeded',job.error);self.assertEqual(len(calls),1)
        encounter.refresh_from_db();first=json.loads(json.dumps(encounter.answers))
        dump(folder,'first-current-answers.json',first);dump(folder,'job-config.json',job.config)
        self.assertEqual({k:semantic(v) for k,v in first.items()},{k:semantic(v) for k,v in retained['first'].items()})
        dump(folder,'first-pass-counts.json',{'actual_status_counts':{state:sum(a['status']==state for a in first.values())
              for state in ('supported','conflict','missing')},'exact_retained_answer_equality':True,
              'original_classification_unchanged':retained['classification'],
              'manual_answer_corrections':0,'scope':'Semantic equality preserves the original declared gold adjudication; this does not create new paid outcomes.'})
        page=self.client.get(url);(folder/'review-page.html').write_bytes(page.content)
        payload=steps.review_payload(version.fields,first,steps.review_controls(page.content),encounter.revision,version.review_requirements)
        self.assertEqual(steps.save_review(self.client,encounter.pk,payload).status_code,302)
        encounter.refresh_from_db();saved=json.loads(json.dumps(encounter.answers));dump(folder,'saved-reviewed-answers.json',saved)
        self.assertEqual(steps.finalize(self.client,encounter.pk,encounter.revision).status_code,302)
        encounter.refresh_from_db();self.assertEqual(encounter.status,'finalized')
        export=self.client.get(url+'export/');self.assertEqual(export.status_code,200)
        exported=b''.join(export.streaming_content);(folder/'current-export.docx').write_bytes(exported)
        self.assertEqual(private_path(encounter.export_path).read_bytes(),exported)
        self.assertEqual(encounter.export_sha256,sha(exported))
        repeated=self.client.get(url+'export/');self.assertEqual(repeated.status_code,200)
        self.assertEqual(b''.join(repeated.streaming_content),exported)
        reading=stages.export_read_back(original,exported,version.fields,saved);dump(folder,'export-read-back.json',reading)
        self.assertTrue(reading['passed'],reading['problems']);self.assertEqual(private_path(template.original_path).read_bytes(),original)
        receipts=list(ProviderReceipt.objects.filter(job__encounter=encounter).values())
        self.assertTrue(receipts);self.assertTrue(all(row['simulated'] and row['actual_cost']==0 for row in receipts))
        self.assertTrue(all(u.actual_cost==0 and u.charged_cost==0 for u in Usage.objects.filter(job__encounter=encounter)))
        self.assertFalse(Reservation.objects.filter(job__encounter=encounter,state='held').exists())
        dump(folder,'persisted-final-state.json',{'encounter':list(Encounter.objects.filter(pk=encounter.pk).values()),
            'jobs':list(Job.objects.filter(encounter=encounter).values()),'receipts':receipts,
            'usage':list(Usage.objects.filter(job__encounter=encounter).values()),
            'ledger':list(LedgerEntry.objects.filter(job__encounter=encounter).values()),
            'audits':list(AuditEvent.objects.filter(target__in=[str(encounter.pk),str(job.pk)]).values()),
            'original_immutable':True,'read_back_passed':True,'manual_answer_corrections':0,'provider_calls':0,
            'new_paid_qualification':False,'first_pass_sha256':sha((folder/'first-current-answers.json').read_bytes()),
            'export_sha256':sha(exported)})


for attempt in GROUPS[GROUP]:
    def test(self, attempt=attempt): self.walk(attempt)
    setattr(Transfer,f'test_cached_{attempt:03}',test)

def refused(*args,**kwargs): raise AssertionError('No real provider request in cached fixture transfer')
original_connect=socket.socket.connect
original_connect_ex=socket.socket.connect_ex
original_getaddrinfo=socket.getaddrinfo
def connect(sock,address):
    if isinstance(address,tuple) and address[0]=='127.0.0.1' and address[1]==55731:return original_connect(sock,address)
    raise AssertionError('External network/renderer refused in fixture transfer')
def connect_ex(sock,address):
    if isinstance(address,tuple) and address[0]=='127.0.0.1' and address[1]==55731:return original_connect_ex(sock,address)
    raise AssertionError('External network/renderer refused in fixture transfer')
def resolve(host,port,*args,**kwargs):
    if host=='127.0.0.1' and str(port)=='55731':return original_getaddrinfo(host,port,*args,**kwargs)
    raise AssertionError('External DNS/network refused in fixture transfer')

from unittest import TestLoader
with patch('anthropic.Anthropic',side_effect=refused), patch('httpx.post',side_effect=refused), \
        patch.object(socket.socket,'connect',connect),patch.object(socket.socket,'connect_ex',connect_ex), \
        patch.object(socket,'getaddrinfo',resolve), \
        patch.dict(os.environ,{'QUILLMD_DEEPGRAM_RATE_PER_MINUTE':'0.0043','QUILLMD_DEEPGRAM_RATE_PER_SECOND':''}):
    runner=DiscoverRunner(interactive=False,verbosity=2)
    suite=TestLoader().loadTestsFromTestCase(Transfer)
    # DiscoverRunner.run_tests accepts labels only. Build this literal suite explicitly.
    runner.setup_test_environment()
    old=runner.setup_databases()
    try:
        result=runner.run_suite(suite)
    finally:
        runner.teardown_databases(old);runner.teardown_test_environment()
    code=len(result.failures)+len(result.errors)
after=guarded_source()
assert BEFORE==after
for attempt in GROUPS[GROUP]:load(attempt) # closed evidence hashes remain unchanged
dump(OUT,'packet-result.json',{'source':HEAD,'paid_source':PAID_SOURCE,'group':GROUP,'attempts':GROUPS[GROUP],
     'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'source_sha256':after,
     'provider_calls':0,'paid_evidence_unchanged':True,'scope':'Cached-response fixture route/export transfer; no new paid or human/native acceptance'})
raise SystemExit(bool(code))
