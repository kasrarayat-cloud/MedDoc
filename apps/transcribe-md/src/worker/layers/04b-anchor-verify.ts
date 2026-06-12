// ============================================================================
// L4b — anchored-claim verification (hybrid evidence-anchored generation).
// ----------------------------------------------------------------------------
// Design: docs/strategy/evidence-anchored-generation-20260611T214934Z.md
// (path 1: anchors + fail-closed entailment). Spike findings carried in:
// the model anchors reliably (98% verbatim-quote fidelity) but DETERMINISTIC
// token-derivability cannot bridge register translation ("had migraines in
// the past? No." → "no prior diagnosis of migraines"), so derivability is
// judged by a focused per-claim ENTAILMENT verifier (tm_anchor_entailment),
// with the spike's deterministic digit/negation rules kept as HARD OVERRIDES
// that the model verdict cannot overrule.
//
// HONEST FRAMING (carried through all docs): this is "deterministic anchors
// + fail-closed model entailment, measured under a pre-registered protocol"
// — NOT "mechanically impossible to fabricate".
//
// FAIL-CLOSED CONTRACT (the L6b-gate lessons, regression-pinned):
//   - This module NEVER throws. Any uncertainty, verifier API error,
//     malformed/ambiguous verdict, missing per-claim verdict, or internal
//     exception DEMOTES the claim(s) to the suggestions lane.
//   - The verdict schema is STRICT — no .default() anywhere (the L6b BLOCK-1
//     class); a missing `verdicts` key is malformed, not approval.
//   - Demoted ≠ deleted: every demoted claim lands in the lane with its
//     anchor text (or 'no anchor') attached, for explicit doctor adoption.
//
// ANCHOR GRAMMARS (both accepted — the spike's instrument lesson):
//   ⟦A:"span one ... span two"⟧   and   ⟦A:"span one" ... "span two"⟧
//   ⟦S⟧ = the model itself proposes the claim as a suggestion.
// ============================================================================

import { z } from 'zod';
import { modelClient } from '@meddoc/ai';

const MODEL = process.env.TRANSCRIBE_MD_CLINICAL_MODEL || 'claude-sonnet-4-6';

export const ANCHOR_BLOCK_RE = /⟦A:([\s\S]*?)⟧/g;
export const SUGGEST_MARK = '⟦S⟧';

/** Appended to the L4 system prompt when TRANSCRIBE_MD_EVIDENCE_ANCHORS is
 *  on (production wording of the spike addendum — 98% quote fidelity
 *  measured). Flag off → the prompt is byte-identical to today's. */
export const ANCHOR_GENERATION_ADDENDUM = [
  '',
  'EVIDENCE ANCHORS (required — adds to, never overrides, the rules above):',
  'After EVERY sentence that asserts clinical content (symptoms, findings,',
  'negatives, history, medications, doses, diagnoses, assessments, plan',
  'items, instructions, education), append one or more anchors of the form',
  '⟦A:"<verbatim transcript quote>"⟧ quoting the transcript span(s) that',
  'support it, copied EXACTLY as written in the transcript (you may join up',
  'to 3 sub-spans with " ... "). If a sentence is clinically appropriate but',
  'you CANNOT quote transcript support for it, append ⟦S⟧ instead — it will',
  'be routed to a clinician suggestions list rather than the note body.',
  'Structural headers and "[not documented]" placeholders need no anchor.',
  '',
  'ANCHORING MUST NOT REDUCE COMPLETENESS (iteration 1): document EVERY',
  'clinically relevant statement from the transcript — each ROS answer',
  'including denials, social history, patient concerns and expectations,',
  'instructions, demographics — each with its anchor. When you are unsure',
  'whether support is quotable, WRITE THE SENTENCE with ⟦S⟧ rather than',
  'omitting it: an omitted fact is lost, a suggested one is one click away.',
].join('\n');

export type DemotionReason =
  | 'model_suggested'
  | 'no_anchor'
  | 'anchor_not_in_transcript'
  | 'anchor_overlaps_unclear'
  | 'digits_unsupported'
  | 'negation_mismatch'
  | 'not_entailed'
  | 'verifier_failed';

export interface SuggestedClaim {
  text: string;
  reason: DemotionReason;
  section: string;
  /** The anchor quote(s) the model offered, joined — or 'no anchor'. */
  anchor: string;
}

export interface AnchorVerifyResult {
  body: string;
  suggestions: SuggestedClaim[];
  stats: {
    anchored: number;
    demoted: number;
    entailmentChecked: number;
    verifierErrored: boolean;
  };
}

