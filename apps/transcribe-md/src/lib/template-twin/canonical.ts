import { createHash } from 'node:crypto';

/**
 * Canonical JSON for hashes that cross compiler, resolver, renderer, and
 * persistence boundaries. Object keys are sorted; array order is preserved.
 * Undefined values are rejected so two runtimes cannot hash them differently.
 */
export function canonicalJson(value: unknown): string {
  return JSON.stringify(canonicalize(value));
}

export function canonicalSha256(value: unknown): string {
  return createHash('sha256').update(canonicalJson(value), 'utf8').digest('hex');
}

function canonicalize(value: unknown): unknown {
  if (
    value === null ||
    typeof value === 'string' ||
    typeof value === 'boolean'
  ) {
    return value;
  }

  if (typeof value === 'number') {
    if (!Number.isFinite(value)) {
      throw new TypeError('Canonical JSON does not support non-finite numbers');
    }
    return Object.is(value, -0) ? 0 : value;
  }

  if (Array.isArray(value)) {
    return value.map((entry) => {
      if (entry === undefined) {
        throw new TypeError('Canonical JSON does not support undefined array entries');
      }
      return canonicalize(entry);
    });
  }

  if (typeof value === 'object') {
    const record = value as Record<string, unknown>;
    return Object.fromEntries(
      Object.keys(record)
        .sort()
        .map((key) => {
          const entry = record[key];
          if (entry === undefined) {
            throw new TypeError('Canonical JSON does not support undefined object values');
          }
          return [key, canonicalize(entry)];
        }),
    );
  }

  throw new TypeError(`Canonical JSON does not support ${typeof value}`);
}
