// ============================================================================
// GATE — B4's CLOSING STEP, THE HALF THAT RUNS IN CI.
// ----------------------------------------------------------------------------
// B4's gate is *"one full QA pipeline run produces one event per stage, counted
// against THE ENUMERATED STAGE LIST"*. That sentence has two halves and they
// need two different machines:
//
//   · the RUN — a real worker, a real queue, a real database. It cannot happen
//     in CI; it happens on the QA stack, driven by
//     `scripts/qa/b4-stage-coverage.ts`.
//   · the LIST — pure source. It happens here, every push.
//
// ⚠️ AND THE LIST IS THE HALF THAT ROTS. A run against a stale list is a gate
// that is flawless at counting a universe which does not contain the thing it
// was asked to protect — the failure AGENTS.md records as *"a gate's WATCHED
// SET is diffed against the spec's NAMED set"*, where the ratchet reached zero
// having never looked at `doctor_edit_patterns`. Nothing would ever have
// surfaced it: both of its reads were correct, no test failed, and there is no
// observable difference between "the guard watched it and found nothing" and
// "the guard never watched it".
//
// So this file does not test behaviour. It diffs two sets:
//
//   A. LIST → SOURCE. Every stage in `PIPELINE_STAGES` names source files, and
//      every one of those files really does declare that purpose. A stage that
//      was deleted from the pipeline and left in the list fails here.
//   B. SOURCE → LIST. Every purpose ASSIGNMENT in `apps/transcribe-md/src` is
//      bucketed — pipeline / declared-non-pipeline / UNCLASSIFIED — and the
//      buckets sum to the total. A stage added to the pipeline and not added to
//      the list fails here.
//
// ⚠️ THE MATCHER IS NOT `purpose: '…'`, AND THIS SESSION IS WHY. That grep was
// the first thing written, and it silently missed `judge` — `llm-mdm.ts:439`
// declares `const purpose = 'judge' as const;`, a different shape one line
// above the object that uses it. A census built on it would have reported a
// clean bucket sum over 14 stages while the 15th, the one B4 step 3 had just
// finished building, was invisible. That miss is positive-controlled below by
// name, because a matcher's zero and a matcher that cannot see are the same
// output.
//
// ⚠️ AND THE SOURCE IS COMMENT-STRIPPED — BUT READ THE CONTROL BEFORE YOU
// BELIEVE THAT MATTERS TODAY. Prose is where the words you are grepping for are
// guaranteed to appear, and this repo documents its own call sites constantly.
// The stripper is shared with the B1 gates. Measured, however: stripping
// changes NOTHING about the current tree — no non-test file under
// `apps/transcribe-md/src` writes `purpose: 'x'` inside a comment, and the only
// file in the app that does is THIS ONE, four lines up, which `walk()` skips.
// So the stripper is a guard against a future comment, not a cure for a present
// one, and both facts are asserted below rather than assumed. The first version
// of that control was VACUOUS and mutation M3 is what proved it.
// ============================================================================

import { readdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

import {
  COUPLED_STAGES,
  PIPELINE_STAGES,
  PIPELINE_INPUT_MODES,
  LEGACY_OPERATION_ALIASES,
  canonicalOperation,
  isEnumeratedOperation,
  stagesForMode,
  violation,
} from '../pipeline-stages';

// The stripper lives with the B1 gates that first needed it. Imported by path
// rather than copied: two strippers is two behaviours, and the whole value of
// this one is that it is the same code the other gates trust.
import { stripComments } from '../../../../../../packages/ai/src/__tests__/helpers/strip-comments';

const HERE = dirname(fileURLToPath(import.meta.url));
/** apps/transcribe-md/src/lib/billing/__tests__ → repo root */
const ROOT = resolve(HERE, '..', '..', '..', '..', '..', '..');
const APP_SRC = resolve(ROOT, 'apps/transcribe-md/src');

// ---------------------------------------------------------------------------
// THE MATCHER — a purpose ASSIGNMENT, in either shape the tree actually uses.
// ---------------------------------------------------------------------------
// `purpose: 'x'`  — the object-literal shape, 21 sites.
// `purpose = 'x'` — the const shape, 1 site (`llm-mdm.ts`), and the one a
//                   naive grep misses.
const PURPOSE_ASSIGNMENT = /\bpurpose\s*[:=]\s*'([a-z0-9_]+)'/g;

interface Occurrence {
  file: string; // repo-relative
  operation: string;
}

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    const st = statSync(full);
    if (st.isDirectory()) {
      if (entry === 'node_modules' || entry === '__tests__') continue;
      walk(full, out);
    } else if (/\.tsx?$/.test(entry) && !/\.(test|spec)\.tsx?$/.test(entry)) {
      out.push(full);
    }
  }
  return out;
}

