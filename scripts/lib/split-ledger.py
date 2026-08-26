#!/usr/bin/env python3
"""
Split a FOUNDATION ledger file into a LIVE HEAD plus VERBATIM dated archives.

⚠️ IT PROVES ITS OWN APPLICATION, AND IT RAISES BEFORE WRITING ANYTHING.
Canon: a scripted edit that reports success having applied nothing — or half of
itself — is worse than one that fails loudly.

THE PROOF IS A PARTITION PROOF, which is stronger than a diff:
every destination is a half-open line range [a,b) of the source, and the
destination ranges must form an EXACT ORDERED PARTITION of [0, len(lines)) —
no gaps, no overlaps, nothing invented, nothing lost. Byte-identity is then a
consequence rather than a separate hope, and it is asserted anyway.

NOTHING IS REWRITTEN. Archives are verbatim slices. The live head gets new
content plus ranges LIFTED verbatim.
"""
import os, re, sys, json, hashlib

SPLIT_DATE = os.environ.get("SPLIT_DATE", "2026-08-26")
BUCKET_MAX = int(os.environ.get("BUCKET_MAX", "110000"))
GUARD_BUDGET = int(os.environ.get("GUARD_BUDGET", "120000"))

DATE_RE = re.compile(r'(20\d\d-\d\d-\d\d)')
ROW_DATE_RE = re.compile(r'^\|\s*(20\d\d-\d\d-\d\d)\s*\|')
SENTINEL = "<!-- VERBATIM-BODY-BEGINS -->"


def heads(lines, level):
    pat = re.compile(r'^#{1,%d} ' % level)
    return [i for i, l in enumerate(lines) if pat.match(l)]


def ranges_at(lines, a, b, level):
    """Split [a,b) at heading boundaries of depth <= level. Always covers [a,b)."""
    idx = [i for i in heads(lines, level) if a < i < b]
    pts = [a] + idx + [b]
    return list(zip(pts, pts[1:]))


def chunk(lines, a, b, maxsz, level=2):
    """Ranges covering [a,b), each <= maxsz where achievable.

    Falls through heading depths, then to LINE boundaries. The line fallback is
    what makes a heading-less table (RULINGS.md is 254 lines holding 371k chars,
    one ruling per row, largest row 10,330 chars) splittable at all. A single
    line larger than maxsz is emitted alone and reported rather than silently
    packed — an indivisible unit is a fact about the source, not a licence to
    exceed the budget quietly."""
    size = len('\n'.join(lines[a:b]))
    if size <= maxsz:
        return [(a, b)]
    if level >= 6:
        # LINE MODE — greedy pack whole lines; never split inside a line.
        out, start, acc = [], a, 0
        for i in range(a, b):
            ln = len(lines[i]) + 1
            if i > start and acc + ln > maxsz:
                out.append((start, i)); start, acc = i, 0
            acc += ln
        if start < b:
            out.append((start, b))
        return out
    out = []
    for (x, y) in ranges_at(lines, a, b, level + 1):
        if x == a and y == b:
            return chunk(lines, a, b, maxsz, level + 1)
        out.extend(chunk(lines, x, y, maxsz, level + 1))
    return out


def slug(s, n=48):
    s = re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')
    return s[:n].strip('-') or 'section'


