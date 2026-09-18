# What is submitted, what is charged, and what is claimed about coverage

Written 2026-09-18. Three questions that had been collapsed into one, now answered separately,
because conflating any two of them produces a statement nobody can support.

## The fact everything rests on

⚠️ **SUPERSEDED 2026-09-18 BY THE NORMALISATION BELOW. The original wording is kept because it is
what the code did, and because the paragraph it ends with is the instruction the change had to obey.**

> The uploaded recording is sent to the provider **verbatim**:
>
>     core/jobs.py transcribe():   response=httpx.post(..., content=raw)
>
> `raw` is the bytes of the stored upload. There is no transcoding, no normalisation and no stream
> selection. **So the submitted payload IS the uploaded file**, and a question about "what was
> submitted" is a question about that file — which is why `core/media.py` probes exactly it. If a
> normalisation step is ever introduced, probe its OUTPUT, because that would become the submission.

**What is true now:** the payload is usually a losslessly remuxed artifact built from the upload, and
the measurement is taken of that artifact — the bytes POSTed — exactly as the last sentence above
required. When no lossless remux is available the original is submitted unchanged, as before, and
the record says which of the two happened. See *Deterministic submission*, below.

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

## The outcomes, and the one that is new

⚠️ **There are FOUR now, not three** — a fourth was added on 2026-09-18 for loss that happens BEFORE the provider request. See *The fourth outcome*, below.

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

### The fourth outcome — loss before the request

Added 2026-09-18, after a lens demonstrated that the first three were all about the PROVIDER's side of the transfer.
Nothing asked whether what we submitted was materially less than the recording we measured and priced, so any loss
before the request was invisible by construction and the transcript said nothing at all.

    [Only 0:02 of this recording could be read as audio, although the file could hold up to 0:11.
     That 0:02 is what was sent for transcription; nothing is claimed about the rest.]

It offers no reason, deliberately. The payload may be short because of a trimming edit list, a second `data` chunk no
decoder reaches, or bytes after the audio that were never audio at all — and distinguishing those from the file alone
is not something this code can do. It states the two measurements and stops.

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

- ~~Where the payload carries several audio streams, which one the provider decodes is **not knowable
  from our side**.~~ **ANSWERED 2026-09-18, and differently from the way this paragraph proposed.**
  It suggested normalising a multi-stream payload down to one stream, and noted that picking the
  stream is a product decision. It is — so the code does not pick. A recording with more than one
  audio track is **refused before any job, any hold and any provider request**, with the reason and
  the remedy (export a single audio track), and nothing is charged. Choosing for the doctor and
  choosing for the provider are the same act; neither is ours to make silently.
- ffprobe's reading and the provider's decoder are two different implementations. They agree on every
  fixture exercised here, and that agreement is evidence, not a guarantee.
- **A WAV carrying more than one `data` chunk is still not resolved, and is not made worse.** A
  decoder reaches one of them; the priced ceiling covers all of them, so the charge is safe; the
  submitted measurement describes what actually went; and no completeness claim is made about the
  part no decoder reaches. Normalisation neither creates this nor fixes it — the chunk is already
  unreachable to the decoder of record before anything is remuxed. It is pinned by a test that says
  exactly this, so the silence is not mistaken for a guarantee.

## Deterministic submission

Added 2026-09-18. The payload is now decided here, by us, and then measured — rather than handed to
the provider's demuxer to interpret.

**What it does, and only this:** for a payload with exactly one audio stream, `ffmpeg -map 0:a:0
-c:a copy` moves the coded audio frames into a clean container of the same family. There is no `-ar`,
no `-ac`, no `-t` and no `-ss` — no resampling, no downmix, no trimming, no stream mixing. Then the
output is probed, and *that* measurement is what `submitted_seconds` records.

**Why a remux and not a transcode.** Re-encoding to PCM would inflate a 47 KB WebM past the 15 MB
submission limit somewhere around two and a half minutes; re-encoding to another lossy codec would
discard audio to save bytes. So when a lossless remux is not available — an unrecognised codec,
ffmpeg absent, a refusal, a timeout, an output too large, a measurement that disagrees — **the
original is submitted unchanged, exactly as before, and the reason is recorded.** A recording a
doctor made is never re-encoded into something smaller to make this code path succeed.

**Measured, not asserted.** Each accepted format was decoded to raw s16le before and after the
remux and compared byte for byte:

| input | remux target | decoded samples | what changed |
| --- | --- | --- | --- |
| WebM / Opus (the browser path) | WebM | identical | container rounding, +≈7 ms declared |
| WAV / PCM | WAV | identical | nothing |
| MP3 | MP3 | identical | metadata stripped |
| M4A / AAC | M4A | identical | nothing |
| MP3 + trailing ID3v1 tag + 4 KB junk | MP3 | identical to its own source | 84,717 → 80,493 bytes |
| M4A with an edit-list start offset | M4A | identical | start_time 1.478 → 0.000 |

