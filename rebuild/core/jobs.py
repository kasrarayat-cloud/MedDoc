from .retention import begin_private_file,cleanup_file
from datetime import timedelta
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import hashlib
import json
import re
import secrets
import os
import sys
import time
import httpx
from inspect import unwrap
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connection, transaction
from django.db.backends.base.base import BaseDatabaseWrapper
from django.utils import timezone
from .models import AuditEvent, Job, Encounter, Usage, ProviderReceipt, CodeSuggestion
from .security import membership,audit,private_path
from .media import (AMBIGUOUS,MISSING,RETRYABLE,SUBMISSION_BUDGET_SECONDS,TOO_LARGE,TOO_SLOW,UNAVAILABLE,UNREADABLE,NotNormalised,
                    SubmissionUnprobeable,normalise_submission,plan_normalisation,probe_submission,refusal_text,
                    scrubbed)
from .billing import reserve,settle,release,absorb_failed_job,sandbox_hold,MULTIPLIER
from . import generation, v3_mapping
from . import audio


class NotAdoptedByUser(ValidationError):
    """A successful, user-requested generation whose output the user's own state kept from adoption. It stays billable."""


class PlatformFailure(ValidationError):
    """A post-settlement failure QuillMD absorbs. Its message is a fixed, non-clinical string that is safe to display."""


class CancellationRefused(ValidationError):
    """The job is past the point where cancellation is free; the message is the one-line reason."""


class NoProviderRequest(ValidationError):
    """Raised before any provider request is made: nothing billable happened, so the held funds are released."""


class JobNoLongerRunning(ValidationError):
    """The job left 'running' while its worker was busy with it (the stale sweep, an administrator's resolution): the worker
    adopts nothing and records nothing over what the other party recorded."""


#: What the doctor reads when the provider SDK refused to build a request for want of a credential. Fixed, non-clinical.
PROVIDER_NOT_CONNECTED='Generation provider is not connected.'


#: What the doctor reads about a request the provider refused without processing it (after NOT_PROCESSED). Fixed and
#: non-clinical: the status and the provider's request id, never the provider's own words, which can quote the request.
PROVIDER_REFUSED=('The AI provider refused this request without processing it (HTTP {status}, request {request}). Nothing '
                  'was charged and the held funds were released.')
#: The audit action that records a definite provider refusal, with the provider's request id.
PROVIDER_REFUSED_ACTION='provider.refused'
#: A provider request id (or error type) as the provider writes it; anything else is recorded as ''. Bounded so every
#: message carrying it fits its 250-character column (a live id is 28 characters).
REQUEST_ID=re.compile(r'[A-Za-z0-9_-]{1,64}')


class ProviderRefusedRequest(ValidationError):
    """The provider DEFINITELY refused the request without processing it (`provider_refused`): an HTTP 400
    invalid_request_error or an HTTP 413, for the request's only attempt. Nothing was processed, so nothing is billed
    (the provider bills processed tokens; a refused request has none) and the held funds are released."""
    def __init__(self,refusal):
        self.refusal=refusal
        super().__init__(PROVIDER_REFUSED.format(status=refusal['status'],
                                                 request=refusal['request_id'] or 'without a request id'))


def sdk_code(module,owner,name):
    """The code object of a LOADED provider SDK's own method, or None. Nothing is imported: an SDK this process never
    loaded cannot be in a traceback, and an exception handler must not pay for, or fail on, an import."""
    try: return getattr(getattr(sys.modules[module],owner),name).__code__
    except Exception: return None


def never_transmitted(error):
    """True only when a provider SDK refused before its request existed, so provably nothing left (MONEY-2).

    The proof is structural, never a message match: the innermost frame is the SDK's own refusal code. Two shapes:
    - A TypeError from the SDK's own header validation while BUILDING the request, inside `_build_request`, before
      `_client.send`, on the only attempt (max_retries=0). anthropic 0.125.0 resolves its credential there, not when the
      client is constructed (no api_key, auth_token or credentials provider); openai 2.54.0 does the same for a client
      constructed with only OPENAI_ADMIN_KEY, which satisfies its constructor but gives the Responses request no bearer
      credential (R1-MONEY2-OPENAI).
    - The base OpenAIError itself (never a subclass: APIConnectionError and every other transport or status error is a
      subclass) raised by openai's own client constructor, called directly from generation.generate: with no credential at
      all no client exists, so nothing can have been sent. That construction sits in a before_the_provider block that is
      inactive for a legacy form, so it read as an unknown outcome and the hold was kept (R1-MONEY2-OPENAI).
    Every send sits outside its pre-provider guard, and the send sites stay exactly as the cost scanner binds them; the
    failure is classified where it lands. Anything else, including a later SDK that moves either check, the same class
    and message raised by a send, or a constructor reached from anywhere but generate(), stays an unknown outcome with its
    hold kept: the conservative status quo, never a guess.
    """
    trace=error.__traceback__
    if trace is None: return False
    frames=[]
    while trace is not None: frames.append(trace.tb_frame.f_code); trace=trace.tb_next
    # Identity, never equality: code objects compare equal by content, and only the SDK's own object is proof. A missing
    # SDK or method gives None, which is never a frame's code, so it proves nothing.
    if type(error) is TypeError:
        return any(frames[-1] is code for code in (sdk_code('anthropic._client','Anthropic','_validate_headers'),
                                                   sdk_code('openai._client','OpenAI','_validate_headers')))
    OpenAIError=getattr(sys.modules.get('openai._exceptions'),'OpenAIError',None)
    if OpenAIError is None or type(error) is not OpenAIError: return False
    return (len(frames)>1 and frames[-1] is sdk_code('openai._client','OpenAI','__init__')
            and frames[-2] is getattr(generation.generate,'__code__',None))


def provider_refused(error):
    """{'status', 'request_id', 'error_type'} when `error` PROVES the provider refused the request without processing
    it; otherwise None (2026-10-02: campaign 3's 400 'Schema is too complex for compilation' was held as an unknown
    outcome with its hold kept).

    The proof is structural, like `never_transmitted`, never a message match. All of:
    - the class IS the loaded anthropic SDK's own BadRequestError (whose body's error type is invalid_request_error) or
      RequestTooLargeError - identity, never a subclass or a name;
    - it carries the httpx.Response the SDK built it from, whose status is that class's status, and whose request is the
      error's own request;
    - the innermost frame is the SDK's own request loop (SyncAPIClient.request), where it raises a status error for a
      response it received - so the provider answered, and nothing else raised it;
    - the request was the Messages call itself (POST /v1/messages), never another endpoint;
    - that request was the FIRST and only attempt: the SDK's own x-stainless-retry-count header is '0'. Every QuillMD
      client is built with max_retries=0; a 400 answering a retry would prove nothing about the attempt before it.
    A 400 or 413 is the provider's refusal to process the request at all: no tokens are processed and nothing is billed.
    Every other outcome - 401, 403, 404, 408, 409, 422, 429, 5xx, 529, a timeout, a dropped connection, any other
    provider SDK, the same class raised anywhere else - stays an unknown outcome with its hold kept: the conservative
    status quo, which an administrator's reconciliation resolves from provider evidence."""
    module=sys.modules.get('anthropic._exceptions')
    if module is None: return None
    statuses={getattr(module,'BadRequestError',None):400,getattr(module,'RequestTooLargeError',None):413}
    status=statuses.get(type(error))
    if status is None: return None
    response=getattr(error,'response',None)
    try: request=response.request if isinstance(response,httpx.Response) else None
    except RuntimeError: request=None
    if (request is None or response.status_code!=status or getattr(error,'status_code',None)!=status
            or getattr(error,'request',None) is not request
            or request.headers.get('x-stainless-retry-count')!='0'): return None
    # Only the one call a job makes: POST /v1/messages (refutation of 9c2ffa92, T4 - a refused count_tokens, models or
    # batches call must never release the hold of a messages request the provider did process).
    if request.method!='POST' or request.url.path!='/v1/messages': return None
    error_type=getattr(error,'type',None)
    if status==400 and error_type!='invalid_request_error': return None
    trace=error.__traceback__
    if trace is None: return None
    while trace.tb_next is not None: trace=trace.tb_next
    if trace.tb_frame.f_code is not sdk_code('anthropic._base_client','SyncAPIClient','request'): return None
    request_id=getattr(error,'request_id',None)
    return {'status':status,'request_id':request_id if isinstance(request_id,str) and REQUEST_ID.fullmatch(request_id) else '',
            'error_type':error_type if isinstance(error_type,str) and REQUEST_ID.fullmatch(error_type) else ''}


def record_refusal(job,exc,action):
    """Inside the caller's transaction, under the job's row lock: the provider's request id on the job and the audit
    record of the refusal (status, error type, request id; never the provider's message)."""
    refusal=exc.refusal
    job.provider=f"anthropic:{job.config.get('model','')}"[:60];job.provider_request_id=refusal['request_id']
    audit(job.user,PROVIDER_REFUSED_ACTION,job.pk,department=job.department,kind=job.kind,status=refusal['status'],
          error_type=refusal['error_type'],request_id=refusal['request_id'],job_action=action)
    return ['provider','provider_request_id']


