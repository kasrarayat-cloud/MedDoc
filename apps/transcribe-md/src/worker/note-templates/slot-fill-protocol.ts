// ============================================================================
// SLOT-FILL PROTOCOL — the wire format between the prompt and the assembler.
// ----------------------------------------------------------------------------
// WHY THIS IS ITS OWN MODULE (ruling #106(a), SPEC §4.3a)
//
// `section-assembly.ts` owns BYTES: it splits the doctor's text into literals
// and slots and stitches values back in. This module owns the CONVERSATION: how
// the model is asked for slot values, and how its answer is read back. The two
// are separable and were separated on purpose — the assembler must be provable
// without a model in the room, and the protocol must be changeable without
// touching the code that handles the doctor's bytes.
//
// ⚠️ THE CONTRACT INVERTED, AND THAT IS THE WHOLE FIX. Until today the prompt
// handed the model the doctor's fixed prose and asked it to REPRODUCE it
// (CHOICE_SLOT_DIRECTIVE: "Preserve the scaffold's LINE STRUCTURE … reproduce
// each labeled field"). A model asked to reproduce prose will normalise it, and
// one did: `500 milliseconds` came back as `0.5 seconds`. Now the model never
// receives that text as writable at all. It is told the section exists, told
// which holes it may fill and from which menus, and asked for the VALUES.
//
//     A model cannot paraphrase text it never receives as writable.
//
// ⚠️ THE SENTINEL IS DELIBERATELY NOT A MARKDOWN FENCE. A clinical note can
// legitimately contain ```-fenced text, and "find the last fence" is exactly the
// substring trap AGENTS.md records four sightings of. `<<<SLOT_VALUES` is a
// token no note contains and no template can produce.
//
// ⚠️ ABSENCE IS FAIL-CLOSED, NOT AN ERROR. A missing, truncated or unparseable
// block yields NO fills, every slot renders the form's visible empty marker, and
// the doctor's fixed prose is emitted regardless. The failure mode of this
// protocol is a note with visible holes — never a note with invented values, and
// never a note missing the doctor's paragraph.
// ============================================================================

import type { AssemblyLine } from './section-assembly';
import { sectionSlots } from './section-assembly';
import type { NoteTemplateSection } from './system-default-template';

/** Opening sentinel of the slot-values block. */
export const SLOT_VALUES_OPEN = '<<<SLOT_VALUES';
/** Closing sentinel of the slot-values block. */
export const SLOT_VALUES_CLOSE = 'SLOT_VALUES>>>';

/** `{ [sectionKey]: { [slotId]: value } }` — the model's answer, already
 *  narrowed to strings. Validation against each slot's OWN menu happens in
 *  `assembleSection`, structurally, not here. */
export type SlotFills = Record<string, Record<string, string>>;

/**
 * The per-section block that tells the model a section is SYSTEM-COMPOSED and
 * lists the holes it may fill.
 *
 * ⚠️ IT NAMES THE DISCARD EXPLICITLY. "Anything you write under this heading is
 * discarded" is a true statement about `composeNote`, and stating a mechanical
 * consequence beats asking for compliance: a model that writes the section
 * anyway costs tokens and changes nothing.
 */
export function renderStaticSectionRequest(
  section: NoteTemplateSection,
  lines: readonly AssemblyLine[]
): string[] {
  const slots = sectionSlots(lines);
  const out = [
    'SYSTEM-COMPOSED SECTION. Do NOT write this section. Its text is inserted',
    "verbatim from the clinician's own form by the system, and anything you",
    'write under this heading is discarded.',
  ];
  if (slots.length === 0) {
    out.push('It has no fillable slots — there is nothing to supply for it.');
    return out;
  }
  out.push(
    `Supply ONLY the values for its ${slots.length} slot${slots.length === 1 ? '' : 's'}, under the key "${section.key}":`
  );
  for (const s of slots) {
    out.push(`  ${s.id} — one of: ${s.options.join(' | ')}`);
  }
  return out;
}

/**
 * The global directive describing the slot-values block.
 *
 * ⚠️ WHAT SURVIVED FROM `CHOICE_SLOT_DIRECTIVE` AND WHAT DID NOT — the split is
 * the point of the ruling, so it is written down rather than left to a diff.
 *
 * KEPT, because they govern WHICH VALUE IS RIGHT, which is still the model's
 * job: pick only a listed option; never invent; laterality is sacred; a
 * multi-slot carrier is filled as ONE coherent set; a normal side does not get
 * an abnormal option forced into it.
 *
 * RETIRED, because they governed HOW THE TEXT IS PRODUCED, which is now code's
 * job: "replace the ENTIRE `{{...}}` marker", "drop that marker (leave it
 * blank)", "omit the sentence entirely", "Preserve the scaffold's LINE
 * STRUCTURE". Every one of those was an instruction to hold the doctor's bytes
 * and hand them back, and each is now unreachable by construction.
 */
