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
        # ⚠️ KEYED ON (NUMBER, RULING TEXT), NOT ON THE NUMBER ALONE — AND THE
        # ARM THAT FOUND THIS WAS ABOUT DELETING AMENDMENTS. The ledger records
        # a ruling's own clauses as their own rows under one number: `#116` has
        # three, `#131` has three. Keying on the number collapsed them to one, so
        # two clause rows arriving on OPPOSITE sides of a conflict lost one —
        # silently, and a lost amendment reads exactly like a ruling that never
        # had one.
        #
        # The ruling TEXT is cell 4 and is identical between a POINTER row and
        # its PROSE twin (the prose sits in an extra column), so the same ruling
        # still collapses to one row while different clauses stay apart.
        def key(l):
            c = cells(l)
            return (num(l), c[3].strip() if len(c) > 3 else '')

        o = {key(l): l for l in ours if num(l) is not None}
        t = {key(l): l for l in theirs if num(l) is not None}
        seen_o |= {k[0] for k in o}; seen_t |= {k[0] for k in t}
        merged = []
        for k in sorted(set(o) | set(t), key=lambda k: (k[0], k[1])):
            if k in o and k in t:
                # POINTER FORM WINS: fewer cells is the pointer row.
                merged.append(t[k] if len(cells(t[k])) <= len(cells(o[k])) else o[k])
            else:
                merged.append(t.get(k, o.get(k)))
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


def dedupe(path):
    """⚠️ THE WHOLE FILE, NOT JUST THE CONFLICT REGION — AND THIS GAP COST TWICE.

    `resolve()` unions the rows INSIDE the markers. git will have auto-merged
    identical or non-overlapping rows OUTSIDE them, so where one side's PROSE
    row auto-merged and this script emitted the POINTER row for the same ruling,
    BOTH landed. Measured twice on one branch: 18 duplicate rows the first time,
    18 again after the next merge, each caught only by `gate-ruling-row-identity`
    downstream.

    Two shapes, and the second is the one the first pass missed:
      · POINTER + PROSE — different cell counts, same leading cells;
      · the SAME row twice — identical cell count AND identical text.

    ⚠️ AND THE CLAUSE ROWS ARE NOT DUPLICATES. `#106`, `#109`, `#115`, `#116`
    (x3) and `#131` (x3) legitimately share a number: the ledger records a
    ruling's own clauses and corrections as their own rows. They have the same
    shape and DIFFERENT text, so the text comparison is what keeps a dedupe from
    deleting recorded amendments.
    """
    lines = open(path).read().split('\n')
    cells = lambda l: l.split('|')[1:-1]
    groups = {}
    for i, l in enumerate(lines):
        m = ROW.match(l)
        if m:
            groups.setdefault(int(m.group(1)), []).append(i)
    drop = set()
    for _, idxs in groups.items():
        if len(idxs) < 2:
            continue
        for a in idxs:
            for b in idxs:
                if a >= b or a in drop or b in drop:
                    continue
                ca, cb = cells(lines[a]), cells(lines[b])
                lead = lambda c: [x.strip() for x in c[:3]]
                if len(ca) == len(cb):
                    if [x.strip() for x in ca[:4]] == [x.strip() for x in cb[:4]]:
                        drop.add(b)          # the same row twice
                elif lead(ca) == lead(cb):
                    drop.add(a if len(ca) > len(cb) else b)   # keep the POINTER
    if drop:
        open(path, 'w').write('\n'.join(l for i, l in enumerate(lines) if i not in drop))
        print(f'  deduped {len(drop)} row(s) that auto-merged OUTSIDE the conflict region')
    return len(drop)


def repo_root_of(path):
    """The repository that OWNS this file — never the caller's cwd."""
    d = os.path.dirname(os.path.abspath(path)) or '.'
    r = subprocess.run(['git', 'rev-parse', '--show-toplevel'],
                       cwd=d, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def stage_membership(path):
    """
    WHOLE-FILE membership of each side, from the MERGE INDEX.

    ⚠️ THIS IS THE UNIVERSE THE LOST/INVENTED CHECKS MUST ASK ABOUT, AND THE
    FIRST VERSION ASKED THE CONFLICT REGION INSTEAD. A real ledger conflict has
    hundreds of rows OUTSIDE the markers; measured against region membership,
    every one of them is "invented", so the resolver refuses every real merge it
    was built for. Its arms could not see this because they all construct files
    where the whole file IS the region.

    Stages 2 and 3 are ours and theirs as git recorded them, so they are the
    authoritative whole-file sides and need no ref to be named by hand.
    Returns None when they cannot be read — which the caller treats as
    CANNOT-TELL, not as agreement.
    """
    root = repo_root_of(path)
    if root is None:
        return None
    rel = os.path.relpath(os.path.abspath(path), root)
    out = []
    for stage in (2, 3):
        r = subprocess.run(['git', 'show', f':{stage}:{rel}'],
                           cwd=root, capture_output=True, text=True)
        if r.returncode != 0:
            return None
        out.append(nums_of(r.stdout))
    return out[0], out[1]


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
    dedupe(path)
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

    # ── the WHOLE-FILE sides, which is the universe these checks are about ──
    root = repo_root_of(path)
    stages = stage_membership(path)
    universe = None
    if stages is not None:
        s_o, s_t = stages
        universe = s_o | s_t
        print(f'  whole-file sides: ours={len(s_o)} theirs={len(s_t)}')
        for label, want in (('ours', s_o), ('theirs', s_t)):
            lost = sorted(want - after)
            if lost:
                print(f'🔴 LOST from whole-file {label}: {lost}'); bad = True

    for ref in refs:
        # ⚠️ IN THE FILE'S OWN REPOSITORY. Run from elsewhere, `git show` answers
        # about the CALLER's repo — where the ref may not exist — and the check
        # was silently weaker rather than refusing.
        txt = subprocess.run(['git', 'show', f'{ref}:{path}'],
                             cwd=root or '.', capture_output=True, text=True).stdout
        rn = nums_of(txt)
        universe = rn if universe is None else (universe | rn)
        lost = sorted(rn - after)
        if lost:
            print(f'🔴 LOST vs {ref}: {lost}'); bad = True
        else:
            print(f'  ✔ every ruling on {ref} survives')

    # ⚠️ FAIL CLOSED ON CANNOT-TELL. No merge stages and no refs means there is
    # no whole-file side to compare against — and the previous form quietly fell
    # back to the CONFLICT REGION, which reports every untouched row as invented.
    # A weaker answer given silently is the failure this repo has a name for.
    if universe is None:
        print('🔴 CANNOT TELL — no merge stages for this path and no refs given, '
              'so there is no whole-file side to verify against. Run it on a file '
              'with an unresolved merge, or name refs explicitly.')
        bad = True
    else:
        invented = sorted(after - universe)
        if invented:
            print(f'🔴 INVENTED (on neither side): {invented}'); bad = True
    print(f'  rulings after: {len(after)}   chars: {len(after_txt)}')
    if bad:
        print('🔴 REFUSING — this is not a union.'); sys.exit(2)
    print('🟢 union verified by membership')

main()
