"""What ffprobe says about the payload that is actually submitted to the provider.

`core/audio.py` answers a different question, conservatively and by hand: *what is the most audio
these bytes could possibly hold*, which is the right basis for a charge ceiling and the wrong basis
for a claim about what was transcribed. A floor taken over decoder ambiguity — the shortest track, the
smallest chunk — is not evidence that the provider received or processed the relevant audio. It was
never meant to be, and it must not be presented as such.

So this module asks the decoder of record, with explicit stream selection, about the exact bytes that
go to the provider. Since the normalisation below exists, those bytes are usually NOT the uploaded
file: they are the losslessly remuxed artifact, and it is that artifact this module measures. When a
remux is not available the original is submitted unchanged and the original is what is measured. Which
of the two happened is recorded on the job, because 'what was submitted' has to be answerable later.

Bounded on purpose: a wall-clock timeout, an explicit address-space limit on the child, capped
probe/analyse budgets, no stdin, errors only, and a plain filesystem path so ffprobe never opens a
network protocol.

⚠️ THIS RUNS ON THE REQUEST PATH, not in the worker. enqueue() is called from the upload view, so the
process is a gunicorn worker of the doctor surface — MemoryMax=768M shared by two workers, not the
worker unit's 1024M. A per-child RLIMIT_AS is therefore not a belt-and-braces extra; it is the only
thing standing between a hostile upload and the surface a doctor is using.
"""
import json
import re
import resource
import select
import shutil
import subprocess
import tempfile
import time
from collections import namedtuple
from decimal import Decimal, InvalidOperation
from pathlib import Path

PROBE_TIMEOUT_SECONDS = 20
# ⚠️ THE WHOLE PREPARATION IS BOUNDED BY ONE DEADLINE, AND THE NUMBER COMES FROM THE UNIT FILE.
# quillmd-fresh-worker.service sets TimeoutStopSec=150 with KillMode=mixed: after SIGTERM the worker finishes the job it
# is on, and at 150 s systemd SIGKILLs the whole cgroup, ffmpeg included. Before normalisation existed the longest
# uninterruptible stretch inside transcribe() was the 90 s provider POST, leaving 60 s of margin. Summing the
# sub-step ceilings instead (20 probe + 120 remux + 20 probe + 90 POST = 250 s) puts a routine `systemctl restart`
# past that deadline, which kills a worker mid-remux and leaves a job in reconciliation.
# ⚠️ RAISED FROM 25 s TO 45 s WHEN THE DECODE VERIFICATION WAS ADDED, because 25 s was sized for a remux alone and
# the decode is the expensive half. Re-measured at the 15 MB upload limit — probe + remux + decode:
#   WebM/Opus 39:40  14.24 s (decode 13.67)  ·  WAV 2:35  0.83 s  ·  MP3 30:00  8.67 s  ·  M4A 30:00  9.56 s
# At 25 s that left 1.8x of headroom where the remux alone had 9.5x. The decode cannot be made cheaper: measured at
# 1, 2, 4 and auto threads the 40-minute Opus takes 12.1-12.8 s either way (an Opus stream decodes serially), and
# dropping the resample saves 0.4 s of 12.
#
# ⚠️ AND EXCEEDING IT IS NO LONGER A FALLBACK — IT IS A REFUSED RECORDING, which makes this sizing a real trade
# rather than a tuning knob. Total in-flight becomes 45 + 90 = 135 s against the worker unit's TimeoutStopSec=150,
# so the margin there falls from 35 s to 15 s. That is the right way round: overrunning the unit deadline costs a
# SIGKILL on a restart that happens to land inside the window — recoverable through reconciliation, and only on a
# restart — while too small a budget refuses a doctor's forty-minute recording on a loaded host.
SUBMISSION_BUDGET_SECONDS = 45
PROBE_BUDGET = '10M'          # analyseduration and probesize: enough for real recordings, bounded for hostile ones
MAX_AUDIO_STREAMS = 64
# A hand-built Matroska declaring ~1000 TrackEntry elements costs ffprobe ~264 MB of RSS before a
# single byte of audio is read — and MAX_AUDIO_STREAMS cannot help, because the count is only known
# after the parse. The child gets its own address-space ceiling so the cost is paid by ffprobe dying,
# not by the doctor's request surface.
PROBE_ADDRESS_SPACE_BYTES = 512 * 1024 * 1024


def _bound_child():
    """Runs in the forked child, before exec: cap address space and core files."""
    resource.setrlimit(resource.RLIMIT_AS, (PROBE_ADDRESS_SPACE_BYTES, PROBE_ADDRESS_SPACE_BYTES))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

