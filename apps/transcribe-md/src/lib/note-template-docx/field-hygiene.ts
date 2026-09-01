// ============================================================================
// #163 RULE (2) — TEMPLATE HYGIENE IS A COMPILE-TIME FINDING, NOT A RUNTIME
// DELETION.
// ----------------------------------------------------------------------------
// ⚠️ WHY THIS EXISTS, AND WHY IT LIVES AT UPLOAD RATHER THAN AT RENDER.
//
// Ruling #162 spent three formulations trying to make the RENDERER clear an
// unfilled field's leftover content, and each was falsified a layer deeper:
// paragraph scope, part scope, field balance, element type. The fourth layer is
// the one that ended the approach — `w:sym`, `w:pict` and `w:delText` survived
// EVERY version, because a renderer that deletes what it can classify will
// always miss what it cannot. Measured at its worst, the widened clearing walk
// ERASED a patient's allergy line from a document that would be signed, with
// every guard green.
//
// So #163 inverts it. Runtime NEVER deletes what it cannot classify: a null is
// left unpatched and the field keeps the doctor's own blank representation.
// Leftover content is real, and it is answered HERE — at upload, once, where
// the doctor can act on it:
//
//     "this field contains leftover content and will print on every note —
//      clean it or accept it."
//
// The asymmetry is deliberate and is the whole design. A wrong deletion is
// silent and unrecoverable — it removes clinical text nobody notices is gone.
// A wrong FLAG is loud, costs a doctor ten seconds, and is fixed once at the
// template rather than every time a note renders.
//
// ⚠️ IT DETECTS, IT NEVER JUDGES. This module reports what WILL PRINT. Whether
// that is acceptable is the doctor's call — a placeholder like "Enter
// assessment" and a stale drug name are both leftover content, and only the
// person who owns the form can say which is which.
// ============================================================================
import {
  descendants,
  getAttribute,
  localName,
  tagOf,
  visibleText,
  type OrderedXmlNode,
} from './xml';
import type { TemplateOption } from '../template-twin/ir';
import {
  isWordPlaceholderOption,
  withoutPlaceholderOptions,
} from './placeholder-option';

/**
 * The finding's code, in ONE place. It is exported because three files must
 * agree on it — the compiler that raises it, the validator that grades it, and
 * the gate that proves the grade — and a string literal repeated three times is
 * a string literal that disagrees with itself after the first refactor.
 */
export const FIELD_LEFTOVER_CONTENT = 'FIELD_LEFTOVER_CONTENT';

/**
 * ⚠️ #163 RULE A(ii) — THE ONE SHAPE THAT IS NOT HYGIENE.
 *
 * A selection-shaped control whose RESTING content equals one of its OWN option
 * values is not leftover decoration a doctor may reasonably keep: it is a FALSE
 * ASSERTION WAITING TO PRINT. Nothing on the page distinguishes it from a
 * deliberate pick, so a field the encounter never mentioned — or explicitly
 * DENIED — renders as an answer.
 *
 * That is the harm #157(d) rule (2) was ruled to close, arriving through the
 * back door once the renderer stopped clearing nulls, and it is the single
 * finding of the seventeen that survived re-grounding as a real defect. So it
 * BLOCKS, and the doctor must clean the control before the template can be
 * certified.
 *
 * ⚠️ IT IS DETERMINISTIC SET-MEMBERSHIP, NOT A HEURISTIC. `resting ∈ options`,
 * compared exactly, over the option list the compiler already extracted. #162
 * died of three successive text heuristics; this rule cannot acquire a fourth,
 * because there is nothing here to tune.
 */
export const FIELD_RESTING_CONTENT_IS_OPTION = 'FIELD_RESTING_CONTENT_IS_OPTION';

/**
 * Word's own placeholder scaffolding. `w:showingPlcHdr` is the authoritative
 * marker — Word sets it when the control still holds its placeholder — and the
 * stock strings catch the case where a doctor typed over the flag but left
 * Word's wording. Both print on a blank note like any other content.
 *
 * ⚠️ THE STOCK LIST IS A LABELLING AID, NOT THE DETECTOR. Text is already
 * flagged by `detectFieldHygiene` whatever it says; this only decides whether
 * the sentence names it as Word scaffolding or as the doctor's own words, so an
 * incomplete list mislabels a finding and never hides one. Doctor-authored
 * default text is untouched either way — flagged, never blocked, never removed.
 */
const STOCK_PLACEHOLDERS = [
  'Click or tap here to enter text.',
  'Click here to enter text.',
  'Choose an item.',
  'Click or tap to enter a date.',
  'Enter a date.',
  'Click or tap here to enter a date.',
];

/** What a doctor would SEE in an unfilled field's locus. */
export interface FieldHygieneFinding {
  /**
   * `text` — the doctor's own characters will print.
   * `placeholder` — Word's scaffolding will print.
   * `object` — a glyph, image or drawing will.
   */
  readonly kind: 'text' | 'placeholder' | 'object';
  /** The offending element's local name for `object`; `w:t` for text. */
  readonly element: string;
  /** A short, truncated sample of what prints. Empty for `object`. */
  readonly sample: string;
}