**Two audio tracks are refused before anything is paid for.** Measured: ffmpeg given a two-stream
Matroska and no explicit map emits one stream and reports nothing. The refusal happens in `enqueue`,
before `Job.objects.create` and before `reserve()`, so no job, no hold, no provider request, and the
upload is not kept.

### The artifact is bracketed by the two hand measurements, and each does its own job

`core/audio.py` already produces two numbers for every upload. The remux is judged against both:

- **loss is measured against the FLOOR** (`recording_seconds_confirmed`, the length the file
  certainly holds). An artifact shorter than that has lost real audio, so the original is submitted.
- **gain is measured against the CEILING** (`recording_seconds`, the most the file could hold). An
  artifact declaring more than that is our own muxer making an untrustworthy claim.

⚠️ **THE ARTIFACT IS NOT COMPARED TO THE SOURCE'S *DECLARED* DURATION, AND THE FIRST TWO VERSIONS OF
THIS WERE.** Both failed in the same direction — refusing correct work — and both were found by the
focused checks rather than by reading:

1. Probing the output against the source's ceiling refused **every ordinary browser recording**. A
   copy-remuxed WebM declares 4.028 s where the hand measurement of its source says 4.021 s: 7 ms of
   container rounding. The product's primary path silently stopped being normalised, fell back to the
   original, and every test still passed.
2. Comparing the two *declared* durations refused the tagged-MP3 case — the very shape the feature
   exists for. ffprobe estimates an MP3's length from its size, so 4 KB of appended junk made the
   source declare 4.560 s of audio it does not contain, against the remux's correct 4.032 s.

A declaration inflated by junk is not a measurement of audio. That is the whole reason
`core/audio.py` exists, and it is why the brackets come from there.

### Where the description lives, and why it is not on the job

`Job.config` is **write-once**: the trigger `quillmd_job_financial_guard` (migration 0008) refuses any
update to it, because it carries the authorized pricing and payer. That guard is right and is not
weakened. So the description of what was submitted — duration, container, byte count, sha256, and
whether it was the artifact or the original — goes to the two places designed to accumulate: an
audit row written before the request, and `units` on the provider receipt and the billing row. That
also ties upload → artifact → provider request → charge in one record.

### Bounds, because this is a shared host

| bound | value | enforced by |
| --- | --- | --- |
| wall clock | 120 s | `subprocess.run(timeout=)` |
| address space | 512 MB | `RLIMIT_AS` in the forked child |
| output size | 16 MB | `RLIMIT_FSIZE` — the kernel kills with SIGXFSZ rather than truncating |
| parallelism | one thread | `-threads 1` |

`RLIMIT_NPROC` is deliberately **not** set: on Linux it counts threads per UID, and all three services
run as one UID, so a limit low enough to bound ffmpeg is one the running gunicorn workers already
exceed.

The artifact is written under the same protected storage as the upload, at mode 0600, created before
ffmpeg opens it so it is never briefly readable at the process umask. It lives for one provider
request and is removed in a `finally` — on success, on provider failure, on exception. A crash
between the two leaves a stray, so the worker's existing reaper sweeps that directory as well, by
name and by age, and deletes nothing it does not own.

## Eight defects the refutation pass found in the normalisation itself

Four lenses were run over the finished diff — audio fidelity, money and consent, resource bounds and
storage, false green and false rejection — each told to REFUTE and to report only what it could
demonstrate with a concrete input. Every finding below was verified independently before a line was
changed, and every fix is pinned by a test proved to fail against the unfixed code.

**Seven of the eight failed in the same direction: refusing, charging for, or silently narrowing a
recording a doctor had made correctly.** None was reachable from the happy path.

