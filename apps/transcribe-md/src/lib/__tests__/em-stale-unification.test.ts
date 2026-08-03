// ============================================================================
// One semantics for a changed note, whoever changed it.
// ----------------------------------------------------------------------------
// Before this, only ADOPTING a suggestion computed an E/M delta. A doctor could
// edit the note in the inline editor and sign, and nothing ever revisited the
// billing level. The chat editor would have made that a route a MODEL could
// choose — which is what forced the question, but the hole predates it.
//
// These assert the invariant at the source: every doctor-reachable path that
// changes note content marks the level stale, and the sign route refuses while
// it is. Source-level, because the alternative is a live DB per case; the E2E
// covers the behaviour end to end.
// ============================================================================

import { existsSync, readFileSync } from 'node:fs';

import { describe, expect, it } from 'vitest';

/** Every doctor-reachable writer of note content, from a full sweep of the
 *  codebase. Each must mark the level stale. */
const MUTATORS = [
  {
    file: 'src/actions/soap.ts',
    what: 'the draft save — the inline editor, tap-to-edit, and the chat’s section edit all funnel here',
  },
  {
    file: 'src/app/api/visits/[id]/em-score/apply-additions/route.ts',
    what: 'applying E/M additions',
  },
  {
    file: 'src/app/api/visits/[id]/retry/route.ts',
    what: 'a retry on a READY visit — the pipeline re-persists the note, edits and all',
  },
];

describe('every content mutation marks the level stale', () => {
  for (const m of MUTATORS) {
    it(`${m.what} (${m.file})`, () => {
      expect(readFileSync(m.file, 'utf8')).toContain('emStale: true');
    });
  }
});

describe('the sign gate', () => {
  const src = readFileSync('src/app/api/visits/[id]/sign/route.ts', 'utf8');

  it('refuses a stale visit', () => {
    expect(src).toContain('visit.emStale');
    expect(src).toContain('EM_SIGN_BLOCKED_STALE');
  });

  it('checks staleness BEFORE the existing acknowledgement gate, not instead of it', () => {
    // Gates only ever gain requirements. The pending-change check must still
    // be there, and must still run.
    const stale = src.indexOf('visit.emStale');
    const pending = src.indexOf('unacknowledgedEmChange(visit.emPendingChange)');
    expect(stale).toBeGreaterThan(-1);
    expect(pending).toBeGreaterThan(-1);
    expect(stale).toBeLessThan(pending);
    expect(src).toContain('EM_SIGN_BLOCKED_UNACKNOWLEDGED_CHANGE');
  });

  it('only applies to READY visits — a signed note is not re-gated', () => {
    const line = src.slice(src.indexOf('visit.emStale') - 120, src.indexOf('visit.emStale') + 40);
    expect(line).toContain('TranscribeVisitStatus.READY');
  });
});

describe('the re-score', () => {
  const src = readFileSync('src/actions/rescore-em.ts', 'utf8');

  it('never clears the flag without having scored', () => {
    // The catch returns stale:true. A level we could not check must not
    // become signable because the check failed. Bound the slice to the catch
    // BODY — running it to end-of-file swept in the success path's clear.
    const start = src.indexOf('} catch (err) {');
    const cat = src.slice(start, src.indexOf('\n  }', start));
    expect(cat).toContain('stale: true');
    expect(cat).not.toContain('emStale: false');
  });

  it('arms the EXISTING confirm card when the level moved', () => {
    expect(src).toContain('emPendingChange');
    // …and PRESERVES an existing cause rather than relabelling an AI-caused
    // upcode as an edit, which would put the wrong cause in the audit row.
    expect(src).toContain("existing?.cause ?? 'note_edited'");
  });

  it('has a real BEFORE to compare against', () => {
    // The first version compared the current score to itself, so `moved` was
    // structurally always false for a plain edit: the gate cleared itself and
    // looked exactly like a gate that had checked.
    expect(src).toContain('emScoredCode');
    expect(src).toContain('baseline !== scored');
    expect(src).not.toMatch(/baseline\s*=\s*[^;]*\?\?\s*scored/);
  });

  it('will not write over a note it did not score', () => {
    expect(src).toContain('soapVersion: visit.soapVersion');
    expect(src).toContain('written.count === 0');
  });

  it('uses the one fail-closed coercion, not a raw cast', () => {
    expect(src).toContain('unacknowledgedEmChange(visit.emPendingChange)');
  });

  it('clears the pending record when the level came back', () => {
    expect(src).toContain('Prisma.DbNull');
  });

  it('writes only to a READY row', () => {
    expect(src).toContain('status: TranscribeVisitStatus.READY');
  });
});

