// ============================================================================
// A flag-ON CI image must carry every flag the surface it tests reads.
// ----------------------------------------------------------------------------
// The `doc-preview` project asserts on the note-format CONFIRM CARD. That card
// renders only when `isUxSimplify()` is true — and the image the project built
// did not pass NEXT_PUBLIC_UX_SIMPLIFY. So every test in it waited out its
// 180-second timeout, the project had never passed since the day it was added,
// and it burned ~13 minutes of a 40-minute job budget on every run. The
// workflow was green-by-omission for a while and then simply always red.
//
// Nothing pointed at the cause: the tests failed on a missing element, which
// reads as "the feature is broken", not "the build is missing a flag".
//
// This pins the coupling. It is deliberately a source-grep over the workflow —
// the alternative is discovering the mismatch 18 minutes into CI, which is
// exactly what happened.
// ============================================================================

import { readFileSync } from 'node:fs';

import { describe, expect, it } from 'vitest';

import PW_CONFIG from '../../../playwright.config';

const WORKFLOW = readFileSync('../../.github/workflows/e2e.yml', 'utf8');

/** Each flag-ON image build in the E2E workflow, and the flags its project's
 *  surfaces actually read. */
const IMAGES: { tag: string; needs: string[]; why: string }[] = [
  {
    tag: 'meddoc-pro-transcribe-md:rounds',
    needs: [
      // NEXT_PUBLIC_SKIN_ROUNDS was REMOVED here 2026-08-05 (F-ret.3) because the
      // flag itself is gone — the skin is unconditional, so no image needs the
      // build arg and requiring it would red every build. This entry is deleted
      // rather than commented out in the array: a needs-list that names a flag
      // nothing passes is a gate that fails for a reason unrelated to what it
      // guards.
      // ADDED with Gate B (Screen 2). The stage pack drives the chat DRAWER,
      // and the drawer only mounts when the stage is given a `chat` node —
      // which VisitReadyView only builds behind isChatEditor(). Without this
      // arg every drawer test would burn its full timeout on a missing
      // `rounds-chat-trigger` and read as "the drawer is broken" rather than
      // "the image is missing a flag".
      //
      // The rule, restated for the fourth time in this file: the moment a spec
      // drives a surface, that surface's flag belongs in this list.
      'NEXT_PUBLIC_CHAT_EDITOR',
      // The stage wraps the read-only paper, which is itself behind this flag.
      'NEXT_PUBLIC_REVIEW_DOC_VIEW',
      // The imaging test asserts an ultrasound visit has NO E/M gate. With the
      // specialty flag off, emAppliesToSpecialty is true for EVERY specialty —
      // so that assertion would pass by never being exercised, which is worse
      // than failing.
      'NEXT_PUBLIC_ULTRASOUND_SPECIALTY',
      // ADDED with Gate B Screen 4. The ENTIRE signed branch of the review view
      // is behind isUxSimplify(), so without this arg a signed visit renders the
      // legacy tabbed view and Screen 4 is unreachable on the CI image — every
      // rounds-signed test would fail on a missing testid while the product was
      // correct. The image had carried the other four flags since Gate A and
      // nothing noticed, because until now no pack opened a signed visit.
      'NEXT_PUBLIC_UX_SIMPLIFY',
      // ── ADDED for C1: THE FOUR FLAGS PRODUCTION BUILDS AND THIS IMAGE DID
      //    NOT. Every one is `true` in `.env` and passed in the prod service's
      //    `args:` block, so until now the Rounds packs have been measuring a
      //    build production does not ship.
      //
      //    B4 named the first two as a limit it would not close, because
      //    changing the image's flag set alters what every Rounds pack renders
      //    and that is not a verification item's work. C1 pays it, alone, in a
      //    PR with no product code — so a red here can only mean one thing.
      //
      //    ⚠️ The delta was computed, not guessed: prod's `args:` block carries
      //    13 entries, this image carried 6, and the two that legitimately
      //    differ are the URLs (per-environment by design; the QA stack must
      //    keep pointing at localhost:9020).
      //
      //    ⚠️ SETTINGS_SIMPLE_ROW AND TEMPLATE_NATIVE_DOCX ARE ONE PAIR, and
      //    adding either alone would be worse than adding neither.
      //
      //    `settings/page.tsx:213-215` reads
      //        nativeSlot = templateNativeDocxEnabled() && !isSettingsSimpleRow()
      //    — INVERTED on the second term. Production sets both `true`, so the
      //    slot is `null`: that is the deliberate "no door in" recorded in
      //    AGENTS.md, and it is why prod holds zero twin certifications while
      //    the twin flag is on.
      //
      //    So an image carrying TEMPLATE_NATIVE_DOCX but NOT SETTINGS_SIMPLE_ROW
      //    would MOUNT `NativeTemplateManager` — a surface production
      //    deliberately folds away — and any pack walking settings would be
      //    measuring a door that does not exist for a doctor. Both, or neither.
      //
      //    (It does NOT choose between the two settings LAYOUTS. That is
      //    `isSkinBeta()` at `page.tsx:226`, which this image already carried.
      //    `isSettingsSimpleRow` is read at exactly one place in that file.)
      'NEXT_PUBLIC_SETTINGS_SIMPLE_ROW',
      // DOC_PREVIEW and VISIT_DOC_PAGE change what the visit surface renders —
      // which is the surface Screens 2 and 4 are built on. B4's parity test
      // signs through the Rounds flow on this image; with these off it was
      // exporting from a composition prod does not have.
      'NEXT_PUBLIC_DOC_PREVIEW',
      'NEXT_PUBLIC_VISIT_DOC_PAGE',
      // The OOXML ingest + fail-closed security fork runs on every .docx
      // template upload in production (AGENTS.md, "Template Twin — the parked
      // steady state"). It is load-bearing and absorbed in place, so an image
      // without it is missing a shipped code path. See the pairing note above:
      // this one must never be added without SETTINGS_SIMPLE_ROW.
      'NEXT_PUBLIC_TEMPLATE_NATIVE_DOCX',
      // ⚠️ ADDED BY C1-d, AND IT WAS THE ONE BUILD-ARG THIS FILE DID NOT WATCH.
      // The image has passed `NEXT_PUBLIC_SKIN_BETA=true` since Gate A, and
      // nothing asserted it — the name appeared nowhere under `src/lib/__tests__`
      // (positive control: SKIN_ROUNDS appears in three files there). It is not
      // cosmetic. `isSkinBeta()` chooses which BRANCH of `auth-shell.tsx`
      // renders — the `qm-c3-auth` card that C1-d restyles, or a ~270-line
      // split-screen fallthrough that Rounds never touched. Drop the arg and
      // the rounds-c1 pack fails on missing selectors while the product is
      // perfectly correct, which is the exact diagnosis cost this file exists
      // to remove. It also selects the C3 section-rail in `settings/page.tsx`,
      // so C1-e and C1-f inherit the same dependency.
      'NEXT_PUBLIC_SKIN_BETA',
      // C1-c2's preview door for the state families a walk cannot reach. Its
      // own gate (`gate-devstates`) asserts the Dockerfile ARG and prod's
      // absence; this row is what asserts the IMAGE carries it, which is the
      // half that decides whether /dev/states resolves 200 or 404 on QA.
      'NEXT_PUBLIC_DEV_STATES',
    ],
    why:
      'Gate A + Gate B + C1. The board route 404s with the flag off, so a rounds ' +
      'image built without the build-arg would fail the whole pack for an ' +
      'environment reason. The Dockerfile must also DECLARE the ARG — docker ' +
      'silently discards an undeclared build-arg ("were not consumed") and the ' +
      'flag never inlines, which is how the first flag-ON build shipped the ' +
      'old skin.',
  },
  {
    tag: 'meddoc-pro-transcribe-md:doc-preview',
    needs: ['NEXT_PUBLIC_DOC_PREVIEW', 'NEXT_PUBLIC_UX_SIMPLIFY'],
    why: 'the confirm card it asserts on is behind isUxSimplify()',
  },
  {
    tag: 'meddoc-pro-transcribe-md:visit-doc',
    needs: [
      'NEXT_PUBLIC_VISIT_DOC_PAGE',
      'NEXT_PUBLIC_DOC_PREVIEW',
      'NEXT_PUBLIC_REVIEW_DOC_VIEW',
      'NEXT_PUBLIC_UX_SIMPLIFY',
      // ADDED 2026-07-28, and it cost a 35-minute E2E to learn — which is
      // precisely the expense this file exists to convert into a 30ms unit
      // failure. Deleting the per-section edit pills made the chat editor the
      // only way to amend a note before signing, so the spec now drives it —
      // and `ChatEditorPanel` is behind isChatEditor(). The image did not carry
      // the flag, so the panel never mounted and five tests failed on a
      // missing testid while the product was correct.
      //
      // THE RULE, restated: the moment a spec drives a surface, that surface's
      // flag belongs in this list. A flag a test needs is not optional.
      'NEXT_PUBLIC_CHAT_EDITOR',
    ],
    why: 'it drives the document page, the chat editor that edits it, and the signed view',
  },
  {
    tag: 'meddoc-pro-transcribe-md:review-doc',
    needs: [
      'NEXT_PUBLIC_REVIEW_DOC_VIEW',
      // ADDED 2026-07-28 — the third time this file's rule has been paid for,
      // and the first time a fixture guard named the cause instead of a timeout.
      //
      // The pack now runs its core specs across BOTH specialty classes, and the
      // imaging half asserts an imaging report has NO office-E/M surface. That
      // suppression is `ultrasoundSpecialtyEnabled() && isImagingReportSpecialty()`.
      // Without the flag the conjunction is false, so the build computes and
      // persists an office level on an ultrasound visit — the original prod bug,
      // reproduced in CI by a missing build arg. Three imaging specs failed.
      'NEXT_PUBLIC_ULTRASOUND_SPECIALTY',
    ],
    why: 'the pre-sign document surface, across both specialty classes — imaging suppression is flag-gated',
  },
];

