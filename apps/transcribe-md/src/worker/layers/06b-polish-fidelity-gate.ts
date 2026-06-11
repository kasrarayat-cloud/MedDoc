// ============================================================================
// L6b — post-polish fabrication gate (2026-06-11)
// ----------------------------------------------------------------------------
// Structural fix for the hallucination-reconciliation RED finding
// (docs/qa-reports/hallucination-reconciliation-20260611T072219Z.md): the
// L5 self-critique runs BEFORE L6 polish, so it can never catch clinical
// content L6 ADDS (contraindication reasoning, referrals, red-flag
// narratives — all verified fabrications on PriMock57). This gate runs
// AFTER the polish model call and verifies the polished note introduces no
// new clinical claims relative to its input (the L4 draft + the critique's
// permitted fixes).
//
// FAIL-CLOSED CONTRACT (the load-bearing property):
//   - The gate NEVER throws. Every internal failure — verifier API error,
//     refusal, unparseable/malformed verdict, unexpected exception — returns
//     { ok:false, gateError } so the caller falls back to the pre-L6 draft.
//   - Losing polish is acceptable; gaining content is not. There is no path
//     through this module that lets unverified L6 output ship.
//
// Mechanism (hybrid):
//   1. A deterministic novel-content-term scan (pure, no model) produces a
//      telemetry signal — how many content words appear in the polished
//      note that exist nowhere in its input. It is deliberately NOT an
//      acceptor: a negation flip ("no chest pain" → "chest pain") adds
//      zero novel words, so a clean scan cannot prove fidelity.
//   2. A focused verifier model call (tm_polish_gate) diffs the polished
//      note against the draft + permitted fixes and reports violations:
//      additions (new findings / diagnoses / contraindication or risk
//      reasoning / referrals / screenings / follow-up / education / meds /
//      doses) and meaning changes (negation flips). Any violation → reject.
//
// PHI: the gate result carries counts + enum-class strings only. Verifier
// violation summaries are NOT propagated into audit metadata by the caller.
// ============================================================================

import { z } from 'zod';
import { modelClient } from '@meddoc/ai';

// Same env override pattern as L4/L5/L6 (feat/fable5-eval); unset → Sonnet.
const MODEL = process.env.TRANSCRIBE_MD_CLINICAL_MODEL || 'claude-sonnet-4-6';

const VerifierVerdict = z.object({
  violations: z
    .array(
      z.object({
        kind: z.enum(['addition', 'meaning_change']),
        summary: z.string(),
      })
    )
    .default([]),
});
export type VerifierVerdict = z.infer<typeof VerifierVerdict>;

export type PolishFidelityGateResult =
  | { ok: true; novelTermCount: number }
  | {
      ok: false;
      violationCount: number;
      /** Distinct violation kinds — enum-class strings, PHI-safe. */
      kinds: string[];
      novelTermCount: number;
      /** Non-null when the gate itself failed (fail-closed reject). */
      gateError: string | null;
    };

export interface PolishFidelityGateInput {
  practiceId: string;
  visitId: string;
  userId: string | null;
  /** The pre-L6 note (L4 draft) — the gate's source of truth. */
  draft: string;
  /** The critique's fixable-issue text L6 was permitted to apply. */
  fixesText: string;
  /** L6's model output under test. */
  polished: string;
}

// ---------------------------------------------------------------------------
// Deterministic novel-term scan (telemetry only — see header for why it is
// not an acceptor). Tokens: lowercase alphanumeric/hyphen/apostrophe words
// of length ≥ 4, minus a small neutral stopword set.
// ---------------------------------------------------------------------------
const STOPWORDS = new Set([
  'with', 'that', 'this', 'these', 'those', 'have', 'been', 'were', 'will',
  'from', 'into', 'over', 'under', 'after', 'before', 'during', 'their',
  'there', 'about', 'also', 'than', 'then', 'when', 'which', 'while',
  'patient', 'patients', 'reports', 'reported', 'denies', 'denied', 'notes',
  'noted', 'states', 'stated', 'history', 'present', 'presents', 'without',
  'follow', 'visit', 'documented', 'discussed', 'review', 'plan',
  'assessment', 'objective', 'subjective', 'continue', 'recommend',
  'recommended', 'advised', 'including', 'consistent', 'within',
]);

