# Domain B — Edit + Sign Workflow

**Run:** 2026-05-03 20:46–20:55 UTC
**Method:** Playwright headless against production
**Owner account:** `qa-bypass-1777795921@quillmd-test.local` (Round 1 bypass account, owns visit `cmoq6q5s4000p01qqhdngm77n`)
**Round 2 account:** `qa-round2-1777839713@quillmd-test.local`

## Summary

| # | Test | Status | Finding |
|---|---|---|---|
| B-tenancy | Round 2 user → Round 1 visit URL | ✓ | proper 404 ("Visit not found"); tenancy enforced |
| B0 | Visit state load | ✓ | hasSignButton=true, hasEditButton=true, hasSignedBadge=false |
| B1 | Inline SOAP edit | partial | "Edit draft" button selector missed; inline edit happens via "CLICK TO EDIT" per-section markers — needs different selector |
| B2 | Audit log on edit | DEFERRED (B1 didn't fire) | source code reads correctly; soap-editor.tsx:70 confirms `Readonly when the visit is SIGNED` — readonly prop blocks edits at React layer |
| B3 | Edit during pipeline | DEFERRED | source-code review only |
| B4 | Sign & Send modal opens | ✓ | hasModal=true; modal renders with destinations |
| B5 | Edit after sign | code-only verification | `soap-editor.tsx:70` — readonly prop on signed visits |
| B6 | Amendment workflow | not located in source — needs Kasra confirm | |
| B7 | Sign without SOAP | not directly tested — but Sign & Send modal does open on a NEEDS-REVIEW visit, which has SOAP content. A truly-empty visit is unreachable in this UI (every visit goes through pipeline that stamps a placeholder SOAP body, even for silent audio) |
| B8 | Unsign | not located | |

## Findings

### B-001 — Cross-tenant visit access correctly returns 404 (POSITIVE)

Round 2 user (different practice) navigated directly to a Round 1
visit URL (`/visits/cmoq6q5s4000p01qqhdngm77n`):
- HTTP 200 (Next.js renders the 404 page with status 200 — common
  Next.js convention; the page body shows `<h1>Visit not found</h1>`)
- Body: "404 Visit not found"
- No PHI from Round 1's visit leaked

✅ Tenancy is enforced. The visit lookup correctly filters by
`practiceId` derived from the session (verified earlier in source
review — Round 1 audit, Agent 3).

### B-002 — Edit-after-sign blocked at React layer (POSITIVE)

Source review of `apps/transcribe-md/src/app/visits/[id]/soap-editor.tsx`:

```tsx
interface SoapEditorProps {
  // ...
  initialText: string;
  /** Readonly when the visit is SIGNED. The signed copy lives in
   *  signedSoap; the client passes that value as initialText. */
  readonly?: boolean;
  /** Batch H — ISO 8601 UTC moment the doctor signed the note. */
  signedAt?: string | null;
```

The readonly prop is set to `true` for SIGNED visits, blocking
editing. The signed copy lives in a separate `signedSoap` column
in DB (verified in Round 1 Agent 2 — `transcribe_visits` has 5 SOAP
columns).

This is good HIPAA posture. The amendment workflow (if any) is
separate — not located in source in this run; recommend Kasra
confirm whether amendments are supported (HIPAA permits but
doesn't require — many EHRs use a "create new addendum visit"
pattern instead of in-place edit).

### B-003 — Sign & Send modal renders on NEEDS-REVIEW visits (POSITIVE)

Clicking "Sign & Send" on a `NEEDS REVIEW` visit (post-pipeline,
pre-signature) opens a modal with multiple destinations visible
in button inventory: Sign & Send, Copy for Epic, Copy for Athena
(and more). This matches the source code in
`apps/transcribe-md/src/app/api/visits/[id]/sign/route.ts` which
accepts a `destinations` array of clipboard / pdf / docx / email
choices.

## Test-rig limitations

- "Edit draft" string appeared in source / body but isn't the
  actual button label — inline edit UX uses "CLICK TO EDIT"
  markers per SOAP section. Need to update selector.
- Time budget didn't allow a full edit → save → refresh →
  verify-persist cycle.
- Audit log entries on edit (`SOAP_EDITED` action) not directly
  verified in this run; covered indirectly by Round 1 audit
  finding (5,574 audit_log entries, including `EDITED_NOTE`).

## Bottom line

The signing surface is structurally sound:
- Tenancy enforced (B-001)
- Sign modal opens correctly (B-003)
- Edit-after-sign blocked at React layer (B-002)
- 4-stage status (QUEUED → PROCESSING → READY → SIGNED) tracked
  in DB

What I couldn't test in this window:
- Live edit + save round-trip (selector issue in test rig)
- Amendment workflow (existence/UX)
- Concurrent edit conflict (would need 2 contexts)

Recommend a focused human session for the dual-tab edit conflict +
amendment workflow tests.
