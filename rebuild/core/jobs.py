from datetime import timedelta
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import hashlib
import json
import re
import secrets
import os
import time
import httpx
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from .generation_errors import NoProviderRequest, PlatformFailure
from .models import AuditEvent, Job, Encounter, Usage, ProviderReceipt, CodeSuggestion
from .security import membership,audit,private_path
from .media import (AMBIGUOUS,MISSING,RETRYABLE,SUBMISSION_BUDGET_SECONDS,TOO_LARGE,TOO_SLOW,UNAVAILABLE,UNREADABLE,NotNormalised,
                    SubmissionUnprobeable,normalise_submission,plan_normalisation,probe_submission,refusal_text,
                    scrubbed)
from .billing import reserve,settle,release,absorb_failed_job,MULTIPLIER
from . import generation
from . import audio


class NotAdoptedByUser(ValidationError):
    """A successful, user-requested generation whose output the user's own state kept from adoption. It stays billable."""


class CancellationRefused(ValidationError):
    """The job is past the point where cancellation is free; the message is the one-line reason."""


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
    """Retain an ended attempt under its own key. Generation still deduplicates by
    persisted source revision; transcription retains its existing retry policy.
    Longest key today is transcription (115 chars) + 43 = 158 of 160."""
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
    return billable_outcome(job)


def may_cancel(job,user):
    """Same rule jobs.cancel enforces: the requester, or an owner or clinician of the department."""
    if job.state!='queued': return False
    try: membership(user,job.encounter.department,roles=None if job.user_id==user.pk else ['owner','clinician'])
    except PermissionDenied: return False
    return True


def failure_reason(exc):
    """Display text for a post-settlement failure. Only QuillMD's own fixed messages are shown; any other exception is named by class,
    because provider or validation messages can quote the source text."""
    if isinstance(exc,(NotAdoptedByUser,PlatformFailure,NoProviderRequest)): return '; '.join(exc.messages)
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
    from . import testing_authority
    if testing_authority.identity(config):
        # This remains a conservative estimate, not a sponsor funding limit.
        # Duration and structural/stream checks still precede any provider send.
        testing_authority.validate_config(config,'transcription')
        return bounds,limit,quote
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


def generation_maximum(encounter,config=None):
    """One immutable whole-workflow estimate; legacy versions retain their quote."""
    fresh=config is None
    if fresh:config=generation.configuration()
    from .word_contract import require_generation
    if require_generation(encounter.template_version):
        from .ai_stages import maximum_cost,pipeline_config
        return maximum_cost(pipeline_config(config) if fresh else config)
    return generation.maximum_cost(encounter.notes,encounter.template_version.fields,config,
        context_labels=[row['label'] for row in encounter.template_version.review_requirements])


