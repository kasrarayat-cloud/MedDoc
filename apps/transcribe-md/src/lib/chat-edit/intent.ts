// ============================================================================
// What the chat editor is ALLOWED to want.
// ----------------------------------------------------------------------------
// The model does not act. It returns an INTENT, and the server dispatches that
// intent into the same audited server actions the buttons call. Everything the
// chat can do therefore already has an owner, a refusal set and an audit row —
// and anything not in this union simply has no way to happen.
//
// WHAT IS DELIBERATELY ABSENT, and must stay absent:
//   • overriding a critical Rx warning
//   • confirming an E/M level change
//   • signing
//   • anything belonging to another visit or another patient
// Those are the hard gates. The chat may take a doctor TO them; it may never
// satisfy one on their behalf. A gate a conversation can talk its way through
// is not a gate. There is no intent for any of them, and a test pins that.
//
// The gates did not get weaker when this surface got broader. What grew is the
// set of things a doctor can CHANGE about their own note — a measurement cell,
// a header field — each one going through the same audited action a button
// would call. What cannot be reached from here is exactly what could not be
// reached before.
//
// There is also no bulk adopt. "Accept all" is a LOOP over per-claim adopts, so
// every adopted suggestion gets its own SUGGESTION_ADOPTED row, exactly as if
// the doctor had clicked each card.
// ============================================================================

import { z } from 'zod';

/** Replace one section's body — the same splice-and-save tap-to-edit uses. */
export const EditSectionIntentSchema = z.object({
  kind: z.literal('edit_section'),
  sectionLabel: z.string().min(1).max(120),
  body: z.string().max(20_000),
});

/** Take the doctor to something. A hint to the client; touches no data. */
export const ScrollIntentSchema = z.object({
  kind: z.literal('scroll_to'),
  target: z.enum(['rx_gate', 'em_gate', 'codes', 'document']),
});

/** The model believes this is out of scope. Carried explicitly so a refusal is
 *  a first-class outcome rather than a reply that happens to contain "no". */
export const RefuseIntentSchema = z.object({
  kind: z.literal('refuse'),
  /** PHI-free, doctor-facing. */
  because: z.string().max(300),
});

/**
 * Change ONE cell of ONE measurements table.
 *
 * The model names the coordinates and the value; it never writes markdown. The
 * server locates the cell and splices it. See lib/note-table-edit.ts for why:
 * a model handed a table and asked for a table can change a digit in a row
 * nobody mentioned, and a fabricated measurement is not recoverable downstream.
 */
export const EditTableCellIntentSchema = z.object({
  kind: z.literal('edit_table_cell'),
  sectionLabel: z.string().min(1).max(120),
  /** The row's first-column label, e.g. "GSV at the SFJ". */
  rowLabel: z.string().min(1).max(160),
  /** The column header, e.g. "DIAMETER (mm)" or just "diameter". */
  columnLabel: z.string().min(1).max(160),
  /** The new cell contents. A VALUE, not a sentence. */
  value: z.string().max(200),
  /**
   * WHICH table, when the row label appears under more than one.
   *
   * A bilateral study is the ordinary ultrasound case and it renders one table
   * per leg with identical segment labels. Without this the server could only
   * refuse — and its refusal asked the doctor which leg while giving the model
   * no field to answer in, so the commonest study on this surface was simply
   * uneditable. Matched against the caption line above each table, which is
   * what carries the laterality.
   */
  tableCaption: z.string().max(200).optional(),
});

/** Correct a header field — the patient's name and the visit's own metadata.
 *  Dispatched into an audited action, never a raw column write. */
export const EditHeaderIntentSchema = z.object({
  kind: z.literal('edit_header'),
  field: z.enum(['patient_name', 'chief_complaint']),
  value: z.string().min(1).max(200),
});

/**
 * The turn was a QUESTION, and the reply answers it.
 *
 * Exists so that "I did nothing" is always a positive declaration rather than
 * an absence. See the note on ChatReplySchema.intents.
 */
export const AnswerIntentSchema = z.object({
  kind: z.literal('answer'),
});

/**
 * The doctor asked for a change this editor has no tool for.
 *
 * DISTINCT FROM `refuse`, which is policy — signing, gates, another patient's
 * chart — and always will be. This one is capability: the thing is legitimate,
 * we simply cannot do it here. The contract on the reply is one plain sentence
 * that says what it cannot do and where that lives, so the doctor's next move
 * is obvious instead of being a second guess at the phrasing.
 */
export const CannotIntentSchema = z.object({
  kind: z.literal('cannot'),
  /** PHI-free. What was asked for, in the doctor's terms. */
  what: z.string().max(200),
  /** PHI-free. Where it actually lives, e.g. "Settings › My Note Format". */
  where: z.string().max(200),
});

export const ChatIntentSchema = z.discriminatedUnion('kind', [
  EditSectionIntentSchema,
  EditTableCellIntentSchema,
  EditHeaderIntentSchema,
  ScrollIntentSchema,
  RefuseIntentSchema,
  AnswerIntentSchema,
  CannotIntentSchema,
]);

export type ChatIntent = z.infer<typeof ChatIntentSchema>;

export const ChatReplySchema = z.object({
  /** What the doctor reads. Must NAME what was done — see the system prompt. */
  reply: z.string().min(1).max(4000),
  /**
   * Executed in order. AT LEAST ONE, ALWAYS.
   *
   * This used to permit an empty array, documented as "empty when the turn is
   * purely conversational". That one affordance is the whole of the failure
   * this schema was changed to prevent: a request the model could not map to a
   * tool was indistinguishable from a chat question, so it wrote prose, sent
   * `[]`, and the server executed nothing, wrote nothing, refused nothing and
   * logged SUCCESS. The doctor's audit row read
   * `{intents: [], edited: 0, adopted: 0, refused: 0, failed: 0}` — every
   * counter zero, no record that anything had been asked at all.
   *
   * A turn now has to say which kind of turn it was: it acted, it `answer`ed a
   * question, it `cannot` (no tool), or it `refuse`d (policy). Silence is no
   * longer one of the options, and a schema violation fails loudly instead of
   * succeeding quietly.
   */
  intents: z.array(ChatIntentSchema).min(1).max(50),
});

export type ChatReply = z.infer<typeof ChatReplySchema>;
