// ============================================================================
// Note-format customization — Phase 2a PHI gate (fail-safe)
// ----------------------------------------------------------------------------
// The output gate that guarantees no template with possible PHI is ever
// returned. Pure + testable. Two detection layers feed one fail-safe policy:
//
//   - detectStructuredPhi(): deterministic regex for structured identifiers
//     (email / phone / SSN / dates / ages / MRN-style IDs / long digit runs).
//   - the caller's LLM PHI-scan (conservative, catches names + free-text
//     clinical specifics regex can't) — fed in as `llmPhiFields` / `anyUncertain`.
//
// POLICY (fail-safe — rejects on doubt, never leaks):
//   * A flagged DEFAULT TEXT field → scrubbed (dropped to null +
//     omit_unless_supported) and noted in flags. Defaults are optional, so
//     dropping one is always safe.
//   * A flagged STRUCTURAL field (name / encounterType / label /
//     styleInstructions / styleProfile.*) → REJECT (structure can't be
//     blindly scrubbed without corrupting the template).
//   * `anyUncertain` from the LLM scan → REJECT.
//   * An LLM-flagged path that doesn't map to a known field → REJECT.
//   * After scrubbing defaults, RE-SCAN with regex; any residual hit → REJECT.
//
// Reusing redactPhi's email/phone/SSN patterns for consistency; extending with
// the identifier classes redactPhi (a log scrubber) never covered.
// ============================================================================

import type {
  ParsedTemplateDraft,
  ParseNoteResult,
} from './note-template-schema';