class RecordingOverLimit(ValidationError):
    """The recording's charge limit exceeds the displayed limit. Nothing was sent; the quote says what a shorter segment or a
    higher, explicitly approved limit would be."""
    def __init__(self,message,quote):
        super().__init__(message)
        self.quote=quote


# Recording charge limit (docs/rebuild/cost-definition.md, "Recording charge limit"). The quote adds a margin for the provider
# measuring a slightly longer duration than we do; the limit is rounded UP to a cent and is binding: the charge never exceeds it.
DURATION_MARGIN_FACTOR=Decimal('1.02')
DURATION_MARGIN_SECONDS=Decimal('2')
# Our measurement is what a decoder plays (core/audio.py); a provider that reports more than this much less audio did not
# process all of it, and the transcript says so.
COVERAGE_TOLERANCE_SECONDS=Decimal('2')
NOTE_LIMIT=50000
# Usable output the notes cannot take is delivered for download and stays charged within the approved limit: never discarded,
# never free (an absorbed failure never hands over usable output).
OVERFLOW_ERROR='The transcript was not added because the notes would exceed the 50,000-character limit; download it from the document record. Its recorded usage stays billed.'
# An over-limit upload is kept for the doctor's decision; the approval is valid 30 minutes, so after 40 an unapproved upload
# can never be sent and is removed.
NOTES_FULL='The notes are at the 50,000-character limit, so no transcript could be added. Shorten the notes first. Nothing was sent for transcription.'
#: A generation quote signed under a price or request that is no longer configured: refused before any hold or job.
QUOTE_PRICE_CHANGED=('The prices or the language model changed after this page loaded, so this request was not made. Nothing was '
                     'sent or charged. Review the new maximum charge on this page, then generate again.')
#: The same refusal when the deployment moved between live and synthetic (fixture) processing after the page was quoted.
QUOTE_MODE_CHANGED=('QuillMD was switched between live and synthetic processing after this page loaded, so this request was not '
                    'made. Nothing was sent or charged. Review this page again, then generate again.')
ABANDONED_UPLOAD_SECONDS=2400
UPLOAD_NAME=re.compile(r'audio/[a-f0-9]{48}\.(wav|webm|mp3|m4a)')
# The normalised artifact is TRANSIENT: written under the same protected storage as the upload, at 0600, submitted, and
# removed in a finally. It is never a second copy of a recording sitting around — what survives is its sha256, byte count
# and measured duration on the job, which is what ties the upload, the consent, the provider request and the billing row
# together. A crash between writing and removing leaves a stray, so the reaper sweeps this directory too.
# The suffixes core/media.py CONTAINERS can actually produce. No flac: measure_bounds refuses FLAC input, so no flac
# artifact can exist — and a pattern matching one it can never see is a reaper arm nothing proves.
SUBMISSION_NAME=re.compile(r'submissions/[a-f0-9]{48}\.(wav|webm|mp3|m4a)')
SUBMISSION_LIMIT_BYTES=15*1024*1024
AMBIGUOUS_STREAMS=('This recording holds {count} separate audio tracks, so which one would be transcribed is not decided by '
                   'the file. Export it as a single audio track and upload that. Nothing was sent for transcription.')
NO_AUDIO_TRACK=('No audio track could be found in this recording, so there is nothing to transcribe. Export it again as an '
                'audio file and upload that. Nothing was sent for transcription.')
# The WAV sibling of the multiple-audio-tracks refusal. Same shape of problem, same place, same cost: nothing sent.
AMBIGUOUS_STRUCTURE=('This recording holds {reason}, so which audio a transcriber would process is not decided by the file. '
                     'Export it again as a single continuous audio track and upload that. Nothing was sent for '
                     'transcription.')


def notes_full(notes):
    """No transcript of any length fits: adoption needs the notes, a blank line and at least one character."""
    return len(notes)+2+1>NOTE_LIMIT


def seconds_text(seconds):
    seconds=int(Decimal(seconds).to_integral_value(rounding=ROUND_CEILING))
    return f'{seconds//60}:{seconds%60:02d}'


def voice_rate_per_minute(config):
    """The one transcription rate rule, read by both the quote and settlement: the per-minute rate when set, else per-second x 60."""
    if config.get('voice_rate_minute'): return Decimal(config['voice_rate_minute'])
    if config.get('voice_rate_second'): return Decimal(config['voice_rate_second'])*60
    raise ValidationError('Transcription usage rates have not been configured.')


def standard_voice_limit(voice_max_cost):
    """The displayed per-recording limit: the configured maximum cost x 1.5, rounded DOWN to a cent so the amount shown is never
    above the amount enforced."""
    return (Decimal(voice_max_cost)*MULTIPLIER).quantize(Decimal('0.01'),rounding=ROUND_FLOOR)


def max_recording_seconds():
    return Decimal(os.getenv('QUILLMD_VOICE_MAX_MINUTES','60'))*60


def transcription_quote(seconds,config):
    """The binding charge limit for a recording of this measured length, and how it compares with the displayed standard limit."""
    rate=voice_rate_per_minute(config)
    if not rate.is_finite() or rate<0: raise ValidationError('Transcription usage rates are invalid.')
    discount=generation.discount_rate(config)
    billed=Decimal(seconds)*DURATION_MARGIN_FACTOR+DURATION_MARGIN_SECONDS
    # The same formula transcribe() prices the provider's duration with, applied to the measured length plus the margin.
    cost=generation.discounted_cost((billed*rate/60).quantize(Decimal('0.0000000001')),discount)
    # Rounded UP to a cent; a zero-rate (simulated) configuration costs nothing and holds nothing.
    limit=(cost*MULTIPLIER*100).to_integral_value(rounding=ROUND_CEILING)/100 if cost>0 else Decimal(0)
    standard=standard_voice_limit(config['voice_max_cost'])
    per_second=rate/60*(1-discount)*MULTIPLIER
    fits=((standard/per_second)-DURATION_MARGIN_SECONDS)/DURATION_MARGIN_FACTOR if per_second>0 else max_recording_seconds()
    fits=max(Decimal(0),min(fits,max_recording_seconds())).to_integral_value(rounding=ROUND_FLOOR)
    return {'seconds':str(Decimal(seconds)),'charge_limit':str(limit),'standard_limit':str(standard),'within_standard':limit<=standard,
            'fits_seconds':str(fits),'too_long':Decimal(seconds)>max_recording_seconds(),'pricing_version':config.get('pricing_version','')}


# Billing boundary (docs/rebuild/cost-definition.md, "Billing boundary"): a job.error prefix is the billing classification.
NOT_ADOPTED='not_adopted: '
PLATFORM_FAILURE='platform_failure: '
NOT_PROCESSED='Not processed: '
CANCELLED_ERROR='cancelled: before any provider request'
CANCEL_REFUSALS={'running':'Processing already started; the outcome will be billed by result.',
    'succeeded':'This request already completed; its successful generation remains charged.',
    'failed':'This request already ended; nothing is queued to cancel.',
    'reconciliation':'This request is held for reconciliation; an administrator resolves it.',
    'cancelled':'This request was already cancelled.'}


def ended_key(job,label):
    """Free the request key of a job that ended without success so a fresh request for the same revision is accepted; the ended
    row keeps its history under a key only it can hold. Longest key today is transcription (115 chars) + 43 = 158 of 160.

    ⚠️ Once only. A key that already ends with this job's own id was ended before (a job an administrator resolved, reopened
    by a late provider receipt and resolved again, core.jobs.hold_late_receipt): suffixing it twice would pass 160
    characters and fail the resolution. A key is built before its job exists (enqueue), so a live key never carries its own
    job's id."""
    if job.request_key.endswith(':'+job.pk.hex): return job.request_key
    return f'{job.request_key}:{label}:{job.pk.hex}'


def public_error(job):
    """What the doctor reads about a job: the billing classification in words, never the internal prefix."""
    error=job.error or ''
    if error.startswith(NOT_ADOPTED): return error[len(NOT_ADOPTED):]
    if error.startswith(PLATFORM_FAILURE): return error[len(PLATFORM_FAILURE):]+' This was a platform failure; it is not charged to you.'
    if error==CANCELLED_ERROR: return 'Cancelled before any provider request; nothing was charged.'
    return error


def billable_outcome(job):
    """A job whose provider usage stands charged: a success, or a success the user's own state kept from adoption."""
    return job.state=='succeeded' or (job.state=='failed' and (job.error or '').startswith(NOT_ADOPTED))


def deliverable(job):
    """Provider output the requester may download: exactly the charged outcomes, including a transcript the notes could not take.
    An absorbed failure is never delivered. Department scoping still decides who can see the job at all."""
    # A child artifact is evidence for a complete form, never a standalone draft.
    return job.kind!='generation_part' and billable_outcome(job)


def may_cancel(job,user):
    """Same rule jobs.cancel enforces: the requester, or an owner or clinician of the department."""
    if job.state!='queued': return False
    if job.kind=='generation_part':
        try: membership(user,job.department,roles=None if job.user_id==user.pk else ['owner','clinician'])
        except PermissionDenied:return False
        return (job.generation_part.batch.state=='queued'
                and not job.generation_part.batch.events.filter(kind='send_intent').exists()
                and job.generation_part.ordinal==1)
    try: membership(user,job.department,roles=None if job.user_id==user.pk else ['owner','clinician'])
    except PermissionDenied: return False
    return True