# selected_seconds: the first audio stream — what a default decoder plays, and so what the provider
#   most likely processed. longest_seconds: the longest audio stream, for the honest upper end.
# ambiguous: the payload does not determine what a decoder would process. reasons: why, in words.
# codec: the selected stream's codec, which decides whether a lossless remux is available at all.
# decoded_seconds: what a decoder actually produced from the artifact, as distinct from what its container declares.
# '' until the artifact has been decoded; only a submitted artifact ever carries one.
Submission = namedtuple('Submission', 'container codec audio_streams selected_seconds longest_seconds ambiguous reasons '
                                      'decoded_seconds', defaults=(None,))


class SubmissionUnprobeable(Exception):
    """ffprobe could not describe the payload.

    ⚠️ IT CARRIES A KIND FOR THE SAME REASON NotNormalised DOES, AND THE FIRST VERSION DID NOT. The caller mapped every
    one of these to UNREADABLE — 'this recording could not be read as audio, re-export it' — and four unrelated causes
    arrive here: ffprobe is not installed; ffprobe timed out or could not be forked; ffprobe returned something that is
    not JSON; and ffprobe read the file and refused it. **Only the last is about the file.** On a host where ffprobe is
    missing or cannot fork, every doctor was told their own recording was broken and not to retry — attributing a
    platform outage to the one place it certainly was not, in the one record an operator would use to localise it.
    """

    def __init__(self, kind, detail=''):
        super().__init__(detail or kind)
        self.kind = kind
        self.detail = detail or kind


def _seconds(value):
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return parsed if parsed.is_finite() and parsed >= 0 else None


def probe_submission(path, ceiling_seconds=None, timeout=None):
    """Describe the submitted payload, or raise SubmissionUnprobeable. Never guesses.

    `ceiling_seconds` is the conservative upper bound computed from the bytes themselves
    (`core/audio.py measure_bounds().measured`). It is the cross-check, and it is not optional in
    spirit: ffprobe reads a container's DECLARED duration, and for MP3 that is a Xing/Info header
    field — exactly the class of field `core/audio.py` refuses to trust, because a decoder ignores it.
    An edited header can claim an hour for a ten-second file. Believing it produced
    'the provider processed 0:11 of the 60:12 submitted; 60:02 was not transcribed' on a complete
    recording. When the declared duration exceeds what the bytes can hold, the payload is not
    describing itself honestly and the answer is UNKNOWN, never a false accusation of data loss.
    """
    binary = shutil.which('ffprobe')
    if not binary:
        raise SubmissionUnprobeable(UNAVAILABLE, 'ffprobe is not installed')
    # No -nostdin: ffprobe (unlike ffmpeg) has no such flag and parses it as an option expecting a
    # value, so the whole invocation fails and EVERY payload looks unprobeable. stdin is closed below
    # instead, which is stronger than the flag would have been.
    argv = [binary, '-v', 'error', '-hide_banner',
            '-analyzeduration', PROBE_BUDGET, '-probesize', PROBE_BUDGET,
            '-select_streams', 'a',
            '-show_entries', 'format=format_name,duration:stream=index,codec_name,duration',
            '-of', 'json', str(path)]
    try:
        finished = subprocess.run(argv, capture_output=True,
                                  timeout=max(0.1, PROBE_TIMEOUT_SECONDS if timeout is None else timeout),
                                  stdin=subprocess.DEVNULL, preexec_fn=_bound_child)
    # subprocess.SubprocessError, not TimeoutExpired alone: a preexec_fn that raises — which setrlimit does when a
    # hard limit is lower than the value asked for — surfaces as a bare SubprocessError, and letting that escape
    # turned a benign fallback into a job stuck in reconciliation with the doctor's funds still held.
    except (subprocess.SubprocessError, OSError) as error:
        # A timeout or a failed fork is the host being unable to run the tool. Re-sending the same bytes can work.
        kind = TOO_SLOW if isinstance(error, subprocess.TimeoutExpired) else UNAVAILABLE
        raise SubmissionUnprobeable(kind, 'ffprobe did not complete: %s' % type(error).__name__) from None
    if finished.returncode != 0:
        # Carry ffprobe's own first line: 'refused the payload' alone hides an invocation error, which
        # is how a broken probe can look like a file problem for every file including valid ones.
        detail = (finished.stderr or b'').decode('utf-8', 'replace').strip().splitlines()
        # THIS one is about the file: ffprobe read it and would not describe it.
        raise SubmissionUnprobeable(UNREADABLE, 'ffprobe refused the payload: %s' % (detail[0] if detail else 'no detail'))
    try:
        described = json.loads(finished.stdout or b'{}')
    except ValueError:
        raise SubmissionUnprobeable(UNAVAILABLE, 'ffprobe returned output that is not JSON') from None

    streams = described.get('streams') or []
    container = (described.get('format') or {}).get('format_name') or 'unknown'
    if len(streams) > MAX_AUDIO_STREAMS:
        # ⚠️ THIS USED TO RAISE, AND RAISING MADE THE CALLER'S REFUSAL FAIL OPEN AT THE POINT OF MAXIMUM AMBIGUITY.
        # describe_submission maps every SubmissionUnprobeable to submission_streams='', and the enqueue guard reads
        # `streams.isdigit() and int(streams) > 1` — which is False for ''. So a two-track file was refused and a
        # SIXTY-FIVE-track file was accepted, held against and charged for, with the provider picking one of the 65.
        # Measured: 65-track M4A -> job created, $0.06 held, one provider request, $0.0525 charged.
        # The count is already known here; the parse is already paid for. Returning it is what lets the caller refuse.
        return Submission(container=container, codec='', audio_streams=len(streams), selected_seconds=None,
                          longest_seconds=None, ambiguous=True,
                          reasons=['%d audio streams: more than any recording plausibly has, and which one the '
                                   'provider decodes is not determined by the payload' % len(streams)])
    durations = [_seconds(stream.get('duration')) for stream in streams]

    reasons = []
    if not streams:
        reasons.append('ffprobe found no audio stream in the submitted payload')
    if len(streams) > 1:
        reasons.append('%d audio streams: which one the provider decodes is not determined by the payload'
                       % len(streams))

    known = [value for value in durations if value is not None]
    selected = durations[0] if durations and durations[0] is not None else None
    longest = max(known) if known else None
    container_seconds = _seconds((described.get('format') or {}).get('duration'))
    if selected is None:
        # ⚠️ A MISSING PER-STREAM DURATION IS NOT AMBIGUITY, and treating it as such put a false
        # 'coverage UNKNOWN' on the product's PRIMARY path. No Matroska variant emits a per-stream
        # duration — measured across opus, vorbis and live-recorded WebM — and the browser recorder
        # produces exactly that container (static/app.js: 'audio/webm;codecs=opus'). So every ordinary
        # recording was told its coverage could not be determined, with a remedy ('re-export as a
        # single track') that was unfollowable because the file already WAS a single track.
        # The container total answers the question perfectly well when there is one audio stream.
        if container_seconds is not None:
            selected = longest = container_seconds
            if len(streams) > 1:
                reasons.append('no stream declares a duration, so the container total cannot be '
                               'attributed to any one of them')
        else:
            reasons.append('neither the stream nor the container declares a duration ffprobe could read')

    # The cross-check. A declared duration the bytes cannot support is a lie, not a measurement.
    if selected is not None and ceiling_seconds is not None and selected > ceiling_seconds:
        reasons.append('the payload declares %s s of audio but its bytes can hold at most %s s, so its '
                       'declared duration is not trustworthy' % (selected, ceiling_seconds))
    codec = str((streams[0].get('codec_name') or '')) if streams else ''
    return Submission(container=container, codec=codec, audio_streams=len(streams), selected_seconds=selected,
                      longest_seconds=longest, ambiguous=bool(reasons), reasons=reasons)


