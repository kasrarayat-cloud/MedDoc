// ============================================================================
// E2E helper — out-of-band reads/writes of `note_templates` (+ a visit's
// resolved template) for the Batch-3 note-format lifecycle specs.
// ----------------------------------------------------------------------------
// The note-format lifecycle's source of truth is the DB row, not the UI: the
// version bump, the active/inactive supersede, the partial-unique "one active
// per (doctor, encounterType)" invariant, and the PHI scrub all live there.
// These specs drive the real UI, then assert the resulting ROW state here —
// which is deterministic and immune to the router.refresh() timing that flaked
// scenario 5 (assert the committed DB, not the async-repopulated list).
//
// SQL is piped to psql via STDIN (`-f -`), NOT `-c "<sql>"`, so JSONB inserts
// with embedded double-quotes need no shell escaping. The compose/PSQL_BIN
// channel mirrors helpers/seedVisitStates.ts exactly (CI exports PSQL_BIN to a
// direct psql; locally we shell into the qa stack's postgres). Same fail-closed
// posture: this only ever targets the qa stack's meddoc_qa_test DB.
// ============================================================================

import { execSync } from 'node:child_process';

import { assertNonProdDbName } from '@meddoc/db/guard';

import { QA_COMPOSE as COMPOSE, QA_DB as DB } from './qa-compose';

/** Run SQL against the qa Postgres, returning unaligned tuples-only stdout.
 *  SQL is fed on STDIN (`-f -`) so embedded quotes/JSON need no escaping. */
function psql(sql: string): string {
  const bin = process.env.PSQL_BIN; // CI: full prefix incl. connection string
  if (bin) {
    return execSync(`${bin} -v ON_ERROR_STOP=1 -A -t -f -`, {
      input: sql,
      encoding: 'utf8',
      stdio: ['pipe', 'pipe', 'pipe'],
    }).trim();
  }
  // Compose path → the isolated qa stack. FAIL-CLOSED: never touch a prod DB
  // (same guard the cleanup/seedVisitStates helpers make — resolution alone
  // isn't trusted; this helper both reads AND inserts).
  assertNonProdDbName(DB);
  return execSync(`${COMPOSE} exec -T postgres psql -v ON_ERROR_STOP=1 -U meddoc -d ${DB} -A -t -f -`, {
    input: sql,
    encoding: 'utf8',
    stdio: ['pipe', 'pipe', 'pipe'],
  }).trim();
}

/** SQL-escape a single-quoted literal (double any embedded quote). Test inputs
 *  are controlled, but a doctor-facing template name can carry an apostrophe. */
function lit(v: string): string {
  return `'${v.replace(/'/g, "''")}'`;
}

export interface NoteTemplateRow {
  id: string;
  name: string;
  status: 'draft' | 'active' | 'inactive';
  version: number;
  encounterType: string | null;
}

/** Resolve a seeded/self-signed doctor's user id by email. */
export function getDoctorId(email: string): string {
  const id = psql(`SELECT id FROM users WHERE email = ${lit(email)} LIMIT 1;`).trim();
  if (!id) throw new Error(`[noteTemplates] no user row for ${email}`);
  return id;
}

/** Every note_templates row owned by this doctor, oldest first. The `|` split
 *  is safe — the specs never put a pipe in a template name. */
export function listTemplates(doctorId: string): NoteTemplateRow[] {
  const out = psql(
    `SELECT id, name, status, version, COALESCE("encounterType", '') ` +
      `FROM note_templates WHERE "doctorId" = ${lit(doctorId)} ORDER BY "createdAt" ASC, id ASC;`,
  );
  if (!out) return [];
  return out
    .split('\n')
    .filter((l) => l.length > 0)
    .map((line) => {
      const [id, name, status, version, enc] = line.split('|');
      return {
        id,
        name,
        status: status as NoteTemplateRow['status'],
        version: Number(version),
        encounterType: enc === '' ? null : enc,
      };
    });
}

/** Count this doctor's ACTIVE templates for one encounter slot (null = the
 *  catch-all slot). The partial-unique index guarantees this is ≤ 1. */
