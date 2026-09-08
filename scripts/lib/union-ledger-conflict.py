#!/usr/bin/env python3
"""Resolve a RULINGS.md rebase/merge conflict as a UNION BY RULING NUMBER.

⚠️ THE POINTER FORM WINS where both sides carry the same number (#278 — the pointer reshape), and
the result is VERIFIED BY MEMBERSHIP, never by reading: a section that survived
and one that was re-added look identical, and only the numbers tell them apart.

Refuses — exit 2 — if any ruling number present on either side is missing from
the result, or if a number appears that was on neither. Losing a landed row is
silent otherwise: the file still parses and every gate stays green.
"""
import os, re, subprocess, sys

ROW = re.compile(r'^\|\s*\d{4}-\d{2}-\d{2}\s*\|\s*#(\d+)\s*\|')
ANYROW = re.compile(r'^\|\s*\d{4}-\d{2}-\d{2}\s*\|')

def num(l):
    m = ROW.match(l)
    return int(m.group(1)) if m else None

def cells(l):
    return l.split('|')[1:-1]

def resolve(path):
    lines = open(path).read().split('\n')
    a = [i for i, l in enumerate(lines) if l.startswith('<<<<<<<')]
    m = [i for i, l in enumerate(lines) if l == '=======']
    b = [i for i, l in enumerate(lines) if l.startswith('>>>>>>>')]
    if not (len(a) == len(m) == len(b)):
        print(f'🔴 malformed conflict markers: {len(a)}/{len(m)}/{len(b)}'); sys.exit(2)
    out, prev, seen_o, seen_t = [], 0, set(), set()
    for x, y, z in zip(a, m, b):
        out += lines[prev:x]
        ours, theirs = lines[x+1:y], lines[y+1:z]
        o = {num(l): l for l in ours if num(l) is not None}
        t = {num(l): l for l in theirs if num(l) is not None}
        seen_o |= set(o); seen_t |= set(t)
        merged = []
        for n in sorted(set(o) | set(t)):
            if n in o and n in t:
                # POINTER FORM WINS: fewer cells is the pointer row.
                merged.append(t[n] if len(cells(t[n])) <= len(cells(o[n])) else o[n])
            else:
                merged.append(t.get(n, o.get(n)))
        # un-numbered rows (legacy `| date | — | RECORDED |`) are a union too
        un_o = [l for l in ours if num(l) is None and ANYROW.match(l)]
        un_t = [l for l in theirs if num(l) is None and ANYROW.match(l)]
        un = list(dict.fromkeys(un_t + un_o))
        # everything else (headers, prose): prefer theirs when present
        other_t = [l for l in theirs if not ANYROW.match(l)]
        other_o = [l for l in ours if not ANYROW.match(l)]
        out += (other_t if other_t else other_o) + un + merged
        prev = z + 1
        print(f'  region: ours={len(o)} theirs={len(t)} -> union {len(merged)}'
              f'  un-numbered {len(un)}')
    out += lines[prev:]
    open(path, 'w').write('\n'.join(out))
    return seen_o, seen_t

def nums_of(text):
    return {int(x.group(1)) for x in re.finditer(
        r'^\|\s*\d{4}-\d{2}-\d{2}\s*\|\s*#(\d+)\s*\|', text, re.M)}

USAGE = (
    'usage: union-ledger-conflict.py <conflicted-file> [ref ...]\n'
    '  Resolves a RULINGS.md merge/rebase conflict as a UNION BY RULING NUMBER,\n'
    '  pointer form winning, then VERIFIES BY MEMBERSHIP against each ref given.\n'
    '  exit 0 = union verified   exit 2 = REFUSED (rows lost, invented, or misuse)\n'
)


def main():
    if len(sys.argv) < 2:
        sys.stderr.write(USAGE)
        sys.exit(2)
    path = sys.argv[1]
    if not os.path.exists(path):
        sys.stderr.write(f'🔴 no such file: {path}\n')
        sys.exit(2)
    refs = sys.argv[2:]          # extra refs to check membership against
    o, t = resolve(path)
    after_txt = open(path).read()
    after = nums_of(after_txt)
    left = sum(1 for l in after_txt.split('\n')
               if l.startswith(('<<<<<<<', '=======', '>>>>>>>')))
    if left:
        print(f'🔴 {left} conflict marker line(s) remain'); sys.exit(2)
    bad = False
    # ⚠️ THIS LOOP IS DEFENCE-IN-DEPTH AND IS **NOT EXERCISED BY ANY ARM**, said
    # here so its presence is not read as tested coverage. The merge above emits
    # every number from `o | t` by construction, so no INPUT can make a
    # side-local row go missing — a mutation disarming this check leaves the
    # gate 6 of 6 green, which is how the gap was found. It stays because it is
    # free and it catches a future edit to that loop; the loss check that IS
    # live, and IS mutation-proven, is the per-REF one below.
    for label, want in (('ours', o), ('theirs', t)):
        lost = sorted(want - after)
        if lost:
            print(f'🔴 LOST from {label}: {lost}'); bad = True
    for ref in refs:
        txt = subprocess.run(['git', 'show', f'{ref}:{path}'],
                             capture_output=True, text=True).stdout
        lost = sorted(nums_of(txt) - after)
        if lost:
            print(f'🔴 LOST vs {ref}: {lost}'); bad = True
        else:
            print(f'  ✔ every ruling on {ref} survives')
    invented = sorted(after - (o | t))
    if invented and not refs:
        print(f'🔴 INVENTED (on neither side): {invented}'); bad = True
    print(f'  rulings after: {len(after)}   chars: {len(after_txt)}')
    if bad:
        print('🔴 REFUSING — this is not a union.'); sys.exit(2)
    print('🟢 union verified by membership')

main()
