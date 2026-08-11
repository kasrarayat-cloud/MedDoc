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
import {
  EMPTY_SECTION_PLACEHOLDER,
  renumberOrderedLists,
} from '@/lib/soap-format';
import {
  type TemplateScaffold,
  normForMatch,
  isFixedScaffoldLine,
  matchCarrier,
  picksGroundedInTranscript,
} from '../note-templates/template-scaffold';

const MODEL = process.env.TRANSCRIBE_MD_CLINICAL_MODEL || 'claude-sonnet-4-6';

import {
  PIPELINE_SECTION_POLICY,
  type NoteTemplateSection,
  type SectionProvenance,
} from '../note-templates/system-default-template';

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
  'In a TABLE section, the header and separator rows and any row whose value',
  'cells are all "[not documented]" need no anchor; append the anchor(s) for',
  'a filled row after its final "|". In a CHECKLIST section, unchecked',
  '"- [ ]" lines need no anchor; a checked "- [x]" line is a clinical claim',
  'and needs one. Anchor a checked option with the SHORTEST verbatim span',
  'that affirms that option alone — never include neighboring denials or',
  'unrelated clauses in its anchor (quote "regular rate and rhythm", not',
  '"regular rate and rhythm, no murmur"). These span rules govern ONLY',
  'what you quote inside ⟦A:""⟧ — they never shrink the note itself.',
  'Every clinically relevant fact the transcript supports — including',
  'functional and psychosocial context such as impact on work or usual',
  'activities, the patient’s stated concerns, and self-care already',
  'tried — must still appear in the note (or, when unanchorable, as a ⟦S⟧',
  'suggestion).',
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
  | 'form_route_unsupported'
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
  /** Every generated line, anchors stripped, nothing demoted away. This is the
   *  draft the physician reviews and signs — see the AUDIT-ONLY note above. */
  fullBody: string;
  suggestions: SuggestedClaim[];
  stats: {
    anchored: number;
    demoted: number;
    entailmentChecked: number;
    verifierErrored: boolean;
    /** Ensemble passes (of 3) that errored — telemetry only. */
    entailmentPassErrors?: number;
    /** Section headers whose every content line demoted to the lane — they
     *  were back-filled with the review placeholder so they never render
     *  blank (the live-smoke empty-Assessment blocker). Drives needsReview. */
    filledEmptySections?: string[];
  };
}


// ─── Normalization + deterministic rules (spike rules, kept verbatim) ───────
const NEGATION_RE = /\b(no|not|denies|denied|without|negative|none)\b/i;

/** Function words / particles used ONLY by the anchor content-token floor
 *  below. An anchor whose EVERY token is one of these anchors nothing — the
 *  verbatim substring check would match such a span trivially ("of the", "is
 *  no"). This list is deliberately NOT clinical vocabulary: "clear", "normal",
 *  "stable", "edema", "lungs", "continue", "swollen" are content words and a
 *  short anchor built from them ("lungs clear", "continue lisinopril") MUST
 *  pass. Negations ("no"/"not") are particles HERE — polarity is enforced
 *  separately by NEGATION_RE — so "no edema" still carries one content token
 *  ("edema") and survives. */