/** The `docker build … -t <tag> .` block for one image. */
function buildBlock(tag: string): string {
  const at = WORKFLOW.indexOf(`-t ${tag} .`);
  if (at === -1) return '';
  // Walk back to the `docker build` that owns this -t.
  const start = WORKFLOW.lastIndexOf('docker build', at);
  return start === -1 ? '' : WORKFLOW.slice(start, at);
}

describe('every flag-ON E2E image carries the flags its surface reads', () => {
  for (const img of IMAGES) {
    it(`${img.tag} — ${img.why}`, () => {
      const block = buildBlock(img.tag);
      expect(block, `no docker build found for ${img.tag}`).not.toBe('');
      const missing = img.needs.filter(
        (f) => !new RegExp(`--build-arg\\s+${f}=true`).test(block),
      );
      expect(
        missing,
        `${img.tag} omits ${missing.join(', ')} — its tests will fail on a ` +
          `missing element, which reads as a broken feature rather than a ` +
          `missing build arg, and each one will burn its full timeout first`,
      ).toEqual([]);
    });
  }
});

// ============================================================================
// The OTHER half of the same coupling: a flag-ON pack must be excluded from
// the DEFAULT run.
// ----------------------------------------------------------------------------
// The block above pins "the flag-ON image carries the flag". This pins "the
// flag-OFF run never sees the spec". Both are needed, and the second failure
// mode is the nastier one.
//
// `rounds-board.spec.ts` was added with its own project and its own flag-ON
// image build, correctly. But it was not added to the `chromium` project's
// testIgnore — so the DEFAULT run, against the flag-OFF app, also collected it.
// /board 404s there by design, all five tests failed, and the step exited 1.
//
// The damage is not five red tests. Everything downstream is `skipped`: the
// rounds image is never built, `--project=rounds-board` never runs, and the
// pack that was supposed to prove Gate A **never executed once**. The gate
// reports the Rounds pack red for the only reason that is not about Rounds,
// and a green local run against the flag-ON image says nothing about it.
//
// So: every project other than `chromium` runs against its own app env by
// definition — that is why it is a separate project — and every glob it claims
// must therefore be ignored by `chromium`.
// ============================================================================

