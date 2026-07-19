import { describe, expect, it } from 'vitest';

import { canonicalJson, canonicalSha256 } from '../canonical';

describe('Template Twin canonical hashing', () => {
  it('sorts object keys without changing array order', () => {
    expect(canonicalJson({ z: [2, 1], a: { y: true, x: null } })).toBe(
      '{"a":{"x":null,"y":true},"z":[2,1]}',
    );
    expect(canonicalSha256({ b: 2, a: 1 })).toBe(
      canonicalSha256({ a: 1, b: 2 }),
    );
  });

  it('rejects values JSON would silently erase or normalize ambiguously', () => {
    expect(() => canonicalJson({ absent: undefined })).toThrow('undefined');
    expect(() => canonicalJson([Number.NaN])).toThrow('non-finite');
  });
});
