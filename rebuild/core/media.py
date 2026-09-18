"""What ffprobe says about the payload that is actually submitted to the provider.

`core/audio.py` answers a different question, conservatively and by hand: *what is the most audio
these bytes could possibly hold*, which is the right basis for a charge ceiling and the wrong basis
for a claim about what was transcribed. A floor taken over decoder ambiguity — the shortest track, the
smallest chunk — is not evidence that the provider received or processed the relevant audio. It was
never meant to be, and it must not be presented as such.

So this module asks the decoder of record, with explicit stream selection, about the exact bytes that
go to the provider. Today those bytes are the uploaded file, submitted verbatim
(`core/jobs.py` transcribe(): `content=raw`). If a normalisation step is ever introduced, probe its
OUTPUT here — the thing submitted — not the original.

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
from collections import namedtuple
from decimal import Decimal, InvalidOperation

PROBE_TIMEOUT_SECONDS = 20
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
Submission = namedtuple('Submission', 'container audio_streams selected_seconds longest_seconds ambiguous reasons')


class SubmissionUnprobeable(Exception):
    """ffprobe could not describe the payload. The caller must treat coverage as UNKNOWN, never complete."""


def _seconds(value):
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return parsed if parsed.is_finite() and parsed >= 0 else None


def probe_submission(path, ceiling_seconds=None):
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
        finished = subprocess.run(argv, capture_output=True, timeout=PROBE_TIMEOUT_SECONDS,
                                  stdin=subprocess.DEVNULL, preexec_fn=_bound_child)
    except (subprocess.TimeoutExpired, OSError) as error:
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
    if len(streams) > MAX_AUDIO_STREAMS:
        raise SubmissionUnprobeable('the payload declares more audio streams than are plausible.')
    container = (described.get('format') or {}).get('format_name') or 'unknown'
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
    return Submission(container=container, audio_streams=len(streams), selected_seconds=selected,
                      longest_seconds=longest, ambiguous=bool(reasons), reasons=reasons)
