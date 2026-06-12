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
  'FIRST write the COMPLETE note you would normally write — the same length,',
  'coverage, and detail as if anchors did not exist: every ROS answer',
  'including denials, all social history, medications with timing, patient',
  'concerns and expectations, demographics, and every plan item. Anchoring',
  'must never make the note shorter or less complete.',
  '',
  'THEN, after EVERY sentence that asserts clinical content, append one or',
  'more anchors of the form ⟦A:"<verbatim transcript quote>"⟧ quoting the',
  'transcript span(s) that support it, copied EXACTLY as written (you may',
  'join up to 3 sub-spans with " ... "). If a sentence is clinically',
  'appropriate but you CANNOT quote transcript support for it, append ⟦S⟧',
  'instead — it will be routed to a clinician suggestions list rather than',
  'the note body. NEVER omit a fact because its anchor is hard to find:',
  'an omitted fact is lost, a suggested one is one click away.',
  'Structural headers and "[not documented]" placeholders need no anchor.',
].join('\n');

export type DemotionReason =
  | 'model_suggested'
  | 'no_anchor'
  | 'anchor_not_in_transcript'
  | 'anchor_overlaps_unclear'
  | 'digits_unsupported'
  | 'negation_mismatch'
  | 'gloss_unsupported'
  | 'process_assertion_unsupported'
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
    /** Ensemble passes (of 3) that errored — telemetry only. */
    entailmentPassErrors?: number;
  };
}

// ─── Normalization + deterministic rules (spike rules, kept verbatim) ───────
const NEGATION_RE = /\b(no|not|denies|denied|without|negative|none)\b/i;

/** Clinical-register filler excluded from subject/gloss token matching —
 *  ONE list shared by the negation-subject and gloss overrides (auditor
 *  NIT-1: was maintained by copy-paste). */
const REGISTER_WORDS = ['known', 'other', 'further', 'significant', 'formal', 'prior'];

// Iteration 4 (decisive-run attribution) — CLINICAL-REASONING VERBS. All
// three unanimous residuals asserted a reasoning/certainty ACT the visit
// never spoke: "if migraine with aura is CONFIRMED" (a contingency plan),
// "mother CONFIRMED antihistamines available", "PE was CONSIDERED and
// partially ADDRESSED by history". Deterministic rule: a claim using one
// of these verbs must cite a span that uses the same verb stem — symptom
// talk or Q&A never entails that something was confirmed / considered /
// ruled out / screened / addressed.
// Verb INFLECTIONS only — bare "screen"/"address"/"rule" are common nouns
// ("screen-related eye strain", "home address", "as a rule") and must not
// trip the override; the fabrication register uses the verb forms
// ("screened and denied", "addressed by history", "ruled out").
const PROCESS_VERB_RE =
  /\b(confirm\w*|consider\w*|exclud\w*|screen(?:ed|ing)\w*|establish\w*|address(?:ed|ing)\w*|verif\w*|rul(?:e|es|ing)\s+out|ruled)\b/gi;
/** Stem (≥4 chars, enough to match across inflections) for span lookup. */
function processStems(s: string): string[] {
  return [...s.matchAll(PROCESS_VERB_RE)].map((m) =>
    m[1].toLowerCase().startsWith('rul') ? 'rule' : m[1].toLowerCase().slice(0, 5)
  );
}

// Iteration 5 (gate re-run #1 attribution) — DRUG FORM / ROUTE / CLASS
// SPECIFICATION. Both residuals specified beyond the span: "the pill" →
// "ORAL CONTRACEPTIVE pill", "steroid cream" → "TOPICAL steroid cream".
// A form/route/class adjective in a claim must appear in the anchored
// span (prefix-5, like every other override). Bounded lexicon — these
// adjectives are near-always model register, near-never patient speech.
const FORM_ROUTE_WORDS = [
  'oral', 'topical', 'intravenous', 'intramuscular', 'subcutaneous',
  'inhaled', 'nasal', 'rectal', 'sublingual', 'transdermal', 'ophthalmic',
  'contraceptive', 'systemic',
];
function formRouteTokens(s: string): string[] {
  const toks = norm(s).match(/[a-z]+/g) ?? [];
  return toks.filter((t) => FORM_ROUTE_WORDS.includes(t));
}

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