export const SLOT_VALUES_DIRECTIVE = [
  'SLOT VALUES — the machine-readable half of your answer.',
  'After the note, emit EXACTLY ONE block, last, in this form:',
  SLOT_VALUES_OPEN,
  '{"<section key>": {"<slot id>": "<one listed option, copied verbatim>"}}',
  SLOT_VALUES_CLOSE,
  'Rules for choosing a value:',
  '- Copy ONE of that slot\'s OWN listed options, character for character. A',
  '  value that is not on that slot\'s list is refused by the system and the',
  '  slot is left visibly empty — inventing or rewording an option cannot',
  '  produce output, it can only produce a hole.',
  '- Never place an option from one slot into a different slot.',
  '- OMIT a slot entirely (or give it null) when the transcript does not',
  '  support any of its options. Omitting is CORRECT and expected; it renders',
  '  the form\'s own empty marker, which a clinician can see and fill in.',
  '- SIDE / SUBJECT GROUNDING (laterality is sacred). A slot sits inside a',
  '  sentence that names a specific side and structure. Choose an option ONLY',
  '  when the transcript states it FOR THAT SAME side and structure. A finding',
  '  about the RIGHT leg must NEVER fill a LEFT slot, and the mere appearance',
  '  of an option\'s words elsewhere in the transcript is NOT support for THIS',
  '  slot. Never default to the first-listed option.',
  '- NORMAL FINDING → OMIT. When the transcript describes this slot\'s',
  '  side/structure as normal / competent / no reflux and no listed option',
  '  encodes that, omit the slot. Do not pick an abnormal option to fill a',
  '  sentence.',
  '- ONE COHERENT SET. When several slots sit in one sentence (a vein and the',
  '  segments it runs between), fill them as a set: the segments must belong to',
  '  the vein you chose and read proximal-to-distal.',
  'Emit the block even when you filled nothing — an empty object is a valid,',
  'meaningful answer.',
].join('\n');

export interface ExtractedSlotFills {
  /** The note text with the slot-values block removed. */
  text: string;
  fills: SlotFills;
  /** Why no fills were read, or null when a block parsed. PHI-free enum-ish
   *  string, safe to log. */
  error: string | null;
}

/** Coerce one section's object into `Record<string, string>`, dropping nulls,
 *  numbers, nested objects and anything else the model may have improvised.
 *  A dropped entry is an UNFILLED slot, which is the fail-closed direction. */
function narrowSection(raw: unknown): Record<string, string> {
  const out: Record<string, string> = {};
  if (raw === null || typeof raw !== 'object' || Array.isArray(raw)) return out;
  for (const [k, v] of Object.entries(raw as Record<string, unknown>)) {
    if (typeof v === 'string' && v.length > 0) out[k] = v;
  }
  return out;
}

/**
 * Pull the slot-values block out of the model's output.
 *
 * ⚠️ THE LAST BLOCK WINS, and that is the same reasoning `mockChatEdit` records
 * for taking the last directive: a model that restates the format, or shows an
 * example before its real answer, would otherwise be read by its illustration.
 *
 * ⚠️ EVERY FAILURE PATH RETURNS `{}` AND STRIPS NOTHING IT CANNOT PROVE. There
 * is no throw here: the caller must be able to assemble a note whatever the
 * model did, and a note with visible holes beats no note at all.
 */
export function extractSlotFills(rawText: string): ExtractedSlotFills {
  const open = rawText.lastIndexOf(SLOT_VALUES_OPEN);
  if (open === -1) return { text: rawText, fills: {}, error: 'slot_block_absent' };
  const bodyStart = open + SLOT_VALUES_OPEN.length;
  const close = rawText.indexOf(SLOT_VALUES_CLOSE, bodyStart);
  // An unterminated block is still REMOVED from the note: whatever follows the
  // sentinel is protocol, not prose, and leaving it in would print JSON into a
  // clinical document.
  const body = close === -1 ? rawText.slice(bodyStart) : rawText.slice(bodyStart, close);
  const text =
    close === -1
      ? rawText.slice(0, open)
      : rawText.slice(0, open) + rawText.slice(close + SLOT_VALUES_CLOSE.length);
  const cleaned = text.replace(/\s+$/, '');
  if (close === -1) {
    return { text: cleaned, fills: {}, error: 'slot_block_unterminated' };
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(body.trim());
  } catch {
    return { text: cleaned, fills: {}, error: 'slot_block_not_json' };
  }
  if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
    return { text: cleaned, fills: {}, error: 'slot_block_not_an_object' };
  }
  const fills: SlotFills = {};
  for (const [sectionKey, raw] of Object.entries(parsed as Record<string, unknown>)) {
    fills[sectionKey] = narrowSection(raw);
  }
  return { text: cleaned, fills, error: null };
}