| # | what broke | the input that showed it |
| --- | --- | --- |
| 1 | **The multi-track refusal failed open above 64 tracks.** `describe_submission` mapped every probe failure to `submission_streams=''`, and `''.isdigit()` is `False`, so the guard was skipped. It was strongest on a 2-track file and **absent** on a 65-track one. | a 65-track M4A: job created, **$0.06 held, one provider request, $0.0525 charged**, provider silently decoding one of 65 |
| 2 | **An in-limit recording was refused as "Recording too large."** The MP3 muxer adds an ID3v2 header and a Xing frame, so the artifact crossed a limit the upload sat exactly on — and it fell in the 1 MB window below `RLIMIT_FSIZE`, so ffmpeg was never killed and no fallback ran. Deterministic: re-uploading never helped. | a tagless, Xing-less 16:23 MP3 of exactly 15,728,640 bytes → artifact 15,729,077 |
| 3 | **Loss before the request was invisible by construction.** Every arm of `coverage_note` compares the *provider* against what we submitted. Nothing asked whether what we submitted was less than the recording we measured and priced. | an M4A with a trimming edit list: `mdat` holds 10.4 s, priced 10.027 s, **2.0 s submitted**, note empty |
| 4 | **A failing `audit()` write left the whole artifact on the encrypted volume.** The artifact was created, then the audit row was written outside any guard that could clean it up. Not exotic: the worker holds one DB connection across up to 25 s of subprocess work, so a stale-connection error lands at exactly that INSERT. | `OperationalError` at the audit INSERT → 100,891 bytes left behind |
| 5 | **A host without ffmpeg leaked a zero-byte file per job.** The caller creates the destination before calling in, and the `ffmpeg is not installed` arm was the one refusal that did not unlink. No crash involved — which is what the reaper's own comment assumed. | `shutil.which('ffmpeg') → None` |
| 6 | **The remux could run past the deadline that kills the worker.** Summing the sub-step ceilings gave 20 + 120 + 20 + 90 = **250 s** against the unit's `TimeoutStopSec=150`, so a routine `systemctl restart` could SIGKILL a worker mid-remux. Before the change the longest stretch was the 90 s POST. | the unit file and the constants; measured worst case at the 15 MB upload limit is **2.64 s** |
| 7 | **An unexpected exception escaped both guards.** A `preexec_fn` that raises — which `setrlimit` does when a hard limit sits below the value asked for — surfaced as a bare `SubprocessError`, caught by neither handler. It left a stray artifact and put the job in **reconciliation with the funds still held**, for what should have been a silent fallback. | a hard `RLIMIT_FSIZE` below `NORMALISE_MAX_OUTPUT_BYTES` |
| 8 | **`-threads 1` does not bound ffmpeg's thread count, and the docstring used that claim as its reasoning.** ffmpeg 6.1.1 runs threaded demux and mux regardless; `-c:a copy` has no codec for `-threads` to govern. | 3 tasks, not 1, on every accepted format |

Two further corrections came out of the same pass and are not defects so much as claims that were
larger than the evidence:

- **`RLIMIT_AS = 512 MB` left ~90 MB of working room, not 512.** This ffmpeg links ~200 shared
  objects and maps 413–422 MB before touching the input. Raised to 768 MB, sized against the measured
  baseline. Peak RSS never exceeded 58 MB, and RSS is what `MemoryMax` bounds.
- **Not setting `RLIMIT_NPROC` is correct, and now verified rather than asserted.** With a soft limit
  of 5 against a UID already owning 158 tasks, thread creation fails and `fork` returns `EAGAIN`.
  Linux counts threads UID-wide and all three services share a UID. `TasksMax=64` is the real bound.

### A ninth, found by one of the new tests rather than by a lens

The success path needed the same cleanup as the failure path. A remux that fails *after* the
destination exists returns normally — the original is submitted, which is correct — and the touched
file was simply left there. Every arm inside `normalise_submission` cleans up after itself, so the
gap was exactly the class it does not handle.

### And one test that could not fail, caught while proving the others

The check for finding 7 patched `subprocess.run`, which breaks the source probe before the remux is
reached — so it passed with the handler it named reverted. Worse, at the job level the two handlers
are *observably identical*: the caller's guard produces the same outcome either way. **A handler whose
absence is invisible is not a proven handler.** It is now proved one layer at a time: the caller's
guard at the job level, and `normalise_submission`'s own promise by calling it directly with nothing
behind it.

A second one nearly went the same way: two subTests uploaded byte-identical recordings, so duplicate
prevention correctly returned the first job and the second subTest silently had nothing to run.

## The tolerance, measured rather than chosen

`NORMALISE_TOLERANCE_SECONDS` is the only slack in the loss and gain checks, so it decides both whether a real
recording can be wrongly refused and whether real loss can slip through. It was measured across every accepted format
at five lengths spanning three orders of magnitude, against `core/audio.py`'s own floor and ceiling for the same file:

| length | WAV | WebM/Opus | MP3 | M4A/AAC |
| --- | --- | --- | --- | --- |
| 0.3 s | +0.000 | +0.008 | −0.024 | −0.021 |
| 1 s | +0.000 | +0.008 | −0.024 | −0.021 |
| 5 s | +0.000 | +0.008 | −0.024 | −0.021 |
| 60 s | +0.000 | +0.008 | −0.024 | −0.021 |
| 600 s | *(57.6 MB — refused at the 15 MB upload limit, correctly)* | +0.008 | −0.024 | −0.021 |