describe('the gate cannot strand a doctor', () => {
  const src = readFileSync('src/app/visits/[id]/review-document-view.tsx', 'utf8');

  it('the re-check control is unconditional — it depends on no summary row', () => {
    // HISTORY. This used to assert that `hasSummary` included `props.emStale`,
    // because the codes row WAS the control that cleared the flag: gated on
    // having codes, a visit with none was refused at sign with nothing on the
    // page that could resolve it.
    //
    // The codes row is gone, and with it the whole class of bug — the re-check
    // now lives in the gate stack and renders off `emStale` alone. So the
    // stronger assertion is available: there is no summary condition left to
    // get wrong.
    expect(src).not.toContain('hasSummary');
    expect(src).not.toContain('billingNode');
    expect(src).not.toContain('codesNode');

    // The stale gate, and its button, keyed on nothing but the flag.
    const gate = src.slice(
      src.indexOf('{props.emStale && !props.emPendingChange && ('),
      src.indexOf('{props.emPendingChange && ('),
    );
    expect(gate).toContain('review-doc-em-stale-gate');
    expect(gate).toContain('review-doc-em-rescore');
    expect(gate).toContain('rescore()');
  });

  it('reaching for Sign re-checks first', () => {
    // ⚠️ R2 MOVED THE SIGN BAR OUT OF `review-document-view.tsx` into
    // `review-sign-bar.tsx`, so it could be re-homed into Rounds Gate 3. The
    // BEHAVIOUR this pins is unchanged — reaching for Sign while the level is
    // stale re-scores first, so the doctor meets the confirm card rather than a
    // refusal they have to interpret — so the assertion follows the code
    // instead of being deleted.
    const bar = readFileSync('src/app/visits/[id]/review-sign-bar.tsx', 'utf8');
    expect(bar).toContain('onRescoreEm?.()');

    // ⚠️ AND IT NO LONGER SLICES BY CHARACTER OFFSET. This read
    // `src.slice(indexOf('<SignAndSendModal') - 500, …)` and asserted `emStale`
    // appeared in that window — a guess about how much text happens to sit
    // above the element. Moving the modal a few lines, or adding a prop,
    // silently changes what is measured; and where the modal sits inside the
    // first 500 characters, `slice` clamps to 0 and the window becomes the
    // whole preamble. The relationship being asserted is that the re-check
    // GUARDS the sign trigger, so assert that shape directly.
    const guard = bar.slice(bar.indexOf('onClickCapture'), bar.indexOf('<SignAndSendModal'));
    expect(
      guard,
      'the re-check no longer wraps the sign trigger — a stale level can reach ' +
        'the modal unchecked',
    ).toContain('emStale');
    expect(guard).toContain('onRescoreEm');
  });
});