// ─── Normalization + deterministic rules (spike rules, kept verbatim) ───────
const NEGATION_RE = /\b(no|not|denies|denied|without|negative|none)\b/i;

function norm(s: string): string {
  return s
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

/** Transcript prepared for literal quote matching: role-prefixes stripped
 *  (no legitimate quote contains "[Doctor #0, 0:12]:"), newlines → space. */
export function transcriptForMatching(roleLabeled: string): string {
  return norm(roleLabeled.replace(/^\[[^\]]+\]:\s*/gm, '').replace(/\n/g, ' '));
}

function digitTokens(s: string): string[] {
  return norm(s).match(/\d+(?:\.\d+)?/g) ?? [];
}

/** All sub-span strings from one anchor block body (both grammars). */
export function anchorSubSpans(body: string): string[] {
  const quoted = [...body.matchAll(/"((?:[^"\\]|\\.)*?)"/g)].map((m) => m[1]);
  const sources = quoted.length > 0 ? quoted : [body];
  return sources.flatMap((s) => s.split(' ... ')).map((s) => s.trim()).filter(Boolean);
}

function isExemptLine(stripped: string): boolean {
  const t = stripped.trim();
  if (t.length === 0) return true;
  if (/^#{1,6}\s/.test(t)) return true;
  if (/^\*\*[^*]+\*\*:?\s*$/.test(t)) return true;
  if (/^(?:[-*\d.]\s*)*(?:\*\*[^*]+\*\*:?\s*)?\[not documented\]\.?$/i.test(t)) return true;
  if (/not (formally )?documented in this encounter/i.test(t) && t.length < 100) return true;
  return false;
}

interface ClaimRow {
  index: number;
  text: string; // anchor-free claim text
  section: string;
  spans: string[]; // normalized matched spans (clear sub-spans only)
  anchorRaw: string;
}

/** Deterministic stage. Returns claims that SURVIVE to entailment, plus the
 *  claims already demoted by hard rules (which entailment cannot overrule). */
function deterministicStage(
  anchoredDraft: string,
  roleLabeledTranscript: string
): {
  exemptLines: Map<number, string>;
  toEntail: ClaimRow[];
  demoted: (SuggestedClaim & { index: number })[];
  lineCount: number;
} {
  const asrNorm = transcriptForMatching(roleLabeledTranscript);
  const exemptLines = new Map<number, string>();
  const toEntail: ClaimRow[] = [];
  const demoted: (SuggestedClaim & { index: number })[] = [];
  let section = '(preamble)';
  const lines = anchoredDraft.split('\n');
  lines.forEach((rawLine, index) => {
    const h = rawLine.match(/^#{1,6}\s+(.*)$/);
    if (h) section = h[1].trim();
    const blocks = [...rawLine.matchAll(ANCHOR_BLOCK_RE)].map((m) => m[1]);
    const subSpans = blocks.flatMap(anchorSubSpans);
    const modelSuggested = rawLine.includes(SUGGEST_MARK);
    const stripped = rawLine
      .replace(ANCHOR_BLOCK_RE, '')
      .split(SUGGEST_MARK)
      .join('')
      .replace(/\s+$/g, '');
    if (isExemptLine(stripped)) {
      exemptLines.set(index, stripped);
      return;
    }
    const anchorRaw = subSpans.length > 0 ? subSpans.join(' | ') : 'no anchor';
    const demote = (reason: DemotionReason) =>
      demoted.push({ index, text: stripped.trim(), reason, section, anchor: anchorRaw });

    if (modelSuggested && subSpans.length === 0) return demote('model_suggested');
    if (subSpans.length === 0) return demote('no_anchor');

    // Anchor existence — every CLEAR sub-span must literally exist in the
    // transcript after normalization; sub-spans overlapping the unclear
    // marker contribute nothing (refined from the spike: one marked span
    // no longer voids the whole anchor).
    const spans: string[] = [];
    let sawUnclearOnly = true;
    for (const sub of subSpans) {
      if (/unclear in recording/i.test(sub)) continue; // contributes nothing
      sawUnclearOnly = false;
      const nsub = norm(sub);
      if ((nsub.match(/[a-z0-9]+/g) ?? []).length < 3)
        return demote('anchor_not_in_transcript');
      if (!asrNorm.includes(nsub)) return demote('anchor_not_in_transcript');
      spans.push(nsub);
    }
    if (spans.length === 0)
      return demote(sawUnclearOnly ? 'anchor_overlaps_unclear' : 'anchor_not_in_transcript');

    // HARD OVERRIDES — the model verdict cannot overrule these. List
    // markers ("1.", "- ") are formatting, not clinical digits/content —
    // excluded from the checks (the lane/body keep the full line text).
    const claimCore = stripped.replace(/^\s*(?:\d+[.)]\s+|[-*]\s+)/, '');
    const spanText = spans.join(' ');
    for (const d of digitTokens(claimCore)) {
      if (!spanText.includes(d)) return demote('digits_unsupported');
    }
    if (NEGATION_RE.test(claimCore) !== NEGATION_RE.test(spanText))
      return demote('negation_mismatch');

    toEntail.push({ index, text: stripped.trim(), section, spans, anchorRaw });
  });
  return { exemptLines, toEntail, demoted, lineCount: lines.length };
}

// ─── Entailment verifier (fail-closed) ──────────────────────────────────────
// STRICT schema — `verdicts` REQUIRED, every element fully typed, NO
// .default() (the L6b BLOCK-1 fail-open class).
const EntailmentVerdicts = z.object({
  verdicts: z.array(
    z.object({
      i: z.number().int(),
      entailed: z.boolean(),
    })
  ),
});

function extractAllJsonObjects(text: string): string[] {
  const out: string[] = [];
  let i = 0;
  while (i < text.length) {
    const start = text.indexOf('{', i);
    if (start === -1) break;
    let depth = 0, inStr = false, esc = false, end = -1;
    for (let j = start; j < text.length; j++) {
      const c = text[j];
      if (esc) esc = false;
      else if (c === '\\') esc = true;
      else if (c === '"') inStr = !inStr;
      else if (!inStr) {
        if (c === '{') depth++;
        else if (c === '}') { depth--; if (depth === 0) { end = j; break; } }
      }
    }
    if (end === -1) break;
    out.push(text.slice(start, end + 1));
    i = end + 1;
  }
  return out;
}

const ENTAILMENT_SYSTEM = [
  'You verify clinical-note claims against their quoted transcript evidence.',
  'For EACH numbered claim you receive the claim text and the verbatim',
  'transcript span(s) it cites (with surrounding context). Decide: is the',
  'claim FULLY ENTAILED by its cited span(s) — i.e. a faithful clinical',
  'restatement introducing NO clinical content beyond them? Register',
  'translation of the SAME fact is entailed ("had migraines in the past?',
  'No. No." entails "No prior diagnosis of migraines"). New diagnoses,',
  'differentials, severity, laterality, devices, doses, possession claims,',
  'causal links, or screening/process assertions NOT in the spans are NOT',
  'entailed. When uncertain, answer entailed=false.',
  '',
  'Enforce these STRICTLY (enablement-gate iteration 1 — the measured',
  'escape classes):',
  '- A NEGATIVE finding ("no X", "denies X") is entailed ONLY if the span',
  '  itself asks about or denies THAT SPECIFIC symptom/system. A span',
  '  denying something else never entails a different negative.',
  '- Laterality (left/right/bilateral), quality descriptors (pleuritic,',
  '  crushing, throbbing), and severity words are entailed ONLY if the',
  '  span states them — never inferred from context.',
  '- Process/logistics specifics (how a prescription is sent, where to,',
  '  what was screened, what was documented) are entailed ONLY if the',
  '  span states the mechanism — "we will send the prescription" does NOT',
  '  entail "sent electronically to the pharmacy".',
  '',
  'Respond STRICT JSON only, no prose, no fences:',
  '{"verdicts":[{"i":<claim number>,"entailed":true|false}]}',
  'Include EVERY claim number exactly once.',
].join('\n');

/** Surrounding utterance context for a span (the line(s) containing it). */
function spanContext(spans: string[], roleLabeled: string): string {
  const lines = roleLabeled.split('\n');
  const hits = new Set<string>();
  for (const span of spans) {
    const probe = span.split(' ').slice(0, 5).join(' ');
    for (const l of lines) {
      if (norm(l).includes(probe)) { hits.add(l); break; }
    }
  }
  return [...hits].join('\n');
}

async function entailmentStage(
  claims: ClaimRow[],
  roleLabeledTranscript: string,
  ids: { practiceId: string; visitId: string; userId: string | null }
): Promise<{ entailedIdx: Set<number>; errored: boolean }> {
  if (claims.length === 0) return { entailedIdx: new Set(), errored: false };
  // MOCK short-circuit: under MOCK_AI_CALLS the mock "model" approves —
  // mirrors every other mock fixture; reject/fail-closed paths are covered
  // by deterministic unit tests, never by the MOCK e2e flow.
  if (process.env.MOCK_AI_CALLS === 'true') {
    return { entailedIdx: new Set(claims.map((c) => c.index)), errored: false };
  }
  try {
    const user = claims
      .map((c, k) =>
        [
          `CLAIM ${k}: ${c.text}`,
          `CITED SPAN(S): ${c.anchorRaw}`,
          `CONTEXT: ${spanContext(c.spans, roleLabeledTranscript) || '(no context located)'}`,
        ].join('\n')
      )
      .join('\n\n');
    const { text } = await modelClient.completeText({
      practiceId: ids.practiceId,
      visitId: ids.visitId,
      userId: ids.userId,
      purpose: 'tm_anchor_entailment',
      provider: 'anthropic',
      model: MODEL,
      system: ENTAILMENT_SYSTEM,
      user,
      maxTokens: 2048,
      temperature: 0,
    });
    const objects = extractAllJsonObjects(text ?? '');
    const valid = objects
      .map((raw) => {
        try { return EntailmentVerdicts.safeParse(JSON.parse(raw)); } catch { return null; }
      })
      .filter((p): p is NonNullable<typeof p> => p !== null && p.success)
      .map((p) => (p as { data: z.infer<typeof EntailmentVerdicts> }).data);
    if (valid.length !== 1) return { entailedIdx: new Set(), errored: true }; // none or ambiguous → fail-closed
    const verdicts = valid[0].verdicts;
    const entailedIdx = new Set<number>();
    claims.forEach((c, k) => {
      const v = verdicts.filter((x) => x.i === k);
      // exactly one verdict per claim; duplicates/missing → demote (fail-closed)
      if (v.length === 1 && v[0].entailed === true) entailedIdx.add(c.index);
    });
    return { entailedIdx, errored: false };
  } catch {
    return { entailedIdx: new Set(), errored: true }; // API failure → demote all
  }
}

// ─── Public entry ───────────────────────────────────────────────────────────
export async function runAnchorVerify(input: {
  visitId: string;
  practiceId: string;
  userId: string | null;
  anchoredDraft: string;
  roleLabeledTranscript: string;
}): Promise<AnchorVerifyResult> {
  try {
    const det = deterministicStage(input.anchoredDraft, input.roleLabeledTranscript);
    const ent = await entailmentStage(det.toEntail, input.roleLabeledTranscript, input);

    const demotedByIndex = new Map<number, SuggestedClaim>();
    for (const d of det.demoted) demotedByIndex.set(d.index, d);
    let entailmentDemotions = 0;
    for (const c of det.toEntail) {
      if (!ent.entailedIdx.has(c.index)) {
        entailmentDemotions++;
        demotedByIndex.set(c.index, {
          text: c.text,
          reason: ent.errored ? 'verifier_failed' : 'not_entailed',
          section: c.section,
          anchor: c.anchorRaw,
        });
      }
    }

    // Rebuild the body in original line order: exempt lines + surviving claims.
    const lines = input.anchoredDraft.split('\n');
    const bodyLines: string[] = [];
    lines.forEach((rawLine, index) => {
      if (det.exemptLines.has(index)) { bodyLines.push(det.exemptLines.get(index)!); return; }
      if (demotedByIndex.has(index)) return;
      const claim = det.toEntail.find((c) => c.index === index);
      if (claim) {
        bodyLines.push(
          rawLine.replace(ANCHOR_BLOCK_RE, '').split(SUGGEST_MARK).join('').replace(/\s+$/g, '')
        );
      }
      // lines that are neither exempt, demoted, nor verified claims do not
      // exist (deterministicStage covers every line) — defensive: drop.
    });
    const body = bodyLines.join('\n').replace(/\n{3,}/g, '\n\n').trim();
    const suggestions = [...demotedByIndex.entries()]
      .sort((a, b) => a[0] - b[0])
      .map(([, s]) => s);

    return {
      body,
      suggestions,
      stats: {
        anchored: det.toEntail.length - entailmentDemotions,
        demoted: suggestions.length,
        entailmentChecked: det.toEntail.length,
        verifierErrored: ent.errored,
      },
    };
  } catch {
    // Catastrophic internal failure: serve NOTHING unverified. The whole
    // draft demotes to one suggestion so the doctor still sees the content,
    // labeled — never an unverified body.
    return {
      body: '',
      suggestions: [
        {
          text: input.anchoredDraft.replace(ANCHOR_BLOCK_RE, '').split(SUGGEST_MARK).join(''),
          reason: 'verifier_failed',
          section: '(entire note)',
          anchor: 'no anchor',
        },
      ],
      stats: { anchored: 0, demoted: 1, entailmentChecked: 0, verifierErrored: true },
    };
  }
}
