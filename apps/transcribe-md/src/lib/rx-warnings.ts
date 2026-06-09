// ============================================================================
// Canonical Rx-warning identity — single source of truth
// ----------------------------------------------------------------------------
// The worker (worker/layers/07c-rx-drafting.ts) persists Rx safety warnings to
// `TranscribeVisit.rxDrafts.warnings[]` but does NOT stamp a per-warning id —
// a warning's identity is its POSITIONAL index in that array. Three call sites
// must agree on that identity, byte-for-byte, or the critical-Rx sign gate
// breaks:
//
//   1. the Rx rail client (app/visits/[id]/rx-tab.tsx) — builds the override
//      payload's warningId + maps the 3-band worker severity to the 4-band
//      rail severity;
//   2. recordOverride (lib/rx-warning-audit.ts) — VALIDATES a submitted
//      warningId/severity against the persisted warnings before writing an
//      override audit row;
//   3. the sign gate (api/visits/[id]/sign/route.ts) — clears the
//      READY→SIGNED transition only when EVERY persisted critical warning has
//      a matching override keyed by its real id.
//
// Centralising the derivation here is what closes the override-count-inflation
// bypass (fix/rx-override-gate-correlation): the gate correlates overrides to
// REAL warnings by this id rather than counting bare severity rows, and
// recordOverride rejects ids/severities that don't correspond to an actual
// warning — so client-supplied warning identity is never trusted verbatim.
// ============================================================================

export type WorkerSeverity = 'critical' | 'major' | 'minor';
export type RailSeverity = 'critical' | 'serious' | 'moderate' | 'info';

/** The shape persisted in `rxDrafts.warnings[]` by Layer 7c. No id field —
 *  identity is positional (see `warningIdForIndex`). */
export interface StoredRxWarning {
  severity: WorkerSeverity;
  rx_drug?: string;
  message?: string;
  evidence_quote?: string | null;
}

const WARNING_ID_PREFIX = 'rx-warning-';

/** The stable warningId for the warning at array index `i` of
 *  `rxDrafts.warnings[]`. MUST match what the rail client emits. */
export function warningIdForIndex(i: number): string {
  return `${WARNING_ID_PREFIX}${i}`;
}

/** Inverse of {@link warningIdForIndex}. Returns the index, or `null` if the
 *  id isn't a well-formed positional warning id (e.g. a fabricated/guessed
 *  value like `'x1'` or `'rx-warning-abc'`). */
export function indexForWarningId(id: unknown): number | null {
  if (typeof id !== 'string' || !id.startsWith(WARNING_ID_PREFIX)) return null;
  const raw = id.slice(WARNING_ID_PREFIX.length);
  if (!/^\d+$/.test(raw)) return null;
  return Number(raw);
}

/** Worker 3-band severity → rail 4-band severity. Only `'critical'` is common
 *  to both vocabularies, and it's the only severity the sign gate counts. */
export function mapWorkerSeverity(s: WorkerSeverity): RailSeverity {
  if (s === 'critical') return 'critical';
  if (s === 'major') return 'serious';
  return 'info';
}

/** Pull the persisted warnings array out of a `TranscribeVisit.rxDrafts`
 *  blob, defensively (it's a `Json?` column of unknown runtime shape). */
export function extractWarnings(rxDrafts: unknown): StoredRxWarning[] {
  const blob = rxDrafts as { warnings?: unknown } | null;
  const arr = blob?.warnings;
  return Array.isArray(arr) ? (arr as StoredRxWarning[]) : [];
}

export interface CriticalWarningRef {
  index: number;
  id: string;
  warning: StoredRxWarning;
}

/** Every CRITICAL warning persisted on the visit, paired with its canonical
 *  id. The sign gate requires a matching override for each of these. */
export function criticalWarningRefs(rxDrafts: unknown): CriticalWarningRef[] {
  return extractWarnings(rxDrafts)
    .map((warning, index) => ({ index, id: warningIdForIndex(index), warning }))
    .filter((ref) => ref.warning?.severity === 'critical');
}

/** Resolve a submitted warningId to the persisted warning it references, or
 *  `null` if the id is malformed, out of range, or names no real warning.
 *  This is the server-side check that makes a fabricated/guessed warningId
 *  un-writable as an override. */
export function resolveWarning(
  rxDrafts: unknown,
  warningId: unknown
): StoredRxWarning | null {
  const i = indexForWarningId(warningId);
  if (i === null) return null;
  const warnings = extractWarnings(rxDrafts);
  if (i < 0 || i >= warnings.length) return null;
  return warnings[i] ?? null;
}
