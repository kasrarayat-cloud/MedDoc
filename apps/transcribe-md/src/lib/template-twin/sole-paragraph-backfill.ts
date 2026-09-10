// ============================================================================
// #313 O5 — THE PURE HALF OF THE SOLE-PARAGRAPH BACKFILL.
// ----------------------------------------------------------------------------
// Ruling #313 O5: the new compiler-set IR property `soleParagraphControl` must
// reach the re-issued DRAFT's stored compiled IR "by a ruled, declared,
// in-place write", identity-safe because the property is stripped from both
// structural hashes. The certified, active version is NOT touched.
//
// The act is `scripts/backfill-sole-paragraph-control.ts`. That file reads rows
// and bytes and writes one column; EVERY DECISION lives here, pure, so the
// guard set is proved by `gate-313-backfill.test.ts` without a database — the
// `transfer-args.ts` precedent.
//
// ⚠️ THE STORED IR IS HANDLED AS THE RAW JSON THE COLUMN HOLDS, NEVER A PARSED
// COPY. `TemplateDocIRSchema.parse` fills defaults (`rowLaterality`), so
// writing a parsed IR back would change the stored bytes beyond the one
// property the ruling authorises. The new IR is the raw JSON with exactly one
// key added to exactly the fields the new compiler flags — and a guard proves
// that is the only difference.
// ============================================================================

import { canonicalSha256 } from './canonical';
import { bulletGroups, type BulletGroup } from './bullet-groups';
import {
  TemplateDocIRSchema,
  type SemanticMapping,
  type TemplateDocIR,
} from './ir';
import { fieldForStructuralIdentity } from '../note-template-docx/compiler';

export interface SoleParagraphBackfillArgs {
  readonly compiledVersionId: string;
  readonly expectFields: number;
  readonly expectGroups: number;
  readonly expectMembers: number;
  readonly commit: boolean;
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

/**
 * Every argument is REQUIRED — no default target, no default count. A default
 * is a value nobody declared, and this act writes a production row.
 */
export function parseSoleParagraphBackfillArgs(
  argv: readonly string[],
): { ok: true; args: SoleParagraphBackfillArgs } | { ok: false; reason: string } {
  const value = (name: string): string | null => {
    const at = argv.indexOf(`--${name}`);
    if (at < 0 || at + 1 >= argv.length) return null;
    const next = argv[at + 1]!;
    return next.startsWith('--') || next.trim() === '' ? null : next;
  };
  const known = new Set([
    '--compiled-version',
    '--expect-fields',
    '--expect-groups',
    '--expect-members',
    '--commit',
  ]);
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index]!;
    if (!token.startsWith('--')) continue;
    if (!known.has(token)) return { ok: false, reason: `unknown argument ${token}` };
  }
  const compiledVersionId = value('compiled-version');
  if (compiledVersionId === null) {
    return { ok: false, reason: 'missing required argument --compiled-version' };
  }
  if (!UUID.test(compiledVersionId)) {
    return { ok: false, reason: `--compiled-version must be a uuid, got '${compiledVersionId}'` };
  }
  const counts: Record<'expect-fields' | 'expect-groups' | 'expect-members', number> = {
    'expect-fields': 0,
    'expect-groups': 0,
    'expect-members': 0,
  };
  for (const name of Object.keys(counts) as Array<keyof typeof counts>) {
    const raw = value(name);
    if (raw === null) return { ok: false, reason: `missing required argument --${name}` };
    // ⚠️ STRICT — `parseInt('53x')` is 53, and a guard that accepts garbage
    // reports a number nobody meant.
    if (!/^\d+$/.test(raw)) {
      return { ok: false, reason: `--${name} must be a plain integer, got '${raw}'` };
    }
    counts[name] = Number(raw);
  }
  return {
    ok: true,
    args: {
      compiledVersionId,
      expectFields: counts['expect-fields'],
      expectGroups: counts['expect-groups'],
      expectMembers: counts['expect-members'],
      commit: argv.includes('--commit'),
    },
  };
}

