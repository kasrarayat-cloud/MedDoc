#!/usr/bin/env python3
"""The TRANSCRIPTION stage of the standing synthetic API testing (ops/standing_qa.py), in the request process.

Every rule of ops/standing_qa.py stands (the authority, the committed declaration, the ruled-mutation door, the Stop
file, admission, the ledger, runs, duplicates, the per-request bounds, reconciliation, the leak scan); this module adds
only what transcription needs, stated so a reader can see how each would fail:

  the recording   only an entry of standing_qa.TRANSCRIPTION_AUDIO the declaration names — synthesized speech, never a
                  human microphone recording — read whole and refused unless its bytes are the pinned size and sha256;
                  the product's stored upload must hash to the same sha256 before anything is admitted, and the attempt
                  record carries it (standing_qa.StandingLedger.write_attempt refuses any other recording).
  the credential  the Deepgram key reaches this process only for a transcription run (standing_qa.outer, inner); it is
                  verified against the declared file, kept in memory, and put into the environment — where the product
                  reads it (core.jobs.transcribe) — ONLY around the transcription send's one run_one(), then removed.
  the request     install_transcription_guard sits on the campaign's transport guard: during a transcription attempt it
                  admits exactly ONE request, POST https://api.deepgram.com/v1/listen carrying exactly the declared
                  parameters (model nova-3-medical, smart_format false, mip_opt_out true) and exactly the declared key;
                  it records the request (its credential header removed) and its body BEFORE anything leaves, then the
                  response as received. Anything else — another host, URL, parameter, credential, a second request, a
                  request outside an attempt — is refused before a connection is opened. Outside a transcription attempt
                  every request goes to the campaign guard unchanged (only the Messages URL).
  the send        TranscriptionRun.transcription_send: the frozen synthetic form r1-11 uploaded and confirmed, a
                  voice-first encounter (no typed notes), the page's voice quote, the recording through the real voice
                  view (one transcription job, its hold = the product's own quote within the shown limit), admission,
                  the attempt, run_one, the outcome (request id, duration, the provider cost at the declared per-minute
                  rate, the settlement), then the clinician's review of the transcript and its save as the notes through
                  the real notes view (replace, unedited).
  its generation  TranscriptionRun.transcript_generation_send, on THAT encounter in the same run: the page's quote,
                  Generate, admission, the attempt, the one Messages request, the outcome and its contract checks, the
                  review, finalization, the authenticated export and its two checks (sonnet5_stages.Run's own), and the
                  source-support check of every adopted answer against the saved notes.
Contract failures and unsafe output stop the stage exactly as on the other stages (provider_campaign.classify_case).
"""
import hashlib
import html as htmlmod
import json
import os
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

try:
    from . import provider_campaign as pc
    from . import sonnet5_qa as sq
    from . import standing_qa as st
except ImportError:                                  # (run as a script: ops/ is on sys.path)
    import provider_campaign as pc
    import sonnet5_qa as sq
    import standing_qa as st

stages = sq.stages_module()
steps = stages.steps
require = pc.require
Refused = pc.Refused

LISTEN_HOST = 'api.deepgram.com'
LISTEN_PATH = '/v1/listen'
#: The request's body, retained beside its record (the exact submitted bytes: synthetic speech, prepared by the product).
REQUEST_BODY = 'request.body'
#: Why the guard refused a transcription request (never a credential), kept with the attempt.
TRANSPORT_REFUSAL = 'transport-refusal.json'
#: Headers that carry a credential: never retained, and on a transcription request none but the one Authorization.
CREDENTIAL_HEADERS = frozenset(('authorization', 'x-api-key', 'proxy-authorization', 'cookie'))
#: The product's own submission bound (core.jobs.SUBMISSION_LIMIT_BYTES).
SUBMISSION_LIMIT_BYTES = 15 * 1024 * 1024
VOICE_FORM = re.compile(r'<form[^>]*data-voice-form[^>]*>(.*?)</form>', re.S)
TRANSCRIPT_FORM = re.compile(r'<form[^>]*data-transcript-form[^>]*>(.*?)</form>', re.S)
TRANSCRIPT_AREA = re.compile(r'<textarea[^>]*name="corrected_transcript"[^>]*>(.*?)</textarea>', re.S)
COST_QUANTUM = Decimal('0.0000000001')


# ── the transport guard ──────────────────────────────────────────────────────────────────────────────────────────

