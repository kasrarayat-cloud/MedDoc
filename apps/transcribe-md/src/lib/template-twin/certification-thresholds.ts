/**
 * The certification gate's numeric thresholds, in ONE place with NO imports.
 *
 * ⚠️ IT IS A LEAF MODULE ON PURPOSE. The constant lived privately in
 * `certification-lifecycle.ts`, so the encounter generator hand-copied it — two
 * constants for one threshold, drifting the day either moves, with the copy
 * being the one nobody re-reads. Re-exporting it from the lifecycle module
 * instead dragged next-auth into every consumer and broke the test environment
 * outright (`Cannot find module .../next/server`).
 *
 * A shared value belongs where both sides can reach it cheaply, which means a
 * module that imports nothing.
 */

/** A certification proof must fill at least this many fields, or the certificate
 *  attests a template whose fill path is dead. Read by the lifecycle gate and by
 *  the verification-encounter generator that has to satisfy it. */
export const MIN_CERTIFIED_FILLED_FIELDS = 10;
