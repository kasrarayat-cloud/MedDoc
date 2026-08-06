// ============================================================================
// T5 — the guard that keeps the practice-scoped accessor the ONLY way in.
// ----------------------------------------------------------------------------
// ⚠️ THIS IS A RATCHET, NOT A WALL, AND THAT IS DELIBERATE.
// There were 81 request-context clinical reads when the accessor landed. A guard
// that demanded zero on day one would be red for the whole migration, and a
// permanently-red gate is a gate everyone learns to ignore — which is worse than
// no gate, because it looks like coverage.
//
// So it pins the CURRENT number and forbids it from growing. New code cannot add
// an unscoped clinical read; adoption lowers the ceiling commit by commit. The
// number only ever goes down, and the day it reaches zero this becomes a wall
// with no further work.
//
// ⚠️ WHY THE GUARD LANDS BEFORE THE ADOPTION. If 81 call sites were migrated
// first and the guard added last, the guard's first run would be a bug report
// against work already declared done — and every site missed would be found one
// CI cycle at a time. That is the exact failure T3 and T4 paid five cycles for.
// Landing the guard first makes every unmigrated site fail LOUDLY from the first
// commit.
//
// ⚠️ THE COUNT IS OF **UNSCOPED** READS, WHICH IS NOT WHAT IT FIRST MEASURED.
// The first version counted every `prisma.<clinical>.<read>(` call in request
// context — so routing a call through the accessor left the number UNCHANGED and
// adoption could never lower it. The name said "unscoped"; the implementation
// said "all". Same family of defect as the comment-matching bug above: a check
// whose title is narrower than what it actually measures. A read now counts as
// SCOPED when an accessor appears in its own argument or in the 40 lines above
// it (where a `where` const is usually built), and the classifier FAILS SAFE —
// when it cannot tell, the read counts as unscoped.
//
// Ledger: 81 at accessor-landing → 78 once PERSONAL_SCOPE was declared → 60
// after tranche 1a (by-id API routes) → 22 after tranche 1b finished
// transcribe_visits. What remains is note_templates and transcribe_md_patients:
// tranches 2 and 3.
//
// ⚠️ FOUR CLASSES OF READ, DISTINGUISHED EXPLICITLY.
//   REQUEST — a signed-in user asking. Must be practice-scoped. Counted here.
//   SYSTEM  — the worker on a queued job, a retention sweep. No acting user, so
//             no practice to scope BY; forcing one would mean INVENTING a
//             tenant, which is worse than an honest unscoped read.
//   PERSONAL — a read whose SUBJECT is the user (their own data export). The
//             `userId` filter there is correct and must never be widened.
//   SCOPED  — already carries the accessor's predicate. Migrated; not counted.
// System paths are listed by name below. The list is short, and anything not on
// it counts as a request read — the safe default, because a forgotten request
// read is a cross-tenant leak while a mislabelled system read is only noise.
// ============================================================================

import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

import { describe, it, expect } from 'vitest';

import type { PracticeId } from '../practice-scope';

/** Prisma models holding clinical data. */
const CLINICAL_MODELS = ['transcribeVisit', 'transcribeMdPatient', 'noteTemplate'] as const;

const READ_METHODS =
  '(findMany|findFirst|findUnique|findUniqueOrThrow|count|aggregate|groupBy)';

/**
 * Paths that run WITHOUT an acting user. Listed by name, deliberately:
 * a prefix like `src/lib/` would quietly absorb request code as the tree grows.
 */
const SYSTEM_PATHS = ['src/worker/', 'src/lib/template-twin/', 'src/worker.ts'] as const;

/**
 * ⚠️ THE SYSTEM-CONTEXT ALLOWLIST, CHECKED IN BY FILE AND COUNT.
 *
 * A path prefix alone would let the system side grow silently: drop a new file
 * under `src/worker/`, do an unscoped clinical read, and the guard would wave it
 * through as "system". That is drift with a permission slip.
 *
 * So growth HERE is a declared decision too. Adding a system read means adding
 * its line below, which puts it in a diff where someone can ask whether it is
 * genuinely user-less. Measured 2026-08-06.
 */