def install_transcription_guard(network=None):
    """Wrap the campaign's transport guard (provider_campaign.install_transport_guard, which must be installed: this
    sits on it, never instead of it). `network`: what a transcription request admitted here is handed to — the real
    transport by default; a stand-in `(transport, request) -> httpx.Response` in tests. In this process only."""
    import httpx
    current = httpx.HTTPTransport.handle_request
    if getattr(current, '_transcription_guard', False):
        return
    require(getattr(current, '_campaign_guard', False),
            'The transcription guard sits on the campaign\'s transport guard, which is not installed.')
    original = current._campaign_original
    send_out = original if network is None else network

    def handle_request(self, request):
        attempt = dict(pc.CURRENT_ATTEMPT)
        terms = attempt.get('transcription')
        if not terms:
            return current(self, request)            # (every other request: the campaign guard, the Messages URL only)
        number, evidence = attempt.get('number'), attempt.get('evidence_dir')
        require(number and evidence, 'A transcription request outside an attempt was refused at the transport.')
        evidence = Path(evidence)
        try:
            record, content = capture_transcription_request(request, terms, attempt.get('secret'))
            require(not pc.SENT.get(number), 'A second send inside one attempt was refused at the transport.')
        except Refused as refused:
            # (why it was refused, kept with the attempt: the product records only the error's class; the reason names
            # the declared terms and never a credential)
            if not (evidence / TRANSPORT_REFUSAL).exists():
                pc.write_new(evidence / TRANSPORT_REFUSAL, {'refused': str(refused), 'at': pc.now()})
            raise
        try:
            pc.write_new(evidence / 'request.json', {**record, 'attempt': number, 'captured_at': pc.now()})
        except FileExistsError:
            raise Refused('A second provider request inside one attempt was refused.') from None
        pc.write_new(evidence / REQUEST_BODY, content, raw=True)
        pc.SENT[number] = 1
        response = send_out(self, request)
        response.read()
        secret = terms['secret']
        received = pc.response_record(response, secret)         # (cookies and credentials dropped; a keyed body refused)
        other = attempt.get('secret')
        require(not (other and (other.encode() in response.content or other in json.dumps(received))),
                'The provider response would carry a credential; it was not retained.')
        received.update(attempt=number, received_at=pc.now())
        pc.write_new(evidence / pc.RESPONSE_BODY, response.content, raw=True)
        pc.write_new(evidence / pc.RESPONSE_FILE, received)
        return response

    handle_request._campaign_guard = True            # (provider_campaign.install_transport_guard leaves a guard alone)
    handle_request._campaign_original = original     # (provider_campaign.uninstall_transport_guard restores the network)
    handle_request._transcription_guard = True
    handle_request._transcription_previous = current
    httpx.HTTPTransport.handle_request = handle_request


def uninstall_transcription_guard():
    import httpx
    current = httpx.HTTPTransport.handle_request
    if getattr(current, '_transcription_guard', False):
        httpx.HTTPTransport.handle_request = current._transcription_previous


def capture_transcription_request(request, terms, other_secret=None):
    """(record, body) of a transcription request, refused BEFORE anything is recorded or sent unless it is exactly
    POST https://api.deepgram.com/v1/listen, each declared parameter once and nothing else, `Authorization: Token <the
    declared key>` and no other credential header, an octet-stream body of 1..15 MiB. The record has no credential
    header; it is refused if either key (or the Anthropic key shape) survives anywhere in it."""
    url = request.url
    require(request.method == 'POST' and url.scheme == 'https' and url.host == LISTEN_HOST and url.port is None
            and url.path == LISTEN_PATH and not url.userinfo and not url.fragment,
            f'A request {request.method} {url.host}{url.path} was refused during a transcription send; only POST '
            f'{st.DEEPGRAM_URL} is made.')
    items = list(url.params.multi_items())
    parameters = dict(items)
    declared = dict(terms['parameters'])
    require(len(items) == len(parameters) and parameters == declared,
            f'The transcription request carries other parameters than the declared {declared}; nothing was sent.')
    secret = terms.get('secret')
    authorizations = request.headers.get_list('authorization')
    require(isinstance(secret, str) and secret and len(authorizations) == 1
            and pc.constant_time_equal(authorizations[0], f'Token {secret}'),
            'The transcription request does not carry exactly the declared Deepgram credential; nothing was sent.')
    require(not any(name.lower() in CREDENTIAL_HEADERS - {'authorization'} for name in request.headers),
            'The transcription request carries another credential header; nothing was sent.')
    require(request.headers.get('content-type') == 'application/octet-stream',
            'The transcription request body is not the product\'s octet-stream; nothing was sent.')
    content = request.content
    require(0 < len(content) <= SUBMISSION_LIMIT_BYTES,
            f'The transcription request body is not 1..{SUBMISSION_LIMIT_BYTES} bytes; nothing was sent.')
    headers, removed = {}, []
    for name, value in request.headers.multi_items():
        if name.lower() in CREDENTIAL_HEADERS or secret in value or (other_secret and other_secret in value):
            removed.append(name.lower())
            continue
        headers[name.lower()] = value
    record = {'method': request.method, 'url': str(url), 'params': parameters, 'headers': headers,
              'removed_headers': sorted(removed), 'body_file': REQUEST_BODY,
              'body_sha256': hashlib.sha256(content).hexdigest(), 'body_bytes': len(content)}
    text = json.dumps(record, sort_keys=True)
    require(secret not in text and not (other_secret and other_secret in text) and not pc.KEY_SHAPE.search(text.encode()),
            'The captured transcription request would carry a credential; nothing was sent.')
    return record, content


# ── the request process's checks for a transcription run ──────────────────────────────────────────────────────────

