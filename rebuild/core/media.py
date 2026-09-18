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
import resource
import shutil
import subprocess
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
# Measured at the 15 MB upload limit — the real bound, since it caps the work far below the duration cap:
#   WebM/Opus 39:40  2.64 s   ·   WAV 2:35  0.37 s   ·   MP3 30:00  1.92 s   ·   M4A 30:00  2.06 s
# A deliberately adversarial 720,001-packet Opus file reached 14.45 s. So 25 s is roughly ten times the realistic
# worst case and still covers the adversarial one, and total in-flight becomes 25 + 90 = 115 s against 150.
# Exceeding it is a graceful fallback to the original, not a failure — so a tight budget costs normalisation on
# pathological inputs and costs a doctor nothing.
SUBMISSION_BUDGET_SECONDS = 25
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
Submission = namedtuple('Submission', 'container codec audio_streams selected_seconds longest_seconds ambiguous reasons')


class SubmissionUnprobeable(Exception):
    """ffprobe could not describe the payload. The caller must treat coverage as UNKNOWN, never complete."""


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
        raise SubmissionUnprobeable('ffprobe is not installed, so the submitted audio cannot be measured.')
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
        raise SubmissionUnprobeable('ffprobe did not complete: %s' % type(error).__name__) from None
    if finished.returncode != 0:
        # Carry ffprobe's own first line: 'refused the payload' alone hides an invocation error, which
        # is how a broken probe can look like a file problem for every file including valid ones.
        detail = (finished.stderr or b'').decode('utf-8', 'replace').strip().splitlines()
        raise SubmissionUnprobeable('ffprobe refused the payload: %s' % (detail[0] if detail else 'no detail'))
    try:
        described = json.loads(finished.stdout or b'{}')
    except ValueError:
        raise SubmissionUnprobeable('ffprobe returned output that is not JSON.') from None

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

# Codec -> (muxer, suffix). Same container FAMILY as the input on purpose, so both instruments that
# measure a recording — ffprobe and core/audio.py's own parser — can read the output as well as the
# input. Routing Opus to Ogg would have left core/audio.py unable to parse what we submitted.
# ⚠️ NO flac ROW, DELIBERATELY. One was written and it was unreachable: core/audio.py measure_bounds() refuses FLAC
# as an unsupported format long before enqueue reaches plan_normalisation, so no FLAC input can ever arrive here. A
# row that cannot be reached is worse than a missing one — the next reader believes FLAC is a supported input path
# because this table says so. If measure_bounds ever accepts FLAC, this table and jobs.py's SUBMISSION_NAME both
# need the row, and that coupling is the reason it is written down here rather than left as an absence.
CONTAINERS = {'opus': ('webm', '.webm'), 'vorbis': ('webm', '.webm'),
              'mp3': ('mp3', '.mp3'), 'mp3float': ('mp3', '.mp3'),
              'aac': ('ipod', '.m4a'), 'alac': ('ipod', '.m4a')}
PCM_CONTAINER = ('wav', '.wav')


class NotNormalised(Exception):
    """Normalisation did not happen. The caller submits the original unchanged and records this reason."""


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
        raise NotNormalised('the payload does not hold exactly one audio stream')
    codec = (submission.codec or '').lower()
    if codec.startswith('pcm_'):
        return PCM_CONTAINER
    if codec in CONTAINERS:
        return CONTAINERS[codec]
    raise NotNormalised('no lossless remux is defined for %s audio' % (codec or 'unrecognised'))


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
        raise NotNormalised('ffmpeg is not installed')
    argv = [binary, '-nostdin', '-v', 'error', '-hide_banner', '-nostats', '-threads', '1',
            '-analyzeduration', PROBE_BUDGET, '-probesize', PROBE_BUDGET,
            '-i', str(source),
            # The explicit map is the whole point: it names the stream instead of letting a demuxer
            # pick one. plan_normalisation has already refused anything with more than one.
            '-map', '0:a:0', '-c:a', 'copy', '-map_metadata', '-1', '-fflags', '+bitexact',
            '-f', muxer, '-y', str(destination)]
    allowed = NORMALISE_TIMEOUT_SECONDS if deadline is None else min(NORMALISE_TIMEOUT_SECONDS, deadline)
    if allowed <= 0:
        raise NotNormalised('the submission budget was spent before the remux could start')
    try:
        finished = subprocess.run(argv, capture_output=True, timeout=allowed,
                                  stdin=subprocess.DEVNULL, preexec_fn=_bound_normaliser)
    except subprocess.TimeoutExpired:
        raise NotNormalised('ffmpeg did not finish within %g s' % allowed) from None
    # SubprocessError covers a preexec_fn that raises — setrlimit does, when a hard limit is below the value asked for,
    # which is what a unit gaining LimitFSIZE would produce. Uncaught, it escaped prepare_submission AND transcribe's
    # try/finally, leaving a stray artifact and a job in reconciliation with funds held, for what should have been a
    # silent fallback to the original.
    except (subprocess.SubprocessError, OSError) as error:
        raise NotNormalised('ffmpeg could not be run: %s' % type(error).__name__) from None
    if finished.returncode != 0:
        detail = (finished.stderr or b'').decode('utf-8', 'replace').strip().splitlines()
        raise NotNormalised('ffmpeg refused the payload: %s' % (detail[0][:160] if detail else
                                                                'exit %d' % finished.returncode))
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
        raise NotNormalised('the remuxed payload could not be measured: %s' % error) from None
    # A payload we cannot describe exactly is not an improvement on one we could not describe at all.
    if produced.ambiguous or produced.audio_streams != 1 or produced.selected_seconds is None:
        raise NotNormalised('the remuxed payload is not unambiguous: %s'
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
        raise NotNormalised('the remux holds %s s against the source\'s certain %s s'
                            % (produced.selected_seconds, floor_seconds))
    if ceiling_seconds is not None and produced.selected_seconds > ceiling_seconds + NORMALISE_TOLERANCE_SECONDS:
        raise NotNormalised('the remux declares %s s against the source\'s utmost %s s'
                            % (produced.selected_seconds, ceiling_seconds))
    return produced