# ── Normalisation ──────────────────────────────────────────────────────────
# What goes to the provider is decided HERE, by us, and then measured. Before this, the uploaded bytes
# were POSTed verbatim and the provider's own demuxer decided what to decode — including which of
# several audio streams, silently. Measured on a two-stream Matroska: ffmpeg with no -map emits one
# stream and says nothing.
#
# The conversion is a LOSSLESS REMUX and nothing else: -c:a copy moves the coded audio frames into a
# clean container of the same family. No -ar, no -ac, no -t, no -ss — no resampling, no downmix, no
# trimming, no stream mixing. Measured on a 10 s tone in each accepted format, decoding the source and
# the output to raw s16le gave byte-identical samples in all four cases.
#
# What it removes is exactly the debris that made these inputs unpredictable:
#   · a trailing ID3v1 tag and 4 KB of junk after it — 84,717 bytes in, 80,493 out, the byte-for-byte
#     size of the untagged original, duration unchanged;
#   · an MP4 edit list delaying the start — start_time 1.478 in, 0.000 out, duration unchanged.
#
# Re-encoding is deliberately NOT a fallback. Transcoding a compressed source to PCM would inflate a
# 47 KB WebM past the 15 MB submission limit at around two and a half minutes, and transcoding to
# another lossy codec would discard audio to save bytes. When a lossless remux is not available the
# original is submitted unchanged, exactly as before, and the reason is recorded — never a silent
# downgrade of the audio a doctor recorded.
NORMALISE_TIMEOUT_SECONDS = 120     # the per-child ceiling; SUBMISSION_BUDGET_SECONDS is what actually binds
# ⚠️ SIZED AGAINST A MEASURED BASELINE, BECAUSE THE FIRST VALUE READ AS FAR MORE ROOM THAN IT GAVE. This Ubuntu ffmpeg
# links ~200 shared objects, so a trivial copy remux already maps 413-422 MB of address space before touching the
# input: a 512 MB cap left ~90 MB of working room, not 512. Measured peak VSZ / RSS over the four accepted formats at
# the 15 MB upload limit: WebM 414/51, WAV 413/47, MP3 414/49, M4A 422/58 MB.
# RLIMIT_AS bounds ADDRESS SPACE; the unit's MemoryMax=1024M and MemorySwapMax=0 bound resident memory, and RSS never
# exceeded 58 MB. So this is a backstop against pathological mapping, and it is sized with real headroom above a
# measured baseline rather than at a round number that happened to sit just above it.
NORMALISE_ADDRESS_SPACE_BYTES = 768 * 1024 * 1024
# RLIMIT_FSIZE is the output-size limit, and it is enforced by the kernel rather than by a check afterwards: ffmpeg is
# killed with SIGXFSZ the moment it writes past it, so a runaway output costs a dead child and a fallback, not a full
# disk on a shared host. Verified: rc = -25 on all four muxers, and the partial file is unlinked.
# ⚠️ IT IS A DISK BACKSTOP AND NOT A SUBMISSION-SIZE CHECK, AND THE ORIGINAL COMMENT CLAIMED OTHERWISE. It said
# "anything that would be refused at submission dies here first", which left a 1 MB window this landed in: an MP3 at
# exactly the 15,728,640-byte upload limit, with no Xing header and no ID3 tag, remuxes to 15,729,077 bytes — the
# muxer ADDS an ID3v2 header and a Xing frame — so the artifact is over the submission limit and under this one.
# ffmpeg is not killed, the remux succeeds, and the caller must fall back. That fallback now lives in
# core/jobs.py prepare_submission(); growth measured on tagless CBR MP3: +202 B at 32k, +437 B at 128k, +1064 B at 320k.
NORMALISE_MAX_OUTPUT_BYTES = 16 * 1024 * 1024
# The only slack in the loss and gain checks, so it decides both whether a real recording can be wrongly refused and
# whether real loss can slip through. MEASURED, not chosen: 31 recordings across every accepted format at 0.3, 1, 5,
# 60 and 600 seconds — CBR and VBR MP3, stereo, 24-bit WAV, 8 kHz dictaphone WAV, a MediaRecorder-shaped WebM with no
# seekable duration, an MP3 carrying an ID3v2 tag. The deviation is CONSTANT IN ABSOLUTE TERMS at every length —
# WebM +0.008 s, MP3 -0.024 s, M4A -0.021 s against the source's certain length, identical at 0.3 s and at 600 s —
# because it is per-file container framing and not drift that accumulates. Largest observed: 0.024 s below the floor,
# 0.007 s above the ceiling.
#
# ⚠️ TIGHTENED FROM 0.25 s ON THAT EVIDENCE. 0.25 was about six times the worst real rounding, which sounds safe and
# is the wrong direction to be generous in: it accepted a remux silently losing up to 0.23 s of a doctor's audio.
# The two errors are not symmetric. Refusing wrongly costs a fallback to submitting the original unchanged — exactly
# what happened before this code existed, and harmful to nobody. Accepting wrongly costs audio nobody can detect.
# 0.1 s keeps every measured case with 4x margin on the loss side and 14x on the gain side, and cuts the
# undetectable-loss window by more than half.
NORMALISE_TOLERANCE_SECONDS = Decimal('0.1')
# The decode verification resamples to a known rate purely so the byte count converts to seconds exactly. It touches
# nothing that is submitted. 16 kHz mono s16le is 32 kB per second, so the cap below is about two hours of audio —
# far above the upload limit, and a bound rather than a budget.
# ⚠️ ITS OWN TOLERANCE, NOT THE REMUX ONE, because it measures a different disagreement. The remux tolerance compares
# the artifact against core/audio.py's hand measurement of the SOURCE (worst observed 0.024 s). This compares two
# views of the SAME artifact — what its container declares against what a decoder produces — and encoder padding and
# container framing pull those apart further: measured across every accepted format at 0.3, 1, 5, 60 and 600 seconds,
# worst |decoded − declared| is 0.040 s (MP3 at 0.3 s), with WebM constant at −0.028 and M4A up to +0.020.
# Sharing one constant would have left 2.5x of margin on the product's primary path, where a false stop costs a
# doctor a recording. 0.25 s is about six times the worst real case and still catches every failure this exists for —
# an artifact that declares a minute and decodes to nothing is out by tens of seconds, not tenths.
DECODE_TOLERANCE_SECONDS = Decimal('0.25')
DECODE_RATE = 16000
DECODE_MAX_BYTES = 256 * 1024 * 1024

