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

import { readFileSync } from 'node:fs';

import { describe, expect, it } from 'vitest';

/** Every doctor-reachable writer of note content, from a full sweep of the
 *  codebase. Each must mark the level stale. */
const MUTATORS = [
  {
    file: 'src/actions/soap.ts',
    what: 'the draft save — the inline editor, tap-to-edit, and the chat’s section edit all funnel here',
  },
  {
    file: 'src/actions/suggestion-actions.ts',
    what: 'adopting a suggestion',
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

  it('the codes row opens even on a visit with nothing to summarise', () => {
    // The row is the control that clears the flag. Gated on having codes, a
    // visit with none would be refused at sign with no control on the page
    // that could resolve it.
    const decl = src.slice(src.indexOf('const hasSummary'), src.indexOf('const hasSummary') + 400);
    expect(decl).toContain('props.emStale');
  });

  it('reaching for Sign re-checks first', () => {
    expect(src).toContain('onRescoreEm?.()');
    const signArea = src.slice(src.indexOf('<SignAndSendModal') - 500, src.indexOf('<SignAndSendModal'));
    expect(signArea).toContain('emStale');
  });
});

describe('imaging reports have no E/M, so the gate does not apply to them', () => {
  it('the sign route exempts them', () => {
    // Ultrasound is LIVE in prod and the pipeline skips E/M scoring entirely
    // for it. A staleness gate over a level that does not exist would make an
    // imaging report permanently unsignable after any edit, and "resolving"
    // it would mean inventing a clinic code.
    const src = readFileSync('src/app/api/visits/[id]/sign/route.ts', 'utf8');
    expect(src).toContain('isImagingReportSpecialty(visit.specialty)');
    expect(src).toContain('visit.emStale && emApplies');
  });

  it('the re-score clears the flag without scoring one', () => {
    const src = readFileSync('src/actions/rescore-em.ts', 'utf8');
    const guard = src.slice(
      src.indexOf('isImagingReportSpecialty(visit.specialty)'),
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
  it('the three doctor-EDIT paths call it', () => {
    for (const file of [
      'src/actions/soap.ts',
      'src/actions/suggestion-actions.ts',
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

  it('adopt hands over its own prior score, never the failure sentinel', () => {
    const src = readFileSync('src/actions/suggestion-actions.ts', 'utf8');
    expect(src).toContain('emDelta.from !== EM_DELTA_INDETERMINATE.from');
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
