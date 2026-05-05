---
id: A06-P3-015
title: L4 emits SOAP as raw markdown; downstream parsing is regex-based and fragile
severity: P3
domain: Polish / parser fragility / heading drift
files:
  - apps/transcribe-md/src/worker/layers/04-generate-soap.ts (line 93-104, returns markdown)
  - apps/transcribe-md/src/lib/parse-soap-sections.ts
  - apps/transcribe-md/src/lib/ehr-formatters.ts
---

## Issue

L4 produces unstructured markdown using `modelClient.completeText()`.
Downstream code (parse-soap-sections, ehr-formatters, the SOAP
inline editor, PDF/DOCX generators) re-parse the markdown with
regex to find `## Subjective`, `## Objective`, etc.

If the model drifts from the prompt's heading format (e.g. emits
`### Subjective` or `**Subjective:**` or omits a section
entirely), every downstream parser silently mis-renders.

This is not a clinical-correctness bug — it's a robustness gap
that becomes urgent the first time a model upgrade changes
heading conventions.

## Evidence

- L4 prompt (`04-generate-soap.ts:38-39`):
  ```
  'Structure the note with these markdown headings exactly:'
  '## Subjective'
  ```
  "Exactly" is a soft request.

- The downstream parser (`parse-soap-sections.ts`) pattern-matches
  headings; a future model emitting `Subjective` (no hash) breaks
  the parser silently.

- ehr-formatters and pdf-generator both re-parse the same
  markdown; any drift is now THREE places to fix.

- L7c, L7d, L7e all consume `soapFinal: string` (markdown) and
  rely on the model finding the Plan section by header. If headers
  drift, L7c may not see the Rx-relevant content at all.

## Risk

P3 because:

- No active bug today; current Sonnet adheres to the format reliably.
- Future-model risk: an upgrade changing whitespace/heading
  conventions silently breaks the post-pipeline UX.
- Couples 5+ downstream consumers to a fragile contract.

## Recommended Fix (plan only)

Move L4 to a structured output:

```ts
const SoapStructured = z.object({
  subjective: z.object({
    chief_complaint: z.string(),
    hpi: z.string(),
    pmh: z.array(z.string()).default([]),
    medications: z.array(z.string()).default([]),
    allergies: z.array(z.string()).default([]),
    family_history: z.array(z.string()).default([]),
    social_history: z.array(z.string()).default([]),
    ros: z.string(),
  }),
  objective: z.object({
    physical_exam: z.string(),
    vitals: z.array(z.string()).default([]),
    test_results: z.array(z.string()).default([]),
  }),
  assessment: z.object({
    primary: z.string(),
    differentials: z.array(z.string()).default([]),
    severity: z.string().nullable(),
  }),
  plan: z.array(z.object({
    item: z.string(),
    category: z.enum(['diagnostic', 'medication', 'follow_up', 'referral', 'patient_education', 'other']),
  })).default([]),
});
```

Then `renderSoapMarkdown(structured)` produces the markdown
string for display; downstream consumers (L7c, L7d, parsers,
exporters) use the structured form directly. The user-visible
output is unchanged; the contract is enforced.

Also fixes the speaker-attribution gap (P1-005) — the structured
Plan can carry per-item speaker attribution that is dropped from
the rendered markdown.