const SYSTEM_ALLOWLIST: Record<string, number> = {
  'src/lib/template-twin/create-draft.ts': 1,
  'src/lib/template-twin/fill-engine.ts': 1,
  'src/lib/template-twin/native-export.ts': 1,
  'src/lib/template-twin/synthetic-test.ts': 1,
  'src/lib/template-twin/workspace-read.ts': 1,
  'src/worker.ts': 5,
  'src/worker/cleanup/minio-orphans.ts': 1,
  'src/worker/cleanup/retention-sweep.ts': 1,
  'src/worker/cleanup/stale-visits.ts': 2,
  'src/worker/cleanup/stuck-visit-watchdog.ts': 1,
  'src/worker/note-templates/resolve-active-template.ts': 1,
  'src/worker/resume-state.ts': 1,
  'src/worker/template-twin-note-generator.ts': 1,
};

/**
 * ⚠️ THE RATCHET. Lower this as sites migrate; never raise it.
 *
 * Raising it is always the wrong fix: if this test fails because the number went
 * UP, a new clinical read was added without practice scoping, and the fix is to
 * scope it — not to move the line. Measured 2026-08-06.
 */
const MAX_UNSCOPED_REQUEST_READS = 10;

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const p = join(dir, entry);
    if (statSync(p).isDirectory()) {
      if (entry === '__tests__' || entry === 'node_modules') continue;
      out.push(...walk(p));
    } else if (p.endsWith('.ts') || p.endsWith('.tsx')) {
      out.push(p);
    }
  }
  return out;
}

const isSystem = (p: string) => SYSTEM_PATHS.some((s) => p.startsWith(s));

/**
 * ⚠️ MATCHES THAT LIVE IN COMMENTS, DECLARED BY FILE AND COUNT.
 *
 * A commented-out read is not a read, and the scanner has to know that — but a
 * scanner that silently reclassifies things is worse than one that miscounts,
 * because the dangerous direction is invisible: if `stripComments` ever mistakes
 * real CODE for a comment, a genuine unscoped read disappears from the count and
 * the gate reports green about a leak.
 *
 * So every comment-resident match is declared here and checked with `toEqual`.
 * A new one fails until someone writes it down; a misclassification of real code
 * fails the same way. Measured 2026-08-06.
 */
const COMMENT_MATCHES: Record<string, number> = {
  // The accessor's own usage example, which shows the shape it replaces.
  'src/lib/practice-scope.ts': 1,
};

/**
 * Blanks comments, preserving length and newlines so offsets and line numbers
 * still map to the original source.
 *
 * ⚠️ WHY THIS EXISTS AT ALL. The first version of this guard matched raw source,
 * so the usage example inside `practice-scope.ts`'s own doc comment counted as an
 * unscoped read. That is one unit of free headroom — a real unscoped read could
 * be added and stay under the ceiling — and, worse, it put a floor of 1 under a
 * ratchet whose whole purpose is to reach 0 and become a wall.
 *
 * String states are tracked so a `//` inside a URL literal is not read as the
 * start of a comment.
 */
function stripComments(src: string): string {
  const out = src.split('');
  type Mode = 'code' | 'line' | 'block' | 'sq' | 'dq' | 'tpl';
  let mode: Mode = 'code';
  let i = 0;
  while (i < src.length) {
    const c = src[i];
    const d = src[i + 1];
    if (mode === 'code') {
      if (c === '/' && d === '/') {
        mode = 'line';
        out[i] = ' ';
        out[i + 1] = ' ';
        i += 2;
        continue;
      }
      if (c === '/' && d === '*') {
        mode = 'block';
        out[i] = ' ';
        out[i + 1] = ' ';
        i += 2;
        continue;
      }
      if (c === "'") mode = 'sq';
      else if (c === '"') mode = 'dq';
      else if (c === '`') mode = 'tpl';
      i += 1;
      continue;
    }
    if (mode === 'line') {
      if (c === '\n') mode = 'code';
      else out[i] = ' ';
      i += 1;
      continue;
    }
    if (mode === 'block') {
      if (c === '*' && d === '/') {
        mode = 'code';
        out[i] = ' ';
        out[i + 1] = ' ';
        i += 2;
        continue;
      }
      if (c !== '\n') out[i] = ' ';
      i += 1;
      continue;
    }
    // Inside a string literal.
    if (c === '\\') {
      i += 2;
      continue;
    }
    if ((mode === 'sq' && c === "'") || (mode === 'dq' && c === '"') || (mode === 'tpl' && c === '`'))
      mode = 'code';
    i += 1;
  }
  return out.join('');
}