def failure_reason(exc):
    """Display text for a post-settlement failure. Only QuillMD's own fixed messages are shown; any other exception is named by class,
    because provider or validation messages can quote the source text."""
    if isinstance(exc,(NotAdoptedByUser,PlatformFailure,NoProviderRequest,ProviderRefusedRequest)): return '; '.join(exc.messages)
    return f'Output could not be adopted ({type(exc).__name__}); review required.'


def recording_charge_limit(e,input_path,config,approved_limit=None):
    """Measure the recording and fix its binding charge limit BEFORE any provider request. Refuses (nothing sent) when the
    length cannot be measured, the recording is too long, or its limit exceeds the displayed standard limit without an
    explicitly approved higher one."""
    raw=private_path(input_path).read_bytes()
    bounds=audio.measure_bounds(raw)
    seconds=bounds.measured
    quote=transcription_quote(seconds,config)
    if quote['too_long']:
        raise ValidationError(f'This recording is {seconds_text(seconds)} long; the longest recording accepted is {seconds_text(max_recording_seconds())}. '
                              'Upload a shorter segment. Nothing was sent for transcription.')
    limit=Decimal(quote['charge_limit'])
    if approved_limit is None:
        if not quote['within_standard']:
            raise RecordingOverLimit(f'This recording is {seconds_text(seconds)} long. Transcribing it could cost up to ${limit}, above the '
                                     f'${Decimal(quote["standard_limit"]).quantize(Decimal("0.01"))} limit shown. Nothing was sent.',quote)
    else:
        approved_limit=Decimal(approved_limit)
        if limit>approved_limit:
            raise RecordingOverLimit(f'This recording needs a limit of ${limit}, above the ${approved_limit} you approved. Nothing was sent.',quote)
        limit=approved_limit
    return bounds,limit,quote


@transaction.atomic
def enqueue(encounter,user,kind='generation',input_path='',config=None,approved_limit=None,expected_revision=None):
    from . import generation_batch, batch_jobs
    from .disposition_execution import lock_available
    # Both routes lock the document first, the batch route included (batch_jobs.enqueue re-locks the same row in
    # this transaction): a document disposed of since the caller read it is a refusal, never DoesNotExist (RF-3).
    e=lock_available(encounter.pk)
    # ⚠️ D10's LAYOUT GATE IS ADMISSION'S, AND IT IS HERE, never in v3_mapping.generation_refusal: that check also runs
    # before every batch part and at adoption, after money was spent, where a verifier outage discarded paid parts
    # (refutation L1:F1). It is measured before anything is held, and raised only for a request that would take a NEW
    # hold — after each route's own replay answer, so a re-posted admitted request is still answered as that request.
    # It is fill's own answer (v3_mapping.export_needs_verifier: the export path, probed), never the inspection's count,
    # which also counts tab-column rows fill withdraws and exports without any verifier (refutation FV:F1).
    if kind=='generation' and generation_batch.needed(encounter.template_version.fields, encounter.notes,
                                                      config or generation.configuration(encounter.template_version.fields)):
        admission=v3_mapping.admission_refusals(e.template_version)
        job=batch_jobs.enqueue(encounter,user,config or generation.configuration(encounter.template_version.fields),expected_revision)
        # A NEW batch admission raising here is undone whole by this transaction — batch, parts, holds, events, audit —
        # exactly as the batch's own refusals after reserve() are; nothing held or sent survives it.
        if not getattr(job,'reused',False) and (refusal:=admission[0] or admission[1]):
            raise ValidationError(refusal)
        return job
    membership(user,e.department)
    if e.status=='finalized': raise ValidationError('Finalized documents are immutable.')
    if expected_revision is not None and e.revision!=expected_revision:
        raise ValidationError('Source notes changed after the quote. Reload and review the current notes before submitting.')
    layout_refusal=''
    if kind=='generation':
        refusal,layout_refusal=v3_mapping.admission_refusals(e.template_version)
        if refusal: raise ValidationError(refusal)
    if kind=='generation' and not e.notes.strip():
        raise ValidationError('Type and save source notes, or review and add a transcript, before generating answers.')
    fingerprint=hashlib.sha256(private_path(input_path).read_bytes()).hexdigest() if kind=='transcription' else str(e.revision)
    key=f'{kind}:{e.pk}:{fingerprint}'
    old=Job.objects.filter(request_key=key).first()
    # Idempotency is the point: the same revision, or the same audio bytes, must never buy a
    # second provider call. But the CALLER has to be able to tell, because a generation does not
    # renumber the revision, so a stale page's re-POST lands here holding a key a SUCCEEDED job
    # still owns. Announcing that as "queued" tells the doctor a request was made that was not,
    # and invites them to wait for answers that will never change. Not persisted; a per-instance
    # fact about THIS call, never about the row.
    if old:
        old.reused=True
        return old
    if batch_jobs.pending(e): raise ValidationError('This encounter already has a pending job.')
    # ⚠️ A SIGNED QUOTE IS A PRICE THE DOCTOR SAW, NOT A LICENCE TO SEND A REQUEST THE OPERATOR HAS SINCE WITHDRAWN. The
    # quote carries the whole configuration() it was signed under, and for its 600 s it used to be enqueued as it stood:
    # measured, a page loaded under claude-sonnet-5 and clicked after a rollback, restart and drain queued and SENT a
    # claude-sonnet-5 request (profile claude-sonnet-5-v1, 8975b158…) while configuration_status said legacy. pricing_version
    # hashes the model, the rates, the discount and the request profile, so any of them moving refuses the quote here —
    # before Job.objects.create and before any hold — and the page the doctor is sent back to signs a fresh one.
    # ⚠️ AND THE MODE, WHICH pricing_version DOES NOT HASH. Measured: a page quoted live and clicked after the deployment was
    # switched to fixture queued a LIVE job — held, sent, charged — while the console said no request is sent; the reverse
    # queued a fixture job whose synthetic answers entered a live deployment. Both directions are refused here.
    if config is not None and kind=='generation':
        current=generation.configuration(e.template_version.fields)
        if config.get('mode')!=current['mode']: raise ValidationError(QUOTE_MODE_CHANGED)
        if config.get('pricing_version')!=current['pricing_version']: raise ValidationError(QUOTE_PRICE_CHANGED)
    config=dict(config or generation.configuration(e.template_version.fields))
    if kind=='generation' and (refusal:=generation.narrative_refusal(e.template_version.fields,config)):
        raise ValidationError(refusal)
    # Role suggestions are decided HERE, from the setting now, never carried from a quote (refutation I-1).
    if kind=='generation':config=generation.admitted_with_role_suggestions(config,e.template_version)
    if kind=='transcription':
        if not (config['voice_rate_minute'] or config['voice_rate_second']): raise ValidationError('Transcription usage rates have not been configured.')
        # Exact, not an estimate: notes with no room for even one character can take no transcript, so nothing is sent or charged.
        if notes_full(e.notes): raise ValidationError(NOTES_FULL)
        bounds,charge_limit,quote=recording_charge_limit(e,input_path,config,approved_limit)
        # ⚠️ REFUSED BEFORE Job.objects.create AND BEFORE reserve(), exactly like the multiple-audio-tracks case, and
        # for the same reason: the file does not decide what a decoder would play. Measured on a WAV whose samples are
        # split across two `data` chunks — this parser's floor says 1 s, its ceiling says 10 s, and ffmpeg plays
        # whichever chunk comes LAST (9 s one way round, 1 s the other). Three answers, one file, and no basis for any
        # statement about what was transcribed. The signal is `core/audio.py`'s own walk, not a second parser.
        if bounds.ambiguity: raise ValidationError(AMBIGUOUS_STRUCTURE.format(reason=bounds.ambiguity))
        # Two lengths: the conservative one the limit was priced from, and the one this recording certainly holds. Only the
        # confirmed length may support a statement that part of the recording was not transcribed.
        # THREE SEPARATE NUMBERS, because they answer three different questions and conflating any two produces a claim
        # nobody can support:
        #   recording_seconds           — the CONSERVATIVE CEILING the customer charge is held against. Priced, not promised.
        #   recording_seconds_confirmed — the handwritten FLOOR over decoder ambiguity. Kept for continuity, and NOT evidence
        #                                 about what the provider received: measured, a 1 s + 9 s WAV submits 9 s and floors
        #                                 at 1 s, so judging completeness by the floor hides real truncation.
        #   submitted_seconds           — what ffprobe, with explicit stream selection, says is in the payload actually POSTed
        #                                 to the provider. A completeness statement may rest on this and on nothing else.
        config.update(recording_seconds=str(bounds.measured),recording_seconds_confirmed=str(bounds.confirmed),
                      charge_limit=str(charge_limit),limit_basis='approved' if approved_limit is not None else 'standard')
        # New jobs only: the provider request parameters, recorded with the job so the worker sends what was queued.
        config.update(deepgram_parameters=deepgram_parameters())
        # REFUSED HERE, BEFORE Job.objects.create AND BEFORE reserve(): a recording whose payload does not decide which
        # audio a decoder would process never reaches the provider, is never held against, and is never charged for. The
        # provider picking one silently is exactly what this prevents — measured: ffmpeg given a two-stream Matroska and no
        # explicit map emits one stream and reports nothing.
        config.update(describe_submission(input_path,ceiling_seconds=bounds.measured))
        # ⚠️ A POSITIVE TEST ON A STRING THE FAILURE PATH SETS TO EMPTY IS A GUARD THAT FAILS OPEN, and this one did.
        # Every probe failure produced submission_streams='', ''.isdigit() is False, so the refusal was skipped —
        # strongest on a two-track file and ABSENT on a sixty-five-track one, because an implausible count used to
        # raise rather than be reported. media.py now returns the count; this reads it, and anything above one refuses.
        streams=config.get('submission_streams') or ''
        if streams.isdigit() and int(streams)>1: raise ValidationError(AMBIGUOUS_STREAMS.format(count=int(streams)))
        if streams.isdigit() and int(streams)==0: raise ValidationError(NO_AUDIO_TRACK)
    # The last refusal before the job and its hold: every earlier answer (the replay above included) stands as before.
    if layout_refusal: raise ValidationError(layout_refusal)
    job=Job.objects.create(encounter=e,user=user,kind=kind,revision=e.revision,request_key=key,input_path=input_path,config=config)
    job.reused=False
    if kind=='transcription':
        reserve(job,charge_limit=charge_limit)
    else:
        max_cost=generation.maximum_cost(e.notes,e.template_version.fields,job.config,context_labels=[row['label'] for row in e.template_version.review_requirements],
                                         requirements=e.template_version.review_requirements)
        reserve(job,max_cost)
        charge_limit=max_cost*MULTIPLIER
    audit(user,'job.queued',job.pk,department=e.department,kind=kind,charge_limit=str(charge_limit))
    return job

