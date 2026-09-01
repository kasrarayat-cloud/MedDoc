// ============================================================================
// THE npm-audit HIGH/CRITICAL GATE, WITH SCOPED, DEBT-BEARING EXCEPTIONS.
// ----------------------------------------------------------------------------
//   node scripts/audit-gate.mjs            # runs npm audit itself
//   node scripts/audit-gate.mjs --stdin    # reads `npm audit --json` on stdin
//
//   0 = PASS   1 = a HIGH/CRITICAL is not excepted, or an exception is invalid
//   2 = CANNOT TELL — fail-closed
//
// ⚠️ WHY THIS REPLACED A BARE `npm audit`. Ruling #163 B(ii). `npm audit` is
// all-or-nothing: one advisory on a build-time CLI's bundled driver for a
// database engine this product does not use held every merge on the repo,
// including a security fix. The honest disposition is neither "override the
// gate" nor "take a Prisma major on the clinical database at 2am" — it is a
// NAMED exception carrying its own retirement condition.
//
// ⚠️ THREE PROPERTIES MAKE THIS AN EXCEPTION RATHER THAN A HOLE, and the gate
// enforces all three rather than trusting the file:
//
//   1. KEYED BY ADVISORY ID. An exception for a PACKAGE would absorb the next
//      advisory published against it — the one nobody has read.
//   2. EVERY EXCEPTION CARRIES A RETIREMENT CONDITION. An entry without
//      `retires_when` and `justification` FAILS the gate. "For now" never
//      becomes false on its own.
//   3. A STALE EXCEPTION FAILS. An entry matching no live advisory is a
//      justification nobody has re-read, sitting where the next reader will
//      take it for a current decision.
//
// ⚠️ FAIL-CLOSED ON CANNOT-TELL, like every other instrument here: unparseable
// audit output, a missing exceptions file, or a report with no `vulnerabilities`
// key all exit 2. A broken audit and a clean tree must never look the same.
// ============================================================================
import { readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';

const EXCEPTIONS_PATH = new URL('./audit-exceptions.json', import.meta.url);

/**
 * The decision, as a pure function so it can be tested without a network or a
 * lockfile. Returns { code, lines } — never throws, never prints.
 */
export function judgeAudit(report, exceptionsFile) {
  const lines = [];
  const vulns = report && typeof report === 'object' ? report.vulnerabilities : null;
  if (!vulns || typeof vulns !== 'object') {
    return { code: 2, lines: ['CANNOT TELL: audit report has no `vulnerabilities` object.'] };
  }

  const raw = Array.isArray(exceptionsFile?.exceptions) ? exceptionsFile.exceptions : null;
  if (!raw) {
    return { code: 2, lines: ['CANNOT TELL: exceptions file has no `exceptions` array.'] };
  }

  // An exception missing its justification or its retirement condition is not an
  // exception, it is an override wearing one's clothes.
  const malformed = raw.filter(
    (e) => !e?.id || !e?.justification?.trim() || !e?.retires_when?.trim(),
  );
  if (malformed.length > 0) {
    for (const e of malformed) {
      lines.push(`INVALID EXCEPTION ${e?.id ?? '(no id)'}: needs both justification and retires_when.`);
    }
    return { code: 1, lines };
  }
  const excepted = new Map(raw.map((e) => [e.id, e]));

  // Collect every distinct HIGH/CRITICAL advisory, by its own id.
  //
  // ⚠️ `via` IS TWO SHAPES AND ONLY ONE CARRIES AN ID. npm gives an OBJECT for
  // the package that actually has the advisory and a STRING — the name of
  // another entry — for anything vulnerable only through it. `prisma` is HIGH
  // in this repo purely by a string edge to `mysql2`. Reading object entries
  // alone therefore identifies the right ADVISORY, but a package whose chain
  // this walk cannot resolve would contribute NO id and silently vanish from
  // the blocking set — a high with nothing to except and nothing to report.
  // So the chain is followed, and an unattributable high fails CLOSED.
  const found = new Map();
  const unattributable = [];
  const idsOf = (name, seen = new Set()) => {
    if (seen.has(name)) return [];
    seen.add(name);
    const info = vulns[name];
    const ids = [];
    for (const via of info?.via ?? []) {
      if (typeof via === 'string') {
        ids.push(...idsOf(via, seen));
        continue;
      }
      if (!via?.url) continue;
      // ⚠️ THE ADVISORY'S OWN SEVERITY DECIDES, NOT THE PACKAGE'S. A package's
      // severity is the MAX over its chains, so walking a high package reaches
      // its moderate advisories too — and the first version of this walk
      // reported a MODERATE valibot issue as BLOCKING. The gate's threshold is
      // high/critical; anything softer is not this gate's business.
      if (via.severity !== 'high' && via.severity !== 'critical') continue;
      const id = String(via.url).split('/').pop();
      ids.push(id);
      if (!found.has(id)) {
        found.set(id, {
          id,
          pkg: via.name ?? name,
          title: via.title ?? '',
          severity: via.severity,
        });
      }
    }
    return ids;
  };
  for (const [pkg, info] of Object.entries(vulns)) {
    if (info?.severity !== 'high' && info?.severity !== 'critical') continue;
    if (idsOf(pkg).length === 0) unattributable.push(pkg);
  }
  if (unattributable.length > 0) {
    return {
      code: 2,
      lines: unattributable.map(
        (pkg) =>
          `CANNOT TELL: ${pkg} is ${vulns[pkg].severity} but no advisory id could be ` +
          `attributed to it. Refusing rather than passing an advisory nobody can name.`,
      ),
    };
  }

  const blocking = [...found.values()].filter((a) => !excepted.has(a.id));
  const used = [...found.keys()].filter((id) => excepted.has(id));
  const stale = [...excepted.keys()].filter((id) => !found.has(id));

  for (const a of blocking) {
    lines.push(`BLOCKING ${a.severity.toUpperCase()} ${a.id} (${a.pkg}): ${a.title}`);
  }
  for (const id of used) {
    const e = excepted.get(id);
    lines.push(`excepted ${id} (${e.package}) — retires when: ${e.retires_when.split('.')[0]}.`);
  }
  for (const id of stale) {
    lines.push(
      `STALE EXCEPTION ${id}: no live advisory matches it. Delete the entry — a ` +
        `justification nobody re-reads is worse than no entry at all.`,
    );
  }

  if (blocking.length > 0 || stale.length > 0) return { code: 1, lines };
  lines.push(`PASS: ${found.size} high/critical advisories, ${used.length} excepted, 0 blocking.`);
  return { code: 0, lines };
}

function main() {
  let exceptionsFile;
  try {
    exceptionsFile = JSON.parse(readFileSync(EXCEPTIONS_PATH, 'utf8'));
  } catch (error) {
    console.error(`🔴 audit-gate: CANNOT TELL — cannot read exceptions file (${error.message}).`);
    process.exit(2);
  }

  let raw;
  if (process.argv.includes('--stdin')) {
    raw = readFileSync(0, 'utf8');
  } else {
    const workspaces = process.argv
      .filter((a) => a.startsWith('--workspace='))
      .map((a) => a.slice('--workspace='.length));
    const args = ['audit', '--json', '--audit-level=high', '--omit=dev', '--include-workspace-root'];
    for (const w of workspaces) args.push('--workspace', w);
    try {
      // ⚠️ npm audit EXITS NON-ZERO when it finds anything, so a throw here is
      // the NORMAL path and its stdout is the report. Only an empty stdout is a
      // real failure — the distinction a bare `set -e` cannot make.
      raw = execFileSync('npm', args, { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
    } catch (error) {
      raw = error.stdout ?? '';
    }
  }

  let report;
  try {
    report = JSON.parse(raw);
  } catch {
    console.error('🔴 audit-gate: CANNOT TELL — npm audit produced no parseable JSON.');
    process.exit(2);
  }

  const { code, lines } = judgeAudit(report, exceptionsFile);
  for (const line of lines) console.log(`   ${line}`);
  console.log(code === 0 ? '🟢 audit-gate: PASS' : code === 1 ? '🔴 audit-gate: BLOCKED' : '🔴 audit-gate: CANNOT TELL');
  process.exit(code);
}

if (import.meta.url === `file://${process.argv[1]}`) main();