describe('imaging reports have no E/M, so the gate does not apply to them', () => {
  it('the sign route exempts them', () => {
    // Ultrasound is LIVE in prod and the pipeline skips E/M scoring entirely
    // for it. A staleness gate over a level that does not exist would make an
    // imaging report permanently unsignable after any edit, and "resolving"
    // it would mean inventing a clinic code.
    const src = readFileSync('src/app/api/visits/[id]/sign/route.ts', 'utf8');
    expect(src).toContain('emAppliesToSpecialty(visit.specialty)');
    expect(src).toContain('visit.emStale && emApplies');
  });

  it('the re-score clears the flag without scoring one', () => {
    const src = readFileSync('src/actions/rescore-em.ts', 'utf8');
    const guard = src.slice(
      src.indexOf('emAppliesToSpecialty(visit.specialty)'),
      src.indexOf('let scored'),
    );
    expect(guard).toContain('emStale: false');
    expect(guard).not.toContain('computeDisplayedEmCode');
  });
});

describe('the baseline is seeded, so the FIRST edit is gated too', () => {
  const src = readFileSync('src/app/visits/[id]/page.tsx', 'utf8');

  it('records the computed level once per visit', () => {
    // Nothing else writes emScoredCode. Without a seed, every visit's FIRST
    // re-score finds no baseline, concludes nothing moved, and clears the
    // gate — one free unvalidated level change per visit, on the common path
    // (edit once, sign).
    expect(src).toContain('emScoredCode: code');
    expect(src).toContain('emScoredCode: null');
  });

  it('never seeds over a signed row', () => {
    const seed = src.slice(src.indexOf('SEED THE BASELINE'), src.indexOf('} catch (e)'));
    expect(seed).toContain('TranscribeVisitStatus.READY');
  });

  it('seeds the DISPLAYED level, not the raw suggestion', () => {
    // The doctor's override is the level they are billed at; comparing a later
    // score against the un-overridden suggestion would report a move that the
    // doctor had already decided.
    expect(src).toContain('initialEmScore?.override?.code ?? initialEmScore?.suggestedCode');
  });
});

describe('the baseline is also seeded at the FIRST MUTATION', () => {
  // WHAT the seed writes is tested behaviourally in
  // src/lib/em-coding/__tests__/seed-baseline.test.ts — against a stubbed
  // prisma, asserting the written value. These only check that the callers
  // exist, which is all a source-text test can honestly claim.
  it('the doctor-EDIT paths call it', () => {
    // Was three. Adopting a suggestion was one of them, and the suggestion
    // lane is gone — the verifier is audit-only and nothing is staged to
    // adopt. The remaining paths are unchanged and still seed.
    for (const file of [
      'src/actions/soap.ts',
      'src/app/api/visits/[id]/em-score/apply-additions/route.ts',
    ]) {
      expect(readFileSync(file, 'utf8'), `${file} must seed`).toContain(
        'seedEmBaselineIfUnset(',
      );
    }
  });

  it('RETRY does not — it is a regeneration, not an edit', () => {
    // The canonical manual retry failed during L7: soapFinal is populated but
    // every scoring signal is still null. Seeding there records a level
    // derived from absent signals, and the resume then makes the next
    // re-score report a movement the note never made.
    expect(readFileSync('src/app/api/visits/[id]/retry/route.ts', 'utf8')).not.toContain(
      'seedEmBaselineIfUnset(',
    );
  });

  it('no adopt path survives to hand over a score at all', () => {
    // The adopt action carried its own prior-score hand-off so a re-score
    // measured movement against a real level rather than the sentinel. Both
    // the action and the lane it served are deleted; this pins the deletion so
    // the coupling cannot quietly return without the guard that made it safe.
    expect(existsSync('src/actions/suggestion-actions.ts')).toBe(false);
  });

  it('apply-additions selects the signals the level depends on', () => {
    // prisma is untyped here (`as any`), so a missing select column is
    // invisible to tsc — cptCodes absent meant the doctor's override was not
    // projected and the baseline could never match a later score.
    const src = readFileSync(
      'src/app/api/visits/[id]/em-score/apply-additions/route.ts',
      'utf8',
    );
    const select = src.slice(src.indexOf('select: {'), src.indexOf('emStale: true'));
    expect(select).toContain('cptCodes: true');
    expect(select).toContain('specialty: true');
  });
});
