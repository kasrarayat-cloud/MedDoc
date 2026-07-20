"use server";

// ============================================================================
// Note-format customization — Phase 2a server action (DORMANT)
// ----------------------------------------------------------------------------
// Takes a narrowly admitted BLANK text outline and returns a parsed template
// DRAFT (or a PHI-safe rejection). Populated/completed notes fail closed before
// provider egress. Persists NOTHING and activates NOTHING — Phase 2b's review
// flow owns persistence + activation.
//
// PHI posture: the note is processed in-memory by parseNoteToTemplate and
// discarded. This action writes no DB row and logs no raw note content; the
// only persistence anywhere is the AI-call logger's prompt HASH + metadata.
// ============================================================================

import { requireSession } from "@/lib/auth";
import { ModelOutputMalformedError } from "@meddoc/ai";
import {
  claimCurrentLegacyNoteTemplateProviderActor,
  legacyNoteTemplateProviderAuthorityBoundary,
  LegacyNoteTemplateProviderAuthorityError,
  parseNoteToTemplate,
  type LegacyNoteTemplateProviderAuthorityClaim,
} from "@/lib/note-template-parse/parse-note-to-template";
import type { ParseNoteResult } from "@/lib/note-template-parse/note-template-schema";

/** Soft cap on input size — a note far larger than this is almost certainly
 *  not a single template and risks runaway token cost. */
const MAX_NOTE_CHARS = 50_000;

export async function parseNoteTemplateAction(
  noteText: string,
): Promise<ParseNoteResult> {
  const session = await requireSession();

  // `requireSession()` is request-start authentication. This clinical
  // provider action additionally requires a fail-closed current actor/practice
  // claim so stale JWT role, tenant, lifecycle, or product values can never
  // authorize provider spend or content egress.
  let initialActor: LegacyNoteTemplateProviderAuthorityClaim;
  try {
    initialActor = await claimCurrentLegacyNoteTemplateProviderActor({
      actorUserId: session.user.id,
    });
  } catch (error) {
    if (error instanceof LegacyNoteTemplateProviderAuthorityError) {
      return {
        rejected: true,
        template: null,
        reason:
          "Current physician access could not be confirmed. No template content was sent or returned.",
      };
    }
    throw error;
  }

  const text = (noteText ?? "").trim();
  if (text.length === 0) {
    return {
      rejected: true,
      template: null,
      reason: "Empty note — nothing to parse.",
    };
  }
  if (text.length > MAX_NOTE_CHARS) {
    return {
      rejected: true,
      template: null,
      reason: `Outline is too long (max ${MAX_NOTE_CHARS.toLocaleString()} characters). Paste one blank clinical outline.`,
    };
  }

  try {
    return await parseNoteToTemplate(text, {
      providerAuthority: legacyNoteTemplateProviderAuthorityBoundary({
        actorUserId: initialActor.actorUserId,
        expectedPracticeId: initialActor.practiceId,
      }),
    });
  } catch (err) {
    if (err instanceof LegacyNoteTemplateProviderAuthorityError) {
      return {
        rejected: true,
        template: null,
        reason:
          "Current physician access changed while the privacy check was running. No template was returned.",
      };
    }
    // Malformed model output → a generic rejection. NEVER surface raw model
    // output or note content in the reason (PHI guard).
    if (err instanceof ModelOutputMalformedError) {
      return {
        rejected: true,
        template: null,
        reason:
          "Couldn't parse this note into a template. Try a blank template, or simplify the note and try again.",
      };
    }
    throw err;
  }
}
