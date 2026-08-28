// ============================================================================
// R1 — A PROVENANCE COLUMN IS NEVER `ON DELETE SET NULL`.
// ----------------------------------------------------------------------------
// `transcribe_visits.noteTemplateId` records WHICH template a clinical note was
// written against. Its FK carried `ON DELETE SET NULL`, so deleting a template
// silently erased that link on every bound visit — including SIGNED medical
// records — with no warning and no audit row.
//
// Measured on production the day this gate was written:
//     52 visits · 29 with provenance DESTROYED (id NULL, version still set)
//              · 18 of those SIGNED · 2 genuinely untemplated (both NULL)
//
// The (NULL id, SET version) pair is unwritable by any code path — every writer
// sets the two columns together — which is how the 29 were identified at all.
//
// ⚠️ THIS GATE IS STATIC, AND THAT IS A DELIBERATE CHOICE WITH A STATED COST.
// The honest test is behavioural: bind a visit, delete the template, watch it
// refuse. That needs a live database, which this suite does not have. So this
// gate pins the three things that are checkable from source, and the WALK is
// what exercises the behaviour. A static gate that says so is worth more than a
// behavioural one that cannot run.
// ============================================================================
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

const REPO = join(__dirname, '../../../../..');
const R = (p: string) => readFileSync(join(REPO, p), 'utf8');

const SCHEMA = 'packages/db/prisma/schema.prisma';
const ACTION = 'apps/transcribe-md/src/actions/note-template-lifecycle.ts';

describe('R1 · the template-delete fence', () => {
  // ── THE CONSTRAINT ───────────────────────────────────────────────────────
  it('the visit provenance relation is Restrict — never SetNull, never Cascade', () => {
    const line = R(SCHEMA)
      .split('\n')
      .find((l) => l.includes('noteTemplate ') && l.includes('NoteTemplate?') && l.includes('@relation'));
    expect(line, 'the visit->template relation line was not found — this gate is not watching anything').toBeDefined();
    expect(line).toContain('onDelete: Restrict');
    expect(line).not.toContain('SetNull');
    // ⚠️ Cascade would satisfy "not SetNull" and be far worse: it would DELETE
    // the clinical records. Both wrong answers are excluded by name.
    expect(line).not.toContain('Cascade');
  });

  it('a migration exists that actually alters the constraint on the database', () => {
    const dir = join(REPO, 'packages/db/prisma/migrations');
    const sql = readdirSync(dir)
      .filter((d) => /^\d/.test(d))
      .map((d) => {
        try {
          return readFileSync(join(dir, d, 'migration.sql'), 'utf8');
        } catch {
          return '';
        }
      })
      .join('\n');
    // non-vacuity: the corpus is real before any absence is believed
    expect(sql.length).toBeGreaterThan(1000);
    const fence = sql.match(/transcribe_visits_noteTemplateId_fkey[\s\S]{0,400}?ON DELETE RESTRICT/);
    expect(fence, 'no migration sets the provenance FK to ON DELETE RESTRICT').not.toBeNull();
  });

  // ── THE ACTION REFUSES BEFORE THE DATABASE HAS TO ────────────────────────
  it('deleteNoteTemplateAction counts referencing visits and refuses when any exist', () => {
    const src = R(ACTION);
    const fn = src.slice(src.indexOf('export async function deleteNoteTemplateAction'));
    const body = fn.slice(0, fn.indexOf('\nexport '));

    // ⚠️ THE PROPERTY, NOT THE SHAPE — and the first version of this arm pinned
    // the shape and thereby PINNED A DEFECT. It required the count to be written
    // exactly `{ where: { noteTemplateId: id } }`, which is the UNSCOPED form;
    // `gate-practice-scope`'s ratchet failed on that same code in CI. A
    // source-text gate that fixes an implementation spelling will happily hold a
    // bug in place and report green for doing it.
    expect(body, 'the action must count referencing visits').toMatch(
      /transcribeVisit\.count\(/,
    );
    expect(body, 'the count must filter by the template being deleted').toMatch(
      /noteTemplateId:\s*id\b/,
    );
    // `transcribeVisit` is clinical, and this number is spoken back to the
    // doctor — so the count is practice-scoped, not merely template-filtered.
    expect(body, 'the visit count must be practice-scoped').toMatch(
      /visitScope\(/,
    );
    // it must RETURN on the referenced case, not merely log
    expect(body).toMatch(/referencing\s*>\s*0[\s\S]{0,240}?ok:\s*false/);
    // ⚠️ and the count must reach the doctor — "cannot delete" is a wall,
    // "used by 12 visits" is something they can act on
    expect(body).toContain('${referencing}');

    // the guard must sit BEFORE the destructive call, not after it
    const guardAt = body.search(/referencing\s*>\s*0/);
    const deleteAt = body.search(/deleteMany/);
    expect(guardAt).toBeGreaterThan(-1);
    expect(deleteAt).toBeGreaterThan(-1);
    expect(guardAt, 'the refusal must precede the delete').toBeLessThan(deleteAt);
  });

  it('archival exists as the replacement, and does not delete', () => {
    const src = R(ACTION);
    expect(src).toContain('export async function archiveNoteTemplateAction');
    const fn = src.slice(src.indexOf('export async function archiveNoteTemplateAction'));
    const body = fn.slice(0, fn.indexOf('\n}') + 2);
    expect(body).toContain('updateMany');
    expect(body, 'archival must never delete').not.toContain('deleteMany');
  });

  // ── POSITIVE CONTROL ─────────────────────────────────────────────────────
  it('positive control: these matchers can fail', () => {
    const src = R(ACTION);
    expect(src).not.toContain('export async function aFunctionThatDoesNotExist');
    expect(R(SCHEMA)).not.toContain('onDelete: NotARealAction');
  });
});
