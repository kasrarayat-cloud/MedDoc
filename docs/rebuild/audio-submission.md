# What is submitted, what is charged, and what is claimed about coverage

Written 2026-09-18. Three questions that had been collapsed into one, now answered separately,
because conflating any two of them produces a statement nobody can support.

## The fact everything rests on

The uploaded recording is sent to the provider **verbatim**:

    core/jobs.py transcribe():   response=httpx.post(..., content=raw)

`raw` is the bytes of the stored upload. There is no transcoding, no normalisation and no stream
selection. **So the submitted payload IS the uploaded file**, and a question about "what was
submitted" is a question about that file — which is why `core/media.py` probes exactly it. If a
normalisation step is ever introduced, probe its OUTPUT, because that would become the submission.

## Three numbers, three questions

| stored as | what it answers | how it is produced | what it may NOT be used for |
| --- | --- | --- | --- |
| `recording_seconds` | *What is the most audio these bytes could hold?* | `core/audio.py measure_bounds().measured`, by hand, deliberately conservative | anything about what the provider received |
| `recording_seconds_confirmed` | *What length is certain whatever a decoder does?* | the handwritten FLOOR over decoder ambiguity | **judging coverage** — see below |
| `submitted_seconds` | *What is in the payload that was actually POSTed?* | `ffprobe`, explicit stream selection, bounded | pricing (it is not conservative) |

The **charge ceiling** is held against `recording_seconds` and nothing in this change touches money.
The **completeness assessment** uses `submitted_seconds` and nothing else.

## Why the floor could not do this job

A floor over decoder ambiguity is a lower bound on what *some* decoder might play. It is not
evidence about what the provider received, and using it to judge coverage **hides truncation**.

Measured, with ffprobe as the decoder of record:

| fixture | submitted (ffprobe) | priced ceiling | floor |
| --- | --- | --- | --- |
| WAV, chunks 1 s then 9 s | **9.000** | 10.000 | **1.000** |
| WAV, chunks 9 s then 1 s | 1.000 | 10.000 | 1.000 |
| WAV, zero-length trailing chunk | 9.000 | 10.000 | 1.000 |
| WebM, two tracks 30 s and 10 s | 30.008 | 30.021 | **10.020** |

Read the first row. Nine seconds are submitted; the floor says one. If the provider returned one
second, the old rule compared 1 s against a 1 s floor, found them equal, and delivered the transcript
with **no marker at all** — eight seconds silently missing from a clinical note.

## The three outcomes, and the one that is new

`coverage_note()` returns exactly one of:

- **INCOMPLETE** — the provider processed materially less than was submitted. Both numbers are named.
- **coverage UNKNOWN** — the payload does not determine what a decoder would process (more than one
  audio stream), or ffprobe could not describe it. Disclosed as unknown rather than resolved in our
  favour, with the reason, and with the action that fixes it.
- **no claim** — the durations agree. Nothing is asserted.

⚠️ **A MATCHING DURATION IS NOT PROOF THAT EVERY SPOKEN WORD WAS TRANSCRIBED.** It shows the provider
processed about as much audio as was submitted. It says nothing about words inside that audio the
model missed, mis-heard or dropped. The silent case is the ABSENCE of a claim, and no caller, template
or report may render it as a statement of completeness.

## Why ffprobe rather than more handwritten parsing

`core/audio.py` parses WAV, MP3, MP4 and Matroska by hand. That is the right tool for a conservative
ceiling computed before any provider request, and it stays. It is the wrong tool for "what would a
decoder actually play", which is a question about a decoder — so that question is put to one, with:

- explicit stream selection (`-select_streams a`, and the first audio stream is the one reported as
  selected, because that is what a default decoder plays);
- bounded resources — a wall-clock timeout, capped `-analyzeduration` and `-probesize`, stdin closed,
  errors only, and a plain filesystem path so no network protocol is ever opened. The worker unit
  additionally caps the cgroup at `MemoryMax=1024M` and `TasksMax=64`;
- failure that degrades to UNKNOWN, never to a silent success.

⚠️ **A trap worth recording.** The first version of the invocation passed `-nostdin`. `ffprobe` has no
such flag — it parsed it as an option expecting a value, failed, and made **every** payload look
unprobeable, including plainly valid ones. It was caught only because a known-good fixture was in the
comparison. A probe with no positive control cannot tell "this file is bad" from "I am broken".

## Three defects a refutation pass found in this very design

Each was demonstrated on the finished diff, reproduced, and is now pinned by a test that fails if the
defect returns.

**1 · A missing per-stream duration is not ambiguity — and treating it as such broke the PRIMARY
path.** No Matroska variant emits a per-stream duration; measured across opus, vorbis and
live-recorded WebM, ffprobe reports `N/A` for the stream and a good number for the container. The
browser recorder produces exactly that container (`static/app.js`: `audio/webm;codecs=opus`). So
**every ordinary recording** was told its coverage could not be determined — and the advice given,
*re-export as a single track*, was unfollowable, because the file already was one track. The container
total answers the question whenever there is one audio stream; ambiguity is now reserved for payloads
that genuinely do not determine what a decoder would process.

**2 · A declared duration is not a measurement.** ffprobe reads the container's DECLARED duration, and
for MP3 that is the Xing/Info header — precisely the class of field `core/audio.py` refuses to trust,
because a decoder ignores it. An edited frame count claiming an hour for a ten-second file produced
*"the provider processed 0:11 of the 60:12 of audio submitted; 60:02 was not transcribed"* on a
**complete** transcription, and violated this design's own stated invariant that the priced ceiling is
never below the submission. The conservative ceiling computed from the bytes is now the cross-check:
when the declaration exceeds what the bytes can hold, the payload is not describing itself honestly
and the answer is UNKNOWN — never an accusation of data loss.

**3 · The bound was on the wrong process.** `MAX_AUDIO_STREAMS` can only be checked after the parse,
so a hand-built container declaring ~1000 tracks costs ffprobe hundreds of megabytes before it is
rejected — and this code runs on the **request path**, not in the worker: `enqueue()` is called from
the upload view, so the process is a gunicorn worker of the doctor surface, `MemoryMax=768M` shared by
two workers. The earlier docstring cited the worker unit's 1024M, which is not where it runs. The
child now gets an explicit `RLIMIT_AS`, so the cost of a hostile upload is paid by ffprobe dying
rather than by the surface a doctor is using.

## What remains unresolved

- Where the payload carries several audio streams, which one the provider decodes is **not knowable
  from our side**. The honest answer is UNKNOWN, and it is given. Resolving it properly means
  normalising to a single stream before submission — which changes what is sent, and therefore cost
  and quality, and is an owner decision rather than an engineering one.
- ffprobe's reading and the provider's decoder are two different implementations. They agree on every
  fixture exercised here, and that agreement is evidence, not a guarantee.