/** Minimal shape we read off the config; Playwright's types allow more
 *  (RegExp globs among them, which this repo does not use for projects). */
type Project = {
  name?: string;
  testMatch?: string | string[];
  testIgnore?: string | string[];
};

const PROJECTS = (PW_CONFIG.projects ?? []) as Project[];
const CHROMIUM = PROJECTS.find((p) => p.name === 'chromium');

/** A Playwright glob → RegExp, so an umbrella ignore (the `*.eval.spec.ts`
 *  one) is recognised as covering a more specific project glob.
 *
 *  Written as an explicit scan rather than a split/join around a placeholder
 *  character: a placeholder has to be a byte that cannot occur in a glob, and
 *  choosing one is how this function first shipped four literal NUL bytes into
 *  the file. The tests still passed — NUL separates as well as a space does
 *  — but git reclassified the source as BINARY and stopped diffing it, so the
 *  guard below would have landed unreviewable. */
function globToRe(glob: string): RegExp {
  let src = '';
  for (let i = 0; i < glob.length; i += 1) {
    const c = glob[i];
    if (c !== '*') {
      src += c.replace(/[.+?^${}()|[\]\\]/, '\\$&');
    } else if (glob[i + 1] === '*') {
      src += '.*';
      i += 1;
    } else {
      src += '[^/]*';
    }
  }
  return new RegExp(`^${src}$`);
}

describe('every flag-ON E2E project is excluded from the default chromium run', () => {
  it('the chromium project still exists and still has a testIgnore', () => {
    expect(CHROMIUM, 'no project named `chromium`').toBeDefined();
    expect(Array.isArray(CHROMIUM?.testIgnore)).toBe(true);
  });

  const ignores = (
    Array.isArray(CHROMIUM?.testIgnore) ? CHROMIUM.testIgnore : []
  ) as string[];

  for (const project of PROJECTS) {
    if (!project.name || project.name === 'chromium') continue;

    const globs =
      typeof project.testMatch === 'string'
        ? [project.testMatch]
        : (project.testMatch ?? []);

    it(`${project.name} — its specs are ignored by chromium`, () => {
      expect(
        globs.length,
        `project \`${project.name}\` declares no testMatch, so the default ` +
          `run's testIgnore cannot be checked against it`,
      ).toBeGreaterThan(0);

      const leaked = globs.filter(
        (g) => !ignores.some((ig) => ig === g || globToRe(ig).test(g)),
      );

      expect(
        leaked,
        `\`${project.name}\` runs against its own app env, but chromium does ` +
          `not ignore ${leaked.join(', ')} — the default flag-OFF run will ` +
          `collect those specs and fail on an environment it was never meant ` +
          `to meet. That failure exits the E2E step, so every later step is ` +
          `SKIPPED and \`--project=${project.name}\` never runs at all.`,
      ).toEqual([]);
    });
  }
});