function occurrencesIn(absFile: string): Occurrence[] {
  const src = stripComments(readFileSync(absFile, 'utf8'));
  const rel = relative(ROOT, absFile);
  const found: Occurrence[] = [];
  for (const m of src.matchAll(PURPOSE_ASSIGNMENT)) {
    found.push({ file: rel, operation: m[1] });
  }
  return found;
}

/** Every purpose assignment in the app's source tree, comment-stripped. */
const ALL_OCCURRENCES: Occurrence[] = walk(APP_SRC).flatMap(occurrencesIn);

// ---------------------------------------------------------------------------
// BUCKET 2 — the purposes that are NOT pipeline stages, named with reasons.
// ---------------------------------------------------------------------------
// ⚠️ KEYED BY (FILE, OPERATION), NOT BY OPERATION. `tm_soap_draft` is the
// reason: it is a genuine pipeline stage in `04-generate-soap.ts` AND a
// non-pipeline caller in `preview-note-template.ts`, which renders a sample
// note for the template-settings screen against no visit at all. An
// operation-keyed allowlist would have had to exempt the real stage to exempt
// the preview.
const NON_PIPELINE: ReadonlyArray<{ file: string; operation: string; why: string }> = [
  {
    file: 'apps/transcribe-md/src/actions/preview-note-template.ts',
    operation: 'tm_soap_draft',
    why: 'the Settings sample-preview renders one paragraph against a synthetic note with NO visit — it is not a pipeline run and carries no visitId.',
  },
  {
    file: 'apps/transcribe-md/src/lib/note-template-parse/parse-note-to-template.ts',
    operation: 'tm_template_parse',
    why: 'bring-your-own-note parse engine — a settings-time upload, not a visit.',
  },
  {
    file: 'apps/transcribe-md/src/lib/note-template-parse/parse-note-to-template.ts',
    operation: 'tm_template_phi_scan',
    why: 'the PHI gate over parsed template output — settings-time.',
  },
  {
    file: 'apps/transcribe-md/src/lib/template-twin/source-phi.ts',
    operation: 'tm_template_phi_scan',
    why: 'the PHI gate over an uploaded .docx template — settings-time.',
  },
  {
    file: 'apps/transcribe-md/src/lib/template-twin/semantic-mapping/index.ts',
    operation: 'tm_template_parse',
    why: 'Template Twin field mapping — certification-time, and PARKED.',
  },
  {
    file: 'apps/transcribe-md/src/lib/template-twin/synthetic-evidence-gate.ts',
    operation: 'tm_template_synthetic_phi_scan',
    why: 'PHI gate over physician-supplied SYNTHETIC evidence at certify time.',
  },
  {
    file: 'apps/transcribe-md/src/actions/chat-edit-visit.ts',
    operation: 'tm_chat_edit',
    why: 'the pre-sign chat editor — a doctor-driven edit after the pipeline is done, deliberately attributed separately from generation.',
  },
];

function isPipelineSite(o: Occurrence): boolean {
  return PIPELINE_STAGES.some(
    (s) => s.operation === o.operation && s.sources.some((src) => `apps/transcribe-md/${src}` === o.file)
  );
}

function isDeclaredNonPipeline(o: Occurrence): boolean {
  return NON_PIPELINE.some((n) => n.file === o.file && n.operation === o.operation);
}