def preconditions(campaign, *, transcription_secret, database_prefix=sq.DATABASE_PREFIX, rebuild=st.REBUILD,
                  environ=None, expect=None):
    """Asserted before anything is written for a transcription run: the historical door's own checks under the
    `transcription` pricing version (sonnet5_qa.preconditions: the synthetic QA database and state, synthetic mode, live
    AI at the declared model, rates, thinking, effort and geography, every contract flag off, the declared pricing
    version, the Anthropic credential and the scrubbed environment, a clean leak scan, a reconciled ledger); the notes
    stage's settings (v3, no layout socket, no mapping assistance); the declared transcription request — the per-minute
    rate (and no per-second rate), the Model Improvement opt-out on, smart formatting off, and the product's own
    parameters equal to the declared ones; the Deepgram key equal to the declared file's and ABSENT from the environment
    (it enters only around the one request); and no copy of it under the campaign root."""
    from django.conf import settings
    from core import jobs as app_jobs
    declaration, root = campaign.declaration, campaign.root
    terms = declaration.transcription
    environ = os.environ if environ is None else environ
    require(terms is not None, 'The declaration declares no transcription stage.')
    require(st.TRANSCRIPTION_KEY_VARIABLE not in environ,
            'The Deepgram credential is in the request process environment outside its one request; nothing is sent.')
    require(isinstance(transcription_secret, str) and transcription_secret
            and pc.constant_time_equal(transcription_secret, st.load_transcription_credential(declaration)),
            'The run does not carry the declared Deepgram credential.')
    checked = sq.preconditions(declaration, 'transcription', root, database_prefix=database_prefix, rebuild=rebuild,
                               environ=environ, ledger=campaign.ledger, expect=expect)
    require(settings.QUILLMD_WORD_ENGINE == 'v3', 'The transcript is generated on the v3 Word engine.')
    require(not settings.QUILLMD_LAYOUT_SOCKET, 'The deployed-equivalent path has no layout socket.')
    require(not (settings.QUILLMD_MAPPING_ASSISTANCE or settings.QUILLMD_MAPPING_ASSISTANCE_LIVE),
            'Mapping assistance is off for the transcription stage.')
    require(settings.QUILLMD_DEEPGRAM_MIP_OPT_OUT == 'true' and settings.QUILLMD_DEEPGRAM_SMART_FORMAT == 'false',
            'The transcription stage runs with QUILLMD_DEEPGRAM_MIP_OPT_OUT=true and smart formatting off.')
    require(environ.get('QUILLMD_DEEPGRAM_RATE_PER_MINUTE') == terms.rate_per_minute
            and not environ.get('QUILLMD_DEEPGRAM_RATE_PER_SECOND'),
            f'The application\'s transcription rate is not the declared {terms.rate_per_minute} USD per minute.')
    require(app_jobs.DEEPGRAM_MODEL == terms.model and app_jobs.deepgram_parameters() == terms.parameters(),
            'The application would send other transcription parameters than the declared ones.')
    stray = pc.leaked(root, transcription_secret, exclude=(terms.credential_file,))
    require(not stray, 'The Deepgram credential is already present in retained files: ' + ', '.join(stray))
    return {**checked, 'transcription': {'provider': terms.provider, 'model': terms.model,
                                         'rate_per_minute': terms.rate_per_minute, 'parameters': terms.parameters(),
                                         'inputs': list(terms.inputs)}}


def planned_maxima(sends, declaration):
    """{send id: its planned maximum, or None}: a transcription send's from its recording's measured length (the
    product's own reader, core.audio.measure_bounds, on the sha256-verified bytes) at the declared rate; a transcript's
    generation is priced by the application only once the transcript exists (None: no preview)."""
    from core import audio as app_audio
    rate = declaration.transcription.rate_per_minute
    planned = {}
    for send in sends:
        if send.path == 'transcription':
            seconds = app_audio.measure_bounds(st.read_audio(st.audio_entry(send.case))).measured
            planned[send.id] = st.transcription_maximum(seconds, rate)
        else:
            planned[send.id] = None
    return planned


# ── what the pages show ──────────────────────────────────────────────────────────────────────────────────────────

def voice_quote(client, encounter):
    """The voice form exactly as the page shows it: (its signed usage quote, the configuration it signs)."""
    from django.core import signing
    page = client.get(f'/encounters/{encounter.pk}/')
    require(page.status_code == 200, f'The encounter page failed ({page.status_code}).')
    form = VOICE_FORM.search(page.content.decode())
    require(form, 'The page offers no voice form.')
    token = re.search(r'name="usage_quote" value="([^"]*)"', form.group(1))
    require(token, 'The voice form carries no quote.')
    token = htmlmod.unescape(token.group(1))
    return token, signing.loads(token, salt='usage-quote')['config']


def transcript_shown(page, job):
    """The transcript the page offers the clinician to review for `job`, exactly as a browser would submit it unedited
    (a line break straight after <textarea> is not content), or None when the page offers no review of it."""
    for form in TRANSCRIPT_FORM.finditer(page):
        if f'name="transcript_job" value="{job.pk}"' not in form.group(1):
            continue
        area = TRANSCRIPT_AREA.search(form.group(1))
        if area is None:
            return None
        shown = htmlmod.unescape(area.group(1))
        return shown[1:] if shown.startswith('\n') else shown
    return None


def provider_transcript(body):
    """The transcript in a Deepgram response body (the product's own path: results.channels[0].alternatives[0])."""
    try:
        return body['results']['channels'][0]['alternatives'][0]['transcript']
    except (KeyError, IndexError, TypeError):
        return None


def _decimal(value):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return number if number.is_finite() and value is not None and not isinstance(value, bool) else None