# Codec -> (muxer, suffix). Same container FAMILY as the input on purpose, so both instruments that
# measure a recording — ffprobe and core/audio.py's own parser — can read the output as well as the
# input. Routing Opus to Ogg would have left core/audio.py unable to parse what we submitted.
# ⚠️ NO flac AND NO vorbis ROW, DELIBERATELY — both were written and both were unreachable. core/audio.py's
# Matroska reader is Opus-only and says so in its own docstring, so a Vorbis WebM is refused at measurement long
# before it could reach this table; measured, it stops with 'WebM audio that is not Opus'. The flac row had the same
# shape, and this is the second time the same mistake was made in the same dictionary.
# ⚠️ NO flac ROW, DELIBERATELY. One was written and it was unreachable: core/audio.py measure_bounds() refuses FLAC
# as an unsupported format long before enqueue reaches plan_normalisation, so no FLAC input can ever arrive here. A
# row that cannot be reached is worse than a missing one — the next reader believes FLAC is a supported input path
# because this table says so. If measure_bounds ever accepts FLAC, this table and jobs.py's SUBMISSION_NAME both
# need the row, and that coupling is the reason it is written down here rather than left as an absence.
CONTAINERS = {'opus': ('webm', '.webm'),
              'mp3': ('mp3', '.mp3'), 'mp3float': ('mp3', '.mp3'),
              'aac': ('ipod', '.m4a'), 'alac': ('ipod', '.m4a')}
