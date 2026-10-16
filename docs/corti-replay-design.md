# Corti offline replay preview design

## Brief

Designing one private HTML replay for clinicians and integration reviewers.
Goal: inspect provider-selected proposals and their exact source evidence while
keeping unselected material out of the clinician proposal list.
Tone: precise, quiet, and visibly provisional.
Main risk: treating a correct code identifier, provider assertion, or quoted
evidence as verified terminology, approved coding, or production readiness.
Must remember: **Synthetic replay — not live**, with the original **FAIL** visible.
Constraints: standalone file, no external assets or JavaScript, no application
route, no approval/adoption controls, no clinical writes, no provider requests.
Path: direct build using the existing QuillMD coding interface as the reference.

## Research and reference lock (before implementation)

Live Refero tools were unavailable. Research used these inspected local sources:

1. `rebuild/static/app.css`: established green-neutral palette, white surfaces,
   12px panel radius, thin borders, restrained table hierarchy, amber and red states.
2. `rebuild/static/coding.css`: separated result and encounter-context columns,
   evidence-led code rows, responsive collapse, and diagnostic disclosure.
3. `rebuild/templates/coding_panel.html`: source quotations, terminology releases,
   independent coding review, and explicit separation from document exports.
4. Refero `references/typography.md`: neutral product typography, one font family,
   scan-friendly hierarchy, and small number of text sizes.
5. Refero `references/craft-details.md`: visible keyboard focus and native controls.

Primary direction: the existing QuillMD coding panel. Preserve the product's
palette roles, thin border separators, source quotes, and restrained density.
Borrow only typography discipline and focus treatment from the bundled craft
references. Amber means unresolved/unverified; red means failure; green is
product identity rather than approval. Use the local system font stack because
this artifact must remain self-contained. No imagery is necessary for code and
evidence inspection. Reject decorative cards, hero copy, gradients, disabled
approval buttons, and any visual suggestion that replay proposals are approved.

## Decision ledger

| Decision | Source | Role preserved | Reason |
|---|---|---|---|
| Green-neutral canvas and white bordered result surface | `app.css` | Existing product identity | Recognizable proposed QuillMD surface |
| Red original FAIL banner at the top | User requirement and `app.css` error state | Failure indicator | Adapter success must not overwrite original provider-quality verdict |
| Amber validation badges | `app.css` warning state | Unresolved status | Avoid implying reference validation or approval |
| Selected proposals in the main result table | User requirement | Provider-selection boundary | Candidates cannot appear as actionable selections |
| Original provider display text always visible | User requirement | Provenance | Do not conceal the retained CPT description defect |
| Exact evidence quotes below each proposal | `coding_panel.html` | Supporting documentation | Make source support inspectable without navigation |
| Native collapsed diagnostic disclosure | `coding.css` and craft focus guide | Secondary technical detail | Preserve candidates and nested alternatives without promoting them |
| Service date and terminology status beside results | Existing coding layout | Encounter/reference context | Effective dates are part of validation |
| No selection, save, or approval control | User isolation requirement | Static preview | This file cannot write to the application |
| System font, inline CSS, no JavaScript | User private/offline requirement | Self-contained file | No requests or external resource dependency |

## Validation target

Check the rendered page at desktop and narrow widths. Confirm keyboard access to
the diagnostic disclosure, no external resource loads, no horizontal page
overflow, exact original description/evidence visibility, escaped provider text,
the persistent FAIL banner, and absence of approval/adoption actions. Rendered
validation evidence is recorded with the replay artifacts, separate from the
immutable original trial artifacts.

## Rendered validation outcome

The actual normalized response was rendered locally with Playwright at 1440×1000
and 390×844, with HTTP(S) requests blocked. The first desktop pass succeeded;
the first mobile pass found overflow from the long original verdict identifier.
The identifier remains unchanged and now wraps within the notice. The initial
preview, screenshots, and failed browser verification remain retained alongside
the revised `preview-v2.html` and its new screenshots.

The revised preview passed all 15 browser checks at both viewport sizes:
no page overflow, exactly three provider-selected proposals, exact original
descriptions and seven source quotations, no candidates visible in the main
surface, collapsed diagnostics, keyboard disclosure access, persistent FAIL and
replay labels, and no controls, scripts, external assets, or network requests.
Both rendered screenshots were visually inspected against the reference lock.

Diagnostic collection counting also tolerates null collections without hiding
the original malformed data: the displayed count is explicitly marked malformed
and the retained diagnostic JSON still contains the original null value.
