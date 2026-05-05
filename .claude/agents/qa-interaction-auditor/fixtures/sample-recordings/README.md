# Sample recordings — non-PHI fixtures

The QA Interaction Auditor needs audio inputs that drive the upload →
pipeline → SOAP-render workflow without using real patient encounters.
This directory holds (or links to) audio fixtures that can be checked
into the repo or fetched on demand.

## What goes here (and what doesn't)

**OK to commit:**
- Synthetic / scripted clinical scripts narrated by a non-clinician
  reading from a public template. No real patient encounters.
- Public-domain medical-education recordings clearly licensed for
  redistribution.
- Silent / tone test files (a 5-second 1 kHz tone, a 30-second silence)
  for testing the upload pipeline's handling of "no speech".

**NEVER commit:**
- Real doctor-patient encounters, even if names are bleeped.
- Real dictation from a clinician's phone, even if scrubbed.
- Anything pulled from a HIPAA-covered system (EHR voice memos, etc.).
- Anything you can't prove the rights to.

If in doubt, don't commit. Generate synthetic audio via TTS instead
(see "Synthesizing fixtures" below).

## Files in this directory

The repo is shipped with a minimal placeholder set (this README only).
The agent operates on fixtures it generates on demand because audio
files are large and we'd rather not bloat the repo. The expected files
the agent will create or fetch on first run:

| File | Purpose | Source |
|---|---|---|
| `synthetic-followup.m4a` | 2-minute scripted follow-up visit (HTN check, BP review, refills) | TTS-generated, see below |
| `silent-30s.m4a` | 30 seconds of silence | `ffmpeg -f lavfi -t 30 -i anullsrc=r=44100:cl=mono -c:a aac silent-30s.m4a` |
| `non-clinical-statement.m4a` | A non-clinical recording (covers Pattern C from `bug-patterns.md`: triggers L5 critique → L6 refusal-banner) | TTS-generated from a non-medical script |

## Synthesizing fixtures via TTS

The agent does NOT regenerate these on every run; only when the file
is missing locally. Use any TTS that produces clean speech — the goal
is to drive Deepgram's transcription, not to be persuasive.

Example using `say` (macOS) or `espeak` (Linux):

```bash
# Linux fallback — espeak + ffmpeg to m4a
espeak -v en-us -s 160 -f synthetic-followup.txt -w /tmp/raw.wav
ffmpeg -i /tmp/raw.wav -c:a aac -b:a 96k synthetic-followup.m4a
```

`synthetic-followup.txt` is a script the agent ships in this directory
when it first runs. Keep it boring and obviously fake (e.g. patient
name "Test Test", DOB "01/01/1900", chief complaint "this is a
synthetic recording for QA testing").

## Why three specific files

Each of the three fixtures targets a specific failure-mode the agent
needs to verify:

1. **synthetic-followup.m4a** — happy path. Drives the full pipeline
   from upload through L8. The SOAP-render workflow walk uses this
   visit. If `synthetic-followup` produces empty SOAP sections, that's
   the canonical Pattern C reproducer.

2. **silent-30s.m4a** — degenerate case. Pipeline should detect "no
   speech" and either fail gracefully (clear error to doctor) or
   produce a banner-style SOAP. The agent verifies the doctor sees a
   clear state, not a frozen "Processing" view.

3. **non-clinical-statement.m4a** — adversarial case. This is the
   exact shape of Kasra's `cmorjcv0i...` smoke-test failure: the
   pipeline correctly refuses, L6 writes a refusal banner, and the UI's
   `parseSoapSections` regex fails to render it. The agent uses this
   to regression-test the parser fix.

## Generating recordings is OPTIONAL on first run

The agent's static-analysis pass (greps, orphan-dispatcher diff,
prop-render walk) does NOT need any audio. The agent runs static
analysis FIRST and only generates audio fixtures if the run requires
the browser walk + pipeline-dependent verification.

For routine "audit this page for stub features" requests, audio is
not needed at all.

## DO NOT use these fixtures for production data

These are quality-assurance fixtures only. They are not training data
for the AI pipeline; they are not benchmark data; they are not
representative of the production input distribution. If you need
benchmarks, see `/opt/meddoc-pro/docs/benchmarks/` or the AI pipeline
team.