PCM_CONTAINER = ('wav', '.wav')


class NotNormalised(Exception):
    """Processing did not complete. NOTHING IS SUBMITTED — the caller stops before the provider.

    ⚠️ THIS USED TO MEAN 'submit the original unchanged', and that fallback is now removed as unsafe. It made every
    processing failure invisible: the provider received bytes we had not measured, decided for itself what to decode,
    and the doctor was charged for whatever came back. A step that silently stops running is worse than one that
    fails, because nothing anywhere says which of the two happened.

    `kind` selects the FIXED, user-safe sentence shown to the doctor. It is a key, never free text: ffmpeg's stderr
    carries private storage paths, and `failure_reason()` shows a NoProviderRequest's message verbatim.
    `detail` is the technical reason, for the audit row only, and it is scrubbed before it is recorded.
    """

    def __init__(self, kind, detail=''):
        super().__init__(detail or kind)
        self.kind = kind
        self.detail = detail or kind


# What the doctor is told, per failure class. Fixed strings: nothing from a subprocess reaches a user or a ledger.
# `run_one` wraps these in 'Not processed: … No provider request was made; nothing was charged and the held funds
# were released.', so each one reads as the middle of that sentence.
MISSING = 'missing'
UNAVAILABLE = 'unavailable'
TOO_SLOW = 'too_slow'
UNREADABLE = 'unreadable'
AMBIGUOUS = 'ambiguous'
TOO_LARGE = 'too_large'
REFUSAL_TEXT = {
    # ⚠️ ITS WORDING IS FIXED BY AN EXISTING REGRESSION TEST AND BY WHAT IS TRUE: the upload is gone from storage. That
    # is the platform's failure, not a fault in the doctor's file, and telling them to re-export would send them
    # looking in the one place the problem certainly is not.
    MISSING: 'The recording is not available.',
    UNAVAILABLE: ('Recording processing is temporarily unavailable, so this recording was not sent. '
                  'Try again in a few minutes.'),
    TOO_SLOW: ('This recording took too long to prepare, so it was not sent. Try again, or upload a shorter '
               'segment.'),
    UNREADABLE: ('This recording could not be read as audio, so it was not sent. Re-export it as a single audio '
                 'track and upload that.'),
    AMBIGUOUS: ('This recording does not decide which audio a transcriber would process, so it was not sent. '
                'Export it as a single audio track and upload that.'),
    TOO_LARGE: ('This recording is too large to send once prepared. Upload a shorter segment.'),
}
# ⚠️ RETRYABLE IS A PROPERTY OF THE CAUSE, NOT A TONE OF VOICE. Re-sending the same bytes fixes a busy host or a
# missing tool; it can never fix a file that does not decide what it contains. Saying 'try again' about the second
# class trains a doctor to retry something that will fail identically forever.
RETRYABLE = {UNAVAILABLE, TOO_SLOW}


def refusal_text(kind):
    return REFUSAL_TEXT.get(kind, REFUSAL_TEXT[UNREADABLE])


def scrubbed(detail):
    """The technical reason with filesystem paths removed, for the audit row.

    ffmpeg and ffprobe quote the path they were given, and that path is inside protected storage. It reached the
    audit row, `Usage.units` and the billing page's usage-evidence block in the previous version.
    """
    return re.sub(r'(/[^\s:,()\']+)+', '<path>', str(detail))[:200]


