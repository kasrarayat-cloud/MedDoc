"""Code-mutation sensitivity of the self-tests: each mutated COPY of ticked.py must make the fast suite fail."""
import concurrent.futures, hashlib, pathlib, shutil, subprocess, sys
H = pathlib.Path(__file__).resolve().parent
PY = "/opt/meddoc-pro/rebuild/.venv/bin/python"
src = (H / "ticked.py").read_text()
M = {
 "C0-baseline": [],
 "C1-orphan-rule-removed": [("    for li, k in tie.orphans:", "    for li, k in []:")],
 "C2-sdt-display-check-removed": [("    if not (len(shown) == 1 and ord(shown) in (want, want & 0xFF, 0xF000 | (want & 0xFF))):", "    if False:")],
 "C3-any-inserted-glyph-is-a-mark": [('    if t.k == "glyph" and t.ch == INSERTED_MARK and t.state is True:', '    if t.k == "glyph":')],
 "C4-unexplained-mark-scan-removed": [("            if (t.is_box or t.is_control) and j not in explained.get(li, set()):", "            if False:")],
 "C5-conflict-guard-removed": [("        if len(ids) > 1:", "        if len(ids) > 99:")],
 "C6-unreadable-glyph-read-unticked": [('        return Tok("glyph", ch=c, state=None, desc="U+%04X %s outside the glyph table" % (ord(c), c))', '        return Tok("glyph", ch=c, state=False, desc="U+%04X %s outside the glyph table" % (ord(c), c))')],
 "C7-cell-anything-is-ticked": [('    return None, "the cell holds %r (not exactly one of X x \u2713 \u2714 \u2612)" % shown[:30]', '    return True, ""')],
 "C8-list-entries-check-removed": [("        if e0 != e1:", "        if False:")],
 "C9-word-boundary-removed": [("        if not (needle[0].isalnum() and before.isalnum()) and not (needle[-1].isalnum() and after.isalnum()):", "        if True:")],
 "C10-ff-odd-value-unticked": [('        return None, "legacy checkbox w:checked w:val=%r" % v', '        return False, ""')],
 "C11-sym-table-ignores-font": [("    table = SYM_GLYPHS.get(font)", '    table = SYM_GLYPHS["wingdings"]')],
 "C12-symbol-font-wt-read-as-text": [("    if symbol_fonts:\n        if c.isspace()", "    if False:\n        if c.isspace()")],
 "C13-invisible-runs-read": [("        hid = invisible(pkg, r)", '        hid = ""')],
 "C14-bordered-blank-not-a-box": [("        if visible() and bordered_blank(r):", "        if False:")],
 "C15-numbering-bullets-ignored": [("    return pkg.numbering.bullet_tokens(p) + toks", "    return toks")],
 "C16-ff-dropdown-cached-result-ignored": [("    if ws(\"\".join(cached)) and ws(\"\".join(cached)) != shown:", "    if False:")],
}
root = H / "_codemut"
root.mkdir(exist_ok=True)
jobs = []
for name, edits in M.items():
    d = root / name
    d.mkdir(exist_ok=True)
    s = src
    for old, new in edits:
        n = s.count(old)
        assert n == 1, (name, n, old[:60])          # a mutation that does not apply aborts the whole proof
        s = s.replace(old, new)
    (d / "ticked.py").write_text(s)
    shutil.copy(H / "test_ticked.py", d / "test_ticked.py")
    changed = hashlib.sha256(s.encode()).hexdigest() != hashlib.sha256(src.encode()).hexdigest()
    assert changed == bool(edits), name
    jobs.append((name, d))

def run(job):
    name, d = job
    try:
        p = subprocess.run([PY, "-m", "unittest", "test_ticked.Mutants", "test_ticked.PositiveControls",
                            "test_ticked.FailClosedReadings", "test_ticked.SymTable", "test_ticked.PrintedTextTie", "test_ticked.LegacyDropdown"], cwd=d, capture_output=True, text=True, timeout=500)
        code, out = p.returncode, p.stderr
    except subprocess.TimeoutExpired:
        code, out = "timeout", ""
    fails = [l for l in out.splitlines() if l.startswith(("FAIL:", "ERROR:"))]
    return name, code, fails

with concurrent.futures.ThreadPoolExecutor(4) as ex:
    for name, code, fails in ex.map(run, jobs):
        verdict = ("baseline passes" if code == 0 else "BASELINE FAILS") if name == "C0-baseline" else ("DETECTED" if code not in (0, "timeout") else ("SURVIVED" if code == 0 else "timeout"))
        print("%-36s exit=%-4s %s" % (name, code, verdict))
        for f in fails[:3]:
            print("      ", f[:150])
shutil.rmtree(root)                                 # the mutated copies are scratch; remove them
