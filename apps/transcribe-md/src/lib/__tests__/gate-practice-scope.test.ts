// ============================================================================
// T5 — the guard that keeps the practice-scoped accessor the ONLY way in.
// ----------------------------------------------------------------------------
// ⚠️ THIS IS A WALL. IT WAS A RATCHET, AND IT REACHED ZERO ON 2026-08-06.
//
// It landed as a ratchet on purpose: 81 request-context clinical reads predated
// the accessor, and a guard demanding zero on day one would have been red for
// the whole migration. A permanently-red gate is one everyone learns to ignore,
// which is worse than no gate because it looks like coverage.
//
// The ledger, each step lowered in the SAME COMMIT as the code that earned it,
// so the number in the guard and the number in the codebase never disagreed:
//
//     81  the accessor lands (the guard before the adoption, deliberately)
//     78  PERSONAL_SCOPE declared — reads whose SUBJECT is the user
//     60  tranche 1a — the by-id API routes, no authorization change
//     22  tranche 1b — transcribe_visits finished, reads widened to the practice
//     10  tranche 2  — note_templates RULED doctor-scoped, not migrated
//      0  tranche 3  — transcribe_md_patients
//
// ⚠️ WHAT THE ZERO MEANS, STATED NARROWLY. Every request-context read of a
// clinical model either carries the accessor's predicate or sits in a bucket
// that is declared BY FILE AND COUNT and checked in both directions. It does
// NOT mean the app is free of tenancy bugs; it means there is no longer a read
// that nobody has looked at.
//
// ⚠️ AND THE RATCHET IS NOT DELETED, WHICH MATTERS. `MAX_UNSCOPED_REQUEST_READS`
// stays, at 0. The assertion is unchanged — `toBeLessThanOrEqual` — so the same
// line that used to say "do not grow" now says "do not exist". Rewriting it into
// a different shape at the moment it reached zero would have thrown away the one
// thing that makes the zero trustworthy: it is the SAME measurement that has
// been running, lowered, since the first commit.
//
// ⚠️ WHY THE GUARD LANDED BEFORE THE ADOPTION. If 81 call sites were migrated
// first and the guard added last, its first run would have been a bug report
// against work already declared done, and every missed site would surface one CI
// cycle at a time. That is what T3 and T4 paid five cycles for.
//
// ⚠️ THE COUNT IS OF **UNSCOPED** READS, WHICH IS NOT WHAT IT FIRST MEASURED.
// The first version counted every `prisma.<clinical>.<read>(` call in request
// context — so routing a call through the accessor left the number UNCHANGED and
// adoption could never lower it. The name said "unscoped"; the implementation
// said "all". A read counts as SCOPED when an accessor appears in its own
// argument or in the 40 lines above it (where a `where` const is usually built),
// and the classifier FAILS SAFE — when it cannot tell, the read counts as
// unscoped. A false "unscoped" costs a second look; a false "scoped" is a leak
// reported as progress.
//
// ⚠️ SEVEN CLASSES OF READ, EVERY ONE DECLARED.
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

/**
 * Prisma models holding clinical data.
 *
 * ⚠️ `doctorEditPattern` IS ON THIS LIST BY NAME, and T5's own spec is why:
 * "the guard must also catch `doctor_edit_patterns` — the table a source grep is
 * most likely to miss and the one that LEAKS WHOLE NOTES". It stores
 * `originalSoap` and `editedSoap` as full text, so an unscoped read of it is a
 * larger disclosure than an unscoped read of a visit row.
 *
 * It was missing from the first three tranches. Nothing surfaced it — the reads
 * happened to be correct, so no test failed and no sweep complained. That is
 * precisely the shape the spec warned about: a table nobody thinks of is not a
 * table nobody reads.
 */
