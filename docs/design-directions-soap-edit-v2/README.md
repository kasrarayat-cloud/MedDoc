# SOAP edit — ten paradigms (v2)

Branch: `design/soap-edit-patterns-v2`

v1 (PR #209) explored ten ways to *click* into editing. Kasra read it
as one paradigm shown ten times. v2 explores ten **paradigms** —
different mental models for what "editing a SOAP" even is. The
production-mirror constraint is dropped on purpose; each mockup gets
its own visual language so the differences read at a glance.

Open `index.html` in a browser — the top of the page has a contact-
sheet of all ten thumbnails for the visual-diversity self-check.

## Why v1 collapsed

Every v1 pattern was "textarea opens differently." Hover pencil,
header pill, click vs double-click, sticky bar — all variations on
the same paradigm: *render prose → swap to textarea → save*. The
visual ceiling for that paradigm is one screen.

## The ten paradigms

| # | Paradigm | Mental model | Bold |
| - | -------- | ------------ | ---- |
| 1  | **Voice-driven revision**     | Talk to the document; AI rewrites the right section in place | 5/5 |
| 2  | **Diff-based suggestions**    | AI proposes red/green diffs; doctor reviews like code | 3/5 |
| 3  | **Chat-revision sidebar**     | Persistent chat panel; SOAP is read-only — the chat is the input surface | 4/5 |
| 4  | **Highlight + AI rewrite**    | Select text → floating tooltip with rewrite / shorten / expand / clinical | 3/5 |
| 5  | **Outline mode**              | SOAP collapses to bullets; edit short fragments; AI re-expands to prose | 4/5 |
| 6  | **Template-fill**             | Structured fields with types (date, slider, multi-select); AI assembles prose | 4/5 |
| 7  | **Source toggle**             | Flip a switch; edit raw markdown like Linear's issue editor | 2/5 |
| 8  | **Transcript-anchored**       | Split screen; SOAP sentences anchor to transcript turns; edit upstream | 5/5 |
| 9  | **Conversational scrub**      | Video-editor timeline; scrub to a moment, see + edit the AI's state then | 5/5 |
| 10 | **Block-based (Notion)**      | Each element is a draggable block; slash commands; compose, not edit | 4/5 |

## Self-check — paradigm diversity

If you covered the labels on the ten thumbnails and asked someone
which two felt like the same idea, would they answer?

| Paradigm | Visual signature |
| -------- | ---------------- |
| 1 Voice           | Dark vignette + sage glow sphere; serif voice transcription |
| 2 Diff            | VS Code dark; line numbers; red/green diff bars |
| 3 Chat sidebar    | Split with chat bubbles on right (blue user / dim AI) |
| 4 Highlight + AI  | Cream editorial surface; serif body; amber selection |
| 5 Outline         | Tree view with disclosure triangles; tabular monospace bullets |
| 6 Template-fill   | Light clinical form; labeled inputs, sliders, checkbox chips |
| 7 Source          | GitHub-dark code editor; syntax-tinted markdown |
| 8 Transcript      | Split-pane transcript ↔ SOAP with linked-turn highlights |
| 9 Timeline scrub  | 6-card grid above a tick-marked video-editor timeline + playhead |
| 10 Blocks (Notion) | Light Notion-like; drag handles, slash menu, drop indicator |

Five paradigms have light surfaces (4, 6, 10), warm surfaces (1, 4),
or otherwise non-production palettes. Five are dark with paradigm-
specific accents. No two share a layout or chrome.

## Notes on the seed list

- All ten seeds kept — they're already paradigm-distinct.
- Boldness 1–5 noted per paradigm so designer can weight novelty vs
  feasibility. 1 = familiar, 5 = totally novel.
- **Highest leverage from this brief**: paradigms 1 (voice), 8
  (transcript-anchored), and 9 (timeline-scrub) — all 5/5 boldness and
  all rooted in things the QuillMD pipeline already produces
  (transcript, timestamps, per-step inferences). They're harder to
  build than the seed list's #4 or #7 but uniquely valuable because no
  other ambient-AI scribe exposes them.
- **Highest risk**: paradigm 6 (template-fill). It's the boldest
  rethink of "what is a SOAP" but commits to a field schema that
  needs versioning — and might feel rigid to clinicians who think in
  prose. Likely a non-default mode.

## Hosting

Mirror of `index.html` lives in the existing Caddy `/_preview/*`
mount on `app.quillmd.com`. URL is in the PR description. No auth.
Same approach as v1 for review.