// Iteration 3 (gate run-3 attribution) — QUANTIFICATION uses words as often
// as digits ("cut down to two glasses per week, then one"). Spelled numbers
// fall under the digits hard override: a claim's number-words must be
// supported by the span in word OR digit form. Bare "one" is excluded
// (pronoun homonym — "no one", "which one" — would false-demote constantly);
// "once"/"twice" and all other number words are checked.
const NUMBER_WORDS: Record<string, string> = {
  two: '2', three: '3', four: '4', five: '5', six: '6', seven: '7',
  eight: '8', nine: '9', ten: '10', eleven: '11', twelve: '12',
  thirteen: '13', fourteen: '14', fifteen: '15', sixteen: '16',
  seventeen: '17', eighteen: '18', nineteen: '19', twenty: '20',
  thirty: '30', forty: '40', fifty: '50', sixty: '60', seventy: '70',
  eighty: '80', ninety: '90', hundred: '100', thousand: '1000',
  once: '1', twice: '2',
};
const DIGIT_TO_WORD: Record<string, string[]> = Object.entries(
  NUMBER_WORDS
).reduce<Record<string, string[]>>((acc, [w, d]) => {
  (acc[d] = acc[d] ?? []).push(w);
  return acc;
}, {});

function numberWordTokens(s: string): { word: string; digit: string }[] {
  const out: { word: string; digit: string }[] = [];
  for (const t of norm(s).match(/[a-z]+/g) ?? []) {
    if (NUMBER_WORDS[t]) out.push({ word: t, digit: NUMBER_WORDS[t] });
  }
  return out;
}

/** Span supports a digit if it contains the digit string or a word form of
 *  it ("2" ↔ "two"/"twice"). Used by both directions of the quant override. */