def source_support_problems(answer, notes):
    """Why an adopted answer is not supported by the notes it was generated from (empty: it is): it cites nothing; a
    citation is not exactly the notes at its offsets; or a line of the answer is in none of its citations (whitespace
    compared loosely, nothing else)."""
    evidence = answer.get('evidence') or []
    if not isinstance(evidence, list) or not evidence:
        return ['the adopted answer cites no source']
    problems, quotes = [], []
    for item in evidence:
        if not (isinstance(item, dict) and type(item.get('start')) is int and type(item.get('end')) is int
                and 0 <= item['start'] < item['end'] <= len(notes) and notes[item['start']:item['end']] == item.get('quote')):
            problems.append('a citation is not the notes at its offsets')
            continue
        quotes.append(' '.join(item['quote'].split()))
    for line in str(answer.get('text') or '').splitlines():
        flat = ' '.join(line.split())
        if flat and not any(flat in quote for quote in quotes):
            problems.append('a line of the adopted answer is in none of its citations')
    if not str(answer.get('text') or '').strip():
        problems.append('the adopted answer is empty')
    return problems


# ── the worker ───────────────────────────────────────────────────────────────────────────────────────────────────

class TranscriptionRun(stages.Run):
    """sonnet5_stages.Run for the transcription stage: the same admission, attempt, outcome, audit, reconciliation,
    classification, manifest, interruption and export machinery, with the two transcription paths."""

    def __init__(self, campaign, stage, *, secret, transcription_secret, provenance, inputs, forms, world, checked,
                 deadline):
        super().__init__(campaign, stage, secret=secret, provenance=provenance, inputs=inputs, forms=forms, world=world,
                         checked=checked, deadline=deadline)
        require(stage == 'transcription' and campaign.declaration.transcription is not None,
                'The transcription worker runs the declared transcription stage only.')
        require(isinstance(transcription_secret, str) and transcription_secret, 'The transcription worker needs the key.')
        self.transcription_secret = transcription_secret
        self.terms = campaign.declaration.transcription
        self.planned = {}
        #: recording id -> what its transcription send made (this process only: its generation needs it in this run)
        self.transcribed = {}

    def run_send(self, send):
        planned = self.planned.get(send.id)
        if planned is not None:
            self.admit(planned)            # (a preview on the planned maximum: nothing is created if it cannot fit)
        if send.path == 'transcription':
            return self.transcription_send(send)
        if send.path == 'transcription_generation':
            return self.transcript_generation_send(send)
        raise Refused(f'The transcription stage has no path {send.path!r}.')

    def scan(self, evidence, attempt, context):
        """The manifest and the Anthropic key's scan (sonnet5_stages.Run.scan), then the Deepgram key's: a copy of
        either, or a tree that cannot be scanned, is a campaign stop."""
        found = super().scan(evidence, attempt, context)
        reasons = []
        try:
            hits = pc.leaked(self.root, self.transcription_secret, exclude=(self.terms.credential_file,))
        except pc.Refused as refused:
            hits = []
            reasons.append(f'the retained evidence could not be scanned for the Deepgram credential: {refused}')
        if hits:
            reasons.append('the Deepgram credential was found in retained evidence: ' + ', '.join(hits))
        if reasons:
            self.ledger.write_stop({'reason': 'the retained evidence could not be scanned for the Deepgram credential, '
                                              'or carries it', 'detail': reasons})
        return found + [{'code': 'credential_leak', 'why': reason} for reason in reasons]

    # ── the transcription send ───────────────────────────────────────────────────────────────────────────────────
    def transcription_send(self, send):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.utils import timezone
        from core import jobs as app_jobs
        from core.models import Encounter, Job, Reservation
        from core.security import private_path
        terms = self.terms
        require(send.case in terms.inputs, f'{send.id}: the declaration does not name this recording.')
        entry = st.audio_entry(send.case)
        audio = st.read_audio(entry)
        run = self.campaign.runs.current()
        require(run is not None and entry.sha256 in run['allowed_inputs']
                and entry.sha256 not in set(run['restricted_inputs']),
                f'{send.id}: the recording is not one its run allows; nothing is sent.')
        form = self.inputs['cases']['forms'][st.TRANSCRIPTION_FORM]
        number = len(self.ledger.rows()) + 1
        template, version = self.upload(self.forms[st.TRANSCRIPTION_FORM],
                                        f'SYNTHETIC STANDING TRANSCRIPTION {entry.id} attempt {number}', 'intake.docx')
        if version.fields != form['fields']:
            raise stages.StageStop(f'{send.id}: the stored mapping differs from the frozen {st.TRANSCRIPTION_FORM} '
                                   'fields (nothing sent)')
        response = steps.confirm_mapping(self.world.client, template.pk, version.pk)
        version.refresh_from_db()
        require(response.status_code == 302 and version.confirmed, 'The mapping confirmation was refused.')
        before = set(Encounter.objects.values_list('pk', flat=True))
        response = steps.create_encounter(self.world.client, self.world.patient.pk, version.pk, '',
                                          timezone.localdate().isoformat())
        created = Encounter.objects.exclude(pk__in=before)
        require(response.status_code == 302 and created.count() == 1, 'Encounter creation did not create exactly one.')
        encounter = created.get()
        require(encounter.notes == '', 'A voice-first encounter starts with no typed notes.')
        token, quoted = voice_quote(self.world.client, encounter)
        stages.require_price(self.declaration, quoted, send)
        jobs_before = set(Job.objects.values_list('pk', flat=True))
        upload = SimpleUploadedFile(f'synthetic-speech-{entry.id}.wav', audio, content_type='audio/wav')
        response = self.world.client.post(f'/encounters/{encounter.pk}/voice/',
                                          {'audio': upload, 'consent': 'on', 'usage_quote': token})
        jobs = list(Job.objects.exclude(pk__in=jobs_before))
        if not (response.status_code == 302 and len(jobs) == 1 and jobs[0].kind == 'transcription'
                and jobs[0].state == 'queued' and jobs[0].encounter_id == encounter.pk):
            for extra in jobs:
                if extra.state == 'queued':
                    app_jobs.cancel(extra, self.world.user)     # (nothing was sent: whatever was queued is released)
            raise stages.StageStop(f'The recording did not queue exactly one transcription job (status '
                                   f'{response.status_code}: refused, over the limit shown, or more than one); nothing '
                                   'was sent')
        job = jobs[0]
        if list(Job.objects.filter(state='queued').values_list('pk', flat=True)) != [job.pk]:
            self.refuse_job(job, 'another queued job would run first')
        try:
            config = job.config
            stages.require_price(self.declaration, config, send)
            require(config.get('voice_rate_minute') == terms.rate_per_minute and not config.get('voice_rate_second'),
                    f'The transcription job is priced at another rate than the declared {terms.rate_per_minute}/minute.')
            require(config.get('deepgram_parameters') == terms.parameters(),
                    'The transcription job records other request parameters than the declared ones.')
            require(config.get('transcript_review_required') is True,
                    'The transcription job does not require the clinician\'s review before the notes change.')
            require(Decimal(str(config.get('discount_rate', '0'))) == 0, 'A discounted price is not the declared rate.')
            stored = private_path(job.input_path).read_bytes()
            require(hashlib.sha256(stored).hexdigest() == entry.sha256,
                    'The stored recording is not the allowlisted synthetic speech, byte for byte.')
            seconds = Decimal(config['recording_seconds'])
            maximum = st.transcription_maximum(seconds, terms.rate_per_minute)
            quote = app_jobs.transcription_quote(seconds, config)
            held = sum((r.amount for r in Reservation.objects.filter(job=job)), Decimal(0))
            shown = Decimal(config['charge_limit'])
            require(maximum > 0 and quote['within_standard'] and Decimal(quote['charge_limit']) == shown == held,
                    'The transcription job\'s hold, its limit and the product\'s own quote disagree.')
            bound = self.admit(maximum)
        except Exception as error:                         # (a Stop file here: refuse_job's StageStop carries it)
            self.refuse_job(job, str(error) if isinstance(error, Refused) else
                            f'the transcription job could not be checked ({type(error).__name__})')
        evidence = sq.private_evidence(self.root, number)
        case_dir = pc.private_directory(evidence / 'case')
        pc.write_new(case_dir / f'{entry.id}.wav', audio, raw=True)
        pc.write_new(case_dir / 'audio-provenance.json', entry.record())
        pc.write_new(case_dir / 'form.docx', self.forms[st.TRANSCRIPTION_FORM], raw=True)
        pc.write_new(case_dir / 'mapping.json', version.fields)
        try:
            attempt = self.attempt(send, job, maximum, bound, held, shown, {
                'form_sha256': template.sha256, 'audio_sha256': entry.sha256,
                'audio': {'id': entry.id, 'bytes': entry.bytes, 'label': entry.label},
                'template': str(template.pk), 'version': str(version.pk), 'encounter': str(encounter.pk),
                'transcription': {'provider': terms.provider, 'model': terms.model,
                                  'rate_per_minute': terms.rate_per_minute,
                                  'parameters': config['deepgram_parameters'], 'recording_seconds': str(seconds),
                                  'charge_limit': str(shown)}})
        except Refused as refused:                         # (nothing written: the job never ran — release it)
            self.refuse_job(job, str(refused))
        try:
            outcome, findings, made = self.transcribe(attempt, job, evidence, maximum)
            applied = None
            if not findings:
                applied, more = self.apply_transcript(encounter, job, evidence)
                findings += more
            if not findings:
                self.transcribed[entry.id] = {'attempt': attempt['number'], 'encounter': str(encounter.pk),
                                              'template': str(template.pk), 'version': str(version.pk),
                                              'notes_sha256': applied['notes_sha256']}
            return self.finish(send, attempt, evidence, outcome, findings, {},
                               {'audio': entry.record(), 'transcription': made, 'notes': applied})
        except BaseException as error:
            return self.interrupted(send, attempt, evidence, error)

    def transcribe(self, attempt, job, evidence, maximum):
        """run_one ONCE — the Deepgram key in the environment for exactly that call, the guard admitting exactly the
        declared request — under the deadline; then the outcome record and the contract checks."""
        from core.jobs import run_one
        from core.models import AuditEvent, ProviderReceipt, Reservation, Usage
        terms, number = self.terms, attempt['number']
        receipts_before = ProviderReceipt.objects.count()
        pc.CURRENT_ATTEMPT.update(number=number, evidence_dir=str(evidence), secret=self.secret,
                                  transcription={'parameters': terms.parameters(), 'secret': self.transcription_secret})
        timer = stages.Deadline(self.deadline)
        os.environ[st.TRANSCRIPTION_KEY_VARIABLE] = self.transcription_secret
        try:
            try:
                with timer:
                    worked = run_one()
            except stages.SendDeadline:
                worked = None
        finally:
            os.environ.pop(st.TRANSCRIPTION_KEY_VARIABLE, None)
            pc.CURRENT_ATTEMPT.clear()
        deadline = timer.fired
        job.refresh_from_db()
        captured = (evidence / 'request.json').exists()
        request = pc.read_json(evidence / 'request.json') if captured else None
        refusal = (pc.read_json(evidence / TRANSPORT_REFUSAL).get('refused')
                   if (evidence / TRANSPORT_REFUSAL).exists() else None)
        receipt = ProviderReceipt.objects.filter(job=job).first()
        usage_row = Usage.objects.filter(job=job).first()
        received = pc.received_response(evidence)
        data, parsed = sq.raw_result(job)
        if data is not None:
            pc.write_new(evidence / 'provider-result.json', data, raw=True)
        parsed = parsed if isinstance(parsed, dict) else {}
        body = (received or {}).get('body_json')
        body = body if isinstance(body, dict) else {}
        metadata = body.get('metadata') if isinstance(body.get('metadata'), dict) else {}
        duration = _decimal(metadata.get('duration'))
        cost = ((duration * Decimal(terms.rate_per_minute) / 60).quantize(COST_QUANTUM)
                if duration is not None and duration >= 0 else None)
        cls = stages.outcome_class(job, receipt, usage_row, captured) if deadline is None else (
            'not_sent' if stages.unsent(job, receipt, captured) else 'uncertain')
        audit = AuditEvent.objects.filter(target=str(job.pk), action__in=['job.failed', 'job.reconciliation',
                                                                          'job.succeeded']).order_by('-created_at').first()
        details = audit.details if audit else {}
        units = receipt.units if receipt is not None and isinstance(receipt.units, dict) else {}
        transcript, delivered = parsed.get('raw_transcript'), parsed.get('transcript')
        returned = provider_transcript(body)
        outcome = {'class': cls, 'job': str(job.pk), 'job_kind': job.kind, 'job_state': job.state,
                   'job_error': job.error, 'worker_ran': worked, 'deadline': deadline,
                   'error_class': details.get('error_class', ''), 'billing': details.get('billing', ''),
                   'request_captured': captured, 'sends_at_transport': pc.SENT.get(number, 0),
                   'transport_refusal': refusal, 'provider': terms.provider, 'model_requested': terms.model,
                   'served': {'receipt_provider': receipt.provider if receipt else None,
                              'model_info': metadata.get('model_info'), 'models': metadata.get('models')},
                   'provider_request_id': job.provider_request_id, 'response_request_id': metadata.get('request_id'),
                   'duration_seconds': str(duration) if duration is not None else None,
                   'submitted_seconds': units.get('submitted_seconds'), 'recording_seconds': job.config.get(
                       'recording_seconds'),
                   'rate_per_minute': terms.rate_per_minute,
                   'provider_cost': format(cost, 'f') if cost is not None else None,
                   'computed_cost': format(cost, 'f') if cost is not None else None,
                   'raw_result_sha256': job.result_sha256 or None,
                   'request': ({'url': request.get('url'), 'params': request.get('params'),
                                'body_sha256': request.get('body_sha256'), 'body_bytes': request.get('body_bytes')}
                               if request else None),
                   'provider_response': ({'status_code': received.get('status_code'),
                                          'request_id_header': received.get('headers', {}).get('dg-request-id'),
                                          'body_sha256': received.get('body_sha256'),
                                          'body_bytes': received.get('body_bytes')} if received else None),
                   'settlement': {'receipt_actual_cost': str(receipt.actual_cost) if receipt else None,
                                  'usage_actual_cost': str(usage_row.actual_cost) if usage_row else None,
                                  'charged_cost': str(usage_row.charged_cost) if usage_row else None,
                                  'reservations': sorted(r.state for r in Reservation.objects.filter(job=job))},
                   'recorded_at': pc.now()}
        outcome['exposure'] = format(st.attempt_exposure(attempt, outcome, None), 'f')
        self.ledger.write_outcome(number, outcome)                        # AFTER, whatever happened
        findings = []

        def contract(code, why):
            findings.append({'code': code, 'why': why})
        if deadline is not None:
            contract('uncertain_outcome', deadline + '; the outcome is unknown and it is never re-sent')
        if cls != 'completed' or job.state != 'succeeded':
            code = {'reconciliation': 'reconciliation', 'uncertain': 'uncertain_outcome'}.get(cls, 'validator_failure')
            contract(code, f'the attempt ended {cls} with the job {job.state} ({outcome["error_class"] or "no error class"})')
        if ProviderReceipt.objects.count() - receipts_before > 1 or pc.SENT.get(number, 0) > 1:
            contract('more_than_one_request', 'more than one provider request was made for the attempt')
        if receipt is not None and receipt.provider != f'{terms.provider}:{terms.model}':
            contract('wrong_served_model', f'the receipt names {receipt.provider!r}, not {terms.provider}:{terms.model}')
        if not captured:
            contract('request_not_captured', 'the outbound request was not captured'
                     + (f' (the transport guard refused it: {refusal})' if refusal else ''))
        if received is None and (data is not None or receipt is not None):
            contract('response_not_captured', 'the provider answered, but its response was not retained as received')
        if request is not None and (request.get('params') != terms.parameters()
                                    or request.get('body_sha256') != units.get('submission_sha256')
                                    or str(request.get('body_bytes')) != str(units.get('submission_bytes'))):
            contract('transcription_contract', 'the request sent is not the declared request, or not the submission the '
                                               'product prepared and recorded')
        if cost is None or cost > maximum:
            contract('settlement_mismatch', 'the provider-reported duration is unknown, or costs more than the '
                                            'attempt\'s maximum at the declared rate')
        if receipt is None or usage_row is None or not (receipt.actual_cost == usage_row.actual_cost == cost):
            contract('settlement_mismatch', 'the settled cost is not the provider-reported duration at the declared rate')
        if not (isinstance(transcript, str) and transcript.strip()):
            contract('transcript_unusable', 'the provider returned no transcript for synthetic speech')
        elif delivered != transcript:
            contract('transcript_unusable', 'the product discloses incomplete or unknown coverage of the recording')
        elif returned != transcript:
            contract('transcript_unusable', 'the stored transcript is not the one the provider returned')
        made = {'provider_request_id': job.provider_request_id, 'response_request_id': metadata.get('request_id'),
                'duration_seconds': outcome['duration_seconds'], 'submitted_seconds': outcome['submitted_seconds'],
                'provider_cost': outcome['provider_cost'], 'charged_cost': outcome['settlement']['charged_cost'],
                'model_requested': terms.model, 'model_info': metadata.get('model_info'),
                'parameters': (request or {}).get('params'),
                'transcript_sha256': hashlib.sha256(transcript.encode()).hexdigest() if isinstance(transcript, str)
                else None, 'transcript_characters': len(transcript) if isinstance(transcript, str) else None,
                'artifacts': sorted(str(p.relative_to(evidence)) for p in evidence.rglob('*') if p.is_file())}
        return outcome, findings, made

    def apply_transcript(self, encounter, job, evidence):
        """The clinician's review: the transcript the page offers, saved UNEDITED as the notes through the real notes
        view (replace: the encounter had no typed notes). Returns (record, findings)."""
        from core.models import AuditEvent
        from core.views import review_transcript
        encounter.refresh_from_db()
        page = self.world.client.get(f'/encounters/{encounter.pk}/')
        if page.status_code != 200:
            return None, [{'code': 'transcript_not_applied', 'why': f'the review page failed ({page.status_code})'}]
        shown = transcript_shown(page.content.decode(), job)
        raw, _ = review_transcript(job)
        if shown is None or shown != raw:
            return None, [{'code': 'transcript_not_applied',
                           'why': 'the page offers no review of this transcript, or shows another text than the retained '
                                  'one'}]
        response = self.world.client.post(f'/encounters/{encounter.pk}/notes/', {
            'revision': str(encounter.revision), 'transcript_job': str(job.pk), 'transcript_reviewed': 'on',
            'transcript_mode': 'replace', 'corrected_transcript': shown})
        encounter.refresh_from_db()
        applied = list(AuditEvent.objects.filter(action='transcription.applied', target=str(job.pk)))
        raw_sha256 = hashlib.sha256(raw.encode()).hexdigest()
        record = {'status_code': response.status_code, 'mode': 'replace', 'revision': encounter.revision,
                  'notes_sha256': hashlib.sha256(encounter.notes.encode()).hexdigest(),
                  'notes_characters': len(encounter.notes), 'transcript_sha256': raw_sha256,
                  'applied': [{k: v for k, v in event.details.items() if k != 'department'} for event in applied]}
        pc.write_new(evidence / 'notes-applied.json', record)
        if not (response.status_code == 302 and encounter.notes == raw and len(applied) == 1
                and applied[0].details.get('corrected') is False and applied[0].details.get('raw_sha256') == raw_sha256
                and applied[0].details.get('mode') == 'replace'):
            return record, [{'code': 'transcript_not_applied',
                             'why': 'the reviewed transcript was not saved, unedited, as the notes'}]
        return record, []

    # ── the generation on the transcript ─────────────────────────────────────────────────────────────────────────
    def transcript_generation_send(self, send):
        from core.models import Encounter, Template
        entry = st.audio_entry(send.case)
        made = self.transcribed.get(entry.id)
        if made is None:
            # (its transcription send was not made — or did not end clean — in THIS run: never sent; a later run refuses
            # such a remainder before anything is written, standing_qa.require_none_stranded)
            return None
        encounter = Encounter.objects.get(pk=made['encounter'])
        template = Template.objects.get(pk=made['template'])
        version = template.versions.get(pk=made['version'])
        require(hashlib.sha256(encounter.notes.encode()).hexdigest() == made['notes_sha256'] and not encounter.answers
                and encounter.status == 'draft', 'The encounter changed after its transcript was saved as the notes.')
        return self.generate_on(send, template, version, encounter, extra={
            'audio_sha256': entry.sha256, 'audio': {'id': entry.id, 'bytes': entry.bytes, 'label': entry.label},
            'transcription_attempt': made['attempt'], 'case': entry.id}, judge=self.judge_transcript(encounter.notes))

    def generate_on(self, send, template, version, encounter, *, extra, judge):
        """sonnet5_stages.Run.generation_send from the quote on, for an encounter that already exists (its notes are
        the saved transcript)."""
        from core import generation
        from core.jobs import cancel
        from core.models import Job, Reservation
        notes = encounter.notes
        token, revision, shown, quoted = sq.page_quote(self.world.client, encounter)
        stages.require_price(self.declaration, quoted, send)
        jobs_before = set(Job.objects.values_list('pk', flat=True))
        response = steps.request_generation(self.world.client, encounter.pk, token, revision)
        jobs = list(Job.objects.exclude(pk__in=jobs_before))
        if not (response.status_code == 302 and len(jobs) == 1 and jobs[0].kind == 'generation'
                and jobs[0].state == 'queued' and jobs[0].encounter_id == encounter.pk):
            for other in jobs:
                if other.state == 'queued':
                    cancel(other, self.world.user)
            raise stages.StageStop('Generate did not queue exactly one generation job (a batch would make more than one '
                                   'request); nothing was sent')
        job = jobs[0]
        if list(Job.objects.filter(state='queued').values_list('pk', flat=True)) != [job.pk]:
            self.refuse_job(job, 'another queued job would run first')
        try:
            stages.require_price(self.declaration, job.config, send)
            requirements = version.review_requirements
            maximum = generation.maximum_cost(encounter.notes, version.fields, job.config,
                                              context_labels=[row['label'] for row in requirements],
                                              requirements=requirements)
            held = sum((r.amount for r in Reservation.objects.filter(job=job)), Decimal(0))
            require(held == maximum * Decimal('1.5') == shown, 'The job\'s hold, its maximum and the page\'s quote disagree.')
            bound = self.admit(maximum)
        except Exception as error:                         # (a Stop file here: refuse_job's StageStop carries it)
            self.refuse_job(job, str(error) if isinstance(error, Refused) else
                            f'the generation job could not be checked ({type(error).__name__})')
        number = len(self.ledger.rows()) + 1
        evidence = sq.private_evidence(self.root, number)
        case_dir = pc.private_directory(evidence / 'case')
        original = self.forms[send.form]
        pc.write_new(case_dir / 'form.docx', original, raw=True)
        pc.write_new(case_dir / 'notes.txt', notes, raw=True)
        pc.write_new(case_dir / 'mapping.json', version.fields)
        try:
            attempt = self.attempt(send, job, maximum, bound, held, shown, {
                'form_sha256': template.sha256, 'template': str(template.pk), 'version': str(version.pk),
                'encounter': str(encounter.pk), 'notes_sha256': hashlib.sha256(notes.encode()).hexdigest(),
                'request_profile': job.config['request_profile'], **extra})
        except Refused as refused:                         # (nothing written: the job never ran — release it)
            self.refuse_job(job, str(refused))
        try:
            outcome, message, findings = self.send(attempt, job, evidence, maximum,
                                                   job.config['request_profile']['max_output_tokens'])
            encounter.refresh_from_db()
            pc.write_new(evidence / 'answers-adopted.json', {'answers': encounter.answers,
                                                            'template_review': encounter.template_review,
                                                            'status': encounter.status, 'revision': encounter.revision})
            fields, extra_record = {}, {**extra}
            if not findings:
                adopted = steps.field_outcomes(encounter.answers)
                reviewed, exported, export_findings, export_record = self.review_and_export(encounter, version, adopted,
                                                                                            original, evidence)
                findings += export_findings
                extra_record['export'] = export_record
                fields, more, details = judge(send, version, adopted, exported, original, raw=message,
                                              reviewed=reviewed, evidence=evidence)
                findings += more
                extra_record.update(details)
            return self.finish(send, attempt, evidence, outcome, findings, fields, extra_record)
        except BaseException as error:
            return self.interrupted(send, attempt, evidence, error)

    @staticmethod
    def judge_transcript(notes):
        """Each field's outcome (adopted, held, missing — usefulness, never a stop) and, for every ADOPTED answer as
        the product adopted it (the retained answers-adopted.json), its source support in the saved notes: an answer
        that cites nothing, cites what the notes do not say at its offsets, or says what none of its citations says
        is unsafe (adopted_without_source_support); an answer on a signature or initials field is unsafe
        (protected_area_answered). There is no expected answer for a transcript: nothing else is judged."""
        def judge(send, version, outcomes, exported, original, *, raw, reviewed, evidence):
            answers = pc.read_json(evidence / 'answers-adopted.json').get('answers') or {}
            names = {'supported': 'adopted', 'held': 'held', 'missing': 'missing'}
            fields, findings, support = {}, [], {}
            for field in version.fields:
                status = (outcomes.get(field['key']) or {}).get('status')
                fields[field['key']] = names.get(status, 'refused' if status else 'missing')
                answer = answers.get(field['key']) or {}
                if answer.get('status') != 'supported':
                    continue
                if field.get('kind') in ('signature', 'initials'):
                    findings.append({'code': 'protected_area_answered',
                                     'why': f'{field["label"]}: a {field["kind"]} field was answered'})
                problems = source_support_problems(answer, notes)
                support[field['key']] = {'label': field['label'], 'problems': problems,
                                         'citations': len(answer.get('evidence') or [])}
                if problems:
                    findings.append({'code': 'adopted_without_source_support',
                                     'why': f'{field["label"]}: ' + '; '.join(problems)})
            return fields, findings, {'source_support': support}
        return judge
