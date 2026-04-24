// Cosine similarity over a bag-of-words representation. Used by the
// SOAP-determinism test to decide whether three runs of the same input
// produced "substantially the same" note. Not linguistically precise,
// but good enough to catch a drift from temperature=0.2 up to 1.0 — a
// real regression bumps the distance well past the 80% threshold.

function tokenize(s: string): string[] {
  return s
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, ' ')
    .split(/\s+/)
    .filter(Boolean);
}

function bagOfWords(s: string): Map<string, number> {
  const bag = new Map<string, number>();
  for (const tok of tokenize(s)) {
    bag.set(tok, (bag.get(tok) ?? 0) + 1);
  }
  return bag;
}

export function cosineSimilarity(a: string, b: string): number {
  const A = bagOfWords(a);
  const B = bagOfWords(b);
  let dot = 0;
  for (const [tok, count] of A) {
    const bc = B.get(tok);
    if (bc !== undefined) dot += count * bc;
  }
  const normA = Math.sqrt(
    Array.from(A.values()).reduce((s, c) => s + c * c, 0)
  );
  const normB = Math.sqrt(
    Array.from(B.values()).reduce((s, c) => s + c * c, 0)
  );
  if (normA === 0 || normB === 0) return 0;
  return dot / (normA * normB);
}