function spanSupportsDigit(spanText: string, digit: string): boolean {
  if (spanText.includes(digit)) return true;
  return (DIGIT_TO_WORD[digit] ?? []).some((w) =>
    new RegExp(`\\b${w}\\b`).test(spanText)
  );
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
      if (!spanSupportsDigit(spanText, d)) return demote('digits_unsupported');
    }
    // Iteration 3 — spelled quantification is digits ("two glasses per week,
    // then one" must be in the span as words or digits, like "75 mg").
    for (const { word, digit } of numberWordTokens(claimCore)) {
      if (
        !new RegExp(`\\b${word}\\b`).test(spanText) &&
        !spanText.includes(digit)
      )
        return demote('digits_unsupported');
    }
    // Iteration 3 — PARENTHETICAL GLOSS: an explanation/definition/expansion
    // the model adds in parentheses ("fundoscopy (examination of the back of
    // the eyes)") is clinical content; if NO content token of the gloss
    // appears in the span (prefix-5, like the negation rule), demote. A
    // gloss with no ≥5-char token (e.g. an acronym "(COC)") is not checked.
    for (const g of claimCore.matchAll(/\(([^)]{3,})\)/g)) {
      const tokens = (norm(g[1]).match(/[a-z]{5,}/g) ?? []).filter(
        (t) => !REGISTER_WORDS.includes(t)
      );
      if (tokens.length > 0 && !tokens.some((t) => spanText.includes(t.slice(0, 5))))
        return demote('gloss_unsupported');
    }
    // Iteration 4 — clinical-reasoning verbs must be span-stated. The
    // span check uses the verb STEM ("rule" matches "ruled out"; "confi"
    // matches "confirm/confirmed/confirming"); a span that itself speaks
    // the act legitimately supports it.
    for (const stem of processStems(claimCore)) {
      const spanStem = stem === 'rule' ? /\brul(?:e|ed|es|ing)\b/ : null;
      const supported = spanStem
        ? spanStem.test(spanText)
        : spanText.includes(stem);
      if (!supported) return demote('process_assertion_unsupported');
    }
    // Iteration 5 — form/route/class adjectives must be span-stated
    // ("the pill" does not entail "oral contraceptive pill").
    for (const t of formRouteTokens(claimCore)) {
      if (!spanText.includes(t.slice(0, 5)))
        return demote('not_entailed');
    }
    if (NEGATION_RE.test(claimCore) !== NEGATION_RE.test(spanText))
      return demote('negation_mismatch');
    // Iteration 2 — negation SUBJECT matching (deterministic): a negative
    // claim ("No nausea or vomiting") is only anchorable to a span that
    // mentions at least ONE content token of the negated phrase; a span
    // denying something ELSE never supports a different negative (the
    // recurring Gate-1 escape; boolean polarity alone could not see it).
    // Phrase-ANY (not ALL): "No prior diagnosis of migraines" passes via
    // "migraines" even though "prior"/"diagnosis" are register words.
    const negPhrase = norm(claimCore).match(
      /\b(?:no|not|denies|denied|without|negative)\s+([a-z][a-z\s]{3,60})/
    );
    if (negPhrase) {
      const tokens = (negPhrase[1].match(/[a-z]{5,}/g) ?? []).filter(
        (t) => !REGISTER_WORDS.includes(t)
      );
      if (tokens.length > 0 && !tokens.some((t) => spanText.includes(t.slice(0, 5))))
        return demote('negation_mismatch');
    }

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
  '- PLAN instructions and orders (a test "sent to the lab for culture",',
  '  an education "leaflet to be provided", callback thresholds like',
  '  "call back urgently if high temperature") are entailed ONLY if the',
  '  span states THAT instruction — a general safety-net statement does',
  '  not entail specific thresholds or materials.',
  '',
  'And these (iteration 3 — the residual escape classes):',
  '- ELABORATION BEYOND THE SPAN is not entailment: a claim that adds ANY',
  '  specification, quantification, explanation, or detail the span does',
  '  not state is NOT entailed, even when the addition is medically',
  '  correct or "obvious".',
  '- A parenthetical gloss, definition, or expansion ("auscultation',
  '  (listening to the chest)") is NOT entailed unless the span itself',
  '  states that explanation.',
  '- Quantification not in the span ("cut down" does NOT entail "two',
  '  units per week, then one") is NOT entailed — numbers, frequencies,',
  '  and stepped plans must appear in the span.',
  '- BODY-SITE / SUBJECT TRANSFER: a span about one site, organ, or topic',
  '  never entails a claim about another ("nose feels blocked" does NOT',
  '  entail "ears: no blockage"; a denial about chest pain does not cover',
  '  abdominal pain).',
  '- CAUSAL ATTRIBUTION ("screen-related", "due to", "secondary to") is',
  '  entailed ONLY if the span states that cause, not because it is',
  '  clinically plausible.',
  '- DRUG FORM / ROUTE / CLASS SPECIFICATION beyond the span ("the pill"',
  '  does NOT entail "oral contraceptive pill"; "steroid cream" does NOT',
  '  entail "topical steroid cream") is NOT entailed — the form, route, or',
  '  drug class must appear in the span.',
  '- CLINICAL-REASONING ACTS AND CONTINGENCIES: a claim that something was',
  '  "confirmed", "considered", "ruled out", "screened", "addressed", or a',
  '  plan contingency ("may need to change X if Y is confirmed") is',
  '  entailed ONLY if the span states that act or contingency in words.',
  '  Symptom descriptions or question-and-answer NEVER entail that a',
  '  diagnosis was considered, confirmed, or excluded.',
  '',
  'Respond STRICT JSON only, no prose, no fences:',
  '{"verdicts":[{"i":<claim number>,"entailed":true|false}]}',
  'Include EVERY claim number exactly once.',
].join('\n');

