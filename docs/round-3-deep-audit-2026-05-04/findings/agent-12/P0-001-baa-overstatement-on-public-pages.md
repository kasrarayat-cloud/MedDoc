---
id: A12-P0-001
title: Public Privacy + HIPAA pages assert BAAs are signed, while internal BAA tracker shows ZERO signed
severity: P0
domain: docs/compliance
---

# Issue

Public-facing legal pages claim that every PHI-touching subprocessor has a signed Business Associate Agreement on file. The internal BAA tracker contradicts this — every row is `☐ NOT YET` or `☐ VERIFY`. Asserting BAAs that do not exist on a public HIPAA page is a misleading statement to prospective Covered Entity customers. If real PHI flowed through the stack today on the strength of those public assertions, the misrepresentation itself becomes a material compliance fact regulators consider during breach review (45 CFR §164.408 + state UDAP analogues).

# Evidence

`/opt/meddoc-pro/apps/marketing/src/app/privacy/page.tsx:158-178` (Privacy Policy §4 "Who we share it with"):
```tsx
<p style={SECTION_BODY}>
  We use subprocessors for specific functions. All subprocessors
  that touch PHI have signed Business Associate Agreements:
</p>
<ul ...>
  <li><strong style={STRONG}>Anthropic</strong> — Claude models...</li>
  <li><strong style={STRONG}>OpenAI</strong> — embeddings...</li>
  <li><strong style={STRONG}>Deepgram</strong> — audio transcription.</li>
  <li><strong style={STRONG}>Resend</strong> — email delivery...</li>
</ul>
```

`/opt/meddoc-pro/apps/marketing/src/app/hipaa/page.tsx:80-96` (HIPAA page "BAAs" section):
```tsx
<p style={SECTION_BODY}>
  ... Our subprocessors that process PHI on our behalf have signed BAAs with us:
</p>
<ul>
  <li>Anthropic (Claude models)</li>
  <li>OpenAI (embeddings)</li>
  <li>Deepgram (audio transcription, Nova-3 Medical model)</li>
  <li>Resend (email delivery)</li>
</ul>
```

Compared with the source-of-truth tracker at `/opt/meddoc-pro/docs/BAA_CHECKLIST.md:11-23`:

| Processor | BAA status |
|---|---|
| Anthropic | ☐ NOT YET |
| OpenAI | ☐ NOT YET |
| Deepgram | ☐ NOT YET |
| Sentry | ☐ NOT YET |
| Dropbox | ☐ VERIFY |
| DrChrono | ☐ VERIFY |
| VPS host | ☐ VERIFY |

`docs/LAUNCH_CHECKLIST.md:24` echoes the truth: `[ ] 3. All four BAAs signed + on file ... ZERO signed as of this writing. Launch blocker.`

The "[DRAFT — PENDING LEGAL REVIEW]" banner on each public page is not a defence — the body asserts a present-tense factual state ("have signed") rather than an aspiration ("will sign before any Covered Entity sends PHI"). Resend is not even in the BAA tracker matrix, yet it is listed on the public page as a signed-BAA subprocessor.

# Risk

- **Compliance**: false attestation to Covered Entity prospects. Practices that sign onto QuillMD relying on these pages are operating under a misrepresentation. If a HIPAA breach later occurs, OCR will weight pre-incident representations against the licensee.
- **Pilot launch blocker**: the LAUNCH_CHECKLIST already flags BAAs as a launch gate. Pre-pilot operators may rely on the public page's assertion and skip the explicit gate.
- **Legal exposure**: state UDAP (Unfair and Deceptive Acts and Practices) and the FTC Health Breach Notification Rule both consider public privacy-page content when assessing materiality.
- **Trust**: a clinician who later cross-references the public claim against the tracker will lose trust in every other claim on the page.

# Recommended fix

Pre-launch, before any Covered Entity is invited to the pilot:

1. Edit `apps/marketing/src/app/privacy/page.tsx` §4 and `apps/marketing/src/app/hipaa/page.tsx` "BAAs" section to use forward-looking language until the BAAs are actually signed:
   > "Before QuillMD processes Protected Health Information on your behalf, we will execute Business Associate Agreements with all subprocessors that handle PHI. As of YYYY-MM-DD the following BAAs are: in-flight (Anthropic, OpenAI, Deepgram), pending (Resend), or signed (none yet). The current state is tracked at compliance@ashtechgroup.com — request the latest before sending any PHI to QuillMD."
2. Wire a single source of truth: replace the hardcoded JSX list with a render of the BAA tracker JSON (keep `BAA_CHECKLIST.md` as the human-readable mirror). A Covered Entity reading the public page sees only what the operator has actually signed.
3. Add a CI check (e.g. extend the existing axe-core / a11y workflow) that fails the build if `docs/BAA_CHECKLIST.md` contains `☐ NOT YET` while either public page claims the BAA is signed.
4. Once each BAA is countersigned, flip both the tracker and the public page in the same commit. Date-stamp each row.

Until this fix lands, the gap between the public claim and reality must be closed in writing — either by signing the BAAs (preferred) or by softening the public claim. The LAUNCH_CHECKLIST §3 gate is the remaining blocker; the public-page misstatement is independent and pre-existing.