/**
 * Elements that put marks on the page but carry no `w:t`, so no amount of text
 * clearing reaches them. This list is the reason #162's approach could not work
 * and is why the finding is raised rather than the content removed.
 *
 * ⚠️ IT IS A DETECTION LIST, NEVER A DELETION LIST — an incomplete detection
 * list under-reports and the doctor still sees the page; an incomplete deletion
 * list silently ships the thing it missed while a proof says the field is
 * empty. That asymmetry is why this is the safe place to enumerate.
 */
const VISIBLE_OBJECTS = ['sym', 'pict', 'object', 'drawing', 'delText'] as const;

/**
 * What will print if this field is never filled?
 *
 * `locus` is the field's OWN content region as its emitter knows it — the
 * `w:sdtContent` of a content control, the `w:tc` of a table cell, the
 * `w:ffData` of a legacy form field. The caller passes it rather than this
 * module re-deriving it, deliberately: a second implementation of "where does
 * this field live" is exactly the drift that produced #162(b)'s production
 * regression, where a copied helper read a different property from the one it
 * was copied from.
 */
export function detectFieldHygiene(
  locus: OrderedXmlNode | null | undefined,
  properties?: OrderedXmlNode | null,
): FieldHygieneFinding | null {
  if (!locus) return null;

  // ⚠️ THE FLAG IS CONSULTED BEFORE THE TEXT, because it is the only
  // AUTHORITATIVE answer to "is this Word's scaffolding?". A control can show
  // its placeholder with wording the doctor customised, and then no string list
  // could tell. Asking Word is the same move as asking the owner of a piece of
  // state rather than pattern-matching around it.
  const showingPlaceholder =
    !!properties && descendants(properties, 'showingPlcHdr').length > 0;

  // TEXT FIRST, and through the SHARED `visibleText` rather than a local walk —
  // it is already this codebase's definition of what renders as characters, and
  // a second definition would answer differently the day either is fixed.
  const text = visibleText(locus).trim();

  // An UNCHECKED checkbox is the blank state, not leftover content — see
  // `checkboxStates`. Suppressed before anything else looks at the text.
  const states = checkboxStates(properties);
  if (states?.unchecked !== null && states?.unchecked !== undefined && text === states.unchecked) {
    return null;
  }

  if (text.length > 0) {
    const stock = isWordPlaceholderOption(text) || STOCK_PLACEHOLDERS.includes(text);
    return {
      kind: showingPlaceholder || stock ? 'placeholder' : 'text',
      element: 't',
      sample: text.length > 60 ? `${text.slice(0, 59)}…` : text,
    };
  }
  // A control flagged as showing its placeholder, with no text in it, still
  // renders Word's scaffolding — so the flag is reported on its own.
  if (showingPlaceholder) {
    return { kind: 'placeholder', element: 'showingPlcHdr', sample: '' };
  }

  // ⚠️ THEN THE THINGS THAT PRINT WITHOUT BEING TEXT. Checked SECOND, not
  // instead: a field can carry both, and the text sample is the more useful
  // thing to show a doctor when it exists.
  for (const name of VISIBLE_OBJECTS) {
    if (descendants(locus, name).length > 0) {
      return { kind: 'object', element: name, sample: '' };
    }
    // `descendants` does not consider the node itself.
    if (localName(tagOf(locus)) === name) {
      return { kind: 'object', element: name, sample: '' };
    }
  }
  return null;
}


/**
 * ⚠️ EVERY DETAIL IS CAPPED, AND THIS IS NOT DEFENSIVE PROGRAMMING FOR ITS OWN
 * SAKE — IT IS A MEASURED BUG.
 *
 * `UnsupportedElementSchema` caps `detail` at 500 characters, and the compiler
 * refuses the WHOLE IR when a field violates it (`IR_VALIDATION_FAILED`). The
 * first version of these sentences interpolated an untruncated LABEL (up to 240
 * chars by schema) and an untruncated MATCHED VALUE, so on the real customer
 * template — WM IOV, 28 dropdowns — the detail overran and the template stopped
 * compiling ENTIRELY. A hygiene advisory took down the document it was advising
 * about.
 *
 * The cap lives here, at the one place every sentence is built, rather than at
 * each call site, because a call site added later would not know to apply it.
 */
const DETAIL_MAX = 500;
const cap = (text: string, max: number): string =>
  text.length > max ? `${text.slice(0, max - 1)}…` : text;
const capDetail = (text: string): string => cap(text, DETAIL_MAX);

/** The doctor-facing sentence. One place, so the wording cannot drift. */
export function fieldHygieneDetail(
  label: string | null,
  finding: FieldHygieneFinding,
): string {
  const where = label ? `"${cap(label, 80)}"` : 'this field';
  const what =
    finding.kind === 'text'
      ? `leftover content (${finding.sample})`
      : finding.kind === 'placeholder'
        ? `Word placeholder scaffolding${finding.sample ? ` (${finding.sample})` : ''}`
        : `a leftover ${finding.element === 'delText' ? 'tracked deletion' : finding.element} that prints as a mark on the page`;
  return capDetail(
    `${where} contains ${what} and will print on every note where the field is ` +
      `left unfilled. Clean it in the template, or accept it.`,
  );
}

