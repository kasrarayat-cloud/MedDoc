// The scanner the two bridge guards depend on. A guard built on a broken
// classifier is worse than no guard, so this proves BOTH directions — and the
// happy-path arm is the one that matters here, because the bug it replaced was
// a false POSITIVE, not a false negative.
import { describe, expect, it } from 'vitest';

import { enclosingOpenTags } from './jsx-enclosing';

const has = (code: string, needle = 'qm-rounds-host') => {
  const at = code.indexOf('<Target');
  return enclosingOpenTags(code, at).some((a) => a.includes(needle));
};

describe('enclosingOpenTags — ancestors, not neighbours', () => {
  it('SEES a wrapper (the regression shape)', () => {
    expect(has('<div className="qm-rounds-host"><Target /></div>')).toBe(true);
  });

  it('IGNORES a closed sibling that legitimately carries the bridge', () => {
    // ⚠️ THE REAL CASE. `review-document-view` renders two hosted gate panels
    // ABOVE the card. A ±400-char window called this a wrapper; it is not.
    expect(
      has('<section className="qm-rounds-host qm-rdoc-gate">x</section><Target />'),
    ).toBe(false);
  });

  it('IGNORES a self-closing hosted sibling', () => {
    expect(has('<Foo className="qm-rounds-host" /><Target />')).toBe(false);
  });

  it('is not confused by `>` inside an attribute expression', () => {
    expect(
      has('<div className={n > 2 ? "qm-rounds-host" : "x"}><Target /></div>'),
    ).toBe(true);
    expect(has('<div className={n > 2 ? "a" : "b"}><Target /></div>')).toBe(false);
  });

  it('is not confused by a template literal with an interpolation', () => {
    expect(has('<div className={`qm-rounds-host ${x}`}><Target /></div>')).toBe(true);
  });

  it('handles fragments and nesting', () => {
    expect(has('<><div className="qm-rounds-host"><span><Target /></span></div></>')).toBe(true);
    expect(has('<><div className="plain"><span><Target /></span></div></>')).toBe(false);
  });

  it('returns the ancestor chain outermost-first', () => {
    const code = '<a className="A"><b className="B"><Target /></b></a>';
    expect(enclosingOpenTags(code, code.indexOf('<Target'))).toEqual([
      ' className="A"',
      ' className="B"',
    ]);
  });
});