/** A field record with the #313 property removed — the ONLY difference allowed. */
function withoutSole(field: Record<string, unknown>): Record<string, unknown> {
  const { soleParagraphControl: _sole, ...rest } = field;
  return rest;
}

/** The whole IR with the #313 property removed from every field. */
export function irWithoutSoleParagraphControl(ir: unknown): unknown {
  if (typeof ir !== 'object' || ir === null) return ir;
  const record = ir as Record<string, unknown>;
  const fields = Array.isArray(record.fields) ? record.fields : [];
  return {
    ...record,
    fields: fields.map((field) =>
      typeof field === 'object' && field !== null
        ? withoutSole(field as Record<string, unknown>)
        : field,
    ),
  };
}

export interface SoleParagraphBackfillInput {
  /** The `compiledDocumentIr` column, AS STORED (raw JSON). */
  readonly storedIr: unknown;
  /** The same source bytes, compiled by THIS compiler. */
  readonly recompiled: TemplateDocIR;
  readonly mappings: readonly SemanticMapping[];
  readonly certificationStatus: string;
  readonly hasCertificationRecord: boolean;
  readonly templateStatus: string;
  readonly persistedFieldCount: number;
  /** The `structureSha256` / `staticContentSha256` COLUMNS, not the IR's copy. */
  readonly columnStructureSha256: string;
  readonly columnStaticContentSha256: string;
  readonly artifactSha256: string;
  readonly bytesSha256: string;
  /** Fill manifests stored against this compiled version (the #247 window). */
  readonly fillManifestCount: number;
  readonly expect: {
    readonly fields: number;
    readonly groups: number;
    readonly members: number;
  };
}

export type BackfillGuard = readonly [name: string, got: unknown, want: unknown];

export interface SoleParagraphBackfillPlan {
  readonly guards: readonly BackfillGuard[];
  readonly failed: number;
  /** The IR to write, or null when any guard failed. */
  readonly next: unknown | null;
  readonly flaggedFieldIds: readonly string[];
  readonly groups: readonly BulletGroup[];
  readonly members: number;
}

function sameJson(a: unknown, b: unknown): boolean {
  return canonicalSha256(a) === canonicalSha256(b);
}

/**
 * Decide the act. Every premise it rests on becomes a guard, and any failed
 * guard means NOTHING is written. Guards are listed so the transcript shows
 * each one's value against its expectation, not merely a verdict.
 */