def describe_submission(input_path,ceiling_seconds=None):
    """What ffprobe says is in the payload that will be submitted. Unknown is recorded as unknown.

    The ceiling is passed in so the probe can refuse a declared duration the bytes cannot support: a
    container header is not a measurement, and an inflated one would otherwise accuse a complete
    transcription of losing an hour of audio.
    """
    try:
        submission=probe_submission(private_path(input_path),ceiling_seconds=ceiling_seconds)
    except (SubmissionUnprobeable,OSError,ValueError) as error:
        return {'submitted_seconds':'','submission_status':'unprobeable','submission_streams':'',
                'submission_detail':str(error)[:200]}
    return {'submitted_seconds':'' if submission.selected_seconds is None else str(submission.selected_seconds),
            'submission_status':'ambiguous' if submission.ambiguous else 'determined',
            'submission_detail':'; '.join(submission.reasons)[:400],
            'submission_streams':str(submission.audio_streams),
            'submission_container':submission.container[:60]}


def coverage_note(job,units):
    """State what is known about coverage, and nothing more.

    A MATCHING DURATION IS NOT PROOF THAT EVERY SPOKEN WORD WAS TRANSCRIBED. It shows the provider processed about as much
    audio as was submitted. It says nothing about words inside that audio the model missed, mis-heard or dropped. The silent
    case below is therefore the ABSENCE OF A CLAIM, not a statement of completeness, and no caller may render it as one.

    Three outcomes, and the difference between the last two is the whole point:
      · INCOMPLETE — the provider processed materially less than was SUBMITTED. Disclosed with both numbers.
      · UNKNOWN    — the payload does not determine what a decoder would process (several audio streams), or it could not be
                     probed at all. Disclosed as unknown rather than resolved in our favour.
      · SHORT      — the payload holds materially less audio than the recording we measured and priced. Both numbers are
                     stated and no reason is offered, because the reason is not knowable from the file.
      · no claim   — the durations agree. Nothing is asserted.
    """
    try:
        config=job.config or {}
        units=units or {}
        # THE MEASUREMENT OF RECORD IS THE ONE TAKEN OF THE ARTIFACT THAT WAS ACTUALLY POSTED, and it arrives in `units`
        # beside the provider's own number. job.config carries the measurement of the UPLOAD, taken at enqueue before the
        # remux existed; it is the fallback for a job whose submission was never described, and it is never preferred over
        # a measurement of the bytes that went out.
        source=units if 'submission_status' in units else config
        submitted=source.get('submitted_seconds') or ''
        status=source.get('submission_status') or ''
        priced=Decimal(config.get('recording_seconds') or '0')
        processed=Decimal(units.get('duration_seconds') or '0')
    except Exception:
        return ''
    detail=(source.get('submission_detail') or '').strip()
    if status!='determined' or not submitted:
        # This arm used to compare against the handwritten FLOOR, a lower bound over decoder ambiguity. On a recording that
        # submits 9 s and floors at 1 s, that reported 'complete' while eight seconds were missing.
        if priced<=COVERAGE_TOLERANCE_SECONDS: return ''
        because=(' (%s)'%detail) if detail else ''
        return (f'\n[Transcription coverage UNKNOWN: the provider reported {seconds_text(processed)}, and this recording may '
                f'hold up to {seconds_text(priced)}. The submitted audio could not be determined{because}, so no statement is '
                f'made about how much of it was transcribed.]')
    try:
        submitted_seconds=Decimal(submitted)
    except Exception:
        return ''
    notes=''
    # ⚠️ THE FOURTH OUTCOME, AND ITS ABSENCE WAS A STRUCTURAL SILENCE, NOT AN OVERSIGHT IN ONE BRANCH. Every arm above
    # compares the PROVIDER against what we submitted. Nothing asked whether what we submitted is materially less than
    # the recording we measured and priced — so any loss BEFORE the request was invisible by construction, and the
    # transcript said nothing at all. Demonstrated on an M4A carrying a trimming edit list: the file's mdat holds
    # 10.4 s, the priced ceiling is 10.027 s, 2.0 s was submitted, the provider returned 2.0 s, and the note was empty.
    # This says nothing about WHY the payload is shorter — it may be a trimming edit list, a second data chunk no
    # decoder reaches, or bytes after the audio that were never audio at all. Distinguishing those from the file alone
    # is not something this code can do, so it states the two measurements and makes no claim about the difference.
    if priced-submitted_seconds>COVERAGE_TOLERANCE_SECONDS:
        notes+=(f'\n[Only {seconds_text(submitted_seconds)} of this recording could be read as audio, although the file '
                f'could hold up to {seconds_text(priced)}. That {seconds_text(submitted_seconds)} is what was sent for '
                f'transcription; nothing is claimed about the rest.]')
    if processed<submitted_seconds-COVERAGE_TOLERANCE_SECONDS:
        notes+=(f'\n[Transcription incomplete: the provider processed {seconds_text(processed)} of the '
                f'{seconds_text(submitted_seconds)} of audio submitted; {seconds_text(submitted_seconds-processed)} was not '
                f'transcribed.]')
    # An empty string here means the durations agree AND the payload holds what the recording measured. No claim is made,
    # and none may be inferred from the silence.
    return notes


def refuse(kind,detail,job=None):
    """Stop before the provider: the doctor sees a fixed sentence, the audit row keeps the scrubbed technical reason.

    ⚠️ THE TWO ARE DELIBERATELY DIFFERENT STRINGS. `failure_reason()` renders a NoProviderRequest's message verbatim
    into the doctor's error and into `audit_billing`'s export, and ffmpeg quotes the path it was handed — which is
    inside protected storage. So nothing from a subprocess reaches a user or a ledger; the detail is recorded once,
    scrubbed, on an audit row.
    """
    # ⚠️ THE AUDIT WRITE MUST NOT BE ABLE TO STOP THE REFUSAL, and in the first version it could. refuse() added a
    # SELECT and an INSERT to EVERY failure path — paths that previously touched no database at all — and this INSERT
    # lands right after up to 45 s of subprocess work, which is exactly when the worker's single long-held connection
    # is most likely to be stale. If it raised, the exception escaping was no longer a NoProviderRequest, so run_one
    # classified the job `reconciliation` rather than `unsent`: the hold was never released, mark_stale could not help
    # (the job is not `running`), `request_key` was never freed so the encounter refused every later recording, and
    # audit_billing's hold policy only inspects succeeded/failed/cancelled jobs — so `all_checks_pass` stayed True
    # over stranded funds.
    #
    # Losing this row costs one line of operator evidence. Losing the release costs a doctor their balance.
    try:
        audit(job.user if job else None,'voice.submission_refused',job.pk if job else '',
              department=job.department if job else None,
              kind=kind,retryable=kind in RETRYABLE,detail=scrubbed(detail))
    except Exception:
        pass
    return NoProviderRequest(refusal_text(kind))


#: A job whose held funds or payer's paid balance hold sandbox money in real data mode (billing.sandbox_hold): refused
#: before any provider request.
SANDBOX_HOLD_REFUSED='The paid balance for this request holds sandbox (test) payments, which real data mode never spends. Contact support.'


