"""Code-mutation sensitivity of the self-tests: each mutated COPY of ticked.py must make the fast suite fail.

    /opt/meddoc-pro/rebuild/.venv/bin/python codemut_sensitivity.py

C1-C16 are v2.0's mutations (C4 and C11 re-anchored to v2.1's code, same mutation); C17-C32 mutate the v2.1
readings; C33-C35 the inserted-mark reading tightened in v2.1; C36 the typed-bracket-box recognition.
Every mutation must apply exactly once (else the whole proof aborts), the baseline must pass first, and the copies'
tests write their results into the copy's own directory. Work happens under TICKED_OUT (default: the scratch
directory), never next to this file; the mutated copies are removed afterwards. Runs one mutant at a time
(TICKED_JOBS, default 1: the host is shared).
"""
import concurrent.futures, hashlib, os, pathlib, shutil, subprocess, sys
H = pathlib.Path(__file__).resolve().parent
PY = "/opt/meddoc-pro/rebuild/.venv/bin/python"
OUT = pathlib.Path(os.environ.get("TICKED_OUT") or "/tmp/claude-1000/-opt-meddoc-pro/64d93580-8414-4553-b17d-ed04b0550ae1/scratchpad/v1/harness-v21/out").resolve()
for d in (OUT,) + tuple(OUT.parents):
    if (d / ".git").exists():
        raise SystemExit("refusing to work inside a git work tree: %s" % OUT)
src = (H / "ticked.py").read_text()
M = {
 "C0-baseline": [],
 "C1-orphan-rule-removed": [("    for li, k in tie.orphans:", "    for li, k in []:")],
 "C2-sdt-display-check-removed": [("    if not (len(shown) == 1 and ord(shown) in (want, want & 0xFF, 0xF000 | (want & 0xFF))):", "    if False:")],
 "C3-any-inserted-glyph-is-a-mark": [('    if t.k == "glyph" and t.ch == INSERTED_MARK and t.state is True:', '    if t.k == "glyph":')],
 "C4-unexplained-mark-scan-removed": [("            if (t.is_box or t.is_control) and j not in explained.get(li, set()) and region.export_key(li, j) not in foreign_marks:", "            if False:")],
 "C5-conflict-guard-removed": [("        if len(ids) > 1:", "        if len(ids) > 99:")],
 "C6-unreadable-glyph-read-unticked": [('        return Tok("glyph", ch=c, state=None, desc="U+%04X %s outside the glyph table" % (ord(c), c))', '        return Tok("glyph", ch=c, state=False, desc="U+%04X %s outside the glyph table" % (ord(c), c))')],
 "C7-cell-anything-is-ticked": [('    return None, "the cell holds %r (not exactly one of X x ✓ ✔ ☒)" % shown[:30]', '    return True, ""')],
 "C8-list-entries-check-removed": [("        if e0 != e1:", "        if False:")],
 "C9-word-boundary-removed": [("        if not (needle[0].isalnum() and before.isalnum()) and not (needle[-1].isalnum() and after.isalnum()):", "        if True:")],
 "C10-ff-odd-value-unticked": [('        return None, "legacy checkbox w:checked w:val=%r" % v', '        return False, ""')],
 "C11-sym-table-ignores-font": [("    low = value - 0xF000 if 0xF000 <= value <= 0xF0FF else value\n    table = SYM_GLYPHS.get(font)", '    low = value - 0xF000 if 0xF000 <= value <= 0xF0FF else value\n    table = SYM_GLYPHS["wingdings"]')],
 "C12-symbol-font-wt-read-as-text": [("    if symbol_fonts:\n        if c.isspace()", "    if False:\n        if c.isspace()")],
 "C13-invisible-runs-read": [("        hid = invisible(pkg, r)", '        hid = ""')],
 "C14-bordered-blank-not-a-box": [("        if visible() and bordered_blank(r):", "        if False:")],
 "C15-numbering-bullets-ignored": [("    return pkg.numbering.bullet_tokens(p) + toks", "    return toks")],
 "C16-ff-dropdown-cached-result-ignored": [("    if ws(\"\".join(cached)) and ws(\"\".join(cached)) != shown:", "    if False:")],
 # ── v2.1 ──
 "C17-r2-slot-mark-removed": [('            elif not got and not o.startswith("\\x00"):', "            elif False:")],
 "C18-r2-slot-mark-searched-in-every-slot": [("    for li, own in region.slot_lines[s]:", "    for li, own in [(i, region.own[i]) for i in range(len(region.lines0))]:")],
 "C19-r2-longer-option-check-in-slot-removed": [("            if len(n2) > len(needle) and any(c <= a and b <= d for c, d in occurrences(text, n2)):", "            if False:")],
 "C20-r3-font-table-check-removed": [("    if not pkg.symbol_charset(font):", "    if False:")],
 "C21-r3-only-ascii-slot-read": [('    names = {(fonts.get(s) or "").strip().lower() for s in drawing_slots(fonts, c)}', '    names = {(fonts.get("ascii") or "").strip().lower()}')],
 "C22-r3-text-forms-never-read": [('    return Tok("glyph", ch=c, state=table[low], desc="w:t %s %02X" % (font, low))', '    return Tok("glyph", ch=c, state=None, desc="w:t %s %02X" % (font, low))')],
 "C23-r4-white-circle-read-ticked": [('                  "○": False,      # ○ WHITE CIRCLE', '                  "○": True,       # ○ WHITE CIRCLE')],
 "C24-r4-black-circle-read-unticked": [('                  "●": True}       # ● BLACK CIRCLE', '                  "●": False}      # ● BLACK CIRCLE')],
 "C25-r5-foreign-boxes-not-excluded": [("        if region.global_key(li, k) in foreign:", "        if False:")],
 "C26-r5-foreign-marks-not-excluded": [(" and region.export_key(li, j) not in foreign_marks:", ":")],
 "C27-r5-untied-boxes-treated-as-foreign": [("        return bool(ids) and self.qid not in ids", "        return self.qid not in (ids or ())")],
 "C28-r5-conflicted-questions-own-boxes": [('        if area["id"] in conflicted:\n            continue\n        for x in t.ties:', '        for x in t.ties:')],
 "C29-r6-cell-text-case-insensitive": [('    hits = [i for i, o in enumerate(options) if o.strip() == text]', '    hits = [i for i, o in enumerate(options) if o.strip().lower() == text.lower()]')],
 "C30-r6-cell-text-removed": [("    if len(slots) == 1 and len(options) >= 2 and region.cell_slot.get(slots[0]):", "    if False:")],
 "C31-r6-wrong-label-read-unverifiable": [('                fails.append("the cell shows %r; chosen %r" % (options[s1][:40], options[c][:40]))', '                return "unverifiable", ["another option"], kinds')],
 "C32-r1-mapping-read-unverifiable": [('            rec.update(verdict="fail", reason="mapping: %s" % c["mapping"], answered="mapping")', '            rec.update(verdict="unverifiable", reason="mapping: %s" % c["mapping"], answered="mapping")')],
 # ── the inserted-mark reading, tightened fail-closed in v2.1 ──
 "C33-mark-inserted-text-read-unticked": [('        return None, None, "text inserted right before the option (%r) is not a \u2612" % t.ch', '        return False, None, ""')],
 "C34-mark-rewritten-neighbour-ignored": [("        if now != (before if before >= 0 else None):", "        if False:")],
 "C35-mark-broken-option-text-ignored": [(" or any(m[k + 1] != m[k] + 1 for k in range(a, b - 1)):", ":")],
 "C36-typed-bracket-box-not-a-box": [("    toks = typed_boxes(toks)\n", "")],
}
FAST = ["test_ticked.Mutants", "test_ticked.PositiveControls", "test_ticked.FailClosedReadings", "test_ticked.SymTable",
        "test_ticked.PrintedTextTie", "test_ticked.LegacyDropdown", "test_ticked.SymTableV21", "test_ticked.WtTable",
        "test_ticked.RadioCircles", "test_ticked.CellText", "test_ticked.Mapping", "test_ticked.Answering",
        "test_ticked.SlotMarks", "test_ticked.ConflictedTiesAreNoOnes", "test_ticked.TwoQuestionsInOneParagraph",
        "test_ticked.V21IdentityReadings", "test_ticked.MarkReadingFailClosed", "test_ticked.TypedBoxes"]
