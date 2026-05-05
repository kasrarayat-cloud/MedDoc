---
id: A03-P3-001
severity: P3
title: E&M MDM Redis cache key is content-only — confirmed safe but worth a comment
domain: authz
agent: agent-03
---

## Issue

`em_mdm_cache:<sha256>` (apps/transcribe-md/src/lib/em-coding/llm-mdm.ts:179-183) keys solely on the SHA-256 of the normalised SOAP text. Two users in different practices submitting identical SOAP text share a cached judgement.

```ts
export function buildCacheKey(soap: string): string {
  const norm = normalizeSoap(soap);
  const hash = createHash('sha256').update(norm).digest('hex');
  return `${CACHE_KEY_PREFIX}${hash}`;   // no practiceId / userId
}
```

## Evidence

The cache value is an `MdmJudgement` object — pure function of the SOAP content (no demographic, doctor, or practice signal). `computeEmScore(...)` is invoked from POST /api/visits/[id]/em-score (apps/transcribe-md/src/app/api/visits/[id]/em-score/route.ts:77) AFTER an ownership check on the visit, so the cache hit cannot leak someone else's PHI to an unauthenticated caller; it only saves the LLM round-trip when two doctors happen to write identical SOAP bodies.

## Risk

None I can find. The judgement is an opinion about coding-rule applicability, not a derivative of the patient identity. The 7-day TTL bounds drift. Listed as P3 because a future engineer might "harden" by adding userId without realising this key was deliberately content-addressable for cost savings.

## Recommended fix

Add a one-line comment above `buildCacheKey` documenting the intentional design:

```ts
/** SHA-256 cache key over the normalized SOAP. Content-only by design —
 *  the LLM judgement is a pure function of the SOAP body, so two doctors
 *  writing identical text legitimately share an answer. Adding userId
 *  here would shrink the hit rate without any privacy benefit (the
 *  /em-score route gates ownership before this lookup). */
export function buildCacheKey(soap: string): string {
```