const CLINICAL_MODELS = [
  'transcribeVisit',
  'transcribeMdPatient',
  'noteTemplate',
  'doctorEditPattern',
] as const;

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
  // 1 → 2 on 2026-08-14, RC-2 (#106(b)): the ATTACH-TARGET lookup.
  // ⚠️ DECLARED, AND IT IS THE OPPOSITE CLASS FROM THE OTHER READ IN THIS
  // FILE. The existing one is the system-default template — genuinely
  // tenant-less, global by design. This one is the reverse: it reads the
  // note template the caller is asking to attach a compiled twin version
  // to, and it is bounded by `templateScope(asPracticeId(actor.practiceId))`
  // — the accessor, not a hand-written predicate — precisely so a compiled
  // version can never be bound to another practice's row.
  //
  // It sits in the SYSTEM bucket only because `isSystem` classifies by PATH
  // (`src/lib/template-twin/`) before it looks at scoping, so no amount of
  // correct scoping moves it. That is the classifier being conservative in
  // the safe direction — a false 'system' costs a declared line, a false
  // 'scoped' would cost a leak — so the line is written rather than the
  // classifier loosened.
  'src/lib/template-twin/create-draft.ts': 2,
  // ⚠️ NEW 2026-08-24, F24-S5. `listVisitFormControls` reads the note template
  // to discover which enumerated controls a visit's certified twin offers.
  //
  // ⚠️ AND THIS COMMENT DELIBERATELY DOES NOT CLAIM THE GUARD CAUGHT AN
  // UNSCOPED READ. The previous entry written on this file said exactly that
  // and then, correctly, explained that `isSystem` classifies by PATH before it
  // looks at scoping — two statements that cannot both be true, in one comment.
  // What is true: this read IS practice-bound, the bound is DERIVED in the
  // query (`templateTwinCompiledVersion: { practiceId }`) rather than threaded
  // as a value that could drift, and it lands in the system bucket purely
  // because the whole `template-twin/` directory is bucketed before scoping is
  // considered.
  //
  // ⚠️ DECLARING A FILE HERE CONSUMES THE ONLY SIGNAL THAT EVER FIRED FOR IT —
  // after this line, the practice bound could be deleted with this gate green.
  // So the bound has its own assertion below ("the form-control lookup is
  // PRACTICE-bound"), which is not a count and does not move when the allowlist
  // does.
  'src/lib/template-twin/editable-controls.ts': 1,
  // ⚠️ 1 -> 2 on 2026-08-21, DECLARED. The second is the post-signature
  // re-check added with the sign-freeze: the persist re-reads the visit's
  // status immediately before writing and REFUSES to land a manifest on a
  // SIGNED visit, so an orphaned fill whose wait was abandoned cannot land
  // after the signature.
  //
  // It IS practice-scoped — `visitByIdScope(id, asPracticeId(input.practiceId))`
  // — and the classifier still counts it, exactly as the note above predicts:
  // the whole `template-twin/` directory is bucketed as system before scoping
  // is considered. A declared line is the cost of the conservative direction.
  'src/lib/template-twin/fill-engine.ts': 2,
  // ⚠️ 1 -> 2 on 2026-08-21, DECLARED. The second is the FROZEN-POINTER read
  // added by ruling 2(b): a SIGNED record resolves its document by the id the
  // signature stamped, never by lookup, so a manifest landing afterwards is
  // unreachable.
  //
  // The read IS practice-scoped — `{ id, practiceId, deletedAt: null }`, inline,
  // matching this file's own manifest query. I briefly reverted this line on the
  // assumption the count was driven by an `asPracticeId` mint; it is not. The
  // classifier buckets the whole `template-twin/` directory as system BEFORE it
  // looks at scoping, exactly as the note above says, so no amount of correct
  // scoping moves it. The line is written rather than the classifier loosened.
  'src/lib/template-twin/native-export.ts': 2,
  'src/lib/template-twin/synthetic-test.ts': 1,
  'src/lib/template-twin/workspace-read.ts': 1,
  // 5 → 6 on 2026-08-13, RC-3 (#106(c)): the applicable-active-template probe.
  // ⚠️ DELIBERATE, and it is the SAME CLASS as the read directly below it —
  // `resolve-active-template.ts` reads `note_templates` doctor-scoped from the
  // worker, which has no request and therefore no signed-in practice to bound
  // it. The new probe asks the same question about the same rows, one layer up:
  // "does this doctor have an activated format that should have applied to this
  // visit?" It is scoped by `doctorId` — strictly narrower than a practice —
  // and it reads nothing a doctor could not already see in Settings.
  'src/worker.ts': 6,
  'src/worker/cleanup/minio-orphans.ts': 1,
  'src/worker/cleanup/retention-sweep.ts': 1,
  'src/worker/cleanup/stale-visits.ts': 2,
  'src/worker/cleanup/stuck-visit-watchdog.ts': 1,
  'src/worker/note-templates/resolve-active-template.ts': 1,
  'src/worker/resume-state.ts': 1,
  'src/worker/template-twin-note-generator.ts': 1,
};