root = OUT / "_codemut"
if root.exists():
    shutil.rmtree(root)
root.mkdir(parents=True)
jobs = []
for name, edits in M.items():
    d = root / name
    d.mkdir()
    s = src
    for old, new in edits:
        n = s.count(old)
        assert n == 1, (name, n, old[:60])          # a mutation that does not apply aborts the whole proof
        s = s.replace(old, new)
    (d / "ticked.py").write_text(s)
    for f in ("test_ticked.py", "answering.py"):
        shutil.copy(H / f, d / f)
    changed = hashlib.sha256(s.encode()).hexdigest() != hashlib.sha256(src.encode()).hexdigest()
    assert changed == bool(edits), name
    print("%-44s applied: %s" % (name, changed), flush=True)
    jobs.append((name, d))


def run(job):
    name, d = job
    try:
        p = subprocess.run([PY, "-m", "unittest"] + FAST, cwd=d, capture_output=True, text=True, timeout=1200,
                           env=dict(os.environ, TICKED_OUT=str(d / "out")))
        code, out = p.returncode, p.stderr
    except subprocess.TimeoutExpired:
        code, out = "timeout", ""
    fails = [l for l in out.splitlines() if l.startswith(("FAIL:", "ERROR:"))]
    return name, code, fails, out.strip().splitlines()[-1:] if out else []


results = []
with concurrent.futures.ThreadPoolExecutor(int(os.environ.get("TICKED_JOBS") or 1)) as ex:
    for name, code, fails, last in ex.map(run, jobs):
        verdict = ("baseline passes" if code == 0 else "BASELINE FAILS") if name == "C0-baseline" else ("DETECTED" if code not in (0, "timeout") else ("SURVIVED" if code == 0 else "timeout"))
        results.append((name, verdict))
        print("%-44s exit=%-4s %-16s %s" % (name, code, verdict, (last or [""])[0][:60]), flush=True)
        for f in fails[:3]:
            print("      ", f[:150], flush=True)
shutil.rmtree(root)                                 # the mutated copies are scratch; remove them
print("detected %d of %d; baseline: %s" % (sum(v == "DETECTED" for n, v in results), len(results) - 1,
                                          dict(results)["C0-baseline"]))