@transaction.atomic
def enqueue(encounter,user,kind='generation',input_path='',config=None,approved_limit=None,expected_revision=None,
            require_current_generation_quote=False):
    e=Encounter.objects.select_for_update().get(pk=encounter.pk)
    membership(user,e.department)
    if e.status=='finalized': raise ValidationError('Finalized documents are immutable.')
    if expected_revision is not None and e.revision!=expected_revision:
        raise ValidationError('Source notes changed after the quote. Reload and review the current notes before submitting.')
    if kind=='generation' and not e.notes.strip():
        raise ValidationError('Type and save source notes, or review and add a transcript, before generating answers.')
    if e.template_version.preparation_id:
        from .template_source import source_for_version
        source_for_version(e.template_version)
    fingerprint=hashlib.sha256(private_path(input_path).read_bytes()).hexdigest() if kind=='transcription' else str(e.revision)
    key=f'{kind}:{e.pk}:{fingerprint}'
    old=Job.objects.filter(request_key=key).first()
    if old is None and kind=='generation':
        # A failed/cancelled job releases its active request key, but retains its
        # source revision. Replaying a browser submission must still resolve to
        # that exact attempt. Saving source notes is the explicit new-request act.
        old=Job.objects.filter(encounter=e,kind=kind,revision=e.revision).order_by('-created_at','-pk').first()
    # Idempotency is the point: the same revision, or the same audio bytes, must never buy a
    # second provider call. But the CALLER has to be able to tell, because a generation does not
    # renumber the revision, so a stale page's re-POST lands here holding a key a SUCCEEDED job
    # still owns. Announcing that as "queued" tells the doctor a request was made that was not,
    # and invites them to wait for answers that will never change. Not persisted; a per-instance
    # fact about THIS call, never about the row.
    if old:
        old.reused=True
        return old
    if Job.objects.filter(encounter=e,state__in=['queued','running','reconciliation']).exists(): raise ValidationError('This encounter already has a pending job.')
    from .preparation_campaign import campaign_job_config,admit_campaign_job,campaign_identity,JOB_QUOTE_LIMIT
    config=campaign_job_config(dict(config or generation.configuration()),kind)
    from .word_contract import require_generation
    definitions = require_generation(e.template_version) if kind == 'generation' else {}
    if definitions:
        from .ai_stages import pipeline_config
        from .semantic_generation import digest,REFERENCE_INVENTORY_CONTRACT,CLINICAL_REQUIREMENTS_SCOPE_CONTRACT
        prospective=pipeline_config(config)
        if require_current_generation_quote:
            quoted_keys=('semantic_contract','semantic_stage_protocol','semantic_max_calls',
                'semantic_request_byte_limit','semantic_capacity_profile','semantic_timeout_seconds',
                'semantic_output_token_limit','semantic_maximum_cost')
            if any(type(config.get(key)) is not type(prospective[key]) or config[key]!=prospective[key] for key in quoted_keys):
                raise ValidationError('Generation capacity changed after this quote. Reload to review the current maximum charge. Nothing was queued.')
        config=prospective
        graph_definition = all(d.get('version') == 4 for d in definitions.values())
        if any(d.get('version') == 4 for d in definitions.values()) and not graph_definition:
            raise ValidationError('The form mixes incompatible interpretation contracts. Review a complete new definition version; nothing was queued.')
        if graph_definition:
            from .source_assertion_graph import SCOPE_CONTRACT as graph_scope
            config['semantic_encounter_binding'] = {
                'patient_id': str(e.patient_id), 'encounter_id': str(e.pk),
                'department_id': str(e.department_id), 'service_date': e.service_date.isoformat(),
                'template_version_id': str(e.template_version_id),
                'patient_display_name': e.patient.display_name, 'patient_reference': e.patient.reference,
            }
        config.update(semantic_template_version=str(e.template_version_id),
            semantic_fact_reference_contract=REFERENCE_INVENTORY_CONTRACT,
            semantic_fact_scope_contract=graph_scope if graph_definition else CLINICAL_REQUIREMENTS_SCOPE_CONTRACT,
            semantic_source_sha256=hashlib.sha256(e.notes.encode()).hexdigest(),
            semantic_definitions_sha256=digest(definitions))
    from . import testing_authority
    if testing_authority.identity(config):
        testing_authority.admit_actor(user,e.department_id)
        testing_authority.admit_encounter(user,e)
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
    from . import testing_authority
    if testing_authority.identity(config):
        estimated_cost=(charge_limit/MULTIPLIER if kind=='transcription' else
            generation_maximum(e,config))
        config=testing_authority.job_config(config,kind,user,e.department_id,estimated_cost)
    if campaign_identity(config) is not None:
        expected_charge=(charge_limit if kind=='transcription' else
            generation_maximum(e,config)*MULTIPLIER)
        if expected_charge>JOB_QUOTE_LIMIT:
            raise ValidationError('This request exceeds the delivery campaign per-request allowance. Nothing was queued.')
        admit_campaign_job(config,kind,user,e.department_id)
    # Record the release that accepted this new request. An idempotent replay
    # returns above and must never relabel a retained attempt.
    config['queued_release_sha']=settings.RELEASE_SHA
    job=Job.objects.create(encounter=e,user=user,kind=kind,revision=e.revision,request_key=key,input_path=input_path,config=config)
    job.reused=False
    if kind=='transcription':
        reserve(job,charge_limit=charge_limit)
    else:
        max_cost=generation_maximum(e,job.config)
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
              department=job.encounter.department if job else None,
              kind=kind,retryable=kind in RETRYABLE,detail=scrubbed(detail))
    except Exception:
        pass
    return NoProviderRequest(refusal_text(kind))


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
            # Created at 0600 BEFORE ffmpeg opens it: ffmpeg truncates an existing file rather than creating one, so
            # the artifact is never briefly readable at the process umask.
            destination.touch(mode=0o600,exist_ok=False)
            produced=normalise_submission(source,destination,upload,floor_seconds=floor,ceiling_seconds=ceiling,
                                          deadline=SUBMISSION_BUDGET_SECONDS-(time.monotonic()-started))
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
        audit(job.user,'voice.submission_prepared',job.pk,department=job.encounter.department,
              source=submitted['submission_source'],container=submitted['submission_container'],
              seconds=submitted['submitted_seconds'],decoded_seconds=submitted['decoded_seconds'],
              submitted_bytes=submitted['submission_bytes'],sha256=submitted['submission_sha256'])
        return raw,artifact,submitted
    except BaseException:
        if destination is not None: destination.unlink(missing_ok=True)
        raise


