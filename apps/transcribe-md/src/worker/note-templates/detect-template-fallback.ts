// ============================================================================
// RC-3 — THE FALLBACK GOES LOUD (ruling #106(c), SPEC §4.3a(d)).
// ----------------------------------------------------------------------------
// > "The generic layout is for doctors with NO uploaded form. A visit bound to
// >  an activated template either renders through THAT template's path or fails
// >  into a visible 'your form needs review' state naming why. Silently
// >  rendering the generic lookalike is the defect this clause exists to
// >  forbid — it is indistinguishable, to the doctor, from the product simply
// >  not working."
//
// ⚠️ THE PROBLEM IS NOT THAT FALLBACKS EXIST. Every one of them is a reasonable
// local decision: a database hiccup should not break generation, a pick that no
// longer resolves should not fail a visit. The problem is that ALL of them are
// fail-open to a lookalike with no observable signal — a `log.warn` at best,
// nothing at all at worst — and the provenance write-back then records the
// template that was USED, overwriting the evidence that another was ever asked
// for. The doctor sees a note. It is the wrong note. Nothing says so.
//
// ⚠️ THIS MODULE DOES NOT CHANGE WHICH TEMPLATE IS CHOSEN. Making a fallback
// throw would convert "wrong layout" into "failed visit", which is worse for
// the doctor and is not what the ruling asks for. It makes the fallback VISIBLE
// and leaves the note in their hands.
// ============================================================================

/** The system-default row's stable id — a pick of "Standard SOAP — no custom
 *  format" resolves to this, and choosing it deliberately is not a fallback. */
import { SYSTEM_DEFAULT_TEMPLATE_ID } from './system-default-template';

export type TemplateFallbackKind =
  /** Resolution threw. The catch installs the generic constant. */
  | 'resolution_failed'
  /** The visit named a template and a DIFFERENT one produced the note. */
  | 'pinned_template_not_applied'
  /** No pick, but the doctor HAS an activated format that should have applied
   *  to this specialty, and the generic layout was used anyway. */
  | 'active_template_not_applied';

export interface TemplateFallback {
  kind: TemplateFallbackKind;
  /** Doctor-facing. NAMES WHY, per §4.3a(d) — "your form needs review" with no
   *  cause is the same dead end as no message at all. */
  reason: string;
}

export interface DetectTemplateFallbackInput {
  /** The template id the VISIT named, before any resolution. Null when the
   *  doctor did not pick one on the new-visit form. */
  requestedTemplateId: string | null;
  /** The template that actually built the prompt. */
  effective: { id: string; isSystemDefault: boolean };
  /** True when resolution threw and the catch installed the constant. */
  resolutionFailed: boolean;
  /**
   * True when the doctor has an ACTIVE, non-system-default template whose
   * `encounterType` is this visit's specialty or is null (their catch-all).
   *
   * ⚠️ SCOPED TO TEMPLATES THAT SHOULD HAVE APPLIED, deliberately. A doctor with
   * a dermatology format doing a primary-care visit resolves to the generic
   * layout CORRECTLY, and a banner there would be false alarm — the fastest way
   * to teach a clinician to ignore the banner that matters.
   */
  hasApplicableActiveTemplate: boolean;
}

/**
 * Did this visit render through its own template's path — and if not, why?
 *
 * Returns `null` when nothing is wrong, which is the overwhelmingly common
 * case: a doctor with no uploaded form gets the generic layout and that is the
 * product working.
 */
export function detectTemplateFallback(
  input: DetectTemplateFallbackInput
): TemplateFallback | null {
  const { requestedTemplateId, effective, resolutionFailed } = input;

  // A custom template produced the note. Whatever happened upstream, the doctor
  // got their own form — there is nothing to warn about.
  if (!effective.isSystemDefault && !resolutionFailed) {
    // …unless a DIFFERENT custom template produced it, which is still a
    // substitution the doctor never asked for.
    if (
      requestedTemplateId !== null &&
      requestedTemplateId !== SYSTEM_DEFAULT_TEMPLATE_ID &&
      requestedTemplateId !== effective.id
    ) {
      return {
        kind: 'pinned_template_not_applied',
        reason:
          'This visit was set to use a specific note format, but a different one produced the note. Check your note format in Settings before signing.',
      };
    }
    return null;
  }

  if (resolutionFailed) {
    return {
      kind: 'resolution_failed',
      reason:
        'Your note format could not be loaded, so this note was written in the standard layout instead of your own form. Nothing was lost — re-run the visit once Settings shows your format, or sign this version if it reads correctly.',
    };
  }

  // From here the GENERIC layout produced the note.
  //
  // ⚠️ AN EXPLICIT PICK OF "Standard SOAP" ENDS THE QUESTION, and this early
  // return is load-bearing rather than tidy. Without it a doctor who owns a
  // custom format and deliberately chose the standard layout for one visit gets
  // a banner telling them their format was not applied — which is false, and
  // which is the fastest way to teach a clinician to ignore the banner that
  // matters. Caught by the null-case arm of its own test, not by review.
  if (requestedTemplateId === SYSTEM_DEFAULT_TEMPLATE_ID) return null;

  if (
    requestedTemplateId !== null &&
    requestedTemplateId !== SYSTEM_DEFAULT_TEMPLATE_ID &&
    requestedTemplateId !== effective.id
  ) {
    return {
      kind: 'pinned_template_not_applied',
      reason:
        'This visit was set to use one of your own note formats, but that format was not available and the standard layout was used instead. Check the format is still active in Settings before signing.',
    };
  }

  if (input.hasApplicableActiveTemplate) {
    return {
      kind: 'active_template_not_applied',
      reason:
        'You have an activated note format for this visit type, but this note was written in the standard layout instead. Check your note format in Settings before signing.',
    };
  }

  return null;
}