export function planSoleParagraphBackfill(
  input: SoleParagraphBackfillInput,
): SoleParagraphBackfillPlan {
  const guards: BackfillGuard[] = [];
  const guard = (name: string, got: unknown, want: unknown) => guards.push([name, got, want]);

  const parsedStored = TemplateDocIRSchema.safeParse(input.storedIr);
  const stored = parsedStored.success ? parsedStored.data : null;
  const raw = input.storedIr as { fields?: Array<Record<string, unknown>> } | null;
  const rawFields = Array.isArray(raw?.fields) ? raw!.fields : [];

  // ── the target is a DRAFT and nothing has certified it ─────────────────────
  guard('certificationStatus is not CERTIFIED', input.certificationStatus !== 'CERTIFIED', true);
  guard('no certification record exists', input.hasCertificationRecord, false);
  guard('note template status', input.templateStatus, 'draft');
  guard('fill manifests stored against this version (#247 window)', input.fillManifestCount, 0);

  // ── the stored IR is the one the declaration names ─────────────────────────
  guard('stored IR parses', parsedStored.success, true);
  guard(
    'stored IR carries no soleParagraphControl yet',
    rawFields.filter((field) => 'soleParagraphControl' in field).length,
    0,
  );
  guard('stored IR field count', rawFields.length, input.expect.fields);
  guard('persisted field rows', input.persistedFieldCount, input.expect.fields);

  // ── the bytes are the bytes the IR was compiled from ───────────────────────
  guard('bytes sha256 == artifact sha256', input.bytesSha256, input.artifactSha256);
  guard('stored IR source sha256 == artifact sha256', stored?.source.sha256 ?? null, input.artifactSha256);

  // ── the recompile is the SAME document, in every property but one ─────────
  const recompiled = input.recompiled;
  guard('compilerVersion', recompiled.compilerVersion, stored?.compilerVersion ?? null);
  guard(
    'same fieldIds in the same order',
    canonicalSha256(recompiled.fields.map((field) => field.fieldId)),
    canonicalSha256(rawFields.map((field) => field.fieldId ?? null)),
  );
  guard('structureSha256 (recompiled == stored IR)', recompiled.structureSha256, stored?.structureSha256 ?? null);
  guard('structureSha256 (recompiled == column)', recompiled.structureSha256, input.columnStructureSha256);
  guard('staticContentSha256 (recompiled == stored IR)', recompiled.staticContentSha256, stored?.staticContentSha256 ?? null);
  guard('staticContentSha256 (recompiled == column)', recompiled.staticContentSha256, input.columnStaticContentSha256);
  guard(
    'stored IR == recompiled IR except soleParagraphControl',
    sameJson(irWithoutSoleParagraphControl(input.storedIr), irWithoutSoleParagraphControl(recompiled)),
    true,
  );

  const flaggedFieldIds = recompiled.fields
    .filter((field) => field.soleParagraphControl === true)
    .map((field) => field.fieldId);
  guard(
    'recompiled soleParagraphControl values are only ever true',
    recompiled.fields.filter(
      (field) => field.soleParagraphControl !== undefined && field.soleParagraphControl !== true,
    ).length,
    0,
  );

  const preconditionsHold = guards.every(([, got, want]) => sameJson(got, want));

  // ── the write: the stored JSON plus exactly one key on the flagged fields ──
  let next: unknown | null = null;
  let groups: readonly BulletGroup[] = [];
  if (preconditionsHold) {
    const flagged = new Set(flaggedFieldIds);
    const candidate = {
      ...(input.storedIr as Record<string, unknown>),
      fields: rawFields.map((field) =>
        flagged.has(String(field.fieldId)) ? { ...field, soleParagraphControl: true } : field,
      ),
    };
    const parsedNext = TemplateDocIRSchema.safeParse(candidate);
    guard('new IR parses', parsedNext.success, true);
    guard(
      'new IR differs from stored ONLY by soleParagraphControl',
      sameJson(irWithoutSoleParagraphControl(candidate), input.storedIr),
      true,
    );
    guard(
      'new IR == recompiled IR, property included',
      sameJson(candidate, recompiled),
      true,
    );
    if (parsedNext.success) {
      // ⚠️ THE STRUCTURAL HASH, RECOMPUTED OVER THE NEW IR BY THE COMPILER'S OWN
      // NORMALISER — the proof that the property is stripped from both identity
      // comparisons rather than a claim that it is.
      const recomputed = canonicalSha256({
        fields: parsedNext.data.fields.map(fieldForStructuralIdentity),
        tables: parsedNext.data.tables,
        nodes: parsedNext.data.nodes,
        unsupported: parsedNext.data.unsupported,
      });
      guard('structureSha256 recomputed over the new IR', recomputed, input.columnStructureSha256);
      groups = bulletGroups(parsedNext.data.fields, input.mappings);
    }
    const members = groups.reduce((total, group) => total + group.memberFieldIds.length, 0);
    guard('bullet groups under the current mappings', groups.length, input.expect.groups);
    guard('bullet group members under the current mappings', members, input.expect.members);
    next = candidate;
  }

  const failed = guards.filter(([, got, want]) => !sameJson(got, want)).length;
  const members = groups.reduce((total, group) => total + group.memberFieldIds.length, 0);
  return {
    guards,
    failed,
    next: failed === 0 ? next : null,
    flaggedFieldIds,
    groups,
    members,
  };
}