def transcribe(job):
    # Everything before httpx.post raises NoProviderRequest: no provider request was made, so nothing is billable.
    # The key is read FIRST: preparing a payload — and recording that we prepared one — for a request that could never have
    # been made would put a submission row in the audit trail with no provider request behind it.
    key=os.getenv('DEEPGRAM_API_KEY')
    if not key: raise NoProviderRequest('Transcription provider is not connected.')
    raw,artifact,submitted=prepare_submission(job)
    try:
        return submit_transcription(job,raw,key,submitted)
    finally:
        # The artifact is transient by design; its sha256 and measured duration on the job are what survive.
        if artifact is not None: artifact.unlink(missing_ok=True)


def submit_transcription(job,raw,key,submitted):
    response=httpx.post('https://api.deepgram.com/v1/listen',params={'model':'nova-3-medical','smart_format':'false'},headers={'Authorization':f'Token {key}','Content-Type':'application/octet-stream'},content=raw,timeout=90)
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
    from .provider_models import transcription_models
    units=dict(submitted,duration_seconds=str(duration),**transcription_models(data.get('metadata')))
    return transcript,cost,units,rates,'deepgram:nova-3-medical',data['metadata']['request_id'],False

def run_semantic_job(job):
    """Settle the whole known stage chain once; uncertain later stages retain holds."""
    from . import ai_stages,semantic_generation
    from .word_contract import require_generation
    answers=None
    try:
        e=job.encounter
        try:
            definitions=require_generation(e.template_version)
        except ValidationError as exc:
            raise NoProviderRequest('The approved form source or answer definitions need review before generation. '
                'Open its mapping for a new definition version, or contact support if the original is unavailable. '
                'Nothing was sent or charged.') from exc
        if (job.config.get('semantic_template_version')!=str(e.template_version_id)
            or job.config.get('semantic_source_sha256')!=hashlib.sha256(e.notes.encode()).hexdigest()
            or job.config.get('semantic_definitions_sha256')!=semantic_generation.digest(definitions)):
            raise ai_stages.StageNotSent('The approved generation source or definitions changed before processing.')
        from .source_assertion_graph import SCOPE_CONTRACT as graph_scope
        graph_run = job.config.get('semantic_fact_scope_contract') == graph_scope
        interpretation = None
        def send(role,attempt,payload,schema,instructions):
            options = {}
            if graph_run and job.config.get('mode') == 'fixture':
                from .source_assertion_generation import fixture_stage
                options['fixture_output'] = fixture_stage(role, payload)
            return ai_stages.execute_stage(job=job,stage=role,attempt=attempt,payload=payload,
                schema=schema,instructions=instructions,config=job.config,**options)
        if graph_run:
            from . import source_assertion_generation as graph_generation
            from .source_interpretation_store import identity_for
            identity = identity_for(e, definitions, generation_job_id=str(job.pk))
            if {key: value for key, value in identity.items() if key != 'generation_job_id'} != job.config.get('semantic_encounter_binding'):
                raise ai_stages.StageNotSent('The encounter identity or date changed after the interpretation was quoted; nothing was sent.')
            output = graph_generation.run(e.notes, e.template_version.fields, definitions, send, identity=identity)
            answers, interpretation = output['answers'], output['interpretation']
            for field in e.template_version.fields:
                graph_generation.validate_stored_answer(e.notes, field, definitions[field['key']], answers[field['key']], interpretation)
        else:
            answers=semantic_generation.run(e.notes,e.template_version.fields,definitions,send,
                reference_contract=job.config.get('semantic_fact_reference_contract',semantic_generation.LEGACY_REFERENCE_CONTRACT),
                scope_contract=job.config.get('semantic_fact_scope_contract',semantic_generation.POSITIONED_SCOPE_CONTRACT))
            for field in e.template_version.fields:
                semantic_generation.validate_stored_answer(e.notes,field,definitions[field['key']],answers[field['key']])
        result_path,result_sha=ai_stages.retain({'contract':semantic_generation.CONTRACT,'answers':answers,
            **({'interpretation': interpretation} if graph_run else {}),
            'stages':[str(pk) for pk in job.ai_stage_receipts.order_by('created_at','pk').values_list('pk',flat=True)]})
        job.result_path=result_path;job.result_sha256=result_sha;job.save(update_fields=['result_path','result_sha256'])
        settle_semantic_stages(job)
        with transaction.atomic():
            e=Encounter.objects.select_for_update().get(pk=e.pk)
            try:membership(job.user,e.department)
            except PermissionDenied:raise NotAdoptedByUser('Access was revoked before the output could be adopted; its recorded usage stays billed.')
            if e.status=='finalized' or e.revision!=job.revision:
                raise NotAdoptedByUser('Source changed while this job ran; output was not adopted. Its recorded usage stays billed.')
            if graph_run:
                from .source_interpretation_store import adopt
                adopt(e, job, interpretation, answers)
            e.answers=answers;e.status='review';e.template_review={};e.save()
            job.state='succeeded';job.finished_at=timezone.now();job.save(update_fields=['state','finished_at'])
            audit(job.user,'job.succeeded',job.pk,department=e.department,kind=job.kind,
                  contract=semantic_generation.CONTRACT,stage_count=job.ai_stage_receipts.count())
            from .coding_hooks import after_saved_document
            after_saved_document(e.pk, job.user_id)
    except Exception as exc:
        rows=list(job.ai_stage_receipts.all())
        sent=any(row.started_at is not None for row in rows)
        unresolved=any(row.actual_cost is None or row.state not in ('succeeded','failed') for row in rows)
        if sent and not unresolved and not Usage.objects.filter(job=job).exists():
            try:settle_semantic_stages(job)
            except Exception:unresolved=True
        known=Usage.objects.filter(job=job).exists()
        declined=known and isinstance(exc,NotAdoptedByUser)
        unsent=not sent and not unresolved
        job.state='failed' if known or unsent else 'reconciliation'
        if known:job.error=((NOT_ADOPTED if declined else PLATFORM_FAILURE)+failure_reason(exc))[:250]
        elif unsent:
            reason=(failure_reason(exc) if isinstance(exc,NoProviderRequest)
                    else 'Semantic generation was refused before any provider request; nothing was charged.')
            job.error=(NOT_PROCESSED+reason)[:250]
        else:job.error='An independent AI stage has an uncertain outcome or unsettled cost. Retained earlier stages are preserved; administrator reconciliation is required. Do not resubmit.'
        job.finished_at=timezone.now()
        if job.state=='failed':job.request_key=ended_key(job,'failed')
        if unsent:
            with transaction.atomic():job.save();release(job)
        else:job.save()
        if known and not declined:
            try:absorb_failed_job(job)
            except Exception as absorb_error:audit(job.user,'usage.absorb_failed',job.pk,department=job.encounter.department,error_class=type(absorb_error).__name__)
        audit(job.user,'job.'+job.state,job.pk,department=job.encounter.department,error_class=type(exc).__name__,
              billing='not_adopted' if declined else 'platform_failure' if known else 'not_processed' if unsent else 'uncertain')
    return True