// ── Structured-PHI detectors. Labels are returned so flags/reasons can name
//    the class found. ──
const DETECTORS: ReadonlyArray<{ label: string; re: RegExp }> = [
  { label: 'email', re: /\b[\w.+-]+@[\w-]+\.[\w.-]+\b/ },
  { label: 'ssn', re: /\b\d{3}-?\d{2}-?\d{4}\b/ },
  { label: 'phone', re: /\(?\+?\d[\d \-()]{8,}\d/ },
  // Numeric dates: 1/2/2026, 01-02-26, 2026/01/02, ISO 2026-01-02.
  { label: 'date', re: /\b\d{1,4}[\/.-]\d{1,2}[\/.-]\d{1,4}\b/ },
  // Month-name dates: "Jan 3, 2026", "3 February 2025".
  {
    label: 'date',
    re: /\b(?:\d{1,2}\s+)?(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2}(?:,?\s+\d{2,4})?\b/i,
  },
  // Ages: "45-year-old", "45 yo", "45 y/o", "aged 7".
  { label: 'age', re: /\b\d{1,3}\s*-?\s*(?:year|yr|y\/o|yo)s?(?:[ -]?old)?\b/i },
  { label: 'age', re: /\bage[d]?\s*:?\s*\d{1,3}\b/i },
  // Record identifiers. (No trailing \b — it fails after a `#`, which is a
  // non-word char.)
  { label: 'mrn', re: /\bmrn\b/i },
  { label: 'mrn', re: /\b(?:medical record|(?:record|chart)\s*(?:no\.?|number|#))/i },
  // Long digit runs — possible MRN/account/ID. A FORMAT template should never
  // carry a 5+ digit literal.
  { label: 'long-id', re: /\b\d{5,}\b/ },
];

/** Return the distinct structured-PHI class labels found in `text`. Empty
 *  when none. Deterministic. */
export function detectStructuredPhi(text: string | null | undefined): string[] {
  if (!text) return [];
  const found = new Set<string>();
  for (const d of DETECTORS) {
    if (d.re.test(text)) found.add(d.label);
  }
  return [...found];
}

/** Enumerate every text field of a draft with its canonical path (the same
 *  path vocabulary the LLM PHI-scan is instructed to use). */
export function enumerateTextFields(
  draft: ParsedTemplateDraft
): Array<{ path: string; value: string; isDefaultText: boolean }> {
  const fields: Array<{ path: string; value: string; isDefaultText: boolean }> = [];
  const push = (path: string, value: string | null, isDefaultText = false) => {
    if (value != null && value.trim() !== '') fields.push({ path, value, isDefaultText });
  };
  push('name', draft.name);
  push('encounterType', draft.encounterType);
  push('styleProfile.tense', draft.styleProfile.tense);
  push('styleProfile.tone', draft.styleProfile.tone);
  push('styleProfile.abbreviations', draft.styleProfile.abbreviations);
  draft.sections.forEach((s, i) => {
    push(`sections[${i}].label`, s.label);
    push(`sections[${i}].styleInstructions`, s.styleInstructions);
    push(`sections[${i}].defaultText`, s.defaultText, true);
  });
  return fields;
}

/**
 * Apply the fail-safe PHI gate. Pure: given a built draft + the LLM scan
 * result, return either a scrubbed clean draft (+ flags) or a rejection.
 *
 * @param draft           the built template draft
 * @param baseFlags       extraction-time flags (uncertain phrases the model omitted)
 * @param llmPhiFields    field paths the LLM PHI-scan flagged
 * @param llmAnyUncertain LLM scan's uncertainty bit
 */
export function applyPhiGate(
  draft: ParsedTemplateDraft,
  baseFlags: string[],
  llmPhiFields: string[],
  llmAnyUncertain: boolean
): ParseNoteResult {
  const flags = [...baseFlags];

  // 0. LLM not confident the output is clean → reject (fail-safe).
  if (llmAnyUncertain) {
    return {
      rejected: true,
      template: null,
      reason:
        'PHI scan could not confidently clear the parsed template. Try a blank template, or remove patient details from the note and re-parse.',
    };
  }

  const fields = enumerateTextFields(draft);
  const fieldByPath = new Map(fields.map((f) => [f.path, f]));

  // 1. Determine offending fields: regex hits (precise) ∪ LLM-flagged paths.
  const offending = new Map<string, { isDefaultText: boolean; classes: string[] }>();
  for (const f of fields) {
    const classes = detectStructuredPhi(f.value);
    if (classes.length > 0) {
      offending.set(f.path, { isDefaultText: f.isDefaultText, classes });
    }
  }
  for (const path of llmPhiFields) {
    const f = fieldByPath.get(path);
    if (!f) {
      // LLM flagged a path we can't map → can't safely scrub → reject.
      return {
        rejected: true,
        template: null,
        reason: `PHI scan flagged an unrecognized field (${path}); refusing to return a possibly-unsafe template.`,
      };
    }
    const existing = offending.get(path);
    if (existing) existing.classes.push('llm');
    else offending.set(path, { isDefaultText: f.isDefaultText, classes: ['llm'] });
  }

  // 2. Any STRUCTURAL field flagged → reject. Defaults → scrub.
  const scrubbedSections = draft.sections.map((s) => ({ ...s }));
  for (const [path, info] of offending) {
    if (!info.isDefaultText) {
      return {
        rejected: true,
        template: null,
        reason: `Possible PHI in a structural field (${path}: ${info.classes.join('/')}). Couldn't safely strip it — use a blank template or remove patient details.`,
      };
    }
    // Scrub the offending defaultText: drop it + downgrade the mode.
    const m = path.match(/^sections\[(\d+)\]\.defaultText$/);
    if (!m) {
      return {
        rejected: true,
        template: null,
        reason: `PHI flagged in an unscrubable field (${path}).`,
      };
    }
    const idx = Number(m[1]);
    scrubbedSections[idx] = {
      ...scrubbedSections[idx],
      defaultText: null,
      defaultTextMode: 'omit_unless_supported',
    };
    flags.push(
      `Dropped a possible-PHI default from "${scrubbedSections[idx].label}" — add a generic default manually if needed.`
    );
  }

  const scrubbed: ParsedTemplateDraft = { ...draft, sections: scrubbedSections };

  // 3. Belt-and-suspenders: re-scan the scrubbed draft. Any residual structured
  //    hit (should be none after scrubbing defaults) → reject.
  for (const f of enumerateTextFields(scrubbed)) {
    if (detectStructuredPhi(f.value).length > 0) {
      return {
        rejected: true,
        template: null,
        reason: `Residual possible-PHI after scrubbing (${f.path}). Refusing to return.`,
      };
    }
  }

  return { rejected: false, template: scrubbed, flags };
}