def refuse_sandbox_hold(job):
    """The worker's stop for a hold real data mode refuses to spend (billing.sandbox_hold): a NoProviderRequest, so run_one
    marks the job not processed, charges nothing and releases the hold. The audit write cannot stop the refusal (see
    refuse())."""
    try:
        audit(job.user,'usage.sandbox_hold_refused',job.pk,department=job.department,kind=job.kind)
    except Exception:
        pass
    return NoProviderRequest(SANDBOX_HOLD_REFUSED)


def prepare_submission(job):
    """Produce the exact bytes that will be POSTed, describe them durably, and return them with the artifact to reap.

    Normalisation is REQUIRED AND VERIFIED. A lossless remux is produced, measured by the same instrument that measured
    the source, and DECODED to confirm it holds audio a transcriber can read. If any of that cannot be completed —
    ffmpeg absent, a codec with no lossless remux, a timeout, a nonzero exit, an output too large, a measurement that
    disagrees, a decode that reports anything — this raises and NOTHING IS SENT.

    ⚠️ IT USED TO FALL BACK TO THE ORIGINAL ON EVERY ONE OF THOSE, and that is the behaviour being removed. The
    fallback read as conservative and was the opposite: the provider received bytes we had not measured and decided
    for itself what to decode, the doctor was charged for the result, and the only trace that processing had stopped
    running was a detail string on a usage row. A recording a doctor made is still never re-encoded into something
    smaller — the answer to 'we cannot prepare this' is now to say so and charge nothing.

    WHERE THE DESCRIPTION GOES, and it is not the obvious place. `Job.config` is write-once: a database trigger
    (`quillmd_job_financial_guard`, migration 0008) refuses ANY update to it, because it carries the authorized pricing and
    payer. That guard is right and is not weakened here. So what was submitted is recorded in the two places that are
    designed to accumulate — an audit row, and the `units` of the provider receipt and billing row, which is also what ties
    the artifact to the provider request and the charge.
    """
    try: source=private_path(job.input_path)
    except (OSError,ValueError): raise refuse(MISSING,'the upload path is not valid',job)
    # ⚠️ CHECKED BEFORE THE PROBE, because otherwise ffprobe meets the missing file first and its refusal reads as
    # 'this recording could not be read as audio — re-export it'. The upload is GONE FROM STORAGE: that is the
    # platform's failure, and sending a doctor to re-export a file we lost points them at the one place the problem
    # certainly is not. An existing regression test pins this message, and it was RED until this line existed.
    if not source.is_file(): raise refuse(MISSING,'the stored upload is missing',job)
    config=job.config or {}
    # The two hand measurements enqueue already made of this upload: the length it certainly holds, and the most it
    # could hold. They bracket the artifact the remux produces; neither is re-derived here, so there is one measurement
    # of this recording and not two that can disagree.
    try: ceiling=Decimal(config.get('recording_seconds') or '0')
    except Exception: ceiling=None
    if ceiling is not None and ceiling<=0: ceiling=None
    try: floor=Decimal(config.get('recording_seconds_confirmed') or '0')
    except Exception: floor=None
    if floor is not None and floor<=0: floor=None
    # ⚠️ ONE OWNER FOR THE ARTIFACT, FROM THE MOMENT THE FILE EXISTS TO THE MOMENT IT IS HANDED BACK. The first version
    # unlinked at three individual failure points and missed the others: an audit() write failing on a stale database
    # connection — likely, since the worker holds one connection and this INSERT follows up to 25 s of subprocess work —
    # left the whole artifact on the encrypted volume, and a host without ffmpeg left a zero-byte file per job. Both
    # were reachable without any crash. `destination` is what gets cleaned up; `artifact` is only what gets submitted.
    # ⚠️ NO FALLBACK. Every failure below stops BEFORE the provider, and the original upload is never submitted in
    # place of a payload we could not produce or could not verify. The previous version fell back on all of them, so
    # a doctor was charged for whatever the provider made of bytes nobody had measured, and nothing anywhere recorded
    # that the processing step had silently stopped running. NoProviderRequest is the stop: run_one classifies it
    # `unsent`, writes the state and releases the hold in ONE transaction, so nothing is charged and the reservation
    # is released exactly once.
    started=time.monotonic(); destination=artifact=None
    try:
        try: upload=probe_submission(source,ceiling_seconds=ceiling,timeout=SUBMISSION_BUDGET_SECONDS)
        # The probe says WHY it could not describe the payload, and that reason is carried rather than flattened.
        # Overwriting it with UNREADABLE told every doctor on a host missing ffprobe that their own recording was
        # broken, and marked it non-retryable — the one structured signal an operator has, pointing away from the host.
        except SubmissionUnprobeable as error: raise refuse(error.kind,error.detail,job)
        except (OSError,ValueError) as error: raise refuse(UNAVAILABLE,'measuring the upload failed: %s'%type(error).__name__,job)
        try:
            _,suffix=plan_normalisation(upload)
            relative=f'submissions/{secrets.token_hex(24)}{suffix}'
            destination=private_path(relative)
            destination.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            begin_private_file(destination)
            # Created at 0600 BEFORE ffmpeg opens it: ffmpeg truncates an existing file rather than creating one, so
            # the artifact is never briefly readable at the process umask.
            destination.touch(mode=0o600,exist_ok=False)
            produced=normalise_submission(source,destination,upload,floor_seconds=floor,ceiling_seconds=ceiling,
                                          deadline=SUBMISSION_BUDGET_SECONDS-(time.monotonic()-started),
                                          cleanup=lambda path:cleanup_file(path,encounter_id=job.encounter_id))
            artifact=destination
        except NotNormalised as error: raise refuse(error.kind,error.detail,job)
        # Anything else out of the remux is still a stop, not a fallback. An unexpected exception class is exactly the
        # case where least is known about what the artifact contains, so it is the last one to submit anyway.
        except (NoProviderRequest,): raise
        except Exception as error: raise refuse(UNAVAILABLE,'preparing the recording failed: %s'%type(error).__name__,job)
        try: raw=artifact.read_bytes()
        except (OSError,ValueError) as error: raise refuse(MISSING,'the prepared artifact could not be read: %s'%type(error).__name__,job)
        if len(raw)>SUBMISSION_LIMIT_BYTES:
            raise refuse(TOO_LARGE,'the prepared payload is %d bytes, above the %d-byte submission limit'
                                   %(len(raw),SUBMISSION_LIMIT_BYTES),job)
        submitted={'submission_source':'normalised',
                   'submission_bytes':str(len(raw)),'submission_sha256':hashlib.sha256(raw).hexdigest(),
                   'upload_path':str(job.input_path),'normalisation_detail':'',
                   'submitted_seconds':str(produced.selected_seconds),
                   # What a decoder actually produced, kept apart from what the container declares. They agree here
                   # or this line is never reached, and recording both is what makes that checkable afterwards.
                   'decoded_seconds':str(produced.decoded_seconds),
                   'submission_status':'determined','submission_detail':'; '.join(produced.reasons)[:400],
                   'submission_streams':str(produced.audio_streams),'submission_container':produced.container[:60]}
        # Written BEFORE the request, so a provider call that never returns still leaves a record of what was sent.
        audit(job.user,'voice.submission_prepared',job.pk,department=job.department,
              source=submitted['submission_source'],container=submitted['submission_container'],
              seconds=submitted['submitted_seconds'],decoded_seconds=submitted['decoded_seconds'],
              submitted_bytes=submitted['submission_bytes'],sha256=submitted['submission_sha256'])
        return raw,artifact,submitted
    except BaseException:
        if destination is not None: cleanup_file(destination,encounter_id=job.encounter_id)
        raise


DEEPGRAM_MODEL='nova-3-medical'
#: The query parameters a transcription request may carry, and the values Deepgram documents for them
#: (https://developers.deepgram.com/reference/speech-to-text/listen-pre-recorded, read 2026-09-27):
#: `smart_format` and `mip_opt_out` are booleans, both default false. `mip_opt_out=true` excludes the request
#: from Deepgram's Model Improvement Program, which otherwise retains the audio and uses it for training
#: (https://developers.deepgram.com/trust-security/your-data).
DEEPGRAM_BOOLEAN_PARAMETERS=('smart_format','mip_opt_out')
#: The recorded shapes a request may have: without `mip_opt_out` (synthetic mode with the setting unset, the request
#: as it was before V1) or with it.
DEEPGRAM_RECORDED_SHAPES=(frozenset({'model','smart_format'}),frozenset({'model','smart_format','mip_opt_out'}))


def mip_opt_out_parameter():
    """{'mip_opt_out': value} when QUILLMD_DEEPGRAM_MIP_OPT_OUT has a value; {} in synthetic mode with it unset."""
    value=settings.QUILLMD_DEEPGRAM_MIP_OPT_OUT
    return {} if value is None else {'mip_opt_out':value}