def settle_semantic_stages(job):
    from .ai_stages import aggregate
    cost,units,rates,provider,request_id,simulated=aggregate(job)
    with transaction.atomic():
        ProviderReceipt.objects.get_or_create(job=job,defaults={'provider':provider,'provider_request_id':'',
            'provider_resource_id':'','actual_cost':cost,'units':units,'rates':rates,'simulated':simulated})
        job.provider=provider;job.provider_request_id='';job.provider_resource_id=''
        job.save(update_fields=['provider','provider_request_id','provider_resource_id'])
    settle(job,cost,units,rates,provider,'',simulated,provider_resource_id='')


def run_one():
    with transaction.atomic():
        job=Job.objects.select_for_update(skip_locked=True).filter(state='queued').order_by('created_at').first()
        if not job: return False
        try: membership(job.user,job.encounter.department)
        except Exception:
            job.state='failed'; job.error='Access was revoked before processing.'; job.finished_at=timezone.now(); job.request_key=ended_key(job,'failed'); job.save();release(job); return True
        if job.encounter.template_version.preparation_id or job.encounter.template_version.semantic_preparation_id or job.encounter.template_version.semantic_definitions:
            try:
                from .template_source import source_for_version
                source_for_version(job.encounter.template_version)
            except (ValidationError,ValueError,OSError):
                job.state='failed';job.error='The approved form source changed before processing.';job.finished_at=timezone.now();job.request_key=ended_key(job,'failed');job.save();release(job);return True
        job.state='running';job.started_at=timezone.now();job.save(update_fields=['state','started_at'])
        # Financial configuration is immutable after enqueue. Execution
        # provenance belongs in its own append-only audit record.
        audit(job.user,'job.running',job.pk,department=job.encounter.department,
              executing_release_sha=settings.RELEASE_SHA,
              queued_release_sha=job.config.get('queued_release_sha',''))
    if 'semantic_revalidation_contract' in job.config:
        from .semantic_revalidation import run as run_revalidation
        return run_revalidation(job)
    if job.kind=='generation' and job.config.get('semantic_contract')=='semantic-facts-v1':return run_semantic_job(job)
    provider_returned=False
    try:
        e=job.encounter
        from .preparation_campaign import provider_slot
        from . import testing_authority
        if testing_authority.identity(job.config):
            try:
                testing_authority.admit_job_send(job)
            except (ValidationError,PermissionDenied) as exc:
                raise testing_authority.TestingProviderRefusal('Standing request authority or synthetic access changed; nothing was sent.') from exc
        with provider_slot(job.config):
            result,cost,units,rates,provider,request_id,simulated=generation.generate(e.notes,e.template_version.fields,job.config,context_labels=[row['label'] for row in e.template_version.review_requirements]) if job.kind=='generation' else transcribe(job)
            provider_returned=True
            response=(result.get('anthropic_response') or result.get('response')) if isinstance(result,dict) else None
            resource_id=getattr(response,'id','') or ''
            # Hold the provider slot until its actual cost is durably visible.
            # Financial evidence commits before clinical serialization/file IO.
            with transaction.atomic():
                ProviderReceipt.objects.get_or_create(job=job,defaults={'provider':provider,'provider_request_id':request_id,'provider_resource_id':resource_id,'actual_cost':cost,'units':units,'rates':rates,'simulated':simulated})
                job.provider=provider;job.provider_request_id=request_id;job.provider_resource_id=resource_id;job.save(update_fields=['provider','provider_request_id','provider_resource_id'])
                audit(job.user,'provider.receipt',job.pk,department=e.department,provider=provider,request_id=request_id,resource_id=resource_id,actual_cost=str(cost))
        # The delivered transcript, stored and downloaded, carries the same incomplete-portion marker the notes would.
        note=coverage_note(job,units) if job.kind=='transcription' and isinstance(result,str) else ''
        if job.kind=='transcription':
            saved={'transcript':result+note if isinstance(result,str) else result}
            if job.config.get('transcript_review_required'): saved['raw_transcript']=result
        elif isinstance(result,dict) and 'anthropic_response' in result:
            saved={'provider_output':result['anthropic_response'].model_dump(mode='json')}
        elif isinstance(result,dict) and 'response' in result:
            saved={'provider_output':result['response'].model_dump(mode='json')}
        else:saved={'answers':result}
        result_path=f'receipts/{secrets.token_hex(24)}.json'
        path=private_path(result_path);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        payload=json.dumps(saved,ensure_ascii=False).encode()
        with path.open('xb') as file:path.chmod(0o600);file.write(payload)
        job.result_path=result_path;job.result_sha256=hashlib.sha256(payload).hexdigest();job.save(update_fields=['result_path','result_sha256'])
        # Settling provider cost is independent of clinical acceptance: invalid answers are never adopted.
        settle(job,cost,units,rates,provider,request_id,simulated,provider_resource_id=resource_id)
        with transaction.atomic():
            e=Encounter.objects.select_for_update().get(pk=e.pk)
            # Output QuillMD cannot use is a platform failure whatever the user did meanwhile, so it is checked first and absorbed.
            if job.kind=='generation':
                answers=generation.validated(result)
                from .answer_constraints import hold_constraint_mismatches
                answers=hold_constraint_mismatches(e.template_version.fields,answers)
            elif not isinstance(result,str): raise PlatformFailure('Provider supplied no usable transcript.')
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
                audit(job.user,'coding.invalidated_by_transcription',e.pk,department=e.department)
            if not (job.kind=='transcription' and job.config.get('transcript_review_required')):
                e.template_review={}
                e.save()
            job.state='succeeded';job.provider=provider;job.provider_request_id=request_id;job.finished_at=timezone.now();job.save()
            audit(job.user,'job.succeeded',job.pk,department=e.department,kind=job.kind)
            if job.kind == 'generation':
                from .coding_hooks import after_saved_document
                after_saved_document(e.pk, job.user_id)
    except Exception as exc:
        # A timeout can be billable. Never retry it or release its reservation as if cost were known.
        known=Usage.objects.filter(job=job).exists()
        fixture=job.kind=='generation' and job.config.get('mode',settings.AI_MODE)!='live'
        declined=known and isinstance(exc,NotAdoptedByUser)
        from .preparation_campaign import CampaignProviderRefusal
        from .testing_authority import TestingProviderRefusal
        unsent=not known and not provider_returned and isinstance(exc,(NoProviderRequest,CampaignProviderRefusal,TestingProviderRefusal))
        job.state='failed' if known or fixture or unsent else 'reconciliation'
        # After settlement the error prefix is the billing classification audit_billing reads: not_adopted stays charged, platform_failure is absorbed.
        if known: job.error=((NOT_ADOPTED if declined else PLATFORM_FAILURE)+failure_reason(exc))[:250]
        elif unsent: job.error=(NOT_PROCESSED+failure_reason(exc)+' No provider request was made; nothing was charged and the held funds were released.')[:250]
        elif fixture: job.error='Generation failed validation.'
        elif ProviderReceipt.objects.filter(job=job).exists():
            # The provider completed and its receipt is durable; only settlement failed (for example cost above the held maximum).
            job.error='Provider completed, but settlement needs administrator reconciliation; nothing is charged until it is resolved.'
        else: job.error='Provider outcome is uncertain; reconcile before retrying.'
        job.finished_at=timezone.now()
        fields=['state','error','finished_at']
        if job.state=='failed': job.request_key=ended_key(job,'failed'); fields.append('request_key')
        if fixture or unsent:
            # One transaction: a job never reads 'held funds were released' while its hold is still held. If the release
            # fails, the job stays 'running', mark_stale moves it to reconciliation and the audit lists it as unresolved.
            with transaction.atomic():
                job.save(update_fields=fields); release(job)
        else: job.save(update_fields=fields)
        # Released above (fixture, not processed), or a successful generation the user did not adopt: it remains billable,
        # with no reversal and no platform cost.
        if fixture or unsent or declined: pass
        # Settled provider cost whose output was never adopted is a platform failure: QuillMD absorbs it and reverses the user's charge.
        elif known:
            try: absorb_failed_job(job)
            except Exception as absorb_error:
                # The failed job state is already durable; a failed reversal must never stop the worker. audit_billing flags settled-but-unabsorbed failures.
                audit(job.user,'usage.absorb_failed',job.pk,department=job.encounter.department,error_class=type(absorb_error).__name__)
        audit(job.user,'job.'+job.state,job.pk,department=job.encounter.department,error_class=type(exc).__name__,
              billing='not_adopted' if declined else 'platform_failure' if known and not fixture else 'fixture' if fixture else 'not_processed' if unsent else 'uncertain')
    return True