function contentTerms(text: string): Set<string> {
  const out = new Set<string>();
  for (const m of text.toLowerCase().matchAll(/[a-z][a-z0-9'-]{3,}/g)) {
    const t = m[0];
    if (!STOPWORDS.has(t)) out.add(t);
  }
  return out;
}

/** Content words in `output` that appear in none of the `base` texts. */
export function findNovelContentTerms(
  base: string[],
  output: string
): string[] {
  const allowed = new Set<string>();
  for (const b of base) for (const t of contentTerms(b)) allowed.add(t);
  const novel: string[] = [];
  for (const t of contentTerms(output)) {
    if (!allowed.has(t)) novel.push(t);
  }
  return novel;
}

// ---------------------------------------------------------------------------
// Verifier-verdict extraction. Tolerates prose/fences around the JSON (the
// #200 judge-parse lesson) but stays STRICT about shape: anything that does
// not Zod-parse to { violations: [...] } is a gate error → fail-closed.
// ---------------------------------------------------------------------------
function extractFirstJsonObject(text: string): string | null {
  const start = text.indexOf('{');
  if (start === -1) return null;
  let depth = 0;
  let inString = false;
  let escaped = false;
  for (let i = start; i < text.length; i++) {
    const c = text[i];
    if (escaped) {
      escaped = false;
    } else if (c === '\\') {
      escaped = true;
    } else if (c === '"') {
      inString = !inString;
    } else if (!inString) {
      if (c === '{') depth++;
      else if (c === '}') {
        depth--;
        if (depth === 0) return text.slice(start, i + 1);
      }
    }
  }
  return null;
}

const VERIFIER_SYSTEM = [
  'You are a fidelity auditor for clinical-note editing. You receive a',
  'SOURCE draft note, a list of PERMITTED FIXES, and an EDITED note. Your',
  'only job is to detect whether the EDITED note contains clinical content',
  'that is NOT present in (or directly entailed by) the SOURCE draft or',
  'the permitted fixes.',
  '',
  'Report a violation for ANY of:',
  '- a new finding, symptom, exam result, diagnosis, or differential',
  '- new contraindication, risk, or safety reasoning',
  '- a new referral, screening or red-flag statement, follow-up',
  '  instruction, or patient education',
  '- a new medication, dose, or dosing change',
  '- a negation flip or meaning change of an existing statement',
  '',
  'Do NOT report: rewording, reordering, formatting, structural-header',
  'changes, abbreviation expansion of the same content, deletions, or text',
  'taken directly from the permitted fixes.',
  '',
  'Output STRICT JSON only — no prose, no markdown fences:',
  '{"violations":[{"kind":"addition","summary":"<max 20 words>"}]}',
  'Use kind "meaning_change" for negation/meaning flips. An empty array',
  'means the edit is faithful.',
].join('\n');

/**
 * Verify L6's polished output against its input. NEVER throws — every
 * failure mode returns { ok:false } (fail-closed; the caller falls back to
 * the pre-L6 draft).
 */
export async function runPolishFidelityGate(
  input: PolishFidelityGateInput
): Promise<PolishFidelityGateResult> {
  let novelTermCount = 0;
  try {
    novelTermCount = findNovelContentTerms(
      [input.draft, input.fixesText],
      input.polished
    ).length;

    const user = [
      'SOURCE DRAFT:',
      input.draft,
      '',
      'PERMITTED FIXES:',
      input.fixesText || '(none)',
      '',
      'EDITED NOTE:',
      input.polished,
    ].join('\n');

    const { text } = await modelClient.completeText({
      practiceId: input.practiceId,
      visitId: input.visitId,
      userId: input.userId,
      purpose: 'tm_polish_gate',
      provider: 'anthropic',
      model: MODEL,
      system: VERIFIER_SYSTEM,
      user,
      maxTokens: 1024,
      temperature: 0,
    });

    const raw = extractFirstJsonObject(text ?? '');
    if (!raw) {
      return {
        ok: false,
        violationCount: 0,
        kinds: [],
        novelTermCount,
        gateError: 'verifier_output_not_json',
      };
    }
    const parsed = VerifierVerdict.safeParse(JSON.parse(raw));
    if (!parsed.success) {
      return {
        ok: false,
        violationCount: 0,
        kinds: [],
        novelTermCount,
        gateError: 'verifier_verdict_malformed',
      };
    }

    const violations = parsed.data.violations;
    if (violations.length > 0) {
      return {
        ok: false,
        violationCount: violations.length,
        kinds: [...new Set(violations.map((v) => v.kind))],
        novelTermCount,
        gateError: null,
      };
    }
    return { ok: true, novelTermCount };
  } catch {
    // Verifier call failed (API error, refusal, JSON.parse throw, anything).
    // Fail-closed: reject so the caller keeps the measured-clean draft.
    return {
      ok: false,
      violationCount: 0,
      kinds: [],
      novelTermCount,
      gateError: 'verifier_call_failed',
    };
  }
}
