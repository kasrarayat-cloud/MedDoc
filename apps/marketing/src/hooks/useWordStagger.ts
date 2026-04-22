'use client';

import { useEffect, type RefObject } from 'react';

/**
 * Walk the subtree under `ref` and wrap every word in a `<span class="word-anim">`
 * with a staggered `animation-delay`. CSS handles the actual fade-up via the
 * `.word-anim` + `@keyframes charIn` rule in landing.css.
 *
 * Preserves existing element structure (so <em> and <br> survive), only the
 * text content is rewritten. Runs once — if `ref.current` changes, the hook
 * re-runs via the dep array.
 */
export function useWordStagger(
  ref: RefObject<HTMLElement | null>,
  options: { startDelay?: number; stepMs?: number } = {}
): void {
  const { startDelay = 100, stepMs = 70 } = options;

  useEffect(() => {
    const root = ref.current;
    if (!root) return;
    if (root.dataset.wordStaggered === '1') return;

    function wrap(node: Node, delay: number): number {
      let current = delay;
      for (const child of Array.from(node.childNodes)) {
        if (child.nodeType === Node.TEXT_NODE) {
          const text = child.textContent ?? '';
          if (!text) continue;
          const frag = document.createDocumentFragment();
          const parts = text.split(/(\s+)/);
          for (const part of parts) {
            if (!part) continue;
            if (/^\s+$/.test(part)) {
              frag.appendChild(document.createTextNode(part));
              continue;
            }
            const span = document.createElement('span');
            span.className = 'word-anim';
            span.textContent = part;
            current += stepMs;
            span.style.animationDelay = `${current}ms`;
            frag.appendChild(span);
          }
          child.parentNode?.replaceChild(frag, child);
        } else if (child.nodeType === Node.ELEMENT_NODE) {
          current = wrap(child, current);
        }
      }
      return current;
    }

    wrap(root, startDelay);
    root.dataset.wordStaggered = '1';
  }, [ref, startDelay, stepMs]);
}
