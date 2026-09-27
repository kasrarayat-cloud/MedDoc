# D30 finished-diff independent refutation

**REFUTED — two concrete new source-context defects.** No source edits made.

Reviewed candidate: `75e545b2a6469b0d188c779f3c4ee9af02dfc7f5`, base
`0b0395a0922f81f5a38526802136197a4bb74b28`, worktree
`/opt/meddoc-pro/.worktrees/v1-word-d30`.
Engine SHA256: `326a4baf7d3331add09f36f78e05d66a8fb75acd4e10bd1c2c952447835efbd1`.

## 1. Inherited Donor heading disappears from an automatically assigned field

Relevant new code: `rebuild/documents/word_v3.py:1869` skips every paragraph
not accepted by the existing heading reader; `:1950` adds the field without
warning about this lost source context. The underlying reader at`:827` checks
the directly named style and direct run boldness, not its style ancestry.

Concrete synthetic input:

1. A `Donor` paragraph using custom style `DonorSection`.
2. The style has `w:basedOn w:val="Heading1"`; the parent style explicitly carries
   outline level0 and bold heading formatting.
3. `What medications are currently taken?` in an ordinary body paragraph.
4. One empty, directly bordered, unmerged cell table.

Candidate output is a long-text field at`b/tbl[0]/tr[0]/tc[0]` with label
`What medications are currently taken?`, **empty context and no warning**.
The otherwise identical direct Heading1 control correctly emits context`Donor`.
The base emits no assigned field in either input. Thus the newly assigned area
has silently lost the explicit person/section scope. This is a metadata loss
claim; no live clinical generation or rendered result is claimed.

Evidence cases: `inherited-donor-heading` and `direct-donor-heading`.

## 2. A two-paragraph question becomes only its dependent final instruction

Relevant new code: `rebuild/documents/word_v3.py:1922` stops at the nearest
nonempty paragraph; the reference check at`:1933` does not capture this dependency;
`:1950` creates a supported mapping with only that paragraph's text.

Concrete synthetic input:

1. `Which medications are currently taken?`
2. `Please provide their doses and frequencies.`
3. One empty, directly bordered, unmerged cell table.

Candidate output is one field at`b/tbl[0]/tr[0]/tc[0]` labelled only
`Please provide their doses and frequencies.`, **empty context and no warning**.
The medication question is absent from every detected field and warning. The
first paragraph supplies the subject of `their` and part of the requested
answer; the automatic destination therefore lacks its complete source question.
The base emits no field. Original DOCX wording is still present: the demonstrated
loss is in mapping completeness/context, before generation or export.

Evidence case: `two-paragraph-question`.

## Boundaries and controls

Eight cases were predeclared and executed once against exact saved base and
candidate engines, with network sockets denied. A normal question maps to its
box; its synthetic export leaves every other package part byte-identical.
Direct cell nil correctly refuses; the already repaired inline blank preserves
the Patient-name span and visibly warns about the extra box. No additional
finding is asserted from the ancestor-conditional-nil or page-break-spacer cases:
their raw acceptance is retained, but this review does not claim a rendered
border outcome or an independently proven intended destination for them.

No corpus original, holdout, qualification cohort, provider, database, renderer,
native Word, deployment or application write was used. No broad suite was run.
An ancillary XML-read attempt used the system interpreter without lxml and failed
before reading the styles; the corrected standard-library XML read confirmed the
style ancestry above. The scored probe itself used the existing application venv
and completed normally. No dependency installation occurred.

## Evidence and next action

Runtime: `/opt/meddoc-pro/.worktrees/v1-patient-topics/rebuild/.runtime/d30-refutation-20260927/`.
It preserves `probe.py`, `predeclared.json`, exact engine snapshots, `result.json`,
all eight generated blank DOCX files and the synthetic positive export.
Tracked text evidence and artifact hashes are in `d30-independent-evidence-20260927/`.

The parent and source author have both received the exact findings. Parent
verification and bounded repair/re-refutation are required before integration.
This review does not establish whole-D30, family or broad Word compatibility.