def deepgram_parameters():
    """The parameters a NEW transcription job is recorded with at enqueue, from the current settings.

    QUILLMD_DEEPGRAM_MIP_OPT_OUT follows the data mode when unset: real mode sends 'true' ('false' is refused at
    startup); synthetic mode sends no `mip_opt_out` parameter, the request as it was before V1. Whether Deepgram
    prices an opted-out request differently is UNVERIFIED (docs/rebuild/v1/application-settings.md), so the quote is
    unchanged. QUILLMD_DEEPGRAM_SMART_FORMAT defaults to 'false', the request as it always was. Smart Formatting is
    listed as 'Included' for Pay As You Go and Growth on https://deepgram.com/pricing (read 2026-09-27), so it is not
    part of the priced configuration and changes no quote.
    """
    return {'model':DEEPGRAM_MODEL,'smart_format':settings.QUILLMD_DEEPGRAM_SMART_FORMAT,**mip_opt_out_parameter()}


def request_parameters(job):
    """What this job's request carries: the parameters recorded when it was queued.

    `Job.config` is write-once, so a job keeps the parameters it was queued (and quoted) with even if the settings
    change before the worker reaches it. A job queued before parameters were recorded sends the request it was queued
    for — nova-3-medical without smart formatting — plus the current opt-out setting, if it has a value. In real data
    mode nothing is sent without mip_opt_out=true, whatever a job recorded in another mode.
    """
    recorded=(job.config or {}).get('deepgram_parameters')
    if recorded is None:
        params={'model':DEEPGRAM_MODEL,'smart_format':'false',**mip_opt_out_parameter()}
    elif (not isinstance(recorded,dict) or frozenset(recorded) not in DEEPGRAM_RECORDED_SHAPES or recorded['model']!=DEEPGRAM_MODEL
            or any(recorded[name] not in ('true','false') for name in DEEPGRAM_BOOLEAN_PARAMETERS if name in recorded)):
        raise NoProviderRequest('The recorded transcription request parameters are not recognised. Nothing was sent.')
    else:
        params=dict(recorded)
    from .stripe_validation import real_data_mode  # The one definition of 'not synthetic'.
    if real_data_mode() and params.get('mip_opt_out')!='true':
        raise NoProviderRequest('Real data mode sends transcription only with the Model Improvement opt-out. Nothing was sent.')
    return params


def transcribe(job):
    # Everything before httpx.post raises NoProviderRequest: no provider request was made, so nothing is billable.
    # The key is read FIRST: preparing a payload — and recording that we prepared one — for a request that could never have
    # been made would put a submission row in the audit trail with no provider request behind it.
    key=os.getenv('DEEPGRAM_API_KEY')
    if not key: raise NoProviderRequest('Transcription provider is not connected.')
    params=request_parameters(job)
    raw,artifact,submitted=prepare_submission(job)
    try:
        return submit_transcription(job,raw,key,submitted,params)
    finally:
        # The artifact is transient by design; its sha256 and measured duration on the job are what survive.
        if artifact is not None: cleanup_file(artifact,encounter_id=job.encounter_id)


def submit_transcription(job,raw,key,submitted,params=None):
    params=params if params is not None else request_parameters(job)
    response=httpx.post('https://api.deepgram.com/v1/listen',params=params,headers={'Authorization':f'Token {key}','Content-Type':'application/octet-stream'},content=raw,timeout=90)
    response.raise_for_status()
    data=response.json()
    try:transcript=data['results']['channels'][0]['alternatives'][0]['transcript']
    except (KeyError,IndexError,TypeError):transcript=None
    duration=Decimal(str(data['metadata']['duration']))
    config=job.config or generation.configuration()
    rate=voice_rate_per_minute(config)
    if not duration.is_finite() or duration<0 or not rate.is_finite() or rate<0: raise ValidationError('Invalid provider usage.')
    list_cost=(duration*rate/60).quantize(Decimal('0.0000000001'))
    discount=generation.discount_rate(config);cost=generation.discounted_cost(list_cost,discount)
    rates=generation.cost_rates({'usd_per_minute':rate,'cost_quantum_usd':'0.0000000001','rounding':'half_even'},list_cost,discount)
    # The units carry what was SUBMITTED beside what the provider PROCESSED. They are two different measurements of two
    # different things, they are stored together on the receipt and the usage row, and the coverage statement is the
    # comparison between them — which is why neither may be inferred from the other.
    return transcript,cost,dict(submitted,duration_seconds=str(duration)),rates,'deepgram:nova-3-medical',data['metadata']['request_id'],False

def run_one():
    from .disposition import require_processing
    require_processing()
    from .batch_jobs import run_one as run_batch
    if run_batch():return True
    from .mapping_jobs import run_one as run_mapping
    next_kind=Job.objects.filter(state='queued').order_by('created_at').values_list('kind',flat=True).first()
    if next_kind=='mapping' and run_mapping(): return True
    with transaction.atomic():
        job=Job.objects.select_for_update(skip_locked=True).filter(state='queued').exclude(kind__in=['mapping','generation_part']).order_by('created_at').first()
        if not job: return False
        from .disposition_execution import require_access
        require_access(job.encounter_id)
        try: membership(job.user,job.department)
        except Exception:
            job.state='failed'; job.error='Access was revoked before processing.'; job.finished_at=timezone.now(); job.request_key=ended_key(job,'failed'); job.save();release(job); return True
        job.state='running';job.started_at=timezone.now();job.save(update_fields=['state','started_at'])
    provider_returned=False; settling=False; carrier=None
    try:
        # A hold taken before the switch to real data mode may sit on sandbox money, or its payer's paid balance (which a
        # reconciled cost would debit) may hold it: real mode never spends it, and refuses the job as reserve() would.
        if sandbox_hold(job): raise refuse_sandbox_hold(job)
        e=job.encounter
        if job.kind=='generation' and (refusal:=v3_mapping.generation_refusal(e.template_version)):
            raise NoProviderRequest(refusal)
        # The operator's mode switch is a stop: a job queued in the other mode is refused here, before anything is sent.
        if job.kind=='generation': generation.refuse_switched_mode(job.config)
        # A job quoted with the narrative contract after the flag went off stops here: nothing is sent or charged.
        if job.kind=='generation' and (refusal:=generation.narrative_refusal(e.template_version.fields,job.config)):
            raise NoProviderRequest(refusal)
        if job.kind=='generation':
            # ⚠️ A FIELD ON A ROLE PLACE IS NEVER ASKED: the roles are read from the ORIGINAL now, never from the stored
            # mapping (core.destination_roles). An original that cannot be read refuses before anything is sent.
            from . import destination_roles
            from documents import DocumentError
            # (the held rows are asked only while the setting is still on: turning it off stops every queued job asking them)
            try:asked_fields=destination_roles.generation_fields(e.template_version,suggest=generation.role_suggestions(job.config)
                                                                and destination_roles.suggestions_enabled())
            except (DocumentError,ValidationError,OSError):raise NoProviderRequest(v3_mapping.GENERATION_SOURCE_REFUSAL)
            if refusal:=destination_roles.generation_refusal(e.template_version,asked_fields,job.config):
                raise NoProviderRequest(refusal)
        result,cost,units,rates,provider,request_id,simulated=generation.generate(e.notes,asked_fields,job.config,context_labels=[row['label'] for row in e.template_version.review_requirements],requirements=e.template_version.review_requirements) if job.kind=='generation' else transcribe(job)
        provider_returned=True
        response=(result.get('anthropic_response') or result.get('response')) if isinstance(result,dict) else None
        resource_id=getattr(response,'id','') or ''
        # Financial evidence commits before any clinical serialization or file IO.
        with transaction.atomic():
            # Under the job's row lock: the state this receipt arrives into. A receipt is recorded whatever it is — provider
            # cost is never dropped — and one that arrives after the job left 'running' is held for an administrator.
            arrived_into=Job.objects.select_for_update().get(pk=job.pk).state
            ProviderReceipt.objects.get_or_create(job=job,defaults={'provider':provider,'provider_request_id':request_id,'provider_resource_id':resource_id,'actual_cost':cost,'units':units,'rates':rates,'simulated':simulated})
            job.provider=provider;job.provider_request_id=request_id;job.provider_resource_id=resource_id;job.save(update_fields=['provider','provider_request_id','provider_resource_id'])
            audit(job.user,'provider.receipt',job.pk,department=e.department,provider=provider,request_id=request_id,resource_id=resource_id,actual_cost=str(cost))
            if arrived_into!='running': hold_late_receipt(job,arrived_into)
        # The delivered transcript, stored and downloaded, carries the same incomplete-portion marker the notes would.
        note=coverage_note(job,units) if job.kind=='transcription' and isinstance(result,str) else ''
        if job.kind=='transcription':
            saved={'transcript':result+note if isinstance(result,str) else result}
            if job.config.get('transcript_review_required'): saved['raw_transcript']=result
        elif isinstance(result,dict) and 'anthropic_response' in result:
            saved={'provider_output':result['anthropic_response'].model_dump(mode='json')}
        elif isinstance(result,dict) and 'response' in result:
            saved={'provider_output':result['response'].model_dump(mode='json')}
        elif isinstance(result,dict) and 'narrative_replay' in result:
            # A synthetic narrative response (fixture mode): kept as the text the validator read, and named as such.
            saved={'provider_output_text':result['narrative_replay'],'synthetic_source':result['replay_source']}
        else:saved={'answers':result}
        result_path=f'receipts/{secrets.token_hex(24)}.json'
        path=private_path(result_path);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        payload=json.dumps(saved,ensure_ascii=False).encode()
        with path.open('xb') as file:path.chmod(0o600);file.write(payload)
        job.result_path=result_path;job.result_sha256=hashlib.sha256(payload).hexdigest();job.save(update_fields=['result_path','result_sha256'])
        # Settling provider cost is independent of clinical acceptance: invalid answers are never adopted.
        # The connection that will carry settlement's COMMIT, kept to tell afterwards whether Django had to drop it (RS-1).
        connection.ensure_connection(); carrier=connection.connection; settling=True
        settle(job,cost,units,rates,provider,request_id,simulated,provider_resource_id=resource_id)
        settling=False
        with transaction.atomic():
            e=Encounter.objects.select_for_update().get(pk=e.pk)
            # Output QuillMD cannot use is a platform failure whatever the user did meanwhile, so it is checked first and absorbed.
            if job.kind=='generation': answers,review=generation.adoption(result)
            elif not isinstance(result,str): raise PlatformFailure('Provider supplied no usable transcript.')
            # ⚠️ The encounter, then the job (the global lock order, core.retention), and before any write: a job swept or
            # resolved after its settlement committed is never adopted, and its state is never overwritten as succeeded
            # (blockers.txt item 3, case A: this block's full save used to turn a job the sweep held back into 'succeeded').
            # Taken after the validation above, which writes nothing, so a cancellation during it still answers at once.
            if Job.objects.select_for_update().get(pk=job.pk).state!='running':
                raise JobNoLongerRunning('The request left processing before its output could be adopted.')
            # Usable output that the user's own state (finalized, edited, access revoked) declines is not a platform failure:
            # NotAdoptedByUser keeps the settled charge.
            try: membership(job.user,e.department)
            except PermissionDenied: raise NotAdoptedByUser('Access was revoked before the output could be adopted; its recorded usage stays billed.')
            if e.status=='finalized' or e.revision!=job.revision: raise NotAdoptedByUser('Source changed while this job ran; output was not adopted. Its recorded usage stays billed.')
            if job.kind=='generation':
                e.answers=answers; e.status='review'
            elif job.config.get('transcript_review_required'):
                # The usable transcript is delivered and settled, but only an explicit
                # reviewed application can change source notes. Old jobs keep their
                # previously disclosed append behavior.
                audit(job.user,'transcription.review_ready',job.pk,department=e.department)
            else:
                text=result+note
                if len(e.notes)+len(text)+2>NOTE_LIMIT: raise NotAdoptedByUser(OVERFLOW_ERROR)
                e.notes+='\n\n'+text; e.answers={}; e.status='draft'; e.revision+=1
                CodeSuggestion.objects.filter(encounter=e).delete()
                audit(job.user,'coding.invalidated_by_transcription',e.pk,department=e.department,revision=e.revision)
            if not (job.kind=='transcription' and job.config.get('transcript_review_required')):
                # A generation's statement proposals only pre-select the page; the first save replaces them with decisions.
                e.template_review=review if job.kind=='generation' else {}
                e.save()
            job.state='succeeded';job.provider=provider;job.provider_request_id=request_id;job.finished_at=timezone.now()
            job.save(update_fields=['state','provider','provider_request_id','finished_at'])
            audit(job.user,'job.succeeded',job.pk,department=e.department,kind=job.kind)
    except Exception as exc:
        # A request the SDK refused to build never left: it is the pre-send refusal it is (MONEY-2).
        if not provider_returned and never_transmitted(exc): exc=NoProviderRequest(PROVIDER_NOT_CONNECTED)
        # A request the provider definitely refused without processing it is not an unknown outcome (2026-10-02).
        elif not provider_returned and (refusal:=provider_refused(exc)): exc=ProviderRefusedRequest(refusal)
        # Read before anything reconnects: whether settle()'s COMMIT went out and its answer was lost (RS-1).
        in_doubt=settling and commit_in_doubt(exc,carrier)
        usable_connection()
        try: end_failed_job(job,exc,provider_returned,in_doubt)
        except DatabaseError:
            # ⚠️ THE HANDLER'S OWN READ OR WRITE FAILED (RS-2): it used to leave the job 'running' — with a settled charge, if
            # settlement had committed — until the stale sweep. What is left is to hold the job for an administrator,
            # asserting nothing, on a fresh connection; if even that fails, the exception leaves run_one as before (the
            # worker restarts and mark_stale holds the job).
            usable_connection()
            hold_for_reconciliation(job,exc,OUTCOME_UNRECORDED)
    return True