def _bound_normaliser():
    """Runs in the forked child, before exec.

    RLIMIT_NPROC is deliberately NOT set, and that decision is verified: Linux counts threads UID-WIDE, and all three
    services run as one UID. With a soft limit of 5 against a UID already owning 158 tasks, thread creation fails with
    `can't start new thread` and fork with EAGAIN — so a limit tight enough to bound ffmpeg is one the co-resident
    gunicorn workers already exceed.

    ⚠️ AND `-threads 1` IS NOT WHAT BOUNDS THE THREAD COUNT — the earlier wording said it was, and it is measurably
    false. ffmpeg 6.1.1 runs threaded demux and mux regardless, and `-c:a copy` has no codec for `-threads` to govern:
    measured 3 tasks, not 1, on every accepted format. What actually bounds it is the unit's TasksMax=64. `-threads 1`
    stays because it is still the right request; it is simply not the guarantee."""
    resource.setrlimit(resource.RLIMIT_AS, (NORMALISE_ADDRESS_SPACE_BYTES, NORMALISE_ADDRESS_SPACE_BYTES))
    resource.setrlimit(resource.RLIMIT_FSIZE, (NORMALISE_MAX_OUTPUT_BYTES, NORMALISE_MAX_OUTPUT_BYTES))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def plan_normalisation(submission):
    """(muxer, suffix) for a submission that can be losslessly remuxed, or raise NotNormalised."""
    if submission.audio_streams != 1:
        raise NotNormalised(AMBIGUOUS, 'the payload holds %d audio streams' % submission.audio_streams)
    codec = (submission.codec or '').lower()
    if codec.startswith('pcm_'):
        return PCM_CONTAINER
    if codec in CONTAINERS:
        return CONTAINERS[codec]
    raise NotNormalised(UNREADABLE, 'no lossless remux is defined for %s audio' % (codec or 'unrecognised'))


def normalise_submission(source, destination, submission, floor_seconds=None, ceiling_seconds=None, deadline=None):
    """Remux the one audio stream of `source` into `destination`, losslessly, and describe the result.

    `floor_seconds` and `ceiling_seconds` are core/audio.py's two hand measurements of the SOURCE — what it certainly
    holds, and the most it could hold. They bracket the artifact, and each is used for the job it was designed for.

    Raises NotNormalised for every failure. There is no partial success: the destination is removed on
    any error, so the caller is never handed a truncated payload to submit.
    """
    # ⚠️ ONE OWNER, NOT NINE REPEATS. The docstring promises the destination is removed on any error, and the first
    # version delivered that by unlinking at each raise — which is how the `ffmpeg is not installed` arm came to be the
    # one that forgot, leaking a zero-byte file per job on a host without ffmpeg, and how plan_normalisation's own
    # refusal was never covered at all. A promise kept in nine places is one edit away from being broken in a tenth.
    destination = Path(destination)
    try:
        return _remux(source, destination, submission, floor_seconds, ceiling_seconds, deadline)
    except BaseException:
        destination.unlink(missing_ok=True)
        raise