/**
 * ⚠️ READS THAT ARE CORRECTLY AUTHOR-SCOPED, DECLARED BY FILE AND COUNT.
 *
 * NOT EVERY `userId` IN A `where` IS A TENANCY CHECK. Some reads are genuinely
 * about the PERSON: a personal data export, the visit count that goes in an
 * account-deletion audit row. Migrating those to `practiceId` would be a leak in
 * the opposite direction — a colleague's patients inside somebody's personal
 * export — so they must never be swept up by a mechanical migration.
 *
 * They are declared here rather than left to the ratchet, because otherwise the
 * only way to reach zero would be to break them. Measured 2026-08-06.
 */
const PERSONAL_SCOPE: Record<string, number> = {
  // "Export MY data" — subject of the export IS the user.
  'src/app/api/settings/export-data/route.ts': 1,
  // Deletion precondition + the count recorded in the audit row.
  'src/app/api/settings/delete-account/route.ts': 2,
};

/**
 * ⚠️ NOTE TEMPLATES ARE DOCTOR-SCOPED, AND THAT IS THE RULING — NOT AN OMISSION.
 *
 * §4.1b makes reads practice-uniform for the practice's CLINICAL DATA. A note
 * template is not clinical data: it is the doctor's own note FORMAT, authored by
 * them, offered to them at visit creation, managed under "Settings → My Note
 * Format". Widening it would put a colleague's formats in your template picker
 * and list them as yours in Settings — a worse product and a wrong answer.
 *
 * ⚠️ AND THERE IS NO TENANCY HOLE TO CLOSE HERE, which is the load-bearing part.
 * `doctorId = session.user.id` is STRICTLY NARROWER than a practice predicate: a
 * doctor can only ever reach their own rows, so no cross-practice read is
 * reachable. Routing these through `templateScope` would WIDEN them. Every site
 * below was traced to the session before being listed here — none takes a
 * caller-supplied doctor id.
 *
 * `templateScope` stays in the accessor for the day templates become a shared
 * clinic asset. That is a product decision nobody has made, and it is not T5's
 * to make. Measured 2026-08-06.
 */
const DOCTOR_SCOPE: Record<string, number> = {
  'src/actions/certify-pdf-template.ts': 1,
  'src/actions/visits.ts': 1,
  'src/actions/note-template-lifecycle.ts': 4,
  'src/actions/preview-native-document.ts': 1,
  'src/app/settings/page.tsx': 1,
  'src/app/visits/new/page.tsx': 1,
  'src/lib/note-template-persist/read.ts': 1,
  'src/lib/pdf-native/carry-forward.ts': 2,
};

/**
 * ⚠️ THE SYSTEM-DEFAULT TEMPLATE — global BY DESIGN, and the one read here that
 * is deliberately unfiltered. `where: { isSystemDefault: true }` selects the
 * built-in format every practice starts from; scoping it to a practice would
 * mean every practice needs its own copy of a row nobody owns.
 *
 * Listed rather than pattern-matched, because "an unscoped template read is
 * fine when it looks global" is exactly the reasoning that lets a real one
 * through.
 */
const SYSTEM_DEFAULT_READS: Record<string, number> = {
  'src/actions/visits.ts': 1,
};