#: ⚠️ WHAT THE WORKER SAYS WHEN IT CANNOT KNOW WHETHER A CHARGE COMMITTED (RS-1, RS-2): nothing about what was or was not
#: charged. The administrator's resolution (views.admin_resolve_job) reads the committed usage, ledger and holds under the
#: job's row lock and resolves from them, whichever way the commit went.
SETTLEMENT_UNKNOWN='The settlement outcome of this request is unknown; an administrator must reconcile it.'
OUTCOME_UNRECORDED='The outcome of this request could not be recorded; an administrator must reconcile it.'
#: The settled charge of an output that was not adopted could not be reversed (RS-3): the job is held with its key.
ABSORPTION_FAILED=('The output could not be adopted, and its charge could not be reversed automatically; an administrator '
                   'must reconcile it.')
FIXTURE_VALIDATION='Generation failed validation.'
#: RS-5: in fixture (synthetic) mode a failure that is not a validation refusal is named as what it was.
FIXTURE_PLATFORM_ERROR=('Generation failed: a platform {kind}error ({name}) stopped it before its output was adopted. '
                        'Synthetic generation carries no charge; the held funds were released.')


def commit_in_doubt(error,carrier):
    """True when a COMMIT went out and its answer was lost, so whether that transaction committed is unknown here (RS-1).

    Structural, like never_transmitted: the exception passed through Django's own commit() (its code object, identity),
    and `carrier`, the connection that sent it, is gone — Django drops a connection whose rollback after a failed commit
    fails too (and reconnects at once, in atomic's exit, so an absent connection proves nothing; identity does). A COMMIT
    the server answered with an error (a deferred constraint) rolled back on a connection that survived to say so:
    established, not in doubt. An error raised by a statement before the COMMIT never reached one: it cannot commit.
    """
    if not isinstance(error,DatabaseError) or carrier is None or connection.connection is carrier: return False
    commit=unwrap(BaseDatabaseWrapper.commit).__code__
    trace=error.__traceback__
    while trace is not None:
        if trace.tb_frame.f_code is commit: return True
        trace=trace.tb_next
    return False


def usable_connection():
    """A connection that broke outside a transaction stays broken until it is closed, and Django closes one only at a
    request boundary; the worker has none. Before the handler reads and records an outcome, do what that boundary does."""
    if not connection.in_atomic_block: connection.close_if_unusable_or_obsolete()


def outcome_already_recorded(job,exc,state):
    """A committed transaction ended this job before the handler got its lock (the adoption, whose COMMIT answer was lost
    after it committed): that record stands, and the error is recorded beside it."""
    audit(job.user,'job.error_after_commit',job.pk,department=job.department,state=state,error_class=type(exc).__name__)


def hold_for_reconciliation(job,exc,message,billing='uncertain',absorb_error=None,action='job.reconciliation'):
    """Hold a running job for an administrator, asserting nothing: no release, no absorption, and its request key kept, so
    the same request cannot be bought twice meanwhile. Also the mapping worker's (core.mapping_jobs)."""
    with transaction.atomic():
        state=Job.objects.select_for_update().get(pk=job.pk).state
        if state!='running': return outcome_already_recorded(job,exc,state)
        job.state='reconciliation';job.error=message;job.finished_at=timezone.now()
        job.save(update_fields=['state','error','finished_at'])
        if absorb_error is not None: audit(job.user,'usage.absorb_failed',job.pk,department=job.department,error_class=type(absorb_error).__name__)
        audit(job.user,action,job.pk,department=job.department,error_class=type(exc).__name__,billing=billing)


#: A provider receipt that arrived after its job had left 'running' (blockers.txt item 3): recorded, never settled, never
#: dropped, and held for an administrator, whose resolution absorbs the receipt's cost (views.admin_resolve_job).
LATE_RECEIPT=('The provider completed after this request had been ended or held elsewhere. Its receipt is recorded and nothing '
              'is charged for it; an administrator must reconcile it.')
#: The audit action audit_billing reads to find late receipts (late_provider_receipts_resolved).
LATE_RECEIPT_ACTION='provider.receipt_late'