/**
 * ⚠️ ZERO. THIS IS NOW A WALL — reached 2026-08-06, tranche 3.
 *
 * Raising it is always the wrong fix, and at zero it is not even a judgement
 * call: if this fails, a clinical read was added that no signed-in user's
 * practice bounds. Scope it through `src/lib/practice-scope.ts`, or declare it
 * in the bucket that genuinely describes it — SYSTEM, PERSONAL, DOCTOR or
 * SYSTEM_DEFAULT — where somebody can disagree with you in the diff.
 */
const MAX_UNSCOPED_REQUEST_READS = 0;

/**
 * ⚠️ WRITES — ADDED 2026-08-06, AND THE REASON IS A GAP IN THIS FILE'S OWN COVER.
 *
 * SPEC §1.4 says "ONE practice-scoped data accessor. **Every read and write** of
 * a clinical table goes through it." This guard watched READS ONLY through all
 * three T5 tranches, so the ratchet reached zero over half the surface the spec
 * named. The gate passed; it did not cover what was asked.
 *
 * That is the second instance of the same class in one day — after
 * `doctor_edit_patterns` — and both were found by re-reading the criteria rather
 * than by any check. The lesson is banked in AGENTS.md.
 *
 * ⚠️ THIS IS NOW A WALL. IT REACHED ZERO ON 2026-08-07.
 *
 * Ledger, each step lowered in the SAME COMMIT as the code that earned it:
 *
 *     25  T5-W opens — the gap SPEC §1.4 named and the read guard never watched
 *     12  tranche 1a — 13 mechanical update→updateMany, via `scopedUpdate`
 *      9  the classifier LEARNS doctor-scope as a sanctioned narrower scope
 *      6  the 3 return-row sites take transactional re-reads
 *      0  the optimistic-concurrency sites + the last two template writes
 *
 * ⚠️ THE ZERO IS GENUINE, NOT ZERO-WITH-ASTERISKS. There is no carried-exception
 * bucket holding the residue. Doctor-scoped writes count as SCOPED because
 * `doctorId` is strictly narrower than a practice predicate (GATE 0.3) — a
 * ruling about what the scope MEANS, not a footnote excusing what it misses.
 * `userId` is explicitly NOT accepted, with a control proving it.
 *
 * ⚠️ NO LEAK WAS EVER OPEN, AND SAYING SO PRECISELY MATTERS. Every one of these writes
 * is reached only AFTER a practice-scoped read in the same handler, so an
 * out-of-practice caller is already refused before the write is attempted. What
 * they lack is a predicate of their OWN — the "borrowed authorisation" shape T5
 * itself argued against, one refactor away from being wrong.
 *
 * Ledger: 25 at T5-W's start → 12 after tranche 1a (13 mechanical
 * update→updateMany conversions) → 9 once the classifier LEARNED doctor-scope
 * as a sanctioned narrower scope (3 sites: carry-forward ×2, the
 * note-template-lifecycle deleteMany) → 6 after the three return-row sites
 * took transactional re-reads.
 *
 * It BEGAN as a ratchet, exactly as the read side did. 25 was the measured
 * count across ALL FOUR clinical models, after T6 scoped the two `rescore-em`
 * updateManys that had no practice predicate at all. A visits-only count is 19;
 * this guard watches the same model list the read side does. Lower it; never
 * raise it.
 */
