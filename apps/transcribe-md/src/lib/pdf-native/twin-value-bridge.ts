// ============================================================================
// UPLOAD-AND-CERTIFIED · S2-4 — the certified twin's resolved values fill the
// twin-derived anchors on the doctor's ORIGINAL PDF page (owner ruling #322).
// ----------------------------------------------------------------------------
// deriveTwinAnchors keys each anchor by the twin `fieldId`; the twin's fill
// manifest resolves a value per `fieldId`. So the bridge is a 1:1 join on
// fieldId — the twin decides WHAT the value is, the anchor decides WHERE on the
// doctor's page it lands. No re-derivation of values, no note-heading heuristic.
//
// ⚠️ "A VALUE THAT CANNOT BE PLACED" IS A FALLBACK TRIGGER, NOT A DROP. Ruling
// #322: if a resolved field has a value but no anchor (its label was absent, or
// a Fill-in had no marker → `unlocatable`), OR its value is not a scalar a text
// region can hold (a repeating-table value), the export must fall back to the
// twin's STRUCTURAL styled render — which CAN place every field — rather than
// draw a partial page. This module surfaces those as `unplaceable`; the caller
// declines with a coded reason so the route renders the styled document instead.
// Only a field that is genuinely EMPTY (no value) is silently skipped — there is
// nothing to place.
// ============================================================================
import type { FieldResolution, ResolvedFieldValue } from '@/lib/template-twin/ir';
import type { PdfFillAnchor } from './fill-engine';

/**
 * Reduce a resolved twin value to the text a pdf-native region draws, or null
 * when the value cannot live in a text region (a table of rows). Scalars and a
 * multi-select list are placeable; a repeating-table value is not.
 */
export function resolvedValueToText(value: ResolvedFieldValue): string | null {
  if (typeof value === 'string') return value;
  if (typeof value === 'number') return String(value);
  // ⚠️ A boolean is a CHECKBOX. The twin's structural render ticks (or leaves
  // blank) a real box; stamping the literal word "Yes"/"No" at the label anchor
  // misrepresents it — worst of all a denied box that would draw "No" where the
  // form shows an unticked box (adversarial pass, 2026-09-15). A coordinate text
  // region cannot tick a box, so a boolean is UNPLACEABLE → the styled fallback
  // renders the checkbox correctly.
  if (typeof value === 'boolean') return null;
  if (Array.isArray(value)) {
    // A multi-select is string[]; join for a single region. A table value is an
    // array of row records — NOT placeable on a coordinate anchor → null.
    if (value.every((v) => typeof v === 'string')) {
      return (value as string[]).join('; ');
    }
    return null;
  }
  return null;
}

export interface TwinFillBridge {
  /** anchorKey (== fieldId) → the value text to draw. Only placeable, non-empty
   *  resolutions with a matching anchor appear here. */
  texts: Record<string, string>;
  /** fieldIds that HAVE a value but CANNOT be placed — no anchor, or a
   *  non-scalar value. Non-empty ⇒ the caller falls back to the styled render. */
  unplaceable: string[];
}

/**
 * Join the twin's resolutions onto its derived anchors by fieldId. PURE.
 *
 * @param resolutions the fill manifest's field resolutions (fieldId → value)
 * @param anchors     the twin-derived anchors (key === fieldId)
 * @param unlocatable fieldIds deriveTwinAnchors could not place on the page
 */
export function buildTwinFillTexts(
  resolutions: readonly FieldResolution[],
  anchors: readonly PdfFillAnchor[],
  unlocatable: readonly string[],
): TwinFillBridge {
  const anchoredIds = new Set(anchors.map((a) => a.key));
  const unlocatableSet = new Set(unlocatable);
  const texts: Record<string, string> = {};
  const unplaceable: string[] = [];

  for (const r of resolutions) {
    // A field with no value (not_mentioned / withheld) is nothing to place —
    // its region stays blank, exactly as an unfilled control would.
    if (r.value === null || r.value === undefined) continue;

    const text = resolvedValueToText(r.value);
    // A value that reduced to nothing placeable (a table) cannot go on a region.
    if (text === null) {
      unplaceable.push(r.fieldId);
      continue;
    }
    // Whitespace-only reductions are treated as empty (nothing to draw).
    if (text.trim() === '') continue;

    // A value with no anchor on the doctor's page cannot be placed.
    if (!anchoredIds.has(r.fieldId) || unlocatableSet.has(r.fieldId)) {
      unplaceable.push(r.fieldId);
      continue;
    }
    texts[r.fieldId] = text;
  }

  return { texts, unplaceable };
}