*(deviation of the artifact against the source's certain length, in seconds)*

**The deviation is IDENTICAL at every length**, which is the property that matters and is not obvious in advance. It is
per-file container framing — a header frame, a packet boundary, a priming sample — not drift that accumulates. So a
fixed tolerance is sound, and a doctor's hour-long recording is no closer to a refusal than a three-second one. **Had
it grown with duration, a fixed tolerance would have been a length limit nobody wrote down**, which is why the
invariance is asserted by a test rather than assumed.

| | worst observed | margin against 0.1 s |
| --- | --- | --- |
| artifact below the floor (the loss check) | −0.024 s | 0.076 s — **4×** |
| artifact above the ceiling (the gain check) | +0.007 s | 0.093 s — **14×** |

⚠️ **The constant was 0.25 s and is now 0.1 s, tightened on this evidence.** 0.25 sounds safe and is generous in the
wrong direction: it accepted a remux silently losing up to 0.23 s of a doctor's audio. The two errors are not
symmetric — refusing wrongly costs a fallback to submitting the original unchanged, which is exactly what happened
before this code existed and harmed nobody, while accepting wrongly costs audio nobody can detect.

**Nothing in the matrix was refused.** Twenty-four recordings across four formats and five lengths, and the only
refusal was the 600-second PCM WAV — at 57.6 MB, refused where it always was, by the upload limit, before any of this
code is reached.

## The fourth lens: what the CHECKS got wrong

The other three lenses broke the code. This one broke the evidence, and its first finding is the most serious thing
in this document.

### The whole proof rested on one unasserted line of workflow YAML

Measured by removing `ffmpeg` and `ffprobe` from `PATH`:

```
Ran 34 tests in 0.151s
OK (skipped=32)
```

**Thirty-two of thirty-four tests skip and the suite reports OK.** The two survivors are pure Python — a `measure_bounds`
call on a WAV and the reaper on synthetic bytes — and neither makes any claim about what reaches the provider.
`verify-fresh.sh` exits 0 and the job is green. Worse, the one test written to assert the dependency,
`test_both_media_tools_must_resolve_before_the_act`, **skipped itself on exactly the condition it exists to report**:
its `except Exception: raise SkipTest` swallowed the missing-tool refusal.

So editing one line of `.github/workflows/test.yml`, or running on a runner image that drops ffmpeg, would have turned
the entire submission proof into silence with no red anywhere. That is the failure `exercised.py` was written to
prevent, one level above where it had been applied.

> **ABSENT IS A SKIP ON A MACHINE THAT NEVER PROMISED THE TOOL, AND A FAILURE WHERE SOMETHING INSTALLED IT ON
> PURPOSE.** The distinction is `os.getenv('CI')`, and it is the difference between a host gap and a broken promise.

Both behaviours are now measured rather than argued:

| | tools present | tools absent, no `CI` | tools absent, `CI=true` |
| --- | --- | --- | --- |
| `core.tests.test_audio_submission` | 34 pass | `OK (skipped=32)` | **FAILED** |
| `ops.test_audio_submission_activation` | 14 pass | `OK (skipped=1)` | **FAILED** |

### A test whose bound is the constant it is testing

Two assertions bounded themselves by `media.NORMALISE_TOLERANCE_SECONDS` — the very symbol `normalise_submission`
enforces. So the postcondition the code guarantees was the postcondition the test checked, and raising the constant
loosened both together. They now bound themselves by `MEASURED_WORST_DEVIATION`, a literal taken from the table above,
and one assertion runs the comparison the other way round: the measurement must stay inside the production constant.

Drift is now caught in both directions, proved by mutation: loosening the constant to 5 s fails the loss check;
tightening it to 0.001 s fails the duration-invariance check.

### A supported format that could never arrive

`CONTAINERS` carried a `flac → flac` row and `SUBMISSION_NAME` matched `.flac`. `core/audio.py measure_bounds()`
refuses FLAC as an unsupported format long before `enqueue` reaches `plan_normalisation`, so no FLAC input can reach
the remux and no `.flac` artifact can exist for the reaper to match. Both are removed. **A row that cannot be reached
is worse than a missing one**, because the next reader believes the path is supported on the strength of two files
saying so.

### And its refutation of claim 4 is the strongest negative result here

**Thirty-one recordings, not one refused and not one falling back to the original.** Browser WebM/Opus at 0.3, 1, 5, 60
and 600 seconds; a MediaRecorder-shaped WebM with no seekable duration written back; stereo; CBR *and* VBR MP3; MP3
carrying an ID3v2 tag; an 8 kHz mono dictaphone WAV; a 24-bit WAV; a mono 44.1 kHz AAC voice memo; ten-minute
recordings in every format.

Two inputs never reach the new refusals because a pre-existing one fires first, and neither is new behaviour: FLAC,
and a 600-second 48 kHz stereo WAV at 57.6 MB, refused by the 15 MB upload limit.