def _remux(source, destination, submission, floor_seconds, ceiling_seconds, deadline):
    """The remux itself. Every exit but the last raises; the caller above owns the cleanup for all of them."""
    started = time.monotonic()
    muxer, _ = plan_normalisation(submission)
    binary = shutil.which('ffmpeg')
    if not binary:
        # ⚠️ THIS ARM USED TO RETURN WITHOUT UNLINKING, and the caller creates the destination before calling in, so a
        # host without ffmpeg leaked one zero-byte file into private storage per transcription — no crash involved,
        # which is what the stray reaper's comment assumed. The function's contract is that nothing survives a failure;
        # every arm now honours it, including this one, and the caller has its own guard behind it.
        raise NotNormalised(UNAVAILABLE, 'ffmpeg is not installed')
    argv = [binary, '-nostdin', '-v', 'error', '-hide_banner', '-nostats', '-threads', '1',
            '-analyzeduration', PROBE_BUDGET, '-probesize', PROBE_BUDGET,
            '-i', str(source),
            # The explicit map is the whole point: it names the stream instead of letting a demuxer
            # pick one. plan_normalisation has already refused anything with more than one.
            '-map', '0:a:0', '-c:a', 'copy', '-map_metadata', '-1', '-fflags', '+bitexact',
            '-f', muxer, '-y', str(destination)]
    allowed = NORMALISE_TIMEOUT_SECONDS if deadline is None else min(NORMALISE_TIMEOUT_SECONDS, deadline)
    if allowed <= 0:
        raise NotNormalised(TOO_SLOW, 'the submission budget was spent before the remux could start')
    try:
        finished = subprocess.run(argv, capture_output=True, timeout=allowed,
                                  stdin=subprocess.DEVNULL, preexec_fn=_bound_normaliser)
    except subprocess.TimeoutExpired:
        raise NotNormalised(TOO_SLOW, 'ffmpeg did not finish within %g s' % allowed) from None
    # SubprocessError covers a preexec_fn that raises — setrlimit does, when a hard limit is below the value asked for,
    # which is what a unit gaining LimitFSIZE would produce. Uncaught, it escaped prepare_submission AND transcribe's
    # try/finally, leaving a stray artifact and a job in reconciliation with funds held, for what should have been a
    # silent fallback to the original.
    except (subprocess.SubprocessError, OSError) as error:
        raise NotNormalised(UNAVAILABLE, 'ffmpeg could not be run: %s' % type(error).__name__) from None
    if finished.returncode != 0:
        detail = (finished.stderr or b'').decode('utf-8', 'replace').strip().splitlines()
        # ⚠️ SIGXFSZ IS A SIZE FAILURE, NOT A BROKEN FILE, and telling a doctor to re-export would be a dead end.
        # RLIMIT_FSIZE kills with signal 25, which surfaces as returncode -25.
        kind = TOO_LARGE if finished.returncode == -25 else UNREADABLE
        raise NotNormalised(kind, 'ffmpeg exited %d: %s' % (finished.returncode,
                                                            detail[0][:160] if detail else 'no detail'))
    # ⚠️ THE OUTPUT IS NOT PROBED AGAINST THE SOURCE'S CEILING, AND THE FIRST VERSION OF THIS WAS.
    # `ceiling_seconds` comes from core/audio.py's hand measurement of the SOURCE, and it exists to catch a container
    # header claiming more audio than the bytes could hold. An artifact we produced ourselves is not that risk — but it
    # does round differently: a copy-remuxed WebM declared 4.028 s where the hand measurement of its source said 4.021 s,
    # 7 ms over, so every ordinary browser recording was judged 'not trustworthy' and fell back to the original. The
    # product's PRIMARY path silently stopped being normalised while every test still passed.
    # The honest check on an artifact is against the thing it was made from, on BOTH sides, and it is below.
    try:
        produced = probe_submission(destination,
                                     timeout=None if deadline is None else deadline - (time.monotonic() - started))
    except SubmissionUnprobeable as error:
        raise NotNormalised(UNREADABLE, 'the remuxed payload could not be measured: %s' % error) from None
    # A payload we cannot describe exactly is not an improvement on one we could not describe at all.
    if produced.ambiguous or produced.audio_streams != 1 or produced.selected_seconds is None:
        raise NotNormalised(UNREADABLE, 'the remuxed payload is not unambiguous: %s'
                            % ('; '.join(produced.reasons)[:160] or 'no duration'))
    # THE LOSS AND GAIN CHECKS, bracketed by core/audio.py's two hand measurements of the source.
    #
    # ⚠️ THE ARTIFACT IS NOT COMPARED TO THE SOURCE'S *DECLARED* DURATION, AND THE FIRST VERSION OF THIS WAS. ffprobe
    # estimates an MP3's length from its size, so 4 KB of junk appended after a trailing tag made the source declare
    # 4.560 s of audio it does not contain. The remux — correctly, this is the debris it exists to remove — produced
    # 4.032 s, and comparing the two declarations refused the very case the feature was built for. A declaration
    # inflated by junk is not a measurement of audio, which is the whole reason core/audio.py exists.
    #
    # LOSS is measured against the FLOOR, the length the source certainly holds: an artifact shorter than that has lost
    # real audio — a remux killed by the output-size limit, cut short by the timeout, or copied wrong — and the original
    # is submitted instead.
    # GAIN is measured against the CEILING, the most the source could hold: an artifact declaring more than that is our
    # own muxer making an untrustworthy claim, and believing it would let a payload accuse the provider of dropping
    # audio that never existed. Only container rounding is tolerated — a copy-remuxed WebM declares about 7 ms more
    # than the hand measurement of its source, with byte-identical decoded samples.
    if floor_seconds is not None and produced.selected_seconds < floor_seconds - NORMALISE_TOLERANCE_SECONDS:
        raise NotNormalised(UNREADABLE, 'the remux holds %s s against the source\'s certain %s s'
                            % (produced.selected_seconds, floor_seconds))
    if ceiling_seconds is not None and produced.selected_seconds > ceiling_seconds + NORMALISE_TOLERANCE_SECONDS:
        raise NotNormalised(UNREADABLE, 'the remux declares %s s against the source\'s utmost %s s'
                            % (produced.selected_seconds, ceiling_seconds))
    decoded_seconds = decodes(destination, deadline=None if deadline is None else deadline - (time.monotonic() - started))
    # The decoder and the container must agree about how much audio is there. A container can declare a length it
    # cannot deliver; the tolerance is the same container rounding measured everywhere else.
    if abs(decoded_seconds - produced.selected_seconds) > DECODE_TOLERANCE_SECONDS:
        raise NotNormalised(UNREADABLE, 'the artifact declares %s s and decodes to %s s'
                            % (produced.selected_seconds, decoded_seconds))
    return produced._replace(decoded_seconds=decoded_seconds)


