// ============================================================================
// ⚠️ A DECLARATION WITH A MALFORMED NAME REFUSES **EVERYBODY'S** DEPLOY.
// ----------------------------------------------------------------------------
// `scripts/lib/declaration.sh`'s `declaration_resolve` walks every `*.md` in
// `docs/foundation/deploys/`, and an entry that is neither a recognised KIND nor
// `<date>-<sha>` returns **2 — CANNOT TELL**, which aborts the resolution
// entirely. Not "skip that file": the whole gate refuses.
//
// ⚠️ SO THE BLAST RADIUS IS NOT THE AUTHOR'S OWN DEPLOY. A badly-named file
// merged to `main` blocks the next deploy from ANY lane, and it blocks it with a
// message about a file its author has never seen. The refusal is loud and
// correct — and it fires at DEPLOY time, which is the latest and most expensive
// possible moment: mid-release, with the deploying session reading somebody
// else's filename.
//
// ⚠️ AND IT WAS ONE COMMIT FROM HAPPENING. `20260907-registry1-family3.md` was
// written, committed and pushed on this branch. `${base##*-}` reads `family3`,
// which is not hex, so the resolver would have returned 2 for every deploy
// against `main` until somebody renamed it. It was caught by READING the
// resolver while preparing to use it, not by any control — which is exactly the
// gap this file closes.
//
// The check belongs at AUTHORING time because that is where the fix is one
// rename by the person who knows what the file is. The shipped script stays the
// authority on the rule; this arm re-derives its *filename* clause only, and the
// non-vacuity arms below pin that the re-derivation still refuses what the
// script refuses.
// ============================================================================
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

const REPO = join(process.cwd(), '..', '..');
const DECL_DIR = join(REPO, 'docs', 'foundation', 'deploys');
const LIB = join(REPO, 'scripts', 'lib', 'declaration.sh');

/** The recognised non-declaration kinds, as `declaration_resolve` enumerates them. */
const RECOGNISED_KIND =
  /^(README|BASELINE-.*|.*-JUDGED|.*-RETROSPECTIVE|.*-backfill-declaration)$/;

/** Why this base name would refuse, or null when the resolver accepts it. */
export function declarationNameRefusal(base: string): string | null {
  if (RECOGNISED_KIND.test(base)) return null;
  const sha = base.includes('-') ? base.slice(base.lastIndexOf('-') + 1) : base;
  if (sha === '' || /[^0-9a-fA-F]/.test(sha)) {
    return `'${sha}' is not a commit sha and the name matches no recognised kind`;
  }
  if (sha.length < 7) {
    return `'${sha}' is hex but shorter than 7 characters — the resolver never pads or guesses`;
  }
  return null;
}

describe('§2.5 — every file in docs/foundation/deploys is a name the deploy gate accepts', () => {
  const entries = readdirSync(DECL_DIR)
    .filter((f) => f.endsWith('.md'))
    .map((f) => f.replace(/\.md$/, ''));

  it('the corpus is real — this arm is not passing over an empty directory', () => {
    expect(entries.length).toBeGreaterThan(50);
  });

  it('⚠️ NOT ONE ENTRY WOULD MAKE `declaration_resolve` RETURN 2', () => {
    const bad = entries
      .map((b) => ({ b, why: declarationNameRefusal(b) }))
      .filter((x) => x.why !== null)
      .map((x) => `${x.b}.md — ${x.why}`);
    expect(
      bad,
      'a malformed declaration filename refuses EVERY lane\'s next deploy, at ' +
        'deploy time, with a message about a file its author never wrote. Rename ' +
        'it to <date>-<sha>.md, or — if it is a NEW KIND — add it to the ' +
        'recognised-kinds list in scripts/lib/declaration.sh AND to this arm, so ' +
        'the two cannot drift.',
    ).toEqual([]);
  });

  it('⚠️ NON-VACUITY: the predicate really refuses the shapes the script refuses', () => {
    // Without these, the arm above is satisfied by a function that returns null
    // for everything — which is precisely the state the directory was in.
    expect(declarationNameRefusal('20260907-registry1-family3')).toMatch(/not a commit sha/);
    expect(declarationNameRefusal('20260904-c436b8cd-INTERIM')).toMatch(/not a commit sha/);
    expect(declarationNameRefusal('20260907-abc')).toMatch(/shorter than 7/);
    expect(declarationNameRefusal('20260907-interim')).toMatch(/not a commit sha/);
    // ⚠️ AND ONE THAT THE NAME CHECK ACCEPTS AND SHOULD NOT BE READ AS BLESSED.
    // A bare `20260907.md` has no dash, so `${base##*-}` returns the whole
    // string — eight hex digits — and the FILENAME clause passes it. It then
    // fails later, on the sha lookup, because `20260907` is not a commit. This
    // arm is here so the next reader does not "fix" the predicate to refuse it
    // and thereby diverge from the shipped script, which accepts it too.
    expect(declarationNameRefusal('20260907')).toBeNull();
  });

  it('⚠️ NON-VACUITY, the other way: it ACCEPTS every shape the script accepts', () => {
    for (const ok of [
      '20260907-2073ea95',
      '20260907-43fcf4a6b1c2d3e4f5',
      'README',
      'BASELINE-note-content',
      '20260827-b439dcbb-F12E-RETROSPECTIVE',
      '20260903-abcdef1-JUDGED',
      '20260812-b7s3c-backfill-declaration',
    ]) {
      expect([ok, declarationNameRefusal(ok)]).toEqual([ok, null]);
    }
  });

  it('⚠️ THE RECOGNISED-KIND LIST IS STILL THE ONE THE SCRIPT CARRIES', () => {
    // This arm is a re-derivation of a shell `case`, so it can drift from it.
    // Reading the script's own list is what makes the drift visible: a kind
    // added there and not here would make this file refuse a name the deploy
    // accepts, and a kind added here and not there would let one through.
    const lib = readFileSync(LIB, 'utf8');
    for (const kind of ['README', 'BASELINE-*', '*-JUDGED', '*-RETROSPECTIVE', '*-backfill-declaration']) {
      expect([kind, lib.includes(kind)]).toEqual([kind, true]);
    }
    // And the two hard refusals this file mirrors are still the script's.
    expect(lib).toContain('*[!0-9a-fA-F]*');
    expect(lib).toContain('-lt 7');
  });
});