export function countActive(doctorId: string, encounterType: string | null): number {
  const slot =
    encounterType == null ? `"encounterType" IS NULL` : `"encounterType" = ${lit(encounterType)}`;
  return Number(
    psql(
      `SELECT COUNT(*) FROM note_templates ` +
        `WHERE "doctorId" = ${lit(doctorId)} AND status = 'active' AND ${slot};`,
    ).trim() || '0',
  );
}

/** The largest active-count across ALL of this doctor's encounter slots. The
 *  one-active-per-slot invariant means this must never exceed 1 — the direct
 *  E2E assertion that a supersession bug (two live templates) can't slip past. */
export function maxActivePerSlot(doctorId: string): number {
  return Number(
    psql(
      `SELECT COALESCE(MAX(c), 0) FROM (` +
        `SELECT COUNT(*) AS c FROM note_templates ` +
        `WHERE "doctorId" = ${lit(doctorId)} AND status = 'active' ` +
        `GROUP BY "encounterType") s;`,
    ).trim() || '0',
  );
}

/** Raw `sections` JSONB text for a row — used to assert a scrubbed default
 *  never persisted the PHI it carried. */
export function sectionsText(templateId: string): string {
  return psql(`SELECT sections::text FROM note_templates WHERE id = ${lit(templateId)};`).trim();
}

export interface VisitTemplateRef {
  noteTemplateId: string | null;
  noteTemplateVersion: number | null;
}

/** The template a visit's L4 actually resolved (persisted by 04-generate-soap
 *  regardless of validation outcome). Proves resolveActiveTemplate's choice. */
export function visitTemplate(visitId: string): VisitTemplateRef {
  const out = psql(
    `SELECT COALESCE("noteTemplateId", ''), COALESCE("noteTemplateVersion"::text, '') ` +
      `FROM transcribe_visits WHERE id = ${lit(visitId)};`,
  ).trim();
  const [id, version] = out.split('|');
  return {
    noteTemplateId: id ? id : null,
    noteTemplateVersion: version ? Number(version) : null,
  };
}

/** Seed a deterministic ACTIVE custom template directly (a low-flake
 *  precondition for the resolution spec — the template is the *fixture*, the
 *  worker's resolution of it is what's under test). `encounterType: null` is
 *  the catch-all slot, which resolves for a visit of any specialty. Minimal but
 *  schema-valid sections/styleProfile so normalizeTemplate doesn't choke. */
export function seedActiveTemplate(
  doctorId: string,
  opts: { name: string; encounterType: string | null; version?: number },
): string {
  const id = `e2e-tmpl-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
  const enc = opts.encounterType == null ? 'NULL' : lit(opts.encounterType);
  const sections = JSON.stringify([
    {
      key: 'subjective',
      label: 'Subjective',
      order: 0,
      formatHint: 'prose',
      styleInstructions: null,
      defaultText: null,
      defaultTextMode: 'omit_unless_supported',
    },
    {
      key: 'plan',
      label: 'Plan',
      order: 1,
      formatHint: 'bullets',
      styleInstructions: null,
      defaultText: null,
      defaultTextMode: 'omit_unless_supported',
    },
  ]);
  const style = JSON.stringify({ tense: 'past', tone: 'concise clinical', abbreviations: 'standard' });
  // Dollar-quote the JSON so its double-quotes need no escaping; SQL reaches
  // psql via stdin so the shell never sees it either.
  psql(
    `INSERT INTO note_templates ` +
      `(id, "doctorId", name, "encounterType", sections, "styleProfile", version, status, "isSystemDefault", "lineageId", "templateKind", "createdAt", "updatedAt") ` +
      `VALUES (${lit(id)}, ${lit(doctorId)}, ${lit(opts.name)}, ${enc}, ` +
      `$json$${sections}$json$::jsonb, $json$${style}$json$::jsonb, ${opts.version ?? 1}, ` +
      `'active', false, ${lit(id)}, 'structured', now(), now());`,
  );
  return id;
}