def decodes(path, deadline=None):
    """Decode the artifact and return the seconds that actually came out, or raise NotNormalised.

    ⚠️ A SUCCESSFUL REMUX IS NOT VALID AUDIO, AND THE TWO WERE TREATED AS THE SAME THING. `ffmpeg -c:a copy` moves
    frames without decoding them and exits 0 on a container whose frames no decoder can use; ffprobe then reports the
    duration the CONTAINER DECLARES, which is a header field, not a measurement. So an artifact could be produced,
    measured, submitted and charged for while holding nothing a transcriber could read.

    ⚠️ AND THE ANSWER CANNOT COME FROM ffprobe AGAIN — the first version of this ended `return probe_submission(path)
    .selected_seconds`, which compares the declared duration with itself and can never disagree. The count here is of
    decoded SAMPLES: the decode is forced to 16 kHz mono s16le so the byte count converts exactly, which changes
    nothing about the payload because this output is thrown away. Resampling preserves duration; it is the sample
    RATE that is normalised for counting, never the audio that is submitted.

    The bytes are counted as they stream and never held: a 60-minute recording moves 115 MB through this and occupies
    a 64 KB buffer. `-map 0:a:0` names the same stream the remux selected, so what is verified is what is submitted.
    """
    binary = shutil.which('ffmpeg')
    if not binary:
        raise NotNormalised(UNAVAILABLE, 'ffmpeg is not installed')
    allowed = NORMALISE_TIMEOUT_SECONDS if deadline is None else min(NORMALISE_TIMEOUT_SECONDS, deadline)
    if allowed <= 0:
        raise NotNormalised(TOO_SLOW, 'the submission budget was spent before the artifact could be decoded')
    argv = [binary, '-nostdin', '-v', 'error', '-hide_banner', '-nostats', '-threads', '1',
            '-i', str(path), '-map', '0:a:0', '-ac', '1', '-ar', str(DECODE_RATE), '-f', 's16le', '-']
    counted = 0
    deadline_at = time.monotonic() + allowed
    # stderr goes to a file rather than a pipe: at -v error it is nearly always empty, and a pipe nobody drains while
    # stdout is being read is the classic way to deadlock a subprocess.
    with tempfile.TemporaryFile() as errors:
        try:
            child = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=errors, stdin=subprocess.DEVNULL,
                                     preexec_fn=_bound_normaliser)
        except (subprocess.SubprocessError, OSError) as error:
            raise NotNormalised(UNAVAILABLE, 'the decoder could not be run: %s' % type(error).__name__) from None
        try:
            # ⚠️ THE DEADLINE IS CHECKED BEFORE EACH READ, NOT AFTER ONE. The first version tested the clock only
            # after a non-empty read returned, so a child that produced nothing and never exited was never timed out:
            # it blocked in read() indefinitely and only the outer watchdog stopped it. `select` waits for data OR for
            # the remaining budget, whichever comes first, so a silent child is bounded by the same number as a slow
            # one. read1() returns what one read syscall gives rather than blocking for a full buffer.
            while True:
                remaining = deadline_at - time.monotonic()
                if remaining <= 0:
                    raise NotNormalised(TOO_SLOW, 'decoding did not finish within %g s' % allowed)
                if not select.select([child.stdout], [], [], remaining)[0]:
                    raise NotNormalised(TOO_SLOW, 'the decoder produced nothing for %g s' % allowed)
                block = child.stdout.read1(65536)
                if not block:
                    break
                counted += len(block)
                if counted > DECODE_MAX_BYTES:
                    raise NotNormalised(TOO_LARGE, 'decoding produced more than %d bytes' % DECODE_MAX_BYTES)
        finally:
            child.stdout.close()
            if child.poll() is None:
                child.kill()
            child.wait(timeout=10)
        errors.seek(0)
        noise = errors.read().decode('utf-8', 'replace').strip().splitlines()
    # ⚠️ EXIT 0 IS NOT ENOUGH. ffmpeg reports a corrupt or undecodable packet on stderr and still exits 0 for many
    # inputs, so a payload that loses frames to the decoder would pass a returncode check while holding less audio
    # than it claims. At -v error the stream is silent on a clean decode, so any line at all is a finding.
    if child.returncode != 0 or noise:
        raise NotNormalised(UNREADABLE, 'decoding reported %s' % (noise[0][:160] if noise
                                                                  else 'exit %d' % child.returncode))
    if counted <= 0:
        raise NotNormalised(UNREADABLE, 'decoding produced no audio at all')
    return (Decimal(counted) / Decimal(DECODE_RATE * 2)).quantize(Decimal('0.001'))