const ACCESSORS = /\b(visitScope|visitByIdScope|patientScope|templateScope)\s*\(/;

/**
 * True when a read carries a practice predicate from the accessor.
 *
 * ⚠️ IT LOOKS BACKWARDS AS WELL AS INSIDE, because a `where` is often built as a
 * const a few lines above the query. And it FAILS SAFE: when it cannot tell, the
 * read counts as UNSCOPED. A false "unscoped" costs someone a second look; a
 * false "scoped" is a leak the ratchet would report as progress.
 */
function isScoped(code: string, at: number): boolean {
  const argEnd = code.indexOf(')', at);
  const own = code.slice(at, argEnd > at ? Math.min(argEnd + 400, code.length) : at + 400);
  if (ACCESSORS.test(own)) return true;
  const before = code.slice(Math.max(0, at - 2000), at).split('\n').slice(-40).join('\n');
  return ACCESSORS.test(before);
}

function clinicalReads(): {
  request: string[];
  system: string[];
  commented: string[];
  scoped: string[];
  personal: string[];
  doctor: string[];
  systemDefault: string[];
} {
  const re = new RegExp(`prisma\\.(${CLINICAL_MODELS.join('|')})\\.${READ_METHODS}\\(`, 'g');
  const request: string[] = [];
  const system: string[] = [];
  const commented: string[] = [];
  const scoped: string[] = [];
  const personal: string[] = [];
  const doctor: string[] = [];
  const systemDefault: string[] = [];
  for (const file of walk('src')) {
    const src = readFileSync(file, 'utf8');
    const code = stripComments(src);
    for (const m of src.matchAll(re)) {
      const line = src.slice(0, m.index).split('\n').length;
      const at = `${file}:${line}`;
      // The match survives in the blanked copy only if it was real code.
      if (code.slice(m.index, m.index! + m[0].length) !== m[0]) commented.push(at);
      else if (isSystem(file)) system.push(at);
      else if (m[1] === 'noteTemplate' && isSystemDefaultRead(code, m.index! + m[0].length))
        systemDefault.push(at);
      else if (m[1] === 'noteTemplate' && file in DOCTOR_SCOPE) doctor.push(at);
      else if (m[1] !== 'noteTemplate' && file in PERSONAL_SCOPE) personal.push(at);
      else if (isScoped(code, m.index! + m[0].length)) scoped.push(at);
      else request.push(at);
    }
  }
  return { request, system, commented, scoped, personal, doctor, systemDefault };
}

/** True when a noteTemplate read selects the global built-in format. */
function isSystemDefaultRead(code: string, at: number): boolean {
  const end = code.indexOf(')', at);
  return /isSystemDefault:\s*true/.test(code.slice(at, end > at ? end + 200 : at + 200));
}

function byFile(hits: string[]): Record<string, number> {
  const out: Record<string, number> = {};
  for (const h of hits) {
    const file = h.slice(0, h.lastIndexOf(':'));
    out[file] = (out[file] ?? 0) + 1;
  }
  return out;
}

describe('T5 — clinical reads go through the practice-scoped accessor', () => {
  it('NON-VACUITY — the scanner finds reads at all', () => {
    // Without this, a broken regex or a moved source root makes every assertion
    // below trivially true and the gate reports green about nothing. This has
    // happened to a sweep in this repo twice: once returning 0 sites from shell
    // escaping, once flagging 3 false positives from a too-narrow window.
    // ⚠️ COUNTS EVERY BUCKET, and it did not always. The first version summed
    // request + system only, so as adoption moved reads into `scoped` the total
    // fell and this test went red for the SUCCESS of the migration — a check
    // that fails when the thing it guards is working is a check nobody keeps.
    const { request, system, scoped, personal, commented, doctor, systemDefault } =
      clinicalReads();
    const total =
      request.length +
      system.length +
      scoped.length +
      personal.length +
      commented.length +
      doctor.length +
      systemDefault.length;
    expect(total, 'the scanner found NO clinical reads').toBeGreaterThan(50);
    expect(system.length, 'no system-context reads found — the worker paths moved').toBeGreaterThan(
      0,
    );
  });

  it('⚠️ THE RATCHET — unscoped request-context reads never increase', () => {
    const { request } = clinicalReads();
    expect(
      request.length,
      `Unscoped request-context clinical reads went UP (${request.length} > ` +
        `${MAX_UNSCOPED_REQUEST_READS}). A new clinical read was added without ` +
        `practice scoping. Scope it through src/lib/practice-scope.ts — do NOT ` +
        `raise this number.`,
    ).toBeLessThanOrEqual(MAX_UNSCOPED_REQUEST_READS);
  });

  it('the accessor exists and returns a PREDICATE, not a wrapped query', () => {
    const src = readFileSync('src/lib/practice-scope.ts', 'utf8');
    for (const fn of ['visitScope', 'patientScope', 'templateScope', 'visitByIdScope']) {
      expect(src, `practice-scope.ts lost ${fn}`).toContain(`export function ${fn}`);
    }
    // ⚠️ It must scope visits on the COLUMN, not through the author's practice.
    // `{ user: { practiceId } }` answers a different question — whose practice
    // the AUTHOR belongs to — and gives the wrong answer for a locum's note.
    expect(src).toMatch(/export function visitScope[\s\S]{0,200}return \{ practiceId:/);
    expect(src, 'visitScope routes through the author — that is the wrong tenant').not.toMatch(
      /export function visitScope[\s\S]{0,240}user: \{ practiceId/,
    );
  });

  it('⚠️ an empty practiceId THROWS rather than matching every tenant', async () => {
    // Prisma drops a `where` key whose value is undefined, so `{ practiceId:
    // undefined }` is `{}` — every tenant, silently. This is the one failure in
    // this file that produces no error and a WIDER result set, so it gets a
    // behaviour test rather than a source-grep.
    //
    // ⚠️ THE CASTS BELOW ARE THE POINT, NOT A CONCESSION. `PracticeId` now makes
    // the empty string a compile error, so the only way to reach the runtime
    // guard is to force past the type — which is exactly the case the runtime
    // guard exists for. A brand stops honest callers; it does not stop an
    // `as any`, a JSON-parsed value, or JS calling in from an untyped edge. This
    // test asserts the SECOND line still holds after the first one landed.
    const { visitScope, patientScope, templateScope, visitByIdScope, asPracticeId } = await import(
      '../practice-scope'
    );
    const forced = '' as unknown as PracticeId;
    for (const [name, fn] of [
      ['visitScope', () => visitScope(forced)],
      ['patientScope', () => patientScope(forced)],
      ['templateScope', () => templateScope(forced)],
      ['visitByIdScope', () => visitByIdScope('v1', forced)],
    ] as const) {
      expect(fn, `${name} accepted an empty practiceId`).toThrow(/empty practiceId/);
      // `undefined` forced past the type, which is how it would actually arrive.
      expect(
        () => (fn as unknown as (p: unknown) => unknown)(undefined),
        `${name} accepted undefined`,
      ).toThrow();
    }

    // The blessed constructor validates too, so a brand always carries a real id.
    expect(() => asPracticeId(''), 'asPracticeId minted a brand from nothing').toThrow(
      /empty practiceId/,
    );

    // POSITIVE CONTROL — a real id still produces the predicate.
    const p1 = asPracticeId('prac_1');
    expect(visitScope(p1)).toEqual({ practiceId: 'prac_1' });
    expect(visitByIdScope('v1', p1)).toEqual({ id: 'v1', practiceId: 'prac_1' });
  });

  it('⚠️ the BRAND is not cast away outside the session boundary', () => {
    // ⚠️ THIS REPLACES THE ARGUMENT-SHAPE GUARD, which is retired with this
    // commit. That guard read every accessor call and required the practice
    // argument to be spelled like a practice. `PracticeId` now does that job
    // properly and at compile time — a source rule that duplicates the type
    // checker is noise, and noise is what gets deleted in a hurry later.
    //
    // What a brand CANNOT see is a cast. `visitByIdScope(id, userId as
    // PracticeId)` compiles, and is precisely the shape someone reaches for when
    // the compiler is in the way. So the residue gets its own narrow rule: the
    // casts live at the session boundary and in this file's own forced-value
    // tests, and nowhere else.
    const ALLOWED = new Set(['src/lib/practice-scope.ts', 'src/lib/auth.ts']);
    const offenders: string[] = [];
    for (const file of walk('src')) {
      if (ALLOWED.has(file)) continue;
      const code = stripComments(readFileSync(file, 'utf8'));
      for (const m of code.matchAll(/as\s+(?:unknown\s+as\s+)?(PracticeId|UserId)\b/g)) {
        // The forced-value cases in this file are the runtime guard's own proof.
        if (file.endsWith('gate-practice-scope.test.ts')) continue;
        offenders.push(`${file}: ${m[0]}`);
      }
    }
    expect(
      offenders,
      'a branded id was cast into existence outside the session boundary — mint ' +
        'it with asPracticeId()/asUserId() at getSession(), or take it as a ' +
        'parameter already branded',
    ).toEqual([]);
  });

  it('the SYSTEM-context allowlist matches reality, file by file', () => {
    // ⚠️ BOTH DIRECTIONS. An UNLISTED system read is undeclared growth wearing a
    // path prefix; a listed file whose count DROPPED means a read moved and the
    // allowlist is now stale, which is how an allowlist becomes a rubber stamp.
    const { system } = clinicalReads();
    expect(
      byFile(system),
      'the system-context read map changed — update SYSTEM_ALLOWLIST deliberately',
    ).toEqual(SYSTEM_ALLOWLIST);
  });

  it('matches living in COMMENTS are declared, not silently dropped', () => {
    // The reclassification this guards is the invisible-failure direction: if
    // stripComments ever mistakes real code for a comment, a genuine unscoped
    // read vanishes from the ratchet and the gate goes green over a leak.
    const { commented } = clinicalReads();
    expect(
      byFile(commented),
      'a clinical read was classified as living in a comment without being declared',
    ).toEqual(COMMENT_MATCHES);
  });

  it('the PERSONAL-scope allowlist matches reality, file by file', () => {
    // These are correctly author-scoped. Declared so the ratchet's road to zero
    // never runs through breaking them.
    const { personal } = clinicalReads();
    expect(byFile(personal), 'the personal-scope read map changed').toEqual(PERSONAL_SCOPE);
  });

  // ⚠️ RETIRED 2026-08-06 — "every accessor call is given a PRACTICE-shaped
  // argument". It lived here for one commit and did real work: it caught
  // `visitByIdScope(… userId)` when nothing else could, because
  // `practiceId: string` and `userId: string` are the same type and tsc was
  // silent through nine such call sites.
  //
  // `PracticeId`/`UserId` now carry that guarantee at compile time, on every
  // call, including ones this regex could never parse. A source rule that
  // duplicates the type checker is noise — and the cost of noise is that the
  // whole file gets skimmed. It is replaced, not simply deleted, by the
  // cast-ban above: the one hole a brand cannot see.

  it('the DOCTOR-scope map matches reality, file by file', () => {
    // Both directions, like the others. An unlisted doctor-scoped template read
    // is undeclared; a listed file whose count dropped means one moved and the
    // ruling above no longer describes the code.
    const { doctor } = clinicalReads();
    expect(byFile(doctor), 'the doctor-scoped template read map changed').toEqual(DOCTOR_SCOPE);
  });

  it('the SYSTEM-DEFAULT template reads are exactly the declared ones', () => {
    const { systemDefault } = clinicalReads();
    expect(
      byFile(systemDefault),
      'an unfiltered template read appeared that claims to be the system default',
    ).toEqual(SYSTEM_DEFAULT_READS);
  });

  it('POSITIVE CONTROL — the scanner SEES a new unscoped read', () => {
    // Proves the ratchet can actually fire. Without this, a regex that matches
    // nothing keeps the count at 0 forever and the gate passes through any
    // amount of new unscoped access.
    const re = new RegExp(`prisma\\.(${CLINICAL_MODELS.join('|')})\\.${READ_METHODS}\\(`, 'g');
    const code = `const v = await prisma.transcribeVisit.findMany({ where: {} });`;
    expect(
      [...stripComments(code).matchAll(re)].length,
      'the scanner does not match a plainly unscoped clinical read',
    ).toBe(1);
  });

  it('NEGATIVE CONTROL — a COMMENTED read is not counted, but a URL string is not a comment', () => {
    const re = new RegExp(`prisma\\.(${CLINICAL_MODELS.join('|')})\\.${READ_METHODS}\\(`, 'g');

    const commented = `// const v = await prisma.transcribeVisit.findMany({ where: {} });\n`;
    expect(
      [...stripComments(commented).matchAll(re)].length,
      'a commented-out read still counts — the ratchet can never reach zero',
    ).toBe(0);

    const block = `/**\n * const v = await prisma.transcribeVisit.findMany({});\n */\n`;
    expect([...stripComments(block).matchAll(re)].length, 'a doc-comment read still counts').toBe(0);

    // ⚠️ And the stripper must not be over-eager: `//` inside a string is not a
    // comment, and an over-eager stripper hides real reads — the direction that
    // fails silently.
    const url = `const u = 'https://x/y'; await prisma.transcribeVisit.findMany({});`;
    expect(
      [...stripComments(url).matchAll(re)].length,
      'a read after a URL literal was swallowed — the stripper treats // in a string as a comment',
    ).toBe(1);
  });
});