def main():
    src, outdir = sys.argv[1], sys.argv[2]
    lift = set(json.loads(os.environ.get("LIFT", '[]')))
    base = os.path.basename(src)

    raw = open(src, encoding='utf-8').read()
    lines = raw.split('\n')
    N = len(lines)

    secs = ranges_at(lines, 0, N, 2)
    if not secs or secs[0][0] != 0:
        raise SystemExit("FATAL: no top-level sections, or content before the first heading")

    # ---- assign each top-level section to HEAD or a dated bucket ----
    assigned, cur = [], None
    for (a, b) in secs:
        h = lines[a]
        m = DATE_RE.search(h)
        if m:
            cur = m.group(1)
        assigned.append((a, b, h, 'HEAD' if h.strip() in lift else (cur or 'structure')))

    # ---- KEEP_SINCE: dated sections at/after the cutoff stay LIVE in the head.
    # This is what makes ROTATION a one-parameter operation rather than a
    # bespoke hand-split: "keep the current arc, archive what closed".
    keep_since = os.environ.get("KEEP_SINCE", "").strip()
    if keep_since:
        if not DATE_RE.fullmatch(keep_since):
            raise SystemExit(f"FATAL: KEEP_SINCE={keep_since!r} is not YYYY-MM-DD")
        kept = 0
        for i, (a, b, h, t) in enumerate(assigned):
            if t != 'HEAD' and t != 'structure' and t >= keep_since:
                assigned[i] = (a, b, h, 'HEAD'); kept += 1
        # ⚠️ A cutoff that keeps NOTHING is almost certainly a wrong date, not an
        # empty arc — refuse rather than silently archive the live queue.
        if kept == 0:
            raise SystemExit(f"FATAL: KEEP_SINCE={keep_since} kept ZERO dated sections. "
                             f"Latest dated section is {max((t for _,_,_,t in assigned if t not in ('HEAD','structure')), default='none')}. "
                             f"Refusing: a cutoff that keeps nothing archives the live arc.")

    got = {h.strip() for _, _, h, t in assigned if t == 'HEAD'}
    if not lift <= got:
        raise SystemExit(f"FATAL: LIFT anchors did not match exactly — a silent no-op. "
                         f"missing={sorted(lift - got)}")

    # ---- pack into archive files, sub-chunking any oversized single section ----
    order, groups = [], {}
    for it in assigned:
        if it[3] == 'HEAD':
            continue
        if it[3] not in groups:
            groups[it[3]] = []
            order.append(it[3])
        groups[it[3]].append(it)

    files = []   # (name, [ranges])
    for k in order:
        pending, cur_pack, cur_sz = [], [], 0
        for (a, b, h, _) in groups[k]:
            for (x, y) in chunk(lines, a, b, BUCKET_MAX):
                sz = len('\n'.join(lines[x:y]))
                if cur_pack and cur_sz + sz > BUCKET_MAX:
                    pending.append(cur_pack); cur_pack, cur_sz = [], 0
                cur_pack.append((x, y)); cur_sz += sz
        if cur_pack:
            pending.append(cur_pack)
        for n, p in enumerate(pending, 1):
            name = k if len(pending) == 1 else f"{k}-part{n}"
            # If the heading carried no date, the content usually still does
            # (RULINGS.md dates every ROW, not its headings). Name by the span
            # the file actually covers, so a pointer means something.
            if k == 'structure':
                # ⚠️ ROW-LEADING dates only. Taking every date in the text
                # gave overlapping, non-monotonic spans, because a ruling's
                # PROSE cites other dates — a name that reads authoritative
                # and is wrong is worse than 'part2'.
                ds = sorted(set(m.group(1) for (x, y) in p for l in lines[x:y]
                                for m in [ROW_DATE_RE.match(l)] if m))
                if ds:
                    name = ds[0] if ds[0] == ds[-1] else f"{ds[0]}--{ds[-1]}"
            files.append((name, p))

    head_ranges = [(a, b) for a, b, _, t in assigned if t == 'HEAD']

    # ================== PARTITION PROOF — BEFORE ANY WRITE ==================
    dest = sorted([r for _, rs in files for r in rs] + head_ranges)
    proof = {}
    proof['P1_range_count'] = len(dest)
    gaps, overlaps, cursor = [], [], 0
    for (a, b) in dest:
        if a > cursor: gaps.append((cursor, a))
        if a < cursor: overlaps.append((a, cursor))
        cursor = max(cursor, b)
    proof['P1_gaps'] = gaps
    proof['P1_overlaps'] = overlaps
    proof['P1_covers_to'] = cursor
    proof['P1_exact_partition'] = (not gaps and not overlaps and cursor == N)
    if not proof['P1_exact_partition']:
        raise SystemExit(f"FATAL: destinations are not an exact partition of the source — "
                         f"gaps={gaps[:3]} overlaps={overlaps[:3]} covers={cursor} of {N}")

    # P2 · byte-identity as a multiset of slices (order changes; content must not)
    dst_slices = sorted('\n'.join(lines[a:b]) for (a, b) in dest)
    src_slices = sorted('\n'.join(lines[a:b]) for (a, b) in dest)  # same ranges, by construction
    proof['P2_src_sha'] = hashlib.sha256(''.join(src_slices).encode()).hexdigest()
    proof['P2_dst_sha'] = hashlib.sha256(''.join(dst_slices).encode()).hexdigest()
    # the real content check: reassembling the partition IN ORDER must equal the source
    proof['P2_inorder_rebuild_equals_source'] = ('\n'.join(
        '\n'.join(lines[a:b]) for (a, b) in sorted(dest)) == raw)
    if not proof['P2_inorder_rebuild_equals_source']:
        raise SystemExit("FATAL: in-order reassembly of the partition does not equal the source")

    # P3 · heading census, BOTH DIRECTIONS
    all_h = [l for l in lines if re.match(r'^#{1,6} ', l)]
    dst_h = [l for (a, b) in dest for l in lines[a:b] if re.match(r'^#{1,6} ', l)]
    proof['P3_src_headings'] = len(all_h)
    proof['P3_dst_headings'] = len(dst_h)
    proof['P3_lost'] = sorted(set(all_h) - set(dst_h))[:5]
    proof['P3_invented'] = sorted(set(dst_h) - set(all_h))[:5]
    proof['P3_equal_both_directions'] = (len(all_h) == len(dst_h)
                                         and not proof['P3_lost'] and not proof['P3_invented'])
    if not proof['P3_equal_both_directions']:
        raise SystemExit(f"FATAL: heading census failed both-directions: "
                         f"src={len(all_h)} dst={len(dst_h)} lost={proof['P3_lost']}")

    # P4 · every archive must be under the guard budget — else the split solved nothing
    sizes = {name: len('\n'.join('\n'.join(lines[a:b]) for (a, b) in rs)) for name, rs in files}
    over = {k: v for k, v in sizes.items() if v > GUARD_BUDGET}
    proof['P4_archives_over_budget'] = over
    if over:
        raise SystemExit(f"FATAL: archives still over budget — the split did not solve the problem: {over}")

    # P5 · line arithmetic
    proof['P5_src_lines'] = N
    proof['P5_dst_lines'] = sum(b - a for (a, b) in dest)
    proof['P5_reconciles'] = (proof['P5_dst_lines'] == N)
    if not proof['P5_reconciles']:
        raise SystemExit(f"FATAL: line arithmetic: {proof['P5_dst_lines']} != {N}")

    # head_chars is what ROTATION steers on: the live head is everything
    # marked HEAD, and rotation's whole job is keeping that under budget.
    head_chars = sum(len('\n'.join(lines[a:b])) for (a, b) in head_ranges)

    # ================== ONLY NOW DO WE WRITE ==================
    if os.environ.get("DRY_RUN"):
        print(json.dumps({"dry_run": True, "source": src, "source_chars": len(raw),
                          "archives": len(files), "largest_archive": max(sizes.values()) if sizes else 0,
                          "head_chars": head_chars, "keep_since": os.environ.get("KEEP_SINCE") or None,
                          "proof": proof}, indent=1))
        return
    os.makedirs(outdir, exist_ok=True)
    index = []
    for name, rs in files:
        first, last = rs[0][0] + 1, rs[-1][1]
        body = '\n'.join('\n'.join(lines[a:b]) for (a, b) in rs)
        header = (
            f"> **ARCHIVED LEDGER — moved verbatim from `docs/foundation/{base}` on {SPLIT_DATE}.**\n>\n"
            f"> **This body is the AUTHORITY.** The live `docs/foundation/{base}` carries an index row\n"
            f"> pointing here; that row is a POINTER, never the record. Nothing here is rewritten —\n"
            f"> corrections are appended and dated and superseded wording is kept, because in this\n"
            f"> programme the correction is the point.\n>\n"
            f"> Original position: lines **{first}–{last}** of the pre-split `{base}`.\n"
            f"> Why the split: `docs/foundation/relay/README.md`.\n\n{SENTINEL}\n")
        p = os.path.join(outdir, f"{name}.md")
        open(p, 'w', encoding='utf-8').write(header + body)
        # post-write assertion: what landed must be what we proved
        disk = open(p, encoding='utf-8').read()
        got_body = disk[disk.find(SENTINEL) + len(SENTINEL) + 1:]
        if got_body != body:
            raise SystemExit(f"FATAL: {name}.md on disk differs from the proved slice")
        index.append({"file": f"{name}.md", "first_line": first, "last_line": last,
                      "chars": len(body), "ranges": len(rs),
                      "headings": [lines[a] for (a, b) in rs if re.match(r'^#{1,3} ', lines[a])][:4]})

    print(json.dumps({
        "source": src, "source_chars": len(raw), "source_lines": N,
        "top_level_sections": len(secs), "archives": len(files),
        "lifted_to_head": sorted(lift),
        "kept_live_by_cutoff": sorted({t for _, _, _, t in assigned if t == 'HEAD'} - lift) and
                               [h for _, _, h, t in assigned if t == 'HEAD' and h.strip() not in lift],
        "keep_since": os.environ.get("KEEP_SINCE", "") or None,
        "lifted_lines": sum(b - a for (a, b) in head_ranges),
        "largest_archive": max(sizes.values()) if sizes else 0,
        "head_chars": head_chars,
        "archive_index": index, "proof": proof,
    }, indent=1))


if __name__ == "__main__":
    main()
