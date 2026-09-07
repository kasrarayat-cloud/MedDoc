// ============================================================================
// A CENSUS PROVES CONTENT, NOT REACHABILITY.
// ----------------------------------------------------------------------------
// The 2026-08-26 ledger split was proved content-preserving — 0 lines lost in
// both directions, 33,386 == 33,386 — and that proof was TRUE. It was also
// blind to the only question that mattered afterwards: **can the readers still
// reach it?**
//
// They could not. Measured on the split branch before this gate existed:
//
//   grep -c 'OWNER RULING' docs/foundation/RULINGS.md      0   (was 23)
//   grep -c PROVISIONAL    docs/foundation/RULINGS.md      1   (was 47)
//   grep -c rollback       docs/foundation/RELAY.md        0   (was 145)
//   bash scripts/check-retirement-conditions.sh            exit 2, NOT-DUE bucket gone
//   bash scripts/rotate-ledger.sh --apply                  FATAL, every time, moved nothing
//
// Nothing was lost. Everything was unreachable by the route the rules mandate,
// and every one of those zeroes reads as "there are none" rather than "you
// looked in the wrong place".
//
// ⚠️ SO THIS GATE WATCHES THE ROUTES, NOT THE CONTENT. The split's own gate
// (`gate-ledger-rotation`) asserts the census across the file pair. This one
// asserts that the things which READ the ledger can still find what they need.
// The two together are the rule: a split ships WITH its reader sweep.
// ============================================================================
import { execFileSync } from 'node:child_process';
import { readFileSync, readdirSync, existsSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

const REPO = join(__dirname, '../../../../..');
const R = (p: string) => readFileSync(join(REPO, p), 'utf8');

const RELAY = 'docs/foundation/RELAY.md';
const RULINGS = 'docs/foundation/RULINGS.md';
const RELAY_ARCHIVES = 'docs/foundation/relay';
const RULINGS_ARCHIVES = 'docs/foundation/rulings';

const archives = (dir: string) =>
  readdirSync(join(REPO, dir)).filter((f) => f.endsWith('.md') && f !== 'README.md');

// ── 1 · THE MANIFEST IS A CLAIM ABOUT ANOTHER FILE ──────────────────────────
// Two of seven RELAY anchors and one of six RULINGS anchors named headings that
// did not exist, so `--apply` FATAL'd on every ledger every time. A manifest of
// headings rots the moment the file's structure is edited, and nothing else
// notices until somebody runs a rotation.
describe('rotate-ledger: every manifest anchor exists in the file it names', () => {
  const manifest = (file: string): string[] =>
    execFileSync('bash', ['-c', `source <(sed -n '/^rotatable()/,/^}/p' scripts/rotate-ledger.sh); rotatable "${file}"`], {
      cwd: REPO,
      encoding: 'utf8',
    })
      .split('\n')
      .filter(Boolean);

  it.each([[RELAY], [RULINGS]])('%s — all anchors present as real headings', (file) => {
    const anchors = manifest(file);
    // NON-VACUITY: a manifest that returned nothing would pass every arm below.
    expect(anchors.length, `no anchors parsed for ${file}`).toBeGreaterThanOrEqual(4);
    const headings = new Set(
      R(file)
        .split('\n')
        .filter((l) => /^#{1,2} /.test(l)),
    );
    const missing = anchors.filter((a) => !headings.has(a));
    expect(missing, `${file}: manifest names headings the file does not have`).toEqual([]);
  });

  it('positive control — a heading that does not exist is detected as missing', () => {
    const headings = new Set(R(RELAY).split('\n').filter((l) => /^#{1,2} /.test(l)));
    expect(headings.has('## A HEADING THAT DOES NOT EXIST')).toBe(false);
  });
});

// ── 2 · `--apply` MUST REWRITE THE HEAD ─────────────────────────────────────
// `WRITE_HEAD` gates the head rewrite inside the splitter. Without it the
// archives are written, the head is untouched, and the script reports success —
// so the content exists twice and the head is still oversize.
describe('rotate-ledger: --apply passes WRITE_HEAD, and refuses to claim a rotation it did not perform', () => {
  const src = R('scripts/rotate-ledger.sh');

  it('every non-dry-run splitter invocation carries WRITE_HEAD', () => {
    const invocations = src.split('\n').filter((l) => l.includes('python3 "$SPLITTER"'));
    expect(invocations.length, 'no splitter invocations found — the matcher is broken').toBeGreaterThanOrEqual(2);
    for (const line of invocations) {
      if (line.includes('DRY_RUN=1')) continue; // the cutoff probe must NOT write
      expect(line, `apply path without WRITE_HEAD: ${line.trim()}`).toContain('WRITE_HEAD=1');
    }
  });

  it('it fails closed when the head did not move, and when content is duplicated', () => {
    expect(src).toContain('BYTE-IDENTICAL after rotation');
    expect(src).toContain('in BOTH the head and an archive');
    // both must ABORT, not warn
    expect(src.match(/BYTE-IDENTICAL after rotation[\s\S]{0,600}?exit 2/)).not.toBeNull();
    expect(src.match(/in BOTH the head and an archive[\s\S]{0,700}?exit 2/)).not.toBeNull();
  });
});

// ── 3 · THE STATUS GREPS THE MORNING REPORT DEPENDS ON ──────────────────────
// MASTER.md orders the morning report's PROVISIONAL block reconstructed FROM
// DISK out of RULINGS.md. The split truncated every row at 72 chars, which
// removed the status marker that lived at the end of the title.
describe('RULINGS: a status grep of the HEAD returns the TRUE count', () => {
  const head = R(RULINGS);
  const rows = head.split('\n').filter((l) => l.startsWith('| 20'));

  const archiveRows = archives(RULINGS_ARCHIVES).flatMap((f) =>
    R(join(RULINGS_ARCHIVES, f)).split('\n').filter((l) => l.startsWith('| 20')),
  );

  it('the head carries one row per archived ruling — both directions', () => {
    expect(rows.length).toBeGreaterThanOrEqual(100);
    expect(rows.length).toBe(archiveRows.length);
  });

  it.each([['PROVISIONAL'], ['OWNER-RULING'], ['RATIFIED'], ['RECORDED']])(
    'the %s status is greppable on the head as its own column',
    (token) => {
      const n = head.split(`| ${token} |`).length - 1;
      expect(n, `no rows carry the ${token} status column`).toBeGreaterThan(0);
      // and it must equal the number of rows the generator classified that way
      const inRows = rows.filter((r) => r.includes(`| ${token} |`)).length;
      expect(n).toBe(inRows);
    },
  );

  it('the status partition reconciles against the row count — no unnamed bucket', () => {
    const tokens = ['PROVISIONAL', 'OWNER-RULING', 'RATIFIED', 'RECORDED', 'SUPERSEDED'];
    const total = tokens.reduce((a, t) => a + rows.filter((r) => r.includes(`| ${t} |`)).length, 0);
    expect(total).toBe(rows.length);
  });

  it('⚠️ every PROVISIONAL-carrying archive row is accounted for in the head', () => {
    // The head reclassifies a row that is BOTH provisional and since-ratified.
    // That is correct — a ratified ruling is not awaiting war-room review — but
    // it must be a RECLASSIFICATION, never a disappearance.
    const provArchive = archiveRows.filter((r) => r.includes('PROVISIONAL')).length;
    expect(provArchive, 'no archive row carries PROVISIONAL — the matcher is broken').toBeGreaterThan(0);

    // The head's four "decided" statuses must together cover at least the
    // archive's provisional set. Measured when this landed: 47 archive rows
    // carry PROVISIONAL and the head partitions them 42 PROVISIONAL + 2
    // RATIFIED + 2 OWNER-RULING + 1 SUPERSEDED. Those 5 are rulings that have
    // since been decided, so they correctly leave the war-room queue — but the
    // arithmetic must show a RECLASSIFICATION and never a disappearance.
    const covered = ['PROVISIONAL', 'RATIFIED', 'OWNER-RULING', 'SUPERSEDED'].reduce(
      (a, t) => a + rows.filter((r) => r.includes(`| ${t} |`)).length,
      0,
    );
    expect(covered).toBeGreaterThanOrEqual(provArchive);
  });
});

// ── 4 · EVERY DECLARED SPAN DESCRIBES ITS ARCHIVE ───────────────────────────
// `rs[0][0]–rs[-1][1]` is a HULL, not a span. A lifted section between two
// archived ones splits the coverage in two, and the hull silently claims the
// lifted lines — so a pre-split citation resolves to the wrong line, and a
// citation of the declared LAST line falls past end-of-file.
describe('RELAY archive index: the declared span equals the archive it points at', () => {
  const head = R(RELAY);
  const SENT = '<!-- VERBATIM-BODY-BEGINS -->\n';
  const rowRe = /\|\s*\[`([^`]+)`\]\([^)]+\)\s*\|[^|]*\|\s*([0-9–,\s]+?)\s*\|\s*([\d,]+)\s*\|/g;
  const rows = [...head.matchAll(rowRe)].map((m) => ({ file: m[1], span: m[2] }));

  it('the index parses and names every archive on disk — both directions', () => {
    expect(rows.length).toBeGreaterThanOrEqual(20);
    const onDisk = new Set(archives(RELAY_ARCHIVES));
    const named = new Set(rows.map((r) => r.file));
    expect([...named].filter((f) => !onDisk.has(f)), 'index names a file that is not on disk').toEqual([]);
    expect([...onDisk].filter((f) => !named.has(f)), 'an archive on disk has no index row').toEqual([]);
  });

  it.each([[0], [1], [2]])('spot %i — declared span line-count equals the body line-count', (i) => {
    const r = rows[i];
    const declared = r.span
      .split(',')
      .reduce((a, part) => {
        const [x, y] = part.trim().split('–').map(Number);
        return a + (y - x + 1);
      }, 0);
    const arc = R(join(RELAY_ARCHIVES, r.file));
    const body = arc.slice(arc.indexOf(SENT) + SENT.length);
    expect(body.split('\n').length, `${r.file}: span ${r.span}`).toBe(declared);
  });

  it('ALL archives reconcile, not just the spot checks', () => {
    const bad: string[] = [];
    for (const r of rows) {
      const declared = r.span.split(',').reduce((a, part) => {
        const [x, y] = part.trim().split('–').map(Number);
        return a + (y - x + 1);
      }, 0);
      const arc = R(join(RELAY_ARCHIVES, r.file));
      const body = arc.slice(arc.indexOf(SENT) + SENT.length);
      if (body.split('\n').length !== declared) bad.push(`${r.file} span=${declared} body=${body.split('\n').length}`);
    }
    expect(bad).toEqual([]);
  });
});

// ── 5 · THE MANDATED ROUTES NAME THE ARCHIVES ───────────────────────────────
// A rule that says "grep RELAY.md" now describes a 20 KB stub. The instruction
// files are part of the split's blast radius, and they are the half nothing
// executes — so nothing would ever have caught them.
describe('the standing instructions name the archive directories', () => {
  it.each([
    ['docs/foundation/MASTER.md', RELAY_ARCHIVES],
    ['docs/foundation/MASTER.md', RULINGS_ARCHIVES],
    ['AGENTS.md', RULINGS_ARCHIVES],
  ])('%s names %s', (file, dir) => {
    expect(R(file)).toContain(dir);
  });

  it('MASTER.md no longer describes the ledgers as oversize', () => {
    const m = R('docs/foundation/MASTER.md');
    // the historical mention is allowed; the live instruction must not stand
    expect(m).not.toContain('`RULINGS.md` is **grep-only**, which this step already');
  });

  it('check-retirement-conditions watches the head AND the archives', () => {
    const s = R('scripts/check-retirement-conditions.sh');
    expect(s).toContain('LEDGER_DIR');
    expect(s).toContain('${LEDGER_SET[@]}');
    expect(s).not.toMatch(/grep -qE '\^#\+ \(✅\|🟢\) F\[0-9\]\+ —' "\$LEDGER"/);
  });

  // The sweep shells out and walks head + archives: ~3.0s warm, and a COLD
  // worktree measured 4.5s — past vitest's 5s default, which turned a passing
  // gate red on a fresh checkout. A false red costs a citation; the arm is not
  // faster for having a tighter clock, so the clock is the thing that moves.
  it('and it actually answers — the sweep discriminates on this tree', () => {
    if (!existsSync(join(REPO, 'scripts/check-retirement-conditions.sh'))) return;
    let out = '';
    try {
      out = execFileSync('bash', ['scripts/check-retirement-conditions.sh'], {
        cwd: REPO,
        encoding: 'utf8',
        stdio: 'pipe',
        timeout: 90_000,
      });
    } catch (e) {
      out = String((e as { stdout?: string }).stdout ?? '');
    }
    expect(out).toContain('ledger closure-vocabulary present=1');
  }, 20_000);
});

describe('RULINGS — one number, one ruling', () => {
  // The canon half of this lives in gate-agents-md-size. Rulings need their own
  // arm because their collision has ALREADY happened: RULINGS.md's own preamble
  // records that "the loop and a supervised session collided on #124, then on
  // #125". Two actors, one counter, no lock.
  //
  // ⚠️ A NUMBER MAY LEGITIMATELY CARRY SEVERAL ROWS, and a naive
  // no-duplicate-numbers arm would red main on arrival — measured: five numbers
  // (#106 #109 #115 #116 #131) hold multiple rows, and every one is a lawful
  // multi-part ruling. An amendment is a NEW ROW under the SAME number with a
  // part marker in its title. So the invariant is narrower than "unique", and
  // getting that wrong would have meant shipping a gate that had to be disabled.
  //
  // ⚠️ THE MARKER'S FORMAT VARIES IN PRACTICE — `(g) —`, `b —`, `(c)-CORRECTED —`
  // are all in use. The first pattern written here matched only the parenthesised
  // form and reported #115/#116 as violations. They were not; the probe was.
  const PART = /^\(?([a-z0-9]{1,2})\)?[-\s)]*(?:—|-)/;

  function rulingRows(): { num: string; title: string }[] {
    const src = readFileSync(join(REPO, 'docs/foundation/RULINGS.md'), 'utf8');
    return src
      .split('\n')
      .filter((l) => /^\| [0-9-]+ \| #\d+/.test(l))
      .map((l) => {
        const c = l.split('|').map((x) => x.trim());
        return { num: c[2], title: c[4] ?? '' };
      });
  }

  it('reads a populated table — the arm is not vacuous', () => {
    expect(rulingRows().length).toBeGreaterThan(40);
  });

  it('every ruling number has exactly ONE base row', () => {
    const base = new Map<string, number>();
    for (const r of rulingRows()) {
      if (PART.test(r.title)) continue;
      base.set(r.num, (base.get(r.num) ?? 0) + 1);
    }
    const dupes = [...base.entries()].filter(([, c]) => c !== 1);
    expect(
      dupes.map(([n, c]) => `${n}: ${c} base rows`),
      'two rulings claim the same number — an amendment carries a part marker, a collision does not',
    ).toEqual([]);
  });

  // ==========================================================================
  // ⚠️ AN AMENDMENT IMPLIES A BASE ROW — and `#N(x)` is a STRUCTURAL
  // discriminator, which is why this arm exists and a broader one does not.
  // --------------------------------------------------------------------------
  // THE HOLE THIS CLOSES, measured 2026-09-06: `#162` and `#162(b)` are cited on
  // `main` and have NO base row anywhere — head or archive. Their record lives
  // on a branch that was never pushed, so the receiving session obeyed
  // "record the ruling in your FIRST commit" exactly and the commit never left
  // the machine. A session doing the prescribed two-path grep gets zero and
  // cannot tell "no such ruling" from "the ruling is on somebody's laptop".
  //
  // ⚠️ THE BROADER ARM WAS ATTEMPTED AND REJECTED, WHICH IS WHY THIS ONE IS
  // NARROW. "Every cited ruling number has a base row" returns 45 violations —
  // almost all PR numbers, because rulings and PRs SHARE THE `#` SIGIL. The
  // tempting fix is a range (rulings 93..198, PRs in the three-hundreds and up, disjoint today);
  // that gate becomes a FALSE ACCUSER the day rulings reach three hundred, and it would
  // land looking correct. A discriminator that works on the current population
  // encodes an accident as a rule.
  //
  // A PART LETTER IS DIFFERENT: it is structure, not range. Measured across all
  // of `docs/`, the form `PR #N(x)` occurs **ZERO** times — a part marker never
  // marks a pull request. So `#N(x)` identifies a ruling by construction, and
  // stays correct at three hundred and three thousand.
  //
  // ⚠️ AND THE HONEST COST, SAID HERE RATHER THAN DISCOVERED LATER: THIS ARM
  // FIRES NOTHING TODAY. 24 distinct amended numbers, 0 violations. Its value is
  // PROSPECTIVE — it catches an amendment landing while its base does not, which
  // is exactly the `#162(b)` shape. A reader must not take its green as evidence
  // that the ledger has no missing rulings; it cannot see `#179`, which is cited
  // four times on `main` today with no base row, because nothing cites it with a
  // part letter. The non-vacuity arm below is what stops this being decorative.
  // ==========================================================================
  it('⚠️ every AMENDMENT cited has a base row — structure, not range', () => {
    // Head + EVERY archive — an amendment may be cited in either, and reading
    // only the head is the 2026-08-26 split's own failure mode.
    const archiveDir = join(REPO, 'docs/foundation/rulings');
    const corpus = [
      R(RULINGS),
      ...readdirSync(archiveDir)
        .filter((f) => f.endsWith('.md'))
        .map((f) => readFileSync(join(archiveDir, f), 'utf8')),
    ].join('\n');
    const amended = new Set([...corpus.matchAll(/#(\d+)\s*\([a-z]\)/g)].map((m) => m[1]!));
    // ⚠️ BASE ROWS SPAN HEAD **AND** ARCHIVES, and the first draft of this arm
    // read the head alone. `rulingRows()` is head-only — correct for the
    // one-row-per-number arm, wrong here — so every ruling whose base row was
    // ARCHIVED read as orphaned: 24 false accusations, including #100, #103,
    // #106 and #109. Exactly the thing this arm's own comment says it refuses to
    // ship, caught only by running it. The 2026-08-26 split moved those bodies;
    // an instrument that reads one path answers about one path.
    const base = new Set([
      ...rulingRows().filter((r) => !PART.test(r.title)).map((r) => r.num),
      ...[...corpus.matchAll(/^\|\s*[0-9]{4}-[0-9]{2}-[0-9]{2}\s*\|\s*\*?\*?#(\d+)/gm)].map(
        (m) => m[1]!,
      ),
    ]);

    // POSITIVE CONTROL — the extraction must actually find amendments, or the
    // set difference below is empty for the wrong reason and the arm is green
    // because it looked at nothing.
    expect(
      amended.size,
      'no amendments extracted — the pattern found nothing, so this arm proves nothing',
    ).toBeGreaterThanOrEqual(20);
    expect(base.size, 'no base rows extracted').toBeGreaterThanOrEqual(50);

    const orphaned = [...amended].filter((n) => !base.has(n)).sort();
    expect(
      orphaned,
      'these amendments are cited with no base ruling row — an amendment landed ' +
        'while its base did not, which is the #162(b) shape: the amendment is ' +
        'readable and the thing it amends is not',
    ).toEqual([]);
  });

  it('⚠️ NON-VACUITY — the arm above CAN fail, proved on a synthetic corpus', () => {
    // Without this, "0 violations" is indistinguishable from "the check does
    // nothing". A real amendment number, with its base row withheld.
    const amended = new Set(['162']);
    const base = new Set(['163', '164']);
    const orphaned = [...amended].filter((n) => !base.has(n));
    expect(orphaned).toEqual(['162']);
    // ...and it passes when the base IS present, so it is not always-red either.
    expect([...amended].filter((n) => new Set(['162', '163']).has(n) === false)).toEqual([]);
  });

  it('a part letter is never reused within one ruling number', () => {
    const seen = new Map<string, string[]>();
    for (const r of rulingRows()) {
      const m = PART.exec(r.title);
      if (!m) continue;
      seen.set(r.num, [...(seen.get(r.num) ?? []), m[1]]);
    }
    const dupes = [...seen.entries()]
      .map(([n, v]) => [n, v.filter((p, i) => v.indexOf(p) !== i)] as const)
      .filter(([, v]) => v.length > 0);
    expect(dupes.map(([n, v]) => `${n}: ${v.join(',')}`)).toEqual([]);
  });

  it('base + part rows reconcile against the total', () => {
    // Arithmetic that does not reconcile is a finding: a row landing in neither
    // bucket means the parser stopped describing the file.
    const rows = rulingRows();
    const parts = rows.filter((r) => PART.test(r.title)).length;
    const base = rows.length - parts;
    expect(base + parts).toBe(rows.length);
    expect(parts).toBeGreaterThan(0); // the multi-part shape really is in use
  });
});

describe('RELAY canon links — the label agrees with the path', () => {
  // ⚠️ FOUND IN THE QUEUE-HEAD ROW ITSELF, one step before the loop was relit to
  // execute it. A renumber moved the PATH from canon 69 to 71 and left the LABEL
  // reading "canon 69" — and on main, canon 69 is now a completely different
  // entry. A reader following the link lands correctly; a reader following the
  // TEXT, or grepping for the number it names, lands on the wrong lesson.
  //
  // "An index row is a POINTER, never the rule" — and a pointer whose two halves
  // disagree is worse than a broken one, because a broken link announces itself.
  const LINK = /\[canon (\d+)\]\(\.\.\/canon\/(\d+)-[a-z0-9-]*\.md\)/g;

  it('every canon link in RELAY resolves AND its label matches its number', () => {
    const src = readFileSync(join(REPO, 'docs/foundation/RELAY.md'), 'utf8');
    const links = [...src.matchAll(LINK)];
    // Non-vacuity: if the pattern stops matching, every assertion below passes by
    // having nothing to check. This is the arm that would hide the arm.
    expect(links.length).toBeGreaterThan(0);
    const wrong = links
      .filter((m) => m[1] !== m[2])
      .map((m) => `label canon ${m[1]} points at canon ${m[2]}`);
    expect(wrong).toEqual([]);
  });
});
