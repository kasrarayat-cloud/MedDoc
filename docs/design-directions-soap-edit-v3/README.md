# SOAP edit canvas — 10 concepts (v3)

Branch: `design/soap-edit-experience-v3`

v1 explored *where the edit affordance lives*.
v2 explored *what paradigm editing follows*.
v3 starts with a different premise: **the doctor IS editing — what does the canvas itself look and feel like?**

The top of `index.html` reconstructs the screenshot Kasra sent — raw markdown, monospace textarea, green focus ring, inline `[Note: clarify with dictator…]` annotations, "ESC / BLUR SAVES" hint — so each of the 10 concepts can be judged against that baseline.

## Why this version exists

The current production edit state shows:
- Raw markdown rails (`## Subjective`, `**HPI:**`) treated as user-facing text
- Plain monospace textarea — the surface looks like a code editor
- "ESC / BLUR SAVES" — small, easy to miss, anxiety-inducing
- Inline `*[Note: clarify with dictator: dose of metformin in mg?]*` annotations cluttering the prose
- No toolbar, no AI assist, no entity recognition, no structure

Every concept here picks at least one of those off, and uses its own visual language to do so.

## The ten concepts

| # | Concept | Targets | Boldness |
| - | ------- | ------- | -------- |
| 1  | **Focus mode**             | Anxiety + no toolbar | 3/5 |
| 2  | **WYSIWYG rich editor**    | Raw markdown visible | 2/5 |
| 3  | **Clarification workflow** | `[Note: clarify…]` clutter | 4/5 |
| 4  | **Entity-highlighted**     | No structure / NER absent | 4/5 |
| 5  | **Voice + keyboard hybrid** | Single input modality | 4/5 |
| 6  | **Structured fields + prose preview** | No structure (radical) | 4/5 |
| 7  | **AI-assist sidebar**      | No AI assist | 3/5 |
| 8  | **Transcript-linked**      | Provenance / trust | 4/5 |
| 9  | **Diff-as-you-type**       | "What changed?" + anxiety | 3/5 |
| 10 | **Floating command palette · glassmorphic** | No toolbar (radical) | 3/5 |

## Self-check vs the production screenshot

For each concept, place the "Today · production" panel alongside it. Ask:

- **Is the raw markdown gone or hidden?** Concepts 1, 2, 4, 5, 6, 10: yes. 7, 8: yes (rendered). 9: partial (mono editor but with diff context). 3: yes.
- **Is the toolbar / action surface obvious?** 1 has the floating bottom bar; 2 has the float-toolbar; 7 has the right rail; 10 has cmd-K; 9 has the footbar; 3 has the sidebar of resolvable cards. 4, 5, 6, 8 each have their own specialized chrome.
- **Is "what saves and how" explicit?** 1 explicit autosave + ⌘. exit; 9 explicit Save button; 7 cards with Apply; the rest replace blur-saves with mode-specific chrome.
- **Is `[Note: clarify…]` clutter solved?** Concept 3 directly extracts them to a sidebar. Concept 6 absorbs them into field structure. Concept 8 lets the inline annotation become a transcript anchor instead.

If a concept feels like "current textarea + one extra button," it doesn't ship. The self-check passes when every concept is recognizably its own surface.

## Visual diversity self-check

| # | Visual signature |
| - | ---------------- |
| 1  | Cinematic dim, sage-glow vignette, blur-aware focus card, bottom toolbar |
| 2  | Standard dark editor, blue selection, floating toolbar with AI menu |
| 3  | 2-pane editor + right rail with stateful clarification cards (orange / resolved sage) |
| 4  | Colored entity underlines (amber drug, blue dose, sage anatomy, coral dx) with context popover |
| 5  | Editor + floating glowing mic FAB + voice-command overlay with waveform |
| 6  | Card-based structured fields with prose preview band beneath |
| 7  | 2-pane editor + AI suggestion cards in dedicated kinds (Billing / Style / Clinical / Applied) |
| 8  | Sentence-level numbered pins, hover transcript preview with timestamps |
| 9  | True split editor with line-by-line live red/green diff |
| 10 | Backdrop-blur glass palette overlaid on editor — cmd-K for prose |

No two share a layout. Five concepts use a single canvas; five use split or overlay surfaces. Five use chromatic categorical color (entity, AI kinds, diff); five rely on monochrome with sage accent.

## Designer's read

**Most likely to ship combined**: Concepts 2 (WYSIWYG) + 3 (clarification workflow) + a slice of 10 (cmd palette for AI actions). The visible prose, the extracted clarification cards, and a discoverable command surface together fix the four production issues without committing to any single radical paradigm.

**Boldest single bet**: Concept 8 (transcript-linked). Provenance-by-default is the differentiator no other scribe ships, and it's already grounded in pipeline data we have (`utterances`, `speakerMap`, `audioKey`).

**Highest implementation cost**: Concept 6 (structured fields). Needs a field schema with versioning + prose↔fields bidirectional binding.

## Pre-work the brief asked for

- `.claude/agents/` enumerated: ai-pipeline-auditor, code-quality-auditor, hipaa-compliance-auditor, performance-auditor, qa-interaction-auditor. None are design-focused so none invoked. (The qa-interaction-auditor would be the right downstream check before any concept ships to production — call it then.)
- `/mnt/skills/public/frontend-design/SKILL.md` doesn't exist at that path; the equivalent skill lives at `/home/claude/.claude/skills/frontend-design/SKILL.md` and was invoked in earlier turns of the session — guidance carried forward: bold aesthetic direction, distinctive typography per concept, varied palettes, motion as meaning.
- Plugin inventory has no design tooling beyond the user skills (`theme-factory`, `ui-ux-pro-max`, `ui-libraries-reference`, `framer-motion`) — token guidance from `ui-ux-pro-max` cross-checked: 44×44 touch targets, focus rings on inputs, 150–300 ms motion, contrast 4.5:1. All applied.

## Hosting

A copy of `index.html` is mirrored to the existing Caddy `/_preview/*` mount on `app.quillmd.com`. URL is in the PR description; same approach as v1 / v2 hosting.
