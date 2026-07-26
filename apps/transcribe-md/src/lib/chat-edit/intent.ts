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
// Those are the hard gates. The chat may take a doctor TO them; it may never
// satisfy one on their behalf. A gate a conversation can talk its way through
// is not a gate. There is no intent for any of them, and a test pins that.
//
// There is also no bulk adopt. "Accept all" is a LOOP over per-claim adopts, so
// every adopted suggestion gets its own SUGGESTION_ADOPTED row, exactly as if
// the doctor had clicked each card.
// ============================================================================

import { z } from 'zod';

/** Adopt ONE suggestion, by its index in the visit's claim array. */
export const AdoptIntentSchema = z.object({
  kind: z.literal('adopt_suggestion'),
  /** Index into the DB array — the same address the button uses. */
  index: z.number().int().min(0).max(199),
});

/** Adopt several. Dispatched as a LOOP of per-claim adopts, never a bulk
 *  endpoint, and refused unless the suggestions were read out first. */
export const AdoptManyIntentSchema = z.object({
  kind: z.literal('adopt_suggestions'),
  indexes: z.array(z.number().int().min(0).max(199)).min(1).max(50),
});

/** Replace one section's body — the same splice-and-save tap-to-edit uses. */
export const EditSectionIntentSchema = z.object({
  kind: z.literal('edit_section'),
  sectionLabel: z.string().min(1).max(120),
  body: z.string().max(20_000),
});

/** Take the doctor to something. A hint to the client; touches no data. */
export const ScrollIntentSchema = z.object({
  kind: z.literal('scroll_to'),
  target: z.enum(['rx_gate', 'em_gate', 'codes', 'document', 'suggestions']),
});

/**
 * The model declares that its reply renders these suggestions IN FULL.
 *
 * A declaration, not a fact — the server VERIFIES it against the reply text it
 * is about to send, and records the attestation only for claims whose full text
 * actually appears there. The model cannot talk its way past this: the evidence
 * is the words the doctor will read.
 */
export const ListedIntentSchema = z.object({
  kind: z.literal('listed_suggestions'),
  indexes: z.array(z.number().int().min(0).max(199)).min(1).max(50),
});

/** The model believes this is out of scope. Carried explicitly so a refusal is
 *  a first-class outcome rather than a reply that happens to contain "no". */
export const RefuseIntentSchema = z.object({
  kind: z.literal('refuse'),
  /** PHI-free, doctor-facing. */
  because: z.string().max(300),
});

export const ChatIntentSchema = z.discriminatedUnion('kind', [
  AdoptIntentSchema,
  AdoptManyIntentSchema,
  EditSectionIntentSchema,
  ListedIntentSchema,
  ScrollIntentSchema,
  RefuseIntentSchema,
]);

export type ChatIntent = z.infer<typeof ChatIntentSchema>;

export const ChatReplySchema = z.object({
  /** What the doctor reads. Must NAME what was done — see the system prompt. */
  reply: z.string().min(1).max(4000),
  /** Executed in order. Empty when the turn is purely conversational. */
  intents: z.array(ChatIntentSchema).max(50),
});

export type ChatReply = z.infer<typeof ChatReplySchema>;
