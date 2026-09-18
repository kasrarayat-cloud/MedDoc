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

Bounded on purpose: a wall-clock timeout, capped probe/analyse budgets, no stdin, errors only, and a
plain filesystem path so ffprobe never opens a network protocol. The worker unit additionally caps
the whole cgroup at MemoryMax=1024M and TasksMax=64, so a hostile file cannot exhaust the host.
"""
import json
import shutil
import subprocess
from collections import namedtuple
from decimal import Decimal, InvalidOperation

PROBE_TIMEOUT_SECONDS = 20
PROBE_BUDGET = '10M'          # analyseduration and probesize: enough for real recordings, bounded for hostile ones
MAX_AUDIO_STREAMS = 64

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


def probe_submission(path):
    """Describe the submitted payload, or raise SubmissionUnprobeable. Never guesses."""
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
                                  stdin=subprocess.DEVNULL)
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
    if any(value is None for value in durations):
        reasons.append('an audio stream declares no duration ffprobe could read')

    known = [value for value in durations if value is not None]
    selected = durations[0] if durations and durations[0] is not None else None
    longest = max(known) if known else None
    if selected is None:
        container_seconds = _seconds((described.get('format') or {}).get('duration'))
        if container_seconds is not None:
            selected = longest = container_seconds
            reasons.append('the stream duration is unavailable; the container total is used instead')
    return Submission(container=container, audio_streams=len(streams), selected_seconds=selected,
                      longest_seconds=longest, ambiguous=bool(reasons), reasons=reasons)