const ANCHOR_STOPWORDS = new Set([
  'a', 'an', 'the', 'and', 'or', 'but', 'nor', 'so', 'yet',
  'of', 'in', 'on', 'to', 'for', 'with', 'at', 'by', 'from', 'as',
  'into', 'onto', 'upon', 'about', 'over', 'under', 'per', 'than', 'then',
  'is', 'are', 'was', 'were', 'be', 'been', 'being', 'am',
  'has', 'have', 'had', 'do', 'does', 'did',
  'will', 'would', 'shall', 'should', 'can', 'could', 'may', 'might', 'must',
  'no', 'not', 'none', 'this', 'that', 'these', 'those',
  'it', 'its', 'he', 'she', 'him', 'her', 'his', 'they', 'them', 'their',
  'i', 'you', 'we', 'us', 'our', 'your', 'my', 'me',
  'there', 'here', 'if', 'when', 'while', 'because',
  'just', 'only', 'also', 'very', 'too',
]);

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
// 'nasal' deliberately EXCLUDED (auditor WARN-2): "nasal congestion" is
// everyday symptom register and would demote constantly on ENT visits.
const FORM_ROUTE_WORDS = [
  'oral', 'topical', 'intravenous', 'intramuscular', 'subcutaneous',
  'inhaled', 'rectal', 'sublingual', 'transdermal', 'ophthalmic',
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

// ─── WHAT A LINE *IS*, before asking whether it is true ─────────────────────
//
// The verifier's question is "is this claim in the transcript?". That question
// only has an answer for a line that MAKES a claim. Three kinds of line do not:
//
//   • a structural HEADING ("Right Leg:", "What we found") — it introduces the
//     block beneath it and asserts nothing on its own;
//   • a scaffolding placeholder ("[not documented]", an empty table cell);
//   • template BOILERPLATE the doctor's own format mandates.
//
// Asking the transcript question anyway is what produced 22 suggestion cards on
// a clean venous-reflux study, nine of which were literally the headings of the
// patient-summary section. This predicate is the missing step: decide the line's
// ROLE first, and only anchor the ones that assert something.

/** A trailing-colon label with NO value after it — "Right Leg:", "Allergies:".
 *  It names the block that follows; the claim, if any, is in that block. */
const LABEL_ONLY_RE = /^(?:[-*]\s+)?(?:\*\*)?[A-Za-z][A-Za-z0-9 /&()'’-]{0,58}(?:\*\*)?:\s*$/;

/**
 * A short unpunctuated line that TITLES the block below it.
 *
 * "What we found", "Your next steps", "When to call us". No terminal
 * punctuation, no finite clause that could be checked against a recording, and
 * a non-blank line follows it. Requiring the follower is what keeps a genuine
 * short finding ("No reflux") from being read as a heading: a finding stands at
 * the end of its block or among siblings, a heading always has a body under it.
 */
function isTitleLine(t: string, next: string | undefined): boolean {
  if (t.length === 0 || t.length > 60) return false;
  if (/[.;!?,]$/.test(t)) return false; // a sentence, or a sign-off ("Take care,")
  if (/^[-*\d]/.test(t)) return false; // a list item is content
  if (/\|/.test(t)) return false; // a table row is content
  if (/\d/.test(t)) return false; // any number is a measurement, never a title
  const words = t.split(/\s+/).filter(Boolean);
  if (words.length === 0 || words.length > 7) return false;
  // Something must live under it, or it is not titling anything.
  const follower = (next ?? '').trim();
  return follower.length > 0 && !/^#{1,6}\s/.test(follower);
}

/**
 * Scaffolding placeholders carry no assertion — and crucially, no POLARITY.
 *
 * "[not documented]" contains the token "not". Read as prose it looks like a
 * denial, and the polarity rule below duly compared it against a transcript
 * that denies nothing in particular and demoted the row. It is not a denial; it
 * is an empty cell. Same for an em-dash or "N/A". Stripping them before any
 * semantic test is the fix — not a whitelist of the rows they appear in.
 */
const PLACEHOLDER_RE =
  /\[not\s+(?:documented|addressed)\]|(?:^|\s)(?:—|–|n\/a)(?=\s|$)/gi;

/** The part of a line that actually asserts something about the patient. */
export function assertionText(s: string): string {
  return s.replace(PLACEHOLDER_RE, ' ').replace(/\s+/g, ' ').trim();
}

/** Vessels a venous/arterial study names. Anatomy, not phrasing. */
const VESSEL_RE =
  /\b(?:great saphenous|small saphenous|accessory saphenous|anterior accessory|gsv|ssv|aagsv|femoral|popliteal|perforator|saphenofemoral|saphenopopliteal|tibial|peroneal|iliac)\b/gi;

/**
 * The checkable facts inside a patient-facing paraphrase.
 *
 * A summary sentence is written to be understood, not to be diffed — so the
 * only honest thing to verify in it is the clinical content it carries:
 * WHICH SIDE, WHICH VESSEL, WHAT MEASUREMENT, and whether something was said to
 * be present or absent. Everything else is the re-explanation doing its job.
 *
 * Returns normalized fragments to look for in the transcript. An empty result
 * means "this line asserts no checkable fact" — which is the common case and is
 * exactly why the section stopped generating cards.
 */
export function extractClinicalFacts(line: string): string[] {
  const t = assertionText(line);
  const out = new Set<string>();
  for (const m of t.matchAll(VESSEL_RE)) out.add(norm(m[0]));
  // Measurements — a number with a clinical unit. A bare number in prose
  // ("one of the main veins") is not a measurement and must not be checked.
  for (const m of t.matchAll(/\b(\d+(?:\.\d+)?)\s*(mm|cm|sec|secs|seconds)\b/gi)) {
    out.add(norm(m[1]));
  }
  return [...out];
}

function isExemptLine(stripped: string): boolean {
  const t = stripped.trim();
  if (t.length === 0) return true;
  if (/^#{1,6}\s/.test(t)) return true;
  if (/^\*\*[^*]+\*\*:?\s*$/.test(t)) return true;
  // A label with nothing after it. The bold form was already exempt above; the
  // plain form ("Right Leg:") was not, and it is the commonest heading shape in
  // an imaging report — one per leg, per table, every study.
  if (LABEL_ONLY_RE.test(t)) return true;
  // "[not documented]" placeholder — exempt after an optional list marker and
  // an optional label. The label may be BOLD ("**Allergies:**") OR a plain
  // "Label:" prefix ("Family History:", "Comparison:") — both are scaffolding,
  // not a clinical claim. The plain form REQUIRES its trailing colon so a real
  // sentence that merely precedes the marker is never swept in; the line must
  // still END in "[not documented]", which asserts no clinical fact.
  if (/^(?:[-*\d.]\s*)*(?:(?:\*\*[^*]+\*\*:?|[A-Za-z][A-Za-z0-9 /&()'-]*:)\s*)?\[not (?:documented|addressed)\]\.?$/i.test(t)) return true;
  // ── Structured-template scaffolding (feat/structured-templates, 2026-07-02;
  //    pre-registered: docs/eval-runs/verifier-table-option-fix-20260702T165454Z.md).
  //    Lines that assert NO clinical fact. A CHECKED option ("- [x]") and a
  //    FILLED table cell are clinical claims — they get NO exemption here and
  //    still anchor + verify (canaries pin this). ──
  // Markdown table SEPARATOR row: | --- | :--- | ---: |
  if (/^\s*\|(?:\s*:?-{3,}:?\s*\|)+\s*$/.test(t)) return true;
  // Pipe row whose non-first cells are ALL scaffolding (unfilled fixed-row
  // skeleton "| BP | [not documented] |", empty-cell rows "| Allergies |  |").
  if (/^\s*\|.*\|\s*$/.test(t)) {
    const cells = t
      .replace(/^\s*\|/, '')
      .replace(/\|\s*$/, '')
      .split('|')
      .map((c) => c.trim());
    const valueCells = cells.slice(1);
    if (
      valueCells.length > 0 &&
      valueCells.every((c) =>
        /^(?:|—|–|-|n\/?a|\[not (?:documented|addressed)\]\.?)$/i.test(c)
      )
    ) {
      return true;
    }
  }
  // UNCHECKED option line — "- [ ] Clear to auscultation". Asserts nothing;
  // the unchecked box is template scaffolding the doctor reads as "not
  // selected", never as a finding.
  if (/^(?:[-*]\s+)?\[ \]\s/.test(t)) return true;
  // Canonical ultrasound Comparison-negative — the imaging template mandates
  // the EXACT line "No prior study available for comparison." when no prior is
  // dictated. Standard radiology scaffolding, not a dictated finding, so it
  // needs no transcript anchor (light study/imaging + is/are tolerance only).
  if (/^(?:\*\*comparison\*\*:?\s*|comparison:\s*)?no prior (?:study|studies|imaging) (?:is |are )?available for comparison\.?$/i.test(t)) return true;
  if (/not (formally )?documented in this encounter/i.test(t) && t.length < 100) return true;
  return false;
}

interface ClaimRow {
  index: number;
  text: string; // anchor-free claim text (display + default judge claim)
  section: string;
  spans: string[]; // normalized matched spans (clear sub-spans only)
  anchorRaw: string;
  /** For a filled template CARRIER only: the reduced claim (laterality +
   *  picks) the entailment judge evaluates instead of the boilerplate-heavy
   *  full line. Absent for every free-text claim → judge input unchanged. */
  entailText?: string;
}

/** Deterministic stage. Returns claims that SURVIVE to entailment, plus the
 *  claims already demoted by hard rules (which entailment cannot overrule). */
/**
 * Which sections this layer is competent to judge.
 *
 * Built from the ACTIVE TEMPLATE's own declared sections, so it is provenance
 * rather than a list of names. A section the template does not declare is one
 * this layer did not draft and cannot check: `PROCEDURES / E&M` comes from the
 * coding step, `PATIENT SUMMARY` from 07e, and a table caption rendered as a
 * heading ("DIAMETER AND REFLUX TIME") is not a section at all. Before this,
 * every heading in the composed document was treated as a transcript-derived
 * section, which is how the verifier came to evacuate two whole sections it had
 * never written.
 */
export interface SectionPolicy {
  /** normalized label → provenance. Missing ⇒ not this layer's to judge. */
  byLabel: Map<string, SectionProvenance>;
  /** normalized mandated line → the section that mandates it. */
  mandated: Set<string>;
}

/**
 * Sections that are PROTOCOL by their nature, whoever declares them.
 *
 * A scan technique is the machine protocol; a comparison line is "no prior
 * study available". Neither is ever dictated, in any template, by any
 * sonographer — there is no transcript span for them and there never will be.
 *
 * This exists because `provenance` is an OPTIONAL field that only the BUILT-IN
 * templates actually set. A doctor's uploaded form carries no provenance at
 * all, so `?? 'dictation'` marked its every section fully verifiable — which is
 * why TECHNIQUE and IMPRESSION were still being flagged on real visits after
 * the provenance work shipped. Declaring it per-template only ever protected
 * the templates we author, not the ones clinicians actually use.
 */
const PROTOCOL_SECTION_LABELS = new Set(['technique', 'comparison']);

/**
 * What a section's provenance is when the template does not say.
 *
 * Only reached for templates that never declared it — an explicit
 * `provenance` on the section always wins over this.
 */
function inferProvenance(s: NoteTemplateSection): SectionProvenance {
  if (PROTOCOL_SECTION_LABELS.has(normSection(s.label))) return 'template';
  // NOT `defaultText` — see mandatedLinesFromDefaultText below. A structured
  // custom template supplies defaultText for EVERY section including FINDINGS,
  // so treating that as template-provenance would exempt the one section the
  // measurements live in and make the verifier a no-op where it matters most.
  return 'dictation';
}

/**
 * Lines the TEMPLATE supplies verbatim are boilerplate, not clinical claims.
 *
 * The section-level tool is too blunt for this: a custom template's
 * `defaultText` is the form skeleton, and its sections are a mix of fixed
 * scaffolding and dictated content — often in the same section. Exempting the
 * SECTION would take the dictated content with it. Exempting the LINE is exact:
 * "no prior study available for comparison" came from the form, the measurement
 * beneath it came from the sonographer, and only the first is unanchorable by
 * construction.
 *
 * This is the same mechanism `mandatedLines` gives the built-in templates,
 * derived for the templates that never declared it.
 */
function mandatedLinesFromDefaultText(s: NoteTemplateSection): string[] {
  if (typeof s.defaultText !== 'string') return [];
  return s.defaultText
    .split('\n')
    .map((l) => l.trim())
    // Placeholders and structural markup are already exempt upstream; what is
    // worth adding here is real prose the form states on the doctor's behalf.
    .filter((l) => l.length > 12 && !l.startsWith('|') && !l.startsWith('#'));
}

export function buildSectionPolicy(sections: NoteTemplateSection[]): SectionPolicy {
  const byLabel = new Map<string, SectionProvenance>();
  const mandated = new Set<string>();
  for (const s of sections) {
    byLabel.set(normSection(s.label), s.provenance ?? inferProvenance(s));
    for (const line of s.mandatedLines ?? []) mandated.add(norm(line));
    // …and the lines the form itself supplies, for every template that never
    // declared mandatedLines (i.e. every template a clinician uploaded).
    for (const line of mandatedLinesFromDefaultText(s)) mandated.add(norm(line));
  }
  // Sections written by a LATER step. They are in the composed document but
  // were never this layer's to draft or to judge.
  //
  // THESE WIN — unconditionally, over anything the template says. The previous
  // `if (!byLabel.has(label))` let a template's own declaration take precedence,
  // and a doctor's form that lists "PATIENT SUMMARY" or "PROCEDURES / E&M" as
  // one of its sections therefore got 'dictation' and was fully verified. No
  // template can validly claim authorship of content a later step writes: 07e
  // composes the patient summary and the coding step composes PROCEDURES / E&M,
  // whatever the form happens to list. Seven of the ten flags on the visit that
  // prompted this change were patient-summary paraphrase reaching the lane
  // through exactly that inversion.
  for (const [label, prov] of Object.entries(PIPELINE_SECTION_POLICY)) {
    byLabel.set(label, prov);
  }
  return { byLabel, mandated };
}

/** What to do with a line in this section. */
function sectionVerdict(
  policy: SectionPolicy | undefined,
  section: string
): 'verify' | 'exempt' | 'facts_only' {
  // No policy supplied → every section verifies, exactly as before.
  if (!policy) return 'verify';
  const p = policy.byLabel.get(normSection(section));
  // Not a section this pipeline declares anywhere — a table caption rendered as
  // a heading, or a block some other producer appended. Not ours to judge.
  if (p === undefined) return 'exempt';
  if (p === 'template') return 'exempt';
  // A later step wrote it. We do not judge its PHRASING, but a hard clinical
  // fact inside it is still checkable.
  if (p === 'other_step') return 'facts_only';
  return 'verify';
}

function deterministicStage(
  anchoredDraft: string,
  roleLabeledTranscript: string,
  scaffold?: TemplateScaffold,
  policy?: SectionPolicy
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
    // A TITLE line — needs the next line, so it cannot live in isExemptLine.
    if (isTitleLine(stripped.trim(), lines[index + 1])) {
      exemptLines.set(index, stripped);
      return;
    }
    // A line the TEMPLATE mandates verbatim. It is in the note because the
    // format requires it; no dictation will ever contain it.
    if (policy?.mandated.has(norm(stripped.trim()))) {
      exemptLines.set(index, stripped);
      return;
    }
    // SECTION PROVENANCE. Decided before any anchor work: a section this layer
    // did not draft is not one it may demote, and a template's own protocol
    // prose is correct because it is fixed, not because it was dictated.
    const verdict = sectionVerdict(policy, section);
    if (verdict === 'exempt') {
      exemptLines.set(index, stripped);
      return;
    }
    if (verdict === 'facts_only') {
      // The patient summary is a deliberate RE-EXPLANATION for the patient. Its
      // phrasing is its whole job, so "couldn't verify" on a narrative sentence
      // is meaningless. What CAN be wrong is a clinical fact inside it — a side,
      // a vessel, a measurement, a presence/absence. Verify those and nothing
      // else; a line that carries none is prose and is exempt.
      const facts = extractClinicalFacts(stripped);
      if (facts.length === 0) {
        exemptLines.set(index, stripped);
        return;
      }
      const unsupported = facts.filter((f) => !asrNorm.includes(f));
      if (unsupported.length === 0) {
        exemptLines.set(index, stripped);
        return;
      }
      demoted.push({
        index,
        text: stripped.trim(),
        reason: 'not_entailed',
        section,
        anchor: 'no anchor',
      });
      return;
    }
    // Table HEADER row (feat/structured-templates; pre-registered scope
    // item 2 — lives OUTSIDE isExemptLine because it needs one-line
    // lookahead): a pipe row immediately followed by a separator row is
    // template scaffolding, not a claim. Data rows never precede a
    // separator, so this can never sweep a filled row.
    if (
      /^\s*\|.*\|\s*$/.test(stripped) &&
      /^\s*\|(?:\s*:?-{3,}:?\s*\|)+\s*$/.test((lines[index + 1] ?? '').trim())
    ) {
      exemptLines.set(index, stripped);
      return;
    }
    // ── Template-scaffold awareness (feat/verifier-scaffold-exemption,
    //    2026-07-06; pre-registered:
    //    docs/eval-runs/verifier-scaffold-exemption-20260706T202636Z.md).
    //    ONLY active when the caller supplies a custom template's scaffold. ──
    // Bucket A — FIXED template boilerplate (TECHNIQUE prose, "Clinical
    // correlation … required.", "Right Leg:") is the doctor's own approved
    // format, not a generated claim → exempt (same class as the section-header
    // / [not documented] / "No prior study" exemptions). Matched by EXACT
    // normalized equality, so a real assertion can never be swept in.
    // Bucket B — a filled constrained-choice CARRIER: its picks + laterality
    // become the judge's reduced claim (set at the toEntail push below). The
    // line still runs EVERY frozen override first. An UNANCHORED carrier (fixed
    // boilerplate the model reproduced without a quote, e.g. the TECHNIQUE
    // methodology sentence with a filled study-scope slot) is scaffold too —
    // exempt it iff its picks are grounded in the transcript (a fabricated /
    // undictated pick is NOT grounded → falls through to no_anchor).
    const matchTarget = scaffold
      ? normForMatch(stripped.replace(/^\s*(?:\d+[.)]\s+|[-*]\s+)/, ''))
      : '';
    if (scaffold && isFixedScaffoldLine(scaffold, matchTarget)) {
      exemptLines.set(index, stripped);
      return;
    }
    const carrier = scaffold ? matchCarrier(scaffold, matchTarget) : null;
    const anchorRaw = subSpans.length > 0 ? subSpans.join(' | ') : 'no anchor';
    const demote = (reason: DemotionReason) =>
      demoted.push({ index, text: stripped.trim(), reason, section, anchor: anchorRaw });

    if (modelSuggested && subSpans.length === 0) return demote('model_suggested');
    if (subSpans.length === 0) {
      if (carrier && picksGroundedInTranscript(carrier.picks, asrNorm)) {
        exemptLines.set(index, stripped);
        return;
      }
      return demote('no_anchor');
    }

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
      // CONTENT-token floor (was: ≥3 raw alphanumeric tokens). The blunt
      // 3-token count demoted genuine short clinical anchors that ARE verbatim
      // in the transcript ("lungs clear", "no edema", "continue lisinopril").
      // Reject ONLY a span with no content token — an all-stopword/all-particle
      // (or punctuation-only) span that anchors nothing. The verbatim substring
      // guarantee on the NEXT line is UNCHANGED, so a 2-content-token anchor
      // still cannot smuggle a quote that is not literally in the transcript.
      const subToks = nsub.match(/[a-z0-9]+/g) ?? [];
      if (subToks.every((t) => ANCHOR_STOPWORDS.has(t)))
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
        return demote('form_route_unsupported');
    }
    // ── POLARITY, SCOPED TO WHAT IS BEING DENIED ────────────────────────────
    //
    // This was a whole-line boolean: `NEGATION_RE.test(claim) !==
    // NEGATION_RE.test(span)`. Two ways that misfires, both seen in production
    // on a clean study:
    //
    //   1. "| GSV at the Knee | 3.4 | [not documented] |" — the placeholder's
    //      "not" made the claim read as a denial. It is an empty cell.
    //   2. "| AAGSV at the SFJ | 3.0 | — |" — the claim denies nothing, but the
    //      anchoring span came from a reflux study whose transcript is full of
    //      "no thrombus", "no reflux in the left". An unrelated denial ANYWHERE
    //      in the span flipped the boolean and demoted a measurement.
    //
    // Polarity only mismatches when the two are talking about the SAME thing.
    // So: strip placeholders, then compare only when the denial's subject is
    // shared. A span that denies something else is not a contradiction — and
    // the direction that actually risks fabrication (span denies X, claim
    // asserts X) is still caught, which is the whole point of the rule.
    const claimAssert = assertionText(claimCore);
    const claimNeg = NEGATION_RE.test(claimAssert);
    const spanNeg = NEGATION_RE.test(spanText);
    if (!claimNeg && spanNeg) {
      // The span denies something. Demote ONLY if the claim asserts that same
      // subject — i.e. the dictation said "no X" and the draft says "X".
      const spanDenied = spanText.match(
        /\b(?:no|not|denies|denied|without|negative)\s+([a-z][a-z\s]{3,60})/
      );
      const deniedTokens = (spanDenied?.[1].match(/[a-z]{5,}/g) ?? []).filter(
        (t) => !REGISTER_WORDS.includes(t)
      );
      const claimNorm = norm(claimAssert);
      if (
        deniedTokens.length > 0 &&
        deniedTokens.some((t) => claimNorm.includes(t.slice(0, 5)))
      ) {
        return demote('negation_mismatch');
      }
    } else if (claimNeg && !spanNeg) {
      // The draft denies something the span never denies. The subject check
      // below is the precise form of this test; it runs on claimAssert so a
      // placeholder can no longer be the thing "denied".
    }
    // Iteration 2 — negation SUBJECT matching (deterministic): a negative
    // claim ("No nausea or vomiting") is only anchorable to a span that
    // mentions at least ONE content token of the negated phrase; a span
    // denying something ELSE never supports a different negative (the
    // recurring Gate-1 escape; boolean polarity alone could not see it).
    // Phrase-ANY (not ALL): "No prior diagnosis of migraines" passes via
    // "migraines" even though "prior"/"diagnosis" are register words.
    const negPhrase = norm(claimAssert).match(
      /\b(?:no|not|denies|denied|without|negative)\s+([a-z][a-z\s]{3,60})/
    );
    if (negPhrase) {
      const tokens = (negPhrase[1].match(/[a-z]{5,}/g) ?? []).filter(
        (t) => !REGISTER_WORDS.includes(t)
      );
      if (tokens.length > 0 && !tokens.some((t) => spanText.includes(t.slice(0, 5))))
        return demote('negation_mismatch');
    }

    toEntail.push({
      index,
      text: stripped.trim(),
      section,
      spans,
      anchorRaw,
      ...(carrier ? { entailText: carrier.reduced } : {}),
    });
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
// EXPORTED for B4's closing gate. The stage's per-visit expectation is `{0,3}`
// and the 3 is THIS LENGTH, not a constant anybody chose twice: one usage event
// per lens per invocation. A gate asserting a literal 3 would keep passing if
// somebody added a fourth lens and the meter then under-counted; asserting
// against the array is the same claim with no hand-kept copy of the number.
export const ENSEMBLE_LENSES: readonly string[] = [
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
  // ⚠️ THE MOCK SHORT-CIRCUIT THAT USED TO SIT HERE IS GONE — B4 STEP 2.
  //
  // It returned all-entailed under MOCK_AI_CALLS *before* `entailmentPass`,
  // which means before `modelClient`, which means before `logApiUsage`. That
  // is the identical defect B4 step 1 removed from `deepgram-batch.ts` and
  // `embed.ts`, arriving one layer higher: a mock boundary ABOVE the meter.
  //
  // The consequence was not a wrong number, it was NO number. A mocked QA run
  // emitted zero usage events for this stage, and B4's gate — "one full QA
  // pipeline run produces one event per stage, counted against the enumerated
  // stage list" — was therefore unsatisfiable for `tm_anchor_entailment` by
  // construction. Zero usage events looks exactly like a working meter that
  // found nothing to record.
  //
  // ⚠️ BEHAVIOUR IS UNCHANGED, AND THAT IS THE POINT. The three passes below
  // now run as three MOCKED calls; the content-sensitive fixture returns an
  // entailed verdict for every claim the prompt names, so all three lenses
  // agree, every claim clears the ≥2 majority, and `entailedIdx` is the same
  // set the short-circuit returned by hand. What changed is that three usage
  // rows now exist, marked `unitsSource='mock'` — which is what makes the
  // stage countable.
  //
  // The `claims.length === 0` return above still short-circuits, and must:
  // no claims is no work, not a suppressed call. Production agrees — 73 of 73
  // visits carrying this stage carry EXACTLY 3 calls, never 1, 2 or 6.
  const user = claims
    .map((c, k) =>
      [
        // For a filled template carrier, judge the picks + laterality (the
        // clinical content), not the template's connective boilerplate. Absent
        // for every free-text claim → the CLAIM line is byte-identical.
        `CLAIM ${k}: ${c.entailText ?? c.text}`,
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

// Matches the `## {label}` grammar EVERY note template emits
// (note-templates/build-soap-prompt.ts renders `## ${s.label}`, and the L4
// structure validator requires exactly those `##` labels). The empty-section
// guard is anchored to that one grammar ON PURPOSE: a model that deviates to a
// non-`##` header (e.g. a bold-only `**Assessment:**`) fails L4 structure
// validation first → needsReview before READY, so it can't reach a signed
// note un-flagged either way. If a future custom-header grammar is ever added,
// this regex, the structure validator, and backfillEmptySections MUST be
// updated together so the "no empty section" guarantee can't silently drift.
const SECTION_HEADER_RE = /^#{1,6}\s+(.*)$/;
function normSection(s: string): string {
  return s.replace(/\*\*/g, '').replace(/:\s*$/, '').trim().toLowerCase();
}

/** After body composition, inject EMPTY_SECTION_PLACEHOLDER into any section
 *  header whose block (until the next header / EOF) has NO content line, BUT
 *  ONLY when that section actually lost content to demotion. A section that
 *  legitimately holds "[not documented]" counts as having content; a section
 *  that never had drafted content is left alone (an empty section the model
 *  never filled is an L4 concern, not a verification artifact). */
function backfillEmptySections(
  bodyLines: string[],
  demotedSections: Set<string>
): { lines: string[]; filledSections: string[] } {
  const out: string[] = [];
  const filledSections: string[] = [];
  for (let i = 0; i < bodyLines.length; i++) {
    out.push(bodyLines[i]);
    const m = bodyLines[i].match(SECTION_HEADER_RE);
    if (!m) continue;
    let hasContent = false;
    for (let j = i + 1; j < bodyLines.length; j++) {
      if (SECTION_HEADER_RE.test(bodyLines[j])) break;
      if (bodyLines[j].trim().length > 0) { hasContent = true; break; }
    }
    if (!hasContent && demotedSections.has(normSection(m[1]))) {
      out.push(EMPTY_SECTION_PLACEHOLDER);
      filledSections.push(m[1].trim());
    }
  }
  return { lines: out, filledSections };
}

// ─── Public entry ───────────────────────────────────────────────────────────
export async function runAnchorVerify(input: {
  visitId: string;
  practiceId: string;
  userId: string | null;
  anchoredDraft: string;
  roleLabeledTranscript: string;
  /** A custom structured template's scaffold (from buildTemplateScaffold).
   *  Supplied ONLY when a doctor's custom template with `{{one of}}` choice
   *  slots is active; absent for every default SOAP path → byte-identical. */
  templateScaffold?: TemplateScaffold;
  /** The ACTIVE template's sections. Supplied → this layer judges only the
   *  sections that template declares, at the provenance it declares them with.
   *  Absent → every section verifies, byte-identical to the previous
   *  behaviour (every existing caller and test). */
  templateSections?: NoteTemplateSection[];
}): Promise<AnchorVerifyResult> {
  try {
    const det = deterministicStage(
      input.anchoredDraft,
      input.roleLabeledTranscript,
      input.templateScaffold,
      input.templateSections ? buildSectionPolicy(input.templateSections) : undefined
    );
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

    // ── THE AUDIT-ONLY BODY ─────────────────────────────────────────────────
    // Identical to the loop above except it never skips a demoted line. This
    // is what the physician actually reviews and signs now that the verifier
    // no longer stages anything: EVERY generated line, in original order, with
    // the anchor markup stripped. No demotion, no back-filled placeholder, no
    // section that silently lost its content.
    //
    // Kept alongside `body` rather than replacing it so the demotion machinery
    // stays exercised and honest — `suggestions` is still computed in full and
    // is what the audit row counts. The verifier still judges; it just no
    // longer edits the note.
    const fullBodyLines: string[] = [];
    lines.forEach((rawLine, index) => {
      if (det.exemptLines.has(index)) { fullBodyLines.push(det.exemptLines.get(index)!); return; }
      fullBodyLines.push(
        rawLine.replace(ANCHOR_BLOCK_RE, '').split(SUGGEST_MARK).join('').replace(/\s+$/g, '')
      );
    });
    const fullBody = renumberOrderedLists(
      fullBodyLines.join('\n').replace(/\n{3,}/g, '\n\n').trim()
    );

    // FAIL TOWARD COMPLETENESS (live-smoke empty-Assessment blocker): a
    // section whose every drafted line demoted to the lane would otherwise
    // render as a bare header. Back-fill those — and ONLY those (a section
    // that lost content) — with the visible review placeholder, so a section
    // that HAD content can never be EMPTY in a signed note. Demoted content
    // is NOT re-served to the body (that would reintroduce the fabrication
    // the lane exists to quarantine); the placeholder points to the lane.
    const demotedSections = new Set<string>(
      det.demoted
        .concat(
          det.toEntail
            .filter((c) => !ent.entailedIdx.has(c.index))
            .map((c) => ({ ...c, reason: 'not_entailed' as DemotionReason, anchor: c.anchorRaw }))
        )
        .map((d) => normSection(d.section))
    );
    const { lines: filledLines, filledSections } = backfillEmptySections(
      bodyLines,
      demotedSections
    );

    // Plan-numbering fix: surviving ordered-list items kept their original
    // ordinals after demotion (the note rendered 4,5,6,8,9). Renumber every
    // section's list contiguously over whatever lines actually composed it.
    const body = renumberOrderedLists(
      filledLines.join('\n').replace(/\n{3,}/g, '\n\n').trim()
    );
    const suggestions = [...demotedByIndex.entries()]
      .sort((a, b) => a[0] - b[0])
      .map(([, s]) => s);

    return {
      body,
      fullBody,
      suggestions,
      stats: {
        anchored: det.toEntail.length - entailmentDemotions,
        demoted: suggestions.length,
        entailmentChecked: det.toEntail.length,
        verifierErrored: ent.errored,
        entailmentPassErrors: ent.passErrors,
        filledEmptySections: filledSections,
      },
    };
  } catch {
    // Catastrophic internal failure: serve NOTHING unverified. The whole
    // draft demotes to one suggestion so the doctor still sees the content,
    // labeled — never an unverified body.
    return {
      body: '',
      // Even the catastrophic path serves the content now: audit-only means the
      // physician sees the complete draft and the failure is recorded, rather
      // than the note collapsing to a single quarantined blob.
      fullBody: input.anchoredDraft.replace(ANCHOR_BLOCK_RE, '').split(SUGGEST_MARK).join(''),
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