/**
 * A checkbox's TWO DECLARED STATES, read from the control's own properties.
 *
 * ⚠️ THIS EXISTS TO KILL A FALSE POSITIVE, AND THE FALSE POSITIVE MATTERED. The
 * first version of this module flagged every checkbox, because an unfilled
 * checkbox's locus holds `☐` and that is visible text. But `☐` is precisely
 * what a blank checkbox SHOULD look like — it is the doctor's own blank
 * representation, which is the whole thing #163 rule (1) preserves. Telling a
 * doctor to "clean" a correctly-empty checkbox is noise, and a check that cries
 * wolf on every checkbox is one nobody reads by the tenth template.
 *
 * ⚠️ AND IT IS READ FROM THE CONTROL, NEVER FROM A LIST OF KNOWN GLYPHS. Word
 * lets a template declare any code points for the two states. A stock-glyph
 * list would be a text heuristic — the exact instrument that failed three times
 * under #162 — so the states come from the template's own declaration or the
 * check declines to judge.
 */
function checkboxStates(
  properties: OrderedXmlNode | null | undefined,
): { checked: string | null; unchecked: string | null } | null {
  if (!properties) return null;
  const box = descendants(properties, 'checkbox')[0];
  if (!box) return null;
  const glyph = (name: string): string | null => {
    const node = descendants(box, name)[0];
    const raw = node ? getAttribute(node, 'val') : null;
    if (!raw || !/^[0-9a-f]{1,6}$/i.test(raw)) return null;
    const code = Number.parseInt(raw, 16);
    if (code > 0x10ffff || (code >= 0xd800 && code <= 0xdfff)) return null;
    return String.fromCodePoint(code);
  };
  return { checked: glyph('checkedState'), unchecked: glyph('uncheckedState') };
}

/**
 * Does this selection control's RESTING content equal one of its own options?
 *
 * Exact set membership against both spellings the compiler keeps — the option's
 * `value` and the `displayText` a reader actually sees — because a control can
 * rest on either and both print as an answer.
 *
 * Returns the matched option text, so the refusal can NAME it. A blocking
 * finding a doctor cannot act on is just a locked door.
 */
export function detectRestingOptionCollision(
  locus: OrderedXmlNode | null | undefined,
  allowedOptions: readonly TemplateOption[],
  properties?: OrderedXmlNode | null,
): string | null {
  if (!locus) return null;
  const resting = visibleText(locus).trim();
  if (resting.length === 0) return null;

  // ⚠️ WORD'S OWN PLACEHOLDER IS NEVER THE BLOCKING CASE, AND THE REAL CUSTOMER
  // TEMPLATE IS WHY THIS LINE EXISTS.
  //
  // Word seeds every dropdown with a first `listItem` reading "Choose an item.",
  // stored exactly like a real option — so the first version of this rule
  // matched it and BLOCKED ALL 28 DROPDOWNS of `WM IOV Template.docx`, the one
  // real form this programme has. A(iii) rules stock scaffolding a NON-BLOCKING
  // hygiene flag; A(ii) blocks only a REAL option value. Matching the
  // placeholder would have converted the ruling's soft case into a hard refusal
  // of the customer's entire template.
  //
  // The test is `isWordPlaceholderOption`, this codebase's own definition,
  // rather than a second list of stock strings — that module was written for
  // exactly this string after it rendered into a signed imaging report.
  if (isWordPlaceholderOption(resting)) return null;

  // ⚠️ A CHECKBOX'S TWO STATES ARE ITS OPTION VALUES, so the same rule reaches
  // it — and reaches it in only ONE direction. Resting CHECKED prints as an
  // affirmative answer to a question nobody asked, which is this rule's exact
  // harm. Resting UNCHECKED asserts nothing: #157(d) rule (2) says in terms
  // that a checkbox with `value === false` renders unchecked, unchanged. So the
  // unchecked state is not a finding at all, here or in the hygiene pass.
  const states = checkboxStates(properties);
  if (states) {
    if (states.unchecked !== null && resting === states.unchecked) return null;
    if (states.checked !== null && resting === states.checked) return resting;
    return null;
  }

  // And the comparison set drops placeholders too, so a control resting on one
  // spelling of the placeholder cannot match another option's copy of it.
  for (const option of withoutPlaceholderOptions([...allowedOptions])) {
    if (resting === option.value || resting === option.displayText) return resting;
  }
  return null;
}

/** The doctor-facing sentence for the blocking case. One place, as above. */
export function restingOptionCollisionDetail(
  label: string | null,
  matched: string,
): string {
  const where = label ? `"${cap(label, 80)}"` : 'this field';
  return capDetail(
    `${where} rests on "${cap(matched, 80)}", which is one of its own choices. On a note ` +
      `where this field is left unfilled it prints as if that choice had been ` +
      `made, and nothing on the page says otherwise. Clear the control's contents ` +
      `in the template — this must be fixed before the template can be certified.`,
  );
}