// Iteration 3 — k=3 SELF-CONSISTENT ENSEMBLE. Three passes share the full
// rule set above but adopt distinct review postures; a claim survives only
// on MAJORITY (≥2 of 3) entailed=true. An errored/ambiguous pass votes
// not-entailed for every claim (fail-closed); ≥2 errored passes fail the
// whole stage (verifier_failed). Single-verdict run-to-run wobble was the
// measured residual escape path (gate runs 1–3: 4–5 register-inference
// claims each passed the single verdict).
const ENSEMBLE_LENSES: readonly string[] = [
  '', // pass 1 — the base rules, unmodified posture
  [
    '',
    'YOUR POSTURE FOR THIS PASS — ELABORATION HUNTER: read each claim word',
    'by word against its span and hunt for ANY added word that carries',
    'clinical meaning the span does not state (a qualifier, a number, a',
    'mechanism, an explanation, a site). One such word = not entailed.',
  ].join('\n'),
  [
    '',
    'YOUR POSTURE FOR THIS PASS — CLINICAL SKEPTIC: assume each claim is an',
    'embellished clinical-register rewrite until the span proves otherwise.',
    'The span must carry the FULL content of the claim; clinical plausibility',
    'or convention is never evidence.',
  ].join('\n'),
];

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

/** One verifier pass: returns the set of claim POSITIONS (0..k-1) it entails,
 *  or null when the pass errored (API failure, malformed/ambiguous verdict).
 *  All the single-pass fail-closed rules are unchanged: exactly one valid
 *  verdict object per response, exactly one verdict per claim. */
async function entailmentPass(
  claims: ClaimRow[],
  user: string,
  lens: string,
  ids: { practiceId: string; visitId: string; userId: string | null }
): Promise<Set<number> | null> {
  try {
    const { text } = await modelClient.completeText({
      practiceId: ids.practiceId,
      visitId: ids.visitId,
      userId: ids.userId,
      purpose: 'tm_anchor_entailment',
      provider: 'anthropic',
      model: MODEL,
      system: ENTAILMENT_SYSTEM + lens,
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
    if (valid.length !== 1) return null; // none or ambiguous → pass errored (fail-closed)
    const verdicts = valid[0].verdicts;
    const entailedPos = new Set<number>();
    claims.forEach((_, k) => {
      const v = verdicts.filter((x) => x.i === k);
      // exactly one verdict per claim; duplicates/missing → not entailed
      if (v.length === 1 && v[0].entailed === true) entailedPos.add(k);
    });
    return entailedPos;
  } catch {
    return null; // API failure → pass errored
  }
}

async function entailmentStage(
  claims: ClaimRow[],
  roleLabeledTranscript: string,
  ids: { practiceId: string; visitId: string; userId: string | null }
): Promise<{ entailedIdx: Set<number>; errored: boolean; passErrors: number }> {
  if (claims.length === 0)
    return { entailedIdx: new Set(), errored: false, passErrors: 0 };
  // MOCK short-circuit: under MOCK_AI_CALLS the mock "model" approves —
  // mirrors every other mock fixture; reject/fail-closed paths are covered
  // by deterministic unit tests, never by the MOCK e2e flow.
  if (process.env.MOCK_AI_CALLS === 'true') {
    return {
      entailedIdx: new Set(claims.map((c) => c.index)),
      errored: false,
      passErrors: 0,
    };
  }
  const user = claims
    .map((c, k) =>
      [
        `CLAIM ${k}: ${c.text}`,
        `CITED SPAN(S): ${c.anchorRaw}`,
        `CONTEXT: ${spanContext(c.spans, roleLabeledTranscript) || '(no context located)'}`,
      ].join('\n')
    )
    .join('\n\n');
  // k=3 ensemble, distinct lenses, majority ≥2 entailed to survive. An
  // errored pass votes not-entailed for everything (fail-closed): one error
  // leaves survival possible only by BOTH remaining passes agreeing; two
  // errors make majority unreachable → the whole stage is verifier_failed.
  const passes = await Promise.all(
    ENSEMBLE_LENSES.map((lens) => entailmentPass(claims, user, lens, ids))
  );
  const passErrors = passes.filter((p) => p === null).length;
  if (passErrors >= 2)
    return { entailedIdx: new Set(), errored: true, passErrors };
  const entailedIdx = new Set<number>();
  claims.forEach((c, k) => {
    const votes = passes.filter((p) => p !== null && p.has(k)).length;
    if (votes >= 2) entailedIdx.add(c.index);
  });
  return { entailedIdx, errored: false, passErrors };
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
        entailmentPassErrors: ent.passErrors,
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