const WRITE_METHODS = '(update|updateMany|delete|deleteMany|upsert)';
const MAX_UNSCOPED_REQUEST_WRITES = 0;

/** Extracts the balanced argument of a call whose `(` is at `open`. */
function callArg(code: string, open: number): string {
  let depth = 0;
  for (let j = open; j < Math.min(code.length, open + 8000); j += 1) {
    if (code[j] === '(') depth += 1;
    else if (code[j] === ')') {
      depth -= 1;
      if (depth === 0) return code.slice(open + 1, j);
    }
  }
  return code.slice(open + 1, open + 8000);
}

/**
 * Request-context clinical WRITES that carry no practice predicate.
 *
 * ⚠️ IT READS THE WHOLE CALL, NOT A FIXED WINDOW. The read-side classifier uses
 * a 400-character look-ahead, and that window produced a FALSE ZERO during T6:
 * a conjunct was pushed out of range by a comment, and the sweep reported the
 * site as clean while the code still had it. A balanced-paren scan cannot drift
 * that way.
 */
/**
 * ⚠️ DOCTOR SCOPE IS A SANCTIONED SCOPE, NOT AN EXCEPTION — ruled 2026-08-07.
 *
 * GATE 0.3 / SPEC §4.3 rule `note_templates` PER-DOCTOR in TEAMS v1. A
 * `doctorId` predicate is **strictly narrower** than a practice predicate: a
 * doctor can only ever reach their own rows, so a doctor-scoped write cannot
 * cross a practice boundary. Scoping those by practice would WIDEN them.
 *
 * So the classifier RECOGNISES it as scoped rather than carrying it as a
 * declared exception. This matters for what the wall's zero MEANS: the close
 * condition is **zero unscoped clinical writes**, with doctor-scope counted as
 * scoped — never zero-with-asterisks, where a footnote quietly holds the
 * residue. A zero that needs a caveat is not a wall.
 *
 * ⚠️ AND IT IS DELIBERATELY NARROW. Only a literal `doctorId` conjunct counts.
 * `userId` does NOT — that is ownership wearing tenancy's clothes, the exact
 * confusion T5 existed to retire, and it isolates tenants today only because
 * every practice has one member.
 *
 * Reference cases: `pdf-native/carry-forward.ts` ×2 — `markPendingPreview` and
 * the certification carry-forward, both `{ id, doctorId }`.
 */
const DOCTOR_SCOPED_WRITE = /\bdoctorId\b/;