@transaction.atomic
def cancel(job,user):
    """Cancel a queued request before any provider request. The row lock is the same one run_one takes with skip_locked, so a job
    being picked up is never cancelled and a job being cancelled is never picked up. Held reservations are released; nothing is charged."""
    # Lock the job row only: locking the encounter or department too would invert run_one's encounter-then-job order and deadlock.
    job=Job.objects.select_for_update(of=('self',)).select_related('encounter__department').get(pk=job.pk)
    # The requester may cancel their own queued request; anyone else needs a clinician or owner role in the department.
    membership(user,job.encounter.department,roles=None if job.user_id==user.pk else ['owner','clinician'])
    if job.state!='queued': raise CancellationRefused(CANCEL_REFUSALS.get(job.state,'This request can no longer be cancelled.'))
    job.state='cancelled';job.error=CANCELLED_ERROR;job.finished_at=timezone.now()
    job.request_key=ended_key(job,'cancelled')
    job.save(update_fields=['state','error','finished_at','request_key'])
    release(job)
    audit(user,'job.cancelled',job.pk,department=job.encounter.department,kind=job.kind)
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
            path.unlink(missing_ok=True); removed+=1
            audit(None,'voice.over_limit_upload_removed',event.target,department=event.department,path=relative)
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
            path.unlink(missing_ok=True)
        except OSError: continue
        removed+=1
        audit(None,'voice.stray_submission_removed','',path=relative)
    return removed


def mark_stale():
    for job in Job.objects.filter(state='running',started_at__lt=timezone.now()-timedelta(minutes=5)):
        with transaction.atomic():
            locked=Job.objects.select_for_update().get(pk=job.pk)
            if locked.state!='running':continue
            if locked.config.get('semantic_contract')=='semantic-facts-v1':
                # Current stage activity distinguishes a bounded pipeline from
                # a worker that stopped between independent sends.
                recent=locked.ai_stage_receipts.order_by('-created_at').first()
                activity=(recent.finished_at or recent.started_at or recent.created_at) if recent else locked.started_at
                from .ai_stages import generation_limits,StageNotSent
                try:
                    # SDK I/O timeout plus the existing minute of retention grace;
                    # this is not a claimed whole-pipeline wall-clock deadline.
                    grace=generation_limits(locked.config)[1]+60
                except StageNotSent:
                    grace=120
                if activity and activity>timezone.now()-timedelta(seconds=grace):continue
            locked.state='reconciliation';locked.error='Worker stopped with an unknown provider outcome. Automatic retry is disabled.';locked.save(update_fields=['state','error'])
            audit(locked.user,'job.reconciliation',locked.pk)
