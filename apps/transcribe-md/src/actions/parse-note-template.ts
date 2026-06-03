'use server';

// ============================================================================
// Note-format customization — Phase 2a server action (DORMANT)
// ----------------------------------------------------------------------------
// Takes a doctor's note TEXT, returns a parsed template DRAFT (or a PHI-safe
// rejection). Persists NOTHING and activates NOTHING — Phase 2b's review flow
// owns persistence + activation. No UI calls this yet.
//
// PHI posture: the note is processed in-memory by parseNoteToTemplate and
// discarded. This action writes no DB row and logs no raw note content; the
// only persistence anywhere is the AI-call logger's prompt HASH + metadata.
// ============================================================================

import { requireSession } from '@/lib/auth';
import { ModelOutputMalformedError } from '@meddoc/ai';
import { parseNoteToTemplate } from '@/lib/note-template-parse/parse-note-to-template';
import type { ParseNoteResult } from '@/lib/note-template-parse/note-template-schema';

/** Soft cap on input size — a note far larger than this is almost certainly
 *  not a single template and risks runaway token cost. */
const MAX_NOTE_CHARS = 50_000;

export async function parseNoteTemplateAction(
  noteText: string
): Promise<ParseNoteResult> {
  const session = await requireSession();

  const text = (noteText ?? '').trim();
  if (text.length === 0) {
    return { rejected: true, template: null, reason: 'Empty note — nothing to parse.' };
  }
  if (text.length > MAX_NOTE_CHARS) {
    return {
      rejected: true,
      template: null,
      reason: `Note is too long (max ${MAX_NOTE_CHARS.toLocaleString()} characters). Paste a single representative note.`,
    };
  }

  try {
    return await parseNoteToTemplate(text, {
      practiceId: session.user.practiceId,
      userId: session.user.id,
    });
  } catch (err) {
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