function clinicalWrites(): string[] {
  const re = new RegExp(`prisma\\.(${CLINICAL_MODELS.join('|')})\\.${WRITE_METHODS}\\(`, 'g');
  const out: string[] = [];
  for (const file of walk('src')) {
    if (isSystem(file)) continue;
    const src = readFileSync(file, 'utf8');
    const code = stripComments(src);
    for (const m of code.matchAll(re)) {
      const body = callArg(code, m.index! + m[0].length - 1);
      if (ACCESSORS.test(body) || /practiceId/.test(body)) continue;
      if (DOCTOR_SCOPED_WRITE.test(body)) continue; // narrower than practice — see above
      out.push(`${file}:${src.slice(0, m.index).split('\n').length}`);
    }
  }
  return out;
}

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
  // "Export MY data" — subject of the export IS the user. Two reads: the visit
  // list and the doctor's own edit patterns (full note text — see
  // CLINICAL_MODELS). Both correctly keyed on the requesting user.
  'src/app/api/settings/export-data/route.ts': 2,
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

  it('⚠️ the form-control lookup is PRACTICE-bound — an arm that is not a count', () => {
    // F24-S5. `editable-controls.ts` is on SYSTEM_ALLOWLIST, and that line is
    // what makes its read acceptable to the ratchet. The cost of declaring it is
    // that the ratchet stops watching it: delete the practice bound and the
    // allowlist count is UNCHANGED, so every gate stays green over a read that
    // would hand one practice another's form structure.
    //
    // This arm is the replacement signal. It asserts the BOUND, not the COUNT,
    // so it cannot be satisfied by the declaration that silenced the ratchet.
    const src = readFileSync(
      join(__dirname, '..', 'template-twin', 'editable-controls.ts'),
      'utf8',
    );
    const code = src
      .split('\n')
      .filter((l) => !l.trim().startsWith('//') && !l.trim().startsWith('*'))
      .join('\n');
    // The bound is DERIVED in the query, through the compiled version's own
    // practice — not threaded as a separate value that could drift from it.
    expect(
      code,
      'listVisitFormControls lost its practice bound — one practice could be shown another practice’s form structure',
    ).toMatch(/templateTwinCompiledVersion:\s*\{\s*practiceId\s*\}/);
    // And the parameter it binds on must still be required, so a caller cannot
    // simply stop passing one.
    expect(code).toMatch(/practiceId:\s*string/);
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

  it('⚠️ THE WRITE RATCHET — unscoped clinical writes never increase', () => {
    const writes = clinicalWrites();
    expect(
      writes.length,
      `Unscoped request-context clinical WRITES went UP (${writes.length} > ` +
        `${MAX_UNSCOPED_REQUEST_WRITES}). At ZERO this is not a judgement call: ` +
        `a clinical write was added that no signed-in user's practice bounds, ` +
        `and a cross-practice WRITE puts a false entry in another tenant's ` +
        `chart. Scope it through src/lib/practice-scope.ts (or doctorId, which ` +
        `is narrower) — do NOT raise this number.`,
    ).toBeLessThanOrEqual(MAX_UNSCOPED_REQUEST_WRITES);
  });

  it('⚠️ DOCTOR-SCOPE COUNTS AS SCOPED — but `userId` NEVER does', () => {
    // The ruling: doctorId is STRICTLY NARROWER than a practice predicate
    // (GATE 0.3), so a doctor-scoped write cannot cross a practice boundary and
    // the wall's zero counts it as scoped. The danger is the classifier being
    // TOO generous — `userId` is ownership wearing tenancy's clothes, and it
    // isolates tenants today only because every practice has one member.
    expect(DOCTOR_SCOPED_WRITE.test('where: { id, doctorId }')).toBe(true);
    expect(
      DOCTOR_SCOPED_WRITE.test('where: { id, userId }'),
      'userId counted as a scope — that is ownership, not tenancy, and T5 ' +
        'existed to retire the confusion',
    ).toBe(false);
    expect(DOCTOR_SCOPED_WRITE.test('where: { id }')).toBe(false);
  });

  it('POSITIVE CONTROL — the write scanner SEES an unscoped write, and not a scoped one', () => {
    const re = new RegExp(`prisma\\.(${CLINICAL_MODELS.join('|')})\\.${WRITE_METHODS}\\(`, 'g');
    const bare = `await prisma.transcribeVisit.update({ where: { id }, data: {} });`;
    expect([...stripComments(bare).matchAll(re)].length, 'the write scanner matches nothing').toBe(1);
    // …and a scoped write is NOT counted, or the ratchet could never fall.
    const scoped = `await prisma.transcribeVisit.updateMany({ where: visitByIdScope(id, p), data: {} });`;
    const m = [...stripComments(scoped).matchAll(re)][0];
    expect(ACCESSORS.test(callArg(stripComments(scoped), m.index! + m[0].length - 1))).toBe(true);
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
