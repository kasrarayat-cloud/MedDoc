#!/usr/bin/env python3
"""Refresh the self-hosted fonts, reproducing EXACTLY what is committed.

Why these files are committed at all: `next/font/google` fetches font CSS from
Google's servers during `next build`, and when that fetch fails the build dies
with `Module not found: '@vercel/turbopack-next/internal/font/google/font'`
pointing at layout.tsx — a network fault wearing a compile error's clothes.
See AGENTS.md, "an external reach in the build is REMOVED, not retried".

Run from anywhere:  python3 scripts/fetch-self-hosted-fonts.py [--check]

  (no flag)  rewrite the font files in place
  --check    fetch to a temp dir and DIFF against what is committed; exit 1 on
             any difference. Use this to find out whether upstream has changed
             without touching the tree.

⚠️ TWO TRAPS THIS SCRIPT ENCODES, BOTH OF WHICH COST A ROUND:

 1. MOST of these families are VARIABLE fonts. Google emits a separate
    @font-face per requested weight, and every one points at the SAME file. A
    naive per-weight fetch downloads N files of which N-1 are exact duplicates.
    Those families are marked `variable=True` and produce ONE file, declared in
    the layout with a weight RANGE.

 2. IBM PLEX MONO IS NOT VARIABLE. Its 400/500/600 are three genuinely
    different files. Declaring it as a range would load one weight and let the
    browser synthesise the others — a page that looks nearly right. It is
    marked `variable=False` and produces one file per weight.

The `variable` flag is ASSERTED against the downloaded bytes, not trusted: a
family that changes shape upstream fails loudly here rather than silently
shipping the wrong declaration.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# dest dir -> [(google family, weights, styles, variable?, committed basename)]
APPS: dict[str, list[tuple[str, list[str], list[str], bool, str]]] = {
    "apps/transcribe-md/src/app/fonts": [
        ("Inter", ["400", "500", "600", "700"], ["normal"], True, "inter-latin"),
        ("JetBrains+Mono", ["400", "500"], ["normal"], True, "jetbrains-mono-latin"),
        ("Bricolage+Grotesque", ["500", "600", "700"], ["normal"], True, "bricolage-grotesque-latin"),
        ("Figtree", ["400", "500", "600"], ["normal"], True, "figtree-latin"),
        ("Source+Serif+4", ["400", "600"], ["normal", "italic"], True, "source-serif-4-latin"),
    ],
    "apps/marketing/src/app/fonts": [
        ("Inter", ["400", "500", "600", "700"], ["normal"], True, "inter-latin"),
        ("JetBrains+Mono", ["400", "500"], ["normal"], True, "jetbrains-mono-latin"),
        ("Manrope", ["200", "300", "400", "500", "600", "700", "800"], ["normal"], True, "manrope-latin"),
        ("IBM+Plex+Mono", ["400", "500", "600"], ["normal"], False, "ibm-plex-mono-latin"),
    ],
}

BLOCK = re.compile(
    r"/\*\s*(?P<subset>[a-z0-9\-\[\] ]+)\s*\*/\s*@font-face\s*\{(?P<body>[^}]*)\}", re.I
)


def css_for(fam: str, weights: list[str], styles: list[str]) -> str:
    if styles == ["normal"]:
        q = f"{fam}:wght@{';'.join(weights)}"
    else:
        pairs = sorted(f"{0 if s == 'normal' else 1},{w}" for s in styles for w in weights)
        q = f"{fam}:ital,wght@{';'.join(pairs)}"
    url = f"https://fonts.googleapis.com/css2?family={q}&display=swap"
    r = subprocess.run(
        ["curl", "-sS", "--max-time", "40", "-H", f"User-Agent: {UA}", url],
        capture_output=True, text=True,
    )
    if r.returncode != 0 or "@font-face" not in r.stdout:
        raise SystemExit(f"🔴 {fam}: could not fetch CSS ({r.stderr[:160]})")
    return r.stdout


def latin_urls(css: str) -> dict[tuple[str, str], str]:
    """{(style, weight): url} for the LATIN subset only.

    Exact match on 'latin' — 'latin-ext' is a different file for a subset the
    apps do not request, and a substring test would quietly prefer it.
    """
    out: dict[tuple[str, str], str] = {}
    for m in BLOCK.finditer(css):
        if m.group("subset").strip().lower() != "latin":
            continue
        body = m.group("body")
        w = re.search(r"font-weight:\s*(\d+)", body)
        s = re.search(r"font-style:\s*(\w+)", body)
        u = re.search(r"src:\s*url\((https://[^)]+\.woff2)\)", body)
        if w and u:
            out[(s.group(1) if s else "normal", w.group(1))] = u.group(1)
    return out


def download(url: str, path: str) -> bytes:
    r = subprocess.run(["curl", "-sS", "--max-time", "60", "-o", path, url], capture_output=True)
    if r.returncode != 0:
        raise SystemExit(f"🔴 download failed: {url}")
    data = open(path, "rb").read()
    # wOF2 is the woff2 magic number. A captive portal or an error page would
    # download happily and be committed as a font, failing only in a browser.
    if data[:4] != b"wOF2":
        raise SystemExit(f"🔴 {path}: not a woff2 (magic={data[:4]!r})")
    if not 5_000 < len(data) < 400_000:
        raise SystemExit(f"🔴 {path}: implausible size {len(data)}")
    return data


def run(dest_rel: str, specs, outdir: str) -> list[str]:
    os.makedirs(outdir, exist_ok=True)
    names: list[str] = []
    for fam, weights, styles, variable, base in specs:
        urls = latin_urls(css_for(fam, weights, styles))
        want = [(s, w) for s in styles for w in weights]
        missing = [k for k in want if k not in urls]
        if missing:
            raise SystemExit(f"🔴 {fam}: latin subset missing {missing}")

        distinct_per_style = {
            style: {urls[(style, w)] for w in weights} for style in styles
        }
        if variable:
            # ASSERTED, not trusted: one url per style, or the family changed shape.
            for style, u in distinct_per_style.items():
                if len(u) != 1:
                    raise SystemExit(
                        f"🔴 {fam} is declared VARIABLE but style '{style}' returned "
                        f"{len(u)} distinct files. Upstream changed — fix the flag AND "
                        f"the weight declaration in the layout before committing."
                    )
            for style in styles:
                suffix = "" if style == "normal" else f"-{style}"
                name = f"{base}{suffix}.woff2"
                download(urls[(style, weights[0])], os.path.join(outdir, name))
                names.append(name)
        else:
            seen: dict[str, str] = {}
            for style, w in want:
                name = f"{base}-{w}.woff2"
                data = download(urls[(style, w)], os.path.join(outdir, name))
                seen[w] = hashlib.md5(data).hexdigest()
                names.append(name)
            if len(set(seen.values())) != len(seen):
                raise SystemExit(
                    f"🔴 {fam} is declared STATIC but its weights are byte-identical "
                    f"({seen}). It became a variable font upstream — collapse it to one "
                    f"file and a weight range, in the layout too."
                )
    return sorted(names)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="diff against what is committed; do not write")
    args = ap.parse_args()

    failed = False
    for rel, specs in APPS.items():
        dest = os.path.join(ROOT, rel)
        if args.check:
            tmp = tempfile.mkdtemp(prefix="fonts-check-")
            try:
                names = run(rel, specs, tmp)
                for n in names:
                    a, b = os.path.join(tmp, n), os.path.join(dest, n)
                    if not os.path.exists(b):
                        print(f"  🔴 {rel}/{n}: committed file MISSING"); failed = True
                    elif open(a, "rb").read() != open(b, "rb").read():
                        print(f"  🔴 {rel}/{n}: DIFFERS from upstream"); failed = True
                    else:
                        print(f"  ✅ {rel}/{n}")
                extra = sorted(
                    f for f in os.listdir(dest)
                    if f.endswith(".woff2") and f not in names
                )
                for f in extra:
                    print(f"  🟡 {rel}/{f}: committed but no longer fetched"); failed = True
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
        else:
            names = run(rel, specs, dest)
            for n in names:
                print(f"  wrote {rel}/{n}  ({os.path.getsize(os.path.join(dest, n)):,} B)")
    if args.check:
        print("🔴 fonts differ from upstream" if failed else "🟢 fonts match upstream")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