def hold_late_receipt(job,state):
    """Inside the receipt's own transaction, under the job's row lock: a receipt arrived for a job in `state`, not 'running'.

    Somebody ended or held the job while its provider request was in flight: a second worker's stale sweep, or an
    administrator resolving what that sweep held ('Resolved by administrator: no provider cost evidenced.', its hold released
    and its request key freed). The receipt proves provider cost that record denies. So:

    - a job that ENDED with no usage row ('failed', 'cancelled') is reopened for reconciliation, so its record no longer says
      that no provider cost exists; the administrator's resolution then absorbs the receipt's cost (views.admin_resolve_job,
      receipt branch). Its request key stays as it is: a freed key may already carry a new request, charged once, as its own.
    - a job already held for reconciliation keeps its state, and its error now says that a receipt arrived.
    - the arrival is recorded (LATE_RECEIPT_ACTION, with the previous state and error): audit_billing fails until the
      receipt is accounted for, by a usage row or an absorbed platform cost of exactly its amount.

    Nothing is settled here or later: settle() refuses a job that is not running (core.billing.SETTLEABLE_STATES). The batch
    runner reopens an ENDED child the same way (core.batch_jobs.store_response, 'late_response_recorded'); a batch child that
    was only held when its response arrived is not marked late and stays held for the batch resolution."""
    current=Job.objects.get(pk=job.pk)  # the caller holds its row lock
    previous_error=current.error
    if state in ('failed','cancelled') and not Usage.objects.filter(job=job).exists():
        current.state='reconciliation';current.finished_at=None;current.error=LATE_RECEIPT
        current.save(update_fields=['state','finished_at','error'])
    elif state=='reconciliation':
        current.error=LATE_RECEIPT;current.save(update_fields=['error'])
    audit(job.user,LATE_RECEIPT_ACTION,job.pk,department=job.department,previous_state=state,
          previous_error=previous_error[:250],state=current.state)


def end_failed_job(job,exc,provider_returned,in_doubt):
    """Record how a running job that raised ended, from what is committed, under its row lock."""
    # ⚠️ AN IN-DOUBT SETTLEMENT ASSERTS NOTHING (RS-1). Its COMMIT may still be in flight: a read here can come before it is
    # visible, and this used to record 'nothing is charged' for a charge that committed a moment later.
    if in_doubt: return hold_for_reconciliation(job,exc,SETTLEMENT_UNKNOWN)
    absorbing=False
    try:
        with transaction.atomic():
            # Under the job's row lock the committed record is final: a transaction whose COMMIT answer was lost still holds
            # this lock until it ends, and one that committed (the adoption) has already ended the job.
            state=Job.objects.select_for_update().get(pk=job.pk).state
            if state!='running': return outcome_already_recorded(job,exc,state)
            # A timeout can be billable. Never retry it or release its reservation as if cost were known.
            known=Usage.objects.filter(job=job).exists()
            fixture=job.kind=='generation' and job.config.get('mode',settings.AI_MODE)!='live'
            declined=known and isinstance(exc,NotAdoptedByUser)
            unsent=not known and not provider_returned and isinstance(exc,NoProviderRequest)
            # The provider answered with a definite refusal (`provider_refused`): nothing was processed or billed.
            refused=not known and not provider_returned and not fixture and isinstance(exc,ProviderRefusedRequest)
            job.state='failed' if known or fixture or unsent or refused else 'reconciliation'
            # After settlement the error prefix is the billing classification audit_billing reads: not_adopted stays charged, platform_failure is absorbed.
            if known: job.error=((NOT_ADOPTED if declined else PLATFORM_FAILURE)+failure_reason(exc))[:250]
            elif unsent: job.error=(NOT_PROCESSED+failure_reason(exc)+' No provider request was made; nothing was charged and the held funds were released.')[:250]
            elif refused: job.error=(NOT_PROCESSED+failure_reason(exc))[:250]
            elif fixture:
                job.error=FIXTURE_VALIDATION if isinstance(exc,ValidationError) else FIXTURE_PLATFORM_ERROR.format(
                    kind='database ' if isinstance(exc,DatabaseError) else '',name=type(exc).__name__)[:250]
            elif ProviderReceipt.objects.filter(job=job).exists():
                # The provider completed and its receipt is durable; only settlement failed (for example cost above the held
                # maximum), and settlement's transaction is known to have rolled back.
                job.error='Provider completed, but settlement needs administrator reconciliation; nothing is charged until it is resolved.'
            else: job.error='Provider outcome is uncertain; reconcile before retrying.'
            job.finished_at=timezone.now()
            fields=['state','error','finished_at']
            if job.state=='failed': job.request_key=ended_key(job,'failed'); fields.append('request_key')
            if refused: fields+=record_refusal(job,exc,'job.failed')
            job.save(update_fields=fields)
            # One transaction: a job never reads 'held funds were released' while its hold is still held.
            if fixture or unsent or refused: release(job)
            # ⚠️ Settled provider cost whose output was never adopted is a platform failure: QuillMD absorbs it and reverses the
            # user's charge IN THE SAME TRANSACTION as the failed state (RS-3). A successful generation the user did not adopt
            # (declined) remains billable, with no reversal and no platform cost.
            elif known and not declined:
                absorbing=True; absorb_failed_job(job); absorbing=False
            audit(job.user,'job.'+job.state,job.pk,department=job.department,error_class=type(exc).__name__,
                  billing='not_adopted' if declined else 'platform_failure' if known and not fixture else 'not_processed' if unsent else 'provider_refused' if refused else 'fixture' if fixture else 'uncertain')
    except Exception as absorb_error:
        if not absorbing: raise
        # ⚠️ A REVERSAL THAT FAILED NEVER LEAVES A 'failed' JOB CHARGED (RS-3). It used to: the failed state was durable, the
        # charge stayed and the request key was freed, so the same request was bought again. Now nothing of that transaction
        # stands; the job is held with its key and its charge until an administrator resolves it (the settled branch of
        # admin_resolve_job absorbs it).
        hold_for_reconciliation(job,exc,ABSORPTION_FAILED,billing='platform_failure',absorb_error=absorb_error)


@transaction.atomic
def cancel(job,user):
    """Cancel a queued request before any provider request. The row lock is the same one run_one takes with skip_locked, so a job
    being picked up is never cancelled and a job being cancelled is never picked up. Held reservations are released; nothing is charged."""
    if job.kind=='generation_part':
        from .batch_jobs import cancel_child
        return cancel_child(job,user)
    # Lock the job row only: locking the encounter or department too would invert run_one's encounter-then-job order and deadlock.
    job=Job.objects.select_for_update(of=('self',)).select_related('encounter__department').get(pk=job.pk)
    # The requester may cancel their own queued request; anyone else needs a clinician or owner role in the department.
    membership(user,job.department,roles=None if job.user_id==user.pk else ['owner','clinician'])
    if job.state!='queued': raise CancellationRefused(CANCEL_REFUSALS.get(job.state,'This request can no longer be cancelled.'))
    job.state='cancelled';job.error=CANCELLED_ERROR;job.finished_at=timezone.now()
    job.request_key=ended_key(job,'cancelled')
    job.save(update_fields=['state','error','finished_at','request_key'])
    release(job)
    audit(user,'job.cancelled',job.pk,department=job.department,kind=job.kind)
    return job

def reap_abandoned_voice_uploads():
    """Remove over-limit uploads nobody approved within the approval window. Only files an over-limit quote recorded are
    candidates, and never one a job references."""
    cutoff=timezone.now()-timedelta(seconds=ABANDONED_UPLOAD_SECONDS)
    removed=0
    for event in AuditEvent.objects.filter(action='voice.over_limit_quoted',created_at__lt=cutoff,created_at__gte=cutoff-timedelta(days=7)).order_by('created_at')[:500]:
        relative=str((event.details or {}).get('path',''))
        if not UPLOAD_NAME.fullmatch(relative) or Job.objects.filter(input_path=relative).exists(): continue
        path=private_path(relative)
        if path.is_file():
            removed+=int(cleanup_file(path,encounter_id=event.target,department_id=event.department_id))
            if not path.exists():audit(None,'voice.over_limit_upload_removed',event.target,department=event.department,path=relative)
    return removed+reap_stray_submissions()


def reap_stray_submissions():
    """Remove normalised artifacts a crash left behind.

    An artifact lives for one provider request — normalisation is capped at 120 s and the request at 90 s — and is removed in
    a finally. Anything still here after the approval window is residue from a process that died between the two, so there is
    no live job it could belong to. The name is checked against the same pattern that generates it, and nothing outside the
    submissions directory is a candidate: a reaper that deletes by age alone is one bad path away from eating a recording."""
    cutoff=(timezone.now()-timedelta(seconds=ABANDONED_UPLOAD_SECONDS)).timestamp()
    try: entries=sorted(private_path('submissions').iterdir())[:500]
    except (OSError,ValueError): return 0
    removed=0
    for path in entries:
        relative='submissions/'+path.name
        if not SUBMISSION_NAME.fullmatch(relative) or not path.is_file(): continue
        try:
            if path.stat().st_mtime>=cutoff: continue
            deleted=cleanup_file(path)
        except OSError: continue
        if not deleted:continue
        removed+=1
        audit(None,'voice.stray_submission_removed','',path=relative)
    return removed


def mark_stale():
    from .batch_jobs import mark_stale as batch_stale
    batch_stale()
    for job in Job.objects.filter(state='running',started_at__lt=timezone.now()-timedelta(minutes=5)).exclude(kind='generation_part'):
        with transaction.atomic():
            locked=Job.objects.select_for_update().get(pk=job.pk)
            if locked.state!='running':continue
            locked.state='reconciliation';locked.error='Worker stopped with an unknown provider outcome. Automatic retry is disabled.';locked.save(update_fields=['state','error'])
            audit(locked.user,'job.reconciliation',locked.pk)