// ===========================================================================
describe('B4 — the enumerated stage list is the gate’s universe', () => {
  // -------------------------------------------------------------------------
  // 0. THE INSTRUMENT WORKS. Controls first, per canon — a matcher that cannot
  //    see and a codebase with nothing to find produce identical output.
  // -------------------------------------------------------------------------
  describe('positive controls on the matcher itself', () => {
    it('sees the OBJECT-LITERAL shape', () => {
      const soap = ALL_OCCURRENCES.filter(
        (o) => o.file === 'apps/transcribe-md/src/worker/layers/04-generate-soap.ts'
      );
      expect(soap).toEqual([
        {
          file: 'apps/transcribe-md/src/worker/layers/04-generate-soap.ts',
          operation: 'tm_soap_draft',
        },
      ]);
    });

    it('sees the CONST shape — the one a `purpose:` grep misses, which is `judge`', () => {
      // ⚠️ This assertion is the reason the matcher is a regex over two
      // operators instead of the obvious literal. `llm-mdm.ts` writes
      // `const purpose = 'judge' as const;` and then spreads it. A census
      // that missed this would have summed cleanly over 14 of 15 stages.
      const judge = ALL_OCCURRENCES.filter((o) => o.operation === 'judge');
      expect(judge).toEqual([
        {
          file: 'apps/transcribe-md/src/lib/em-coding/llm-mdm.ts',
          operation: 'judge',
        },
      ]);
    });

    it('does NOT see a purpose that appears only in PROSE', () => {
      // ⚠️ THIS CONTROL IS ON A FIXTURE, DELIBERATELY, AND THE FIRST VERSION
      // OF IT WAS VACUOUS. It was originally written against the real
      // `pipeline-stages.ts`, on the reasoning that a file which names every
      // operation in its comments must be the natural haystack. Mutation M3 —
      // delete `stripComments` from the extractor — left all 34 tests GREEN,
      // which is what showed the control was measuring nothing: that file's
      // prose says `tm_anchor_entailment`, but it never says
      // `purpose: 'tm_anchor_entailment'`, and the MATCHER is what the
      // stripper has to defeat, not the operation name.
      //
      // A check whose title is wider than what it measures — AGENTS.md's own
      // class, caught here by the mutation it demands.
      const fixture = [
        "// the meter is set with purpose: 'tm_soap_draft' at the call site",
        "/* purpose: 'tm_critique' — named here in a block comment only */",
        'const notAComment = 1;',
      ].join('\n');
      const stripped = stripComments(fixture);
      expect([...stripped.matchAll(PURPOSE_ASSIGNMENT)]).toEqual([]);
      // …and the same fixture WITHOUT the stripper finds both, so the zero
      // above is a fact about the stripper and not about the fixture.
      expect([...fixture.matchAll(PURPOSE_ASSIGNMENT)].map((m) => m[1])).toEqual([
        'tm_soap_draft',
        'tm_critique',
      ]);
    });

    it('states honestly that NO file in the walked tree carries the pattern in prose', () => {
      // ⚠️ THE STRIPPER IS A GUARD AGAINST A FUTURE COMMENT, NOT A CURE FOR A
      // PRESENT ONE — and saying so is the point. Measured: stripping changes
      // NOTHING about today's tree, because no non-test file under
      // `apps/transcribe-md/src` writes `purpose: 'x'` in a comment. The only
      // file in the whole app that does is THIS ONE, in the header above, and
      // `walk()` skips `__tests__`.
      //
      // Recording the equality is what stops a future reader believing M3's
      // green means the stripper is decoration. It means the haystack is
      // currently clean, and the day somebody documents a call site the way
      // this repo documents everything, it stops being.
      const unstripped = walk(APP_SRC).flatMap((f) => {
        const rel = relative(ROOT, f);
        return [...readFileSync(f, 'utf8').matchAll(PURPOSE_ASSIGNMENT)].map((m) => ({
          file: rel,
          operation: m[1],
        }));
      });
      expect(unstripped).toEqual(ALL_OCCURRENCES);
    });

    it('finds a NON-EMPTY set — the census is not vacuous', () => {
      expect(ALL_OCCURRENCES.length).toBeGreaterThan(15);
    });
  });

  // -------------------------------------------------------------------------
  // A. LIST → SOURCE. A stage that no longer exists cannot sit in the list.
  // -------------------------------------------------------------------------
  describe('every enumerated stage is declared by every source it names', () => {
    for (const stage of PIPELINE_STAGES) {
      for (const src of stage.sources) {
        it(`${stage.operation} ← ${src}`, () => {
          const rel = `apps/transcribe-md/${src}`;
          const hit = ALL_OCCURRENCES.find(
            (o) => o.file === rel && o.operation === stage.operation
          );
          expect(
            hit,
            `${rel} does not assign purpose '${stage.operation}'. Either the ` +
              `stage moved and the list is stale, or the list names the wrong file.`
          ).toBeTruthy();
        });
      }
    }
  });

  // -------------------------------------------------------------------------
  // B. SOURCE → LIST. Nothing declares a purpose the list has never heard of.
  // -------------------------------------------------------------------------
  describe('the bucket sum reconciles — nothing is unclassified', () => {
    const pipeline = ALL_OCCURRENCES.filter(isPipelineSite);
    const nonPipeline = ALL_OCCURRENCES.filter(
      (o) => !isPipelineSite(o) && isDeclaredNonPipeline(o)
    );
    const unclassified = ALL_OCCURRENCES.filter(
      (o) => !isPipelineSite(o) && !isDeclaredNonPipeline(o)
    );

    it('every purpose assignment falls in exactly one named bucket', () => {
      expect(
        unclassified,
        'a purpose is assigned somewhere the stage list has never heard of. ' +
          'If it is a new pipeline stage, add it to PIPELINE_STAGES (and to the ' +
          'QA coverage run). If it is not, add it to NON_PIPELINE with a reason.'
      ).toEqual([]);
      expect(pipeline.length + nonPipeline.length + unclassified.length).toBe(
        ALL_OCCURRENCES.length
      );
    });

    it('the pipeline bucket carries one site per enumerated source', () => {
      // ⚠️ NOT `>= stages.length` — `tm_transcribe` has TWO sources and one
      // label, so a count keyed on stages would be short by one and a count
      // keyed on sites would look wrong. The universe is SITES.
      const declaredSites = PIPELINE_STAGES.flatMap((s) => s.sources).length;
      expect(pipeline.length).toBe(declaredSites);
    });

    it('every NON_PIPELINE entry is still live — a stale exemption is removed', () => {
      // ⚠️ AN EXEMPTION'S REASON IS PROSE AND PROSE DECAYS SILENTLY. This
      // arm can only assert the ENTRY still matches something; it cannot
      // assert the REASON is still true. Re-read the reasons by hand when the
      // code they describe is touched — nothing else will.
      for (const n of NON_PIPELINE) {
        const hit = ALL_OCCURRENCES.find(
          (o) => o.file === n.file && o.operation === n.operation
        );
        expect(hit, `stale exemption: ${n.file} no longer assigns '${n.operation}'`).toBeTruthy();
      }
    });
  });

  // -------------------------------------------------------------------------
  // C. THE EXPECTATIONS ARE WELL-FORMED — a table nobody can misread.
  // -------------------------------------------------------------------------
  describe('the expected-count table', () => {
    it('names at least one input mode per in-band stage', () => {
      for (const s of PIPELINE_STAGES) {
        if (s.expected.kind === 'outOfBand') continue;
        expect(s.modes.length, `${s.operation} runs on no mode`).toBeGreaterThan(0);
        for (const m of s.modes) expect(PIPELINE_INPUT_MODES).toContain(m);
      }
    });

    it('text_notes expects NEITHER transcription NOR speaker roles', () => {
      // The input-mode dependence is the trap the recon named: *"one event per
      // stage is not a property of a visit — it is a property of a visit of a
      // given input mode"*. Asserted in both directions so a table that made
      // every stage universal would fail.
      const ops = stagesForMode('text_notes').map((s) => s.operation);
      expect(ops).not.toContain('tm_transcribe');
      expect(ops).not.toContain('tm_speaker_roles');
      expect(ops).toContain('tm_entities');
    });

    it('voice_dictation transcribes but has no speakers to label', () => {
      const ops = stagesForMode('voice_dictation').map((s) => s.operation);
      expect(ops).toContain('tm_transcribe');
      expect(ops).not.toContain('tm_speaker_roles');
    });

    it('audio_upload is the only mode carrying the full set', () => {
      const ops = stagesForMode('audio_upload').map((s) => s.operation);
      expect(ops).toContain('tm_transcribe');
      expect(ops).toContain('tm_speaker_roles');
      // …and it is the widest of the three, which is why B4 demands it.
      for (const m of PIPELINE_INPUT_MODES) {
        expect(stagesForMode(m).length).toBeLessThanOrEqual(ops.length);
      }
    });

    it('tm_embed is OUT OF BAND — a pipeline run must not expect it', () => {
      const embed = PIPELINE_STAGES.find((s) => s.operation === 'tm_embed')!;
      expect(embed.expected.kind).toBe('outOfBand');
      for (const m of PIPELINE_INPUT_MODES) {
        expect(stagesForMode(m).map((s) => s.operation)).not.toContain('tm_embed');
      }
    });

    it('the anchor-entailment expectation is a DISTRIBUTION, not a product', () => {
      // A gate hardcoding `3 × visits` would be wrong in the direction that
      // reads as a metering hole. Measured invariant: {0, 3}, nothing else.
      const s = PIPELINE_STAGES.find((x) => x.operation === 'tm_anchor_entailment')!;
      expect(s.expected).toMatchObject({ kind: 'oneOf', values: [0, 3] });
      expect(violation(s, 0)).toBeNull();
      expect(violation(s, 3)).toBeNull();
      expect(violation(s, 1)).toBeTruthy();
      expect(violation(s, 2)).toBeTruthy();
      expect(violation(s, 6)).toBeTruthy();
    });

    it('judge is AT LEAST one — the one-per-visit reading is refused', () => {
      const s = PIPELINE_STAGES.find((x) => x.operation === 'judge')!;
      expect(violation(s, 0)).toBeTruthy();
      expect(violation(s, 1)).toBeNull();
      expect(violation(s, 2)).toBeNull();
      expect(violation(s, 13)).toBeNull(); // production's observed tail
    });

    it('the polish stages are {0,1} — the passthrough branch is not a hole', () => {
      // ⚠️ THIS TABLE ORIGINALLY SAID `exactlyOne` FOR BOTH, AND THE FIRST REAL
      // QA RUN REPORTED SIX FINDINGS BECAUSE OF IT. `06-polish.ts:186` returns
      // the draft unchanged when the critique found nothing auto-patchable — no
      // model call, no meter, and correctly so. Production agrees: 28 of 82
      // visits polished. A gate that demanded one would have reported a
      // metering hole on more than half of production.
      for (const op of ['tm_polish', 'tm_polish_gate'] as const) {
        const s = PIPELINE_STAGES.find((x) => x.operation === op)!;
        expect(s.expected).toMatchObject({ kind: 'oneOf', values: [0, 1] });
        expect(violation(s, 0)).toBeNull();
        expect(violation(s, 1)).toBeNull();
        expect(violation(s, 2)).toBeTruthy();
      }
    });

    it('the polish pair is declared COUPLED — a per-stage count cannot see it', () => {
      // Two `{0,1}` stages firing on DIFFERENT visits satisfy every per-stage
      // assertion and every total. The coupling is the only thing that catches
      // it, and it is asserted by the QA run rather than here.
      const pair = COUPLED_STAGES.find((p) => p.leader === 'tm_polish');
      expect(pair, 'tm_polish → tm_polish_gate is not declared coupled').toBeTruthy();
      expect(pair!.follower).toBe('tm_polish_gate');
      // Both members must exist in the stage table, or the coupling names a
      // stage nothing counts.
      for (const p of COUPLED_STAGES) {
        expect(PIPELINE_STAGES.map((s) => s.operation)).toContain(p.leader);
        expect(PIPELINE_STAGES.map((s) => s.operation)).toContain(p.follower);
      }
    });

    it('an exactlyOne stage refuses both 0 and 2', () => {
      const s = PIPELINE_STAGES.find((x) => x.operation === 'tm_entities')!;
      expect(violation(s, 1)).toBeNull();
      expect(violation(s, 0)).toBeTruthy();
      expect(violation(s, 2)).toBeTruthy();
    });
  });

  // -------------------------------------------------------------------------
  // D. RULING 81's TWO-LABEL OBLIGATION.
  // -------------------------------------------------------------------------
  describe('the legacy label is accepted by the join and demanded by nothing', () => {
    it('transcribe_realtime folds onto tm_transcribe', () => {
      expect(canonicalOperation('transcribe_realtime')).toBe('tm_transcribe');
      expect(isEnumeratedOperation('transcribe_realtime')).toBe(true);
      expect(LEGACY_OPERATION_ALIASES.transcribe_realtime).toBe('tm_transcribe');
    });

    it('but it is NOT a stage a coverage run may require', () => {
      // 3 legacy rows in production; nothing can emit it any more. A gate that
      // demanded it would fail on a true statement about history.
      expect(PIPELINE_STAGES.map((s) => s.operation)).not.toContain('transcribe_realtime');
      for (const m of PIPELINE_INPUT_MODES) {
        expect(stagesForMode(m).map((s) => s.operation)).not.toContain('transcribe_realtime');
      }
    });

    it('an operation nobody enumerated is not silently accepted', () => {
      expect(isEnumeratedOperation('tm_chat_edit')).toBe(false);
      expect(isEnumeratedOperation('definitely_not_a_stage')).toBe(false);
    });
  });
});
