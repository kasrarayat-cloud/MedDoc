"""Self-tests of ticked.py (v2.1) on the DEVELOPMENT set only (word-harness-v2.md, "Order of work", step 1, and v2.1).

    /opt/meddoc-pro/rebuild/.venv/bin/python -m unittest -v test_ticked

(a) DevInformation   ticked over the frozen candidate's dev ORDINARY and LONG v1-profile exports, chosen sets from the
                     v2.0 text join (join_chosen). Information, not a gate: every question gets a verdict and every
                     non-pass verdict a reason. (The v2.1 information pass, with the v2.1 answering, is info_v21.py.)
(b) Mutants          planted mutants on in-memory COPIES of exports, one or more per box kind, v2.1 readings 2-6
                     included. Each mutant first proves it applied (the bytes differ, the targeted element's XML
                     differs, and a kind-specific post-condition holds) and only then is its verdict believed.
(c) PositiveControls unmutated passing exports pass; every mutant base passes (also after a null rewrite).
Also: Resolver       every slot listed by the corpus slot tool resolves to the element it names.
      v2.1 classes   SymTableV21, WtTable, RadioCircles, CellText, SlotMarks, MarkReadingFailClosed, Mapping,
                     Answering (answering.py with a stand-in engine), TwoQuestionsInOneParagraph, ConflictedTiesAreNoOnes,
                     V21IdentityReadings.

Reads only: the dev corpus, the frozen dev results, and the v1 scorer / final_eval.py (read, never imported).
Never opens holdout/ or qual/. Writes only self-test-results.json into the output directory: env TICKED_OUT, by
default the session scratch directory - never next to this file, and never inside a git work tree or the corpus.
"""
import collections
import hashlib
import importlib.util
import io
import json
import os
import pathlib
import re
import sys
import unittest
import zipfile

from lxml import etree

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ticked  # noqa: E402
TICKED_SHA256 = hashlib.sha256((HERE / "ticked.py").read_bytes()).hexdigest()   # the reader these tests ran against

CORPUS = pathlib.Path("/opt/meddoc-pro/rebuild/.runtime/v1-word-corpus")
DEV = CORPUS / "dev"
FROZEN = CORPUS / "results" / "dev-79a5b2ec6597-frozen"
SCORE_PY = "/opt/meddoc-pro/.worktrees/v1-release/docs/rebuild/v1/word-eval/score.py"
# Where the tests write their results: an explicit parameter (env TICKED_OUT), defaulting to the session scratch
# directory. The tests never write next to themselves, and refuse an output directory inside a git work tree.
DEFAULT_OUT = "/tmp/claude-1000/-opt-meddoc-pro/64d93580-8414-4553-b17d-ed04b0550ae1/scratchpad/v1/harness-v21/out"


def output_dir():
    out = pathlib.Path(os.environ.get("TICKED_OUT") or DEFAULT_OUT).resolve()
    for d in (out,) + tuple(out.parents):
        if (d / ".git").exists():
            raise AssertionError("refusing to write test results inside a git work tree: %s" % out)
    if out == CORPUS or CORPUS in out.parents:
        raise AssertionError("refusing to write test results inside the corpus: %s" % out)
    out.mkdir(parents=True, exist_ok=True)
    return out


RESULTS_OUT = output_dir() / "self-test-results.json"
PROFILES = ("ordinary", "long")

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
W14 = "{http://schemas.microsoft.com/office/word/2010/wordml}"


def _dev_only(path):
    """Refuse any path outside the development set (holdout / qual are never read)."""
    p = pathlib.Path(path).resolve()
    rel = p.relative_to(CORPUS)
    if rel.parts[0] == "dev" or (rel.parts[0] == "results" and rel.parts[1] == FROZEN.name):
        return p
    raise AssertionError("not a development path: %s" % p)


_spec = importlib.util.spec_from_file_location("score_v1", SCORE_PY)
score = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(score)


def related(area, field):
    return any(score.related(g, d, area.get("kind")) for g in (score.norm(s) for s in area.get("slots", []))
               for d in score.det_slots(field))


def stems():
    return sorted(p.stem for p in _dev_only(DEV / "originals").iterdir())


def original_bytes(stem):
    orig = [p for p in _dev_only(DEV / "originals").iterdir() if p.stem == stem][0]
    return _dev_only(DEV / "converted" / (stem + ".docx") if orig.suffix == ".doc" else orig).read_bytes()


def export_path(stem, profile):
    return _dev_only(FROZEN / ("filled-" + profile) / (stem + ".docx"))


def groundtruth(stem):
    return json.loads(_dev_only(DEV / "groundtruth" / (stem + ".json")).read_text())


def detection(stem):
    return json.loads(_dev_only(FROZEN / "detect" / (stem + ".json")).read_text())


def chosen_for(stem, profile):
    gt, det = groundtruth(stem), detection(stem)
    if "fields" not in det:
        return {}
    answers = json.loads(_dev_only(FROZEN / ("filled-" + profile) / (stem + ".answers.json")).read_text())
    rows = score.score_doc(gt, det)["rows"]
    matched = {r["id"]: r["det"]["key"] for r in rows if r.get("det")}
    return ticked.join_chosen(gt, matched, det["fields"], answers, related)


def stem_of(prefix):
    return [s for s in stems() if s.startswith(prefix)][0]


# ─── (a) the development information run ─────────────────────────────────────────────────────────────────────────

class DevInformation(unittest.TestCase):
    def test_dev_run_every_question_gets_a_verdict(self):
        docs, table = [], {}
        for stem in stems():
            gt, b0 = groundtruth(stem), original_bytes(stem)
            for profile in PROFILES:
                exp = export_path(stem, profile)
                if not exp.exists():
                    docs.append({"stem": stem, "profile": profile, "doc": "no export", "counts": {}, "questions": []})
                    continue
                r = ticked.check_document(b0, exp.read_bytes(), gt, chosen_for(stem, profile))
                for q in r["questions"]:
                    self.assertIn(q["verdict"], ("pass", "fail", "unverifiable"), (stem, q))
                    if q["verdict"] != "pass":
                        self.assertTrue(q["reason"], (stem, q["id"]))
                n = r["counts"]
                doc = "n/a" if not r["questions"] else ("pass" if r["passed"] else ("fail" if n["fail"] else "unverifiable"))
                docs.append({"stem": stem, "profile": profile, "doc": doc, "counts": n, "questions": [
                    {k: q[k] for k in ("id", "kind", "verdict", "reason", "box_kinds", "mode", "answered")} for q in r["questions"]]})
        self.assertEqual(len(docs), 2 * len(stems()))
        self.assertEqual(len(stems()), 40)
        for profile in PROFILES:
            d = [x for x in docs if x["profile"] == profile]
            t = {"documents": collections.Counter(x["doc"] for x in d),
                 "questions": collections.Counter(q["verdict"] for x in d for q in x["questions"]),
                 "answered": collections.Counter("%s/%s" % ({True: "answered", False: "unanswered", "unknown": "chosen-unknown"}[q["answered"]], q["verdict"])
                                                 for x in d for q in x["questions"]),
                 "box_kind": collections.Counter("%s/%s" % ("+".join(q["box_kinds"]) or "(untied)", q["verdict"])
                                                 for x in d for q in x["questions"]),
                 "reasons": collections.Counter(_reason_class(q) for x in d for q in x["questions"] if q["verdict"] != "pass")}
            table[profile] = {k: dict(sorted(v.items())) for k, v in t.items()}
        RESULTS_OUT.write_text(json.dumps({"harness": ticked.VERSION, "ticked_sha256": TICKED_SHA256, "set": "dev", "results": FROZEN.name,
                                           "summary": table, "documents": docs}, indent=1, ensure_ascii=False))
        print("\n" + json.dumps({p: {k: table[p][k] for k in ("documents", "questions", "answered")} for p in PROFILES}, indent=1))


def _reason_class(q):
    r = q["reason"]
    if r.startswith("chosen set unknown"):
        return "chosen set unknown (the dev join): " + re.sub(r"'[^']*'|\([^)]*\)|\d+", "#", r.split(" | ")[0].split(";")[0][20:])[:70]
    if "unreadable glyph" in r:
        return "unreadable glyph"
    if "picture" in r:
        return "picture in the slots"
    if "holds 0 boxes" in r:
        return "an option slot holds no box"
    if re.search(r"holds \d+ boxes", r):
        return "an option slot holds several boxes"
    if "not printed" in r:
        return "an option is not printed in the slots"
    if "mixture" in r:
        return "boxes before some options, not others (mixture)"
    if "also tied to" in r:
        return "a box or printed option tied to two questions"
    if "lists no options" in r:
        return "the ground truth lists no options"
    if "inserted" in r:
        return "an inserted mark that is no option's"
    if "unanswered, but" in r:
        return "unanswered, but a box changed"
    return re.sub(r"'[^']*'|\d+", "#", r)[:70]


# ─── the slot grammar, checked against the tool that wrote the ground-truth slot ids ────────────────────────────

def _tool_text(el):
    """ooxml_slots.text_of, re-stated: every w:t, tab, br/cr and w:sym below el, in document order."""
    out = []
    for n in el.iter():
        if n.tag == W + "t" and n.text:
            out.append(n.text)
        elif n.tag == W + "tab":
            out.append("\t")
        elif n.tag in (W + "br", W + "cr"):
            out.append("\n")
        elif n.tag == W + "sym":
            out.append("[sym:%s]" % n.get(W + "char", "?"))
    return "".join(out)


class Resolver(unittest.TestCase):
    def test_every_listed_slot_resolves_to_the_element_the_slot_tool_named(self):
        checked = 0
        for stem in stems():
            pkg = ticked.Package(original_bytes(stem))
            for rec in json.loads(_dev_only(DEV / "slots" / (stem + ".json")).read_text()):
                part, el, kind = ticked.resolve(pkg, rec["slot"])
                want = {"p": "p", "tc": "tc", "tbl": "tbl", "sdt": "sdt", "formfield": "ff", "txbx": "txbx", "glyphs": "p"}[rec["kind"]]
                self.assertEqual(kind, want, rec["slot"])
                if rec["kind"] == "p":
                    self.assertEqual(_tool_text(el)[:400], rec["text"], rec["slot"])
                elif rec["kind"] == "tc":
                    self.assertEqual(_tool_text(el)[:300], rec["text"], rec["slot"])
                elif rec["kind"] == "sdt":
                    c = el.find(W + "sdtContent")
                    self.assertEqual(_tool_text(c)[:300] if c is not None else "", rec["text"], rec["slot"])
                elif rec["kind"] == "formfield":
                    data = el.find(W + "fldChar").find(W + "ffData")
                    kind_ff = "FORMCHECKBOX" if data.find(W + "checkBox") is not None else (
                        "FORMDROPDOWN" if data.find(W + "ddList") is not None else "FORMTEXT")
                    self.assertEqual(kind_ff, rec["field"], rec["slot"])
                elif rec["kind"] == "glyphs":
                    self.assertEqual(sum(_tool_text(el).count(g) for g in "☐☑☒□■○●❏❑❒"), rec["count"], rec["slot"])
                elif rec["kind"] == "txbx":
                    self.assertEqual(_tool_text(el)[:300], rec["text"], rec["slot"])
                checked += 1
        self.assertGreater(checked, 20000)

    def test_every_groundtruth_choice_slot_resolves(self):
        for stem in stems():
            pkg = ticked.Package(original_bytes(stem))
            for a in groundtruth(stem)["answer_areas"]:
                if a["kind"] in ticked.CHOICE_KINDS:
                    for s in a["slots"]:
                        ticked.resolve(pkg, s)


# ─── mutation helpers: an independent locator and raw lxml edits on copies ──────────────────────────────────────

def locate(root, path):
    """The slot grammar again, written separately from ticked.resolve (b | hf, then tbl tr tc p sdt ff txbx)."""
    segs = path.split("/")
    if segs[-1] == "glyphs":
        segs = segs[:-1]
    cur = root.find(W + "body") if segs[0] == "b" else root
    for seg in segs[1:]:
        name, i = re.match(r"(\w+)\[(\d+)\]$", seg).groups()
        i = int(i)
        if name == "ff":
            runs = [r for r in cur.iter(W + "r") if r.find(W + "fldChar") is not None
                    and r.find(W + "fldChar").get(W + "fldCharType") == "begin" and r.find(W + "fldChar").find(W + "ffData") is not None]
            cur = runs[i]
        elif name == "txbx":
            fallback = {id(x) for fb in cur.iter("{http://schemas.openxmlformats.org/markup-compatibility/2006}Fallback") for x in fb.iter()}
            cur = [t for t in cur.iter(W + "txbxContent") if id(t) not in fallback][i]
        else:
            host = cur.find(W + "sdtContent") if cur.tag == W + "sdt" else cur
            cur = host.findall(W + name)[i]
    return cur


class Editable:
    """An in-memory COPY of a package whose parts can be edited and saved back as new bytes."""

    def __init__(self, data):
        self.base = data
        self.zin = zipfile.ZipFile(io.BytesIO(data))
        self.roots = {}

    def root(self, part):
        if part not in self.roots:
            self.roots[part] = etree.fromstring(self.zin.read(part), etree.XMLParser(resolve_entities=False, no_network=True))
        return self.roots[part]

    def at(self, slot):
        part, _, path = slot.partition("#")
        return self.root(part) if path == "" else locate(self.root(part), path)

    def save(self):
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as z:
            for info in self.zin.infolist():
                data = self.zin.read(info.filename)
                if info.filename in self.roots:
                    data = etree.tostring(self.roots[info.filename], xml_declaration=True, encoding="UTF-8", standalone=True)
                z.writestr(info, data)
        return out.getvalue()


def xml_of(data, slot):
    return etree.tostring(Editable(data).at(slot))


def sdt_set(sdt, on, show=None):
    cb = sdt.find(W + "sdtPr").find(W14 + "checkbox")
    for c in cb.findall(W14 + "checked"):
        cb.remove(c)
    c = etree.Element(W14 + "checked")
    c.set(W14 + "val", "1" if on else "0")
    cb.insert(0, c)
    st = cb.find(W14 + ("checkedState" if on else "uncheckedState"))
    ch = chr(int(st.get(W14 + "val"), 16)) if st is not None else ("☒" if on else "☐")
    ts = list(sdt.find(W + "sdtContent").iter(W + "t"))
    ts[0].text = ch if show is None else show
    for t in ts[1:]:
        t.text = ""


def sdt_is(sdt):
    c = sdt.find(W + "sdtPr").find(W14 + "checkbox").find(W14 + "checked")
    return c is not None and c.get(W14 + "val") == "1"


def ff_box(run):
    return run.find(W + "fldChar").find(W + "ffData").find(W + "checkBox")


def ff_set(run, on):
    cb = ff_box(run)
    for c in cb.findall(W + "checked"):
        cb.remove(c)
    c = etree.SubElement(cb, W + "checked")
    c.set(W + "val", "1" if on else "0")


def ff_default_on(run, drop_checked):
    cb = ff_box(run)
    if drop_checked:
        for c in cb.findall(W + "checked"):
            cb.remove(c)
    d = cb.find(W + "default")
    if d is None:
        d = etree.SubElement(cb, W + "default")
    d.set(W + "val", "1")


def ff_is(run):
    cb = ff_box(run)
    c = cb.find(W + "checked")
    if c is not None:
        return c.get(W + "val", "1") in ("1", "true")
    d = cb.find(W + "default")
    return d is not None and d.get(W + "val") in ("1", "true")


def glyph_set(p, n, ch):
    boxes = [(t, i) for t in p.iter(W + "t") for i, c in enumerate(t.text or "") if c in "☐☒"]
    t, i = boxes[n]
    t.text = t.text[:i] + ch + t.text[i + 1:]


def glyphs_of(p):
    return "".join(c for t in p.iter(W + "t") for c in (t.text or "") if c in "☐☒")


def cell_set(tc, text):
    """Write `text` into the cell (None: remove every X / x mark)."""
    if text is None:
        for t in tc.iter(W + "t"):
            t.text = re.sub(r"[Xx]", "", t.text or "")
        return
    p = tc.find(W + "p")
    r = etree.SubElement(p, W + "r")
    t = etree.SubElement(r, W + "t")
    t.text = text


def cell_text(tc):
    return "".join(t.text or "" for t in tc.iter(W + "t")).strip()


def mark_remove(p):
    for t in p.iter(W + "t"):
        if "☒" in (t.text or ""):
            t.text = t.text.replace("☒ ", "").replace("☒", "")


def mark_insert(p, option):
    for t in p.iter(W + "t"):
        m = re.search(r"(?<![A-Za-z0-9])" + re.escape(option) + r"(?![A-Za-z0-9])", t.text or "", re.I)
        if m:
            t.text = t.text[:m.start()] + "☒ " + t.text[m.start():]
            t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
            return
    raise AssertionError("option %r not found" % option)


def mark_append(p):
    r = etree.SubElement(p, W + "r")
    t = etree.SubElement(r, W + "t")
    t.text = "☒"


def hide_tick(p):
    """Give the run that holds the ☒ a w:vanish (the tick no longer prints)."""
    for r in p.iter(W + "r"):
        if "☒" in "".join(t.text or "" for t in r.findall(W + "t")):
            rpr = r.find(W + "rPr")
            if rpr is None:
                rpr = etree.Element(W + "rPr")
                r.insert(0, rpr)
            rpr.append(etree.Element(W + "vanish"))
            return
    raise AssertionError("no ☒ run")


def tick_hidden(p):
    return any(r.find(W + "rPr") is not None and r.find(W + "rPr").find(W + "vanish") is not None
               and "☒" in "".join(t.text or "" for t in r.findall(W + "t")) for r in p.iter(W + "r"))


def para_text(p):
    return "".join(t.text or "" for t in p.iter(W + "t"))


def dd_show(sdt, text):
    pr = sdt.find(W + "sdtPr")
    for x in pr.findall(W + "showingPlcHdr"):
        pr.remove(x)
    ts = list(sdt.find(W + "sdtContent").iter(W + "t"))
    ts[0].text = text
    for t in ts[1:]:
        t.text = ""


def dd_placeholder(sdt):
    pr = sdt.find(W + "sdtPr")
    if pr.find(W + "showingPlcHdr") is None:
        pr.append(etree.Element(W + "showingPlcHdr"))
    ts = list(sdt.find(W + "sdtContent").iter(W + "t"))
    ts[0].text = "Choose an item."
    for t in ts[1:]:
        t.text = ""


def dd_drop_entry(sdt, display):
    lst = sdt.find(W + "sdtPr").find(W + "dropDownList")
    for li in lst.findall(W + "listItem"):
        if li.get(W + "displayText") == display:
            lst.remove(li)
            return
    raise AssertionError("no entry %r" % display)


def dd_shown(sdt):
    return None if sdt.find(W + "sdtPr").find(W + "showingPlcHdr") is not None else "".join(
        t.text or "" for t in sdt.find(W + "sdtContent").iter(W + "t")).strip()


# ─── v2.1 mutation helpers ───────────────────────────────────────────────────────────────────────────────────────

WT_CIRCLES = {0x81, 0x99, 0x9A, 0x97, 0x98, 0x9B, 0x9C}


def _wt_circle_hits(el):
    return [(t, i) for t in el.iter(W + "t") for i, c in enumerate(t.text or "")
            if 0xF000 <= ord(c) <= 0xF0FF and (ord(c) & 0xFF) in WT_CIRCLES]


def wt_circle_set(el, n, new):
    """The n-th Wingdings 2 circle character carried as w:t text under el becomes `new` (same run, same fonts)."""
    t, i = _wt_circle_hits(el)[n]
    t.text = t.text[:i] + new + t.text[i + 1:]


def wt_circles(el):
    return " ".join("%02X" % (ord(t.text[i]) & 0xFF) for t, i in _wt_circle_hits(el))


def wt_circle_run(el, n=0):
    t, _ = _wt_circle_hits(el)[n]
    return t.getparent()


def run_font_set(run, slot, font):
    rpr = run.find(W + "rPr")
    rf = rpr.find(W + "rFonts")
    rf.set(W + slot, font)


def run_font(run, slot):
    rf = run.find(W + "rPr").find(W + "rFonts")
    return rf.get(W + slot)


def font_charset_set(fonts_root, name, value):
    for f in fonts_root.findall(W + "font"):
        if f.get(W + "name") == name:
            f.find(W + "charset").set(W + "val", value)
            return
    raise AssertionError("no font %r" % name)


def font_charset(fonts_root, name):
    return [f.find(W + "charset").get(W + "val") for f in fonts_root.findall(W + "font") if f.get(W + "name") == name]


def glyph_map(el, mapping):
    """Every character of w:t text under el found in `mapping` is replaced (a box redrawn in another shape)."""
    n = 0
    for t in el.iter(W + "t"):
        if t.text and any(c in mapping for c in t.text):
            n += sum(c in mapping for c in t.text)
            t.text = "".join(mapping.get(c, c) for c in t.text)
    assert n, "glyph_map changed nothing"                   # a synthesis that does not apply aborts


def glyphs_in(el, chars):
    return "".join(c for t in el.iter(W + "t") for c in (t.text or "") if c in chars)


def cell_text_set(tc, text, hidden=False):
    """The cell's written answer (None: none): every text run of the cell's first paragraph is replaced by one run."""
    p = tc.find(W + "p")
    for r in [r for r in p.findall(W + "r") if r.find(W + "t") is not None]:
        p.remove(r)
    if text is None:
        return
    r = etree.SubElement(p, W + "r")
    if hidden:
        etree.SubElement(etree.SubElement(r, W + "rPr"), W + "vanish")
    t = etree.SubElement(r, W + "t")
    t.text = text
    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")


def mark_after(p, option):
    """A ☒ right AFTER the option's printed text (not before it)."""
    for t in p.iter(W + "t"):
        m = re.search(r"(?<![A-Za-z0-9])" + re.escape(option) + r"(?![A-Za-z0-9])", t.text or "", re.I)
        if m:
            t.text = t.text[:m.end()] + " ☒" + t.text[m.end():]
            t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
            return
    raise AssertionError("option %r not found" % option)


# ─── (b) the mutant table ───────────────────────────────────────────────────────────────────────────────────────

class Base:
    """A mutant base: an original, an export, the chosen sets, and the question under test."""

    def __init__(self, prefix, qid, profile="ordinary", synth=None, chosen_override=None, gt_edit=None, osynth=None,
                 from_original=False):
        self.stem = stem_of(prefix)
        self.qid = qid
        self.gt = groundtruth(self.stem)
        self.area = [a for a in self.gt["answer_areas"] if a["id"] == qid][0]
        self.areas = {a["id"]: a for a in self.gt["answer_areas"]}
        if gt_edit:
            gt_edit(self.gt)                            # a copy: groundtruth() re-reads the file every call
        self.original = original_bytes(self.stem)
        if osynth:                                      # the ORIGINAL transformed too (a synthesized box shape)
            ed = Editable(self.original)
            osynth(ed, self)
            self.original = ed.save()
        # from_original: the export starts as the (transformed) original and only `synth` answers it; every other
        # question is then unanswered and unchanged. Otherwise it is the frozen candidate's v1-profile export.
        self.chosen = {} if from_original else dict(chosen_for(self.stem, profile))
        self.export = self.original if from_original else export_path(self.stem, profile).read_bytes()
        self.synthesized = synth is not None
        if synth:
            ed = Editable(self.export)
            synth(ed, self)
            self.export = ed.save()
        if chosen_override:
            self.chosen.update(chosen_override)

    def slot(self, i):
        return self.area["slots"][i]

    def verdict(self, original=None, export=None, qid=None):
        r = ticked.check_document(original or self.original, export or self.export, self.gt, self.chosen)
        q = [x for x in r["questions"] if x["id"] == (qid or self.qid)][0]
        return r["passed"], q

    def verdicts(self, original=None, export=None):
        r = ticked.check_document(original or self.original, export or self.export, self.gt, self.chosen)
        return r["passed"], {x["id"]: x for x in r["questions"]}


_BASES = {}


def base(key):
    if key not in _BASES:
        spec = BASES[key]
        _BASES[key] = Base(*spec[0], **spec[1])
    return _BASES[key]


def _tick_first(ed, b):                            # synthesized: the first option's content-control box ticked
    sdt_set(ed.at(b.area["slots"][0]), True)


BASES = {
    # content-control checkbox: the candidate's dev exports answer no such question in ground-truth terms, so the base
    # is SYNTHESIZED on a copy of its D03 export: option 0 (Right) ticked, chosen = [0]
    "sdt": (("D03", "A50"), {"synth": _tick_first, "chosen_override": {"A50": [0]}}),
    "sdt-lr": (("D03", "A22"), {"synth": _tick_first, "chosen_override": {"A22": [0]}}),
    "ff": (("D09", "A11"), {}),                       # legacy checkboxes, one slot per option, chosen [1]
    "ff-multi": (("D07", "A11"), {}),                 # legacy checkboxes, multi_choice, chosen [0, 1]
    "glyph": (("D15", "A16"), {}),                    # ☐ glyphs, one slot per option, chosen [1] (No)
    "glyph-text": (("D35", "A11"), {}),               # [☐] kg [☐] lbs. [☐] not available: rule 2 second bullet
    "cell": (("D06", "A11"), {}),                     # empty cells, chosen [1] (NO) written as X
    "mark": (("D33", "A1"), {}),                      # YES<tab>NO, no boxes: the inserted mark, chosen [1]
    "dropdown": (("D01", "A17"), {}),                 # dropdown with right / left entries, chosen [1] (left)
    "dropdown2": (("D01", "A7"), {}),                 # dropdown, chosen [1]
    # the orphan-box rule: D35 A11 with its last option removed from a COPY of the ground truth, so the third box
    # ('not available') belongs to no option
    "orphan": (("D35", "A11"), {"gt_edit": lambda gt: _area(gt, "A11").__setitem__("options", _area(gt, "A11")["options"][:2])}),
    # ── v2.1 bases, each SYNTHESIZED from a dev original (the export starts as the original; only the question under
    #    test is answered, so every other question is unanswered and unchanged) ──
    # reading 2: D04 A3, lettered options Male / Female / Others one paragraph each, no box: ☒ before "Female"
    "mark-slot": (("D04", "A3"), {"from_original": True, "synth": lambda ed, b: mark_insert(ed.at(b.slot(1)), "Female"),
                                  "chosen_override": {"A3": [1]}}),
    # reading 3: D28 A7, Yes / No cells whose radio circles are Wingdings 2 U+F081 in w:t; "No" ticked as U+F098 (●)
    "wt-circle": (("D28", "A7"), {"from_original": True, "synth": lambda ed, b: wt_circle_set(ed.at(b.slot(1)), 0, "\uf098"),
                                  "chosen_override": {"A7": [1]}}),
    # reading 4: D15 A16, its ☐ boxes redrawn as Unicode radio circles ○ in the original; "No" ticked as ●
    "radio": (("D15", "A16"), {"from_original": True, "osynth": lambda ed, b: [glyph_map(ed.at(s), {"☐": "○"}) for s in b.area["slots"]],
                               "synth": lambda ed, b: glyph_map(ed.at(b.slot(1)), {"○": "●"}), "chosen_override": {"A16": [1]}}),
    # reading 6: D06 A58, one empty answer cell (Yes / No / NA / ND written as text): "No" written
    "celltext": (("D06", "A58"), {"from_original": True, "synth": lambda ed, b: cell_text_set(ed.at(b.slot(0)), "No"),
                                  "chosen_override": {"A58": [1]}}),
    # reading 5: D17 A11 [injuries/condition] and A12 [he/she] in ONE paragraph, read by inserted marks: "injuries"
    # (A11) and "she" (A12) marked. Under v2.0 each question failed on the other's mark.
    "two-q-marks": (("D17", "A12"), {"from_original": True, "chosen_override": {"A11": [0], "A12": [1]},
                                      "synth": lambda ed, b: (mark_insert(ed.at(b.slot(0)), "injuries"), mark_insert(ed.at(b.slot(0)), "she"))}),
    "two-q-marks-a11": (("D17", "A11"), {"from_original": True, "chosen_override": {"A11": [0], "A12": [1]},
                                         "synth": lambda ed, b: (mark_insert(ed.at(b.slot(0)), "injuries"), mark_insert(ed.at(b.slot(0)), "she"))}),
    # reading 5: D03 A60 (Menstruation / Pregnancy / Menopause) and A61 (Before / During / After) share one paragraph;
    # its U+20DD circles (unreadable) are redrawn as ☐ in the original; "Menstruation" (A60) and "During" (A61) ticked
    "two-q-boxes": (("D03", "A60"), {"from_original": True, "chosen_override": {"A60": [0], "A61": [1]},
                                      "osynth": lambda ed, b: glyph_map(ed.at(b.slot(0)), {"\u20dd": "☐"}),
                                      "synth": lambda ed, b: (glyph_set(ed.at(b.slot(0)), 0, "☒"), glyph_set(ed.at(b.slot(0)), 2, "☒"))}),
    "two-q-boxes-a61": (("D03", "A61"), {"from_original": True, "chosen_override": {"A60": [0], "A61": [1]},
                                          "osynth": lambda ed, b: glyph_map(ed.at(b.slot(0)), {"⃝": "☐"}),
                                          "synth": lambda ed, b: (glyph_set(ed.at(b.slot(0)), 0, "☒"), glyph_set(ed.at(b.slot(0)), 2, "☒"))}),
    # the same, with A61's third option ('After') removed from a COPY of the ground truth: its box belongs to no question
    "two-q-boxes-orphan": (("D03", "A60"), {"from_original": True, "chosen_override": {"A60": [0], "A61": [1]},
                                             "gt_edit": lambda gt: _area(gt, "A61").__setitem__("options", _area(gt, "A61")["options"][:2]),
                                             "osynth": lambda ed, b: glyph_map(ed.at(b.slot(0)), {"⃝": "☐"}),
                                             "synth": lambda ed, b: (glyph_set(ed.at(b.slot(0)), 0, "☒"), glyph_set(ed.at(b.slot(0)), 2, "☒"))}),
}


def _area(gt, qid):
    return [a for a in gt["answer_areas"] if a["id"] == qid][0]


def M(name, kind, base_key, mutate, applied, expect, original_mutate=None, original_applied=None, note="", where=None,
      pretick_positive=True):
    return {"name": name, "kind": kind, "base": base_key, "mutate": mutate, "applied": applied, "expect": expect,
            "omutate": original_mutate, "oapplied": original_applied, "note": note, "where": where,
            "pretick_positive": pretick_positive}


def S(i):
    return lambda b: b.slot(i)


MUTANTS = [
    # content-control checkbox (D03, synthesized base)
    M("chosen box unticked", "sdt", "sdt", lambda ed, b: sdt_set(ed.at(b.slot(0)), False),
      lambda ed, b: not sdt_is(ed.at(b.slot(0))), "fail"),
    M("tick moved to the neighbour", "sdt", "sdt",
      lambda ed, b: (sdt_set(ed.at(b.slot(0)), False), sdt_set(ed.at(b.slot(1)), True)),
      lambda ed, b: not sdt_is(ed.at(b.slot(0))) and sdt_is(ed.at(b.slot(1))), "fail"),
    M("two ticks for one single-choice answer", "sdt", "sdt", lambda ed, b: sdt_set(ed.at(b.slot(1)), True),
      lambda ed, b: sdt_is(ed.at(b.slot(0))) and sdt_is(ed.at(b.slot(1))), "fail"),
    M("left and right swapped", "sdt", "sdt-lr",
      lambda ed, b: (sdt_set(ed.at(b.slot(0)), False), sdt_set(ed.at(b.slot(1)), True)),
      lambda ed, b: not sdt_is(ed.at(b.slot(0))) and sdt_is(ed.at(b.slot(1))), "fail"),
    M("pre-ticked printed default left ticked", "sdt", "sdt", lambda ed, b: sdt_set(ed.at(b.slot(1)), True),
      lambda ed, b: sdt_is(ed.at(b.slot(1))), "fail",
      lambda ed, b: sdt_set(ed.at(b.slot(1)), True), lambda ed, b: sdt_is(ed.at(b.slot(1)))),
    M("state ticked but the control still shows ☐", "sdt", "sdt", lambda ed, b: sdt_set(ed.at(b.slot(1)), True, show="☐"),
      lambda ed, b: sdt_is(ed.at(b.slot(1))), "unverifiable", note="fail-closed extra"),
    # legacy form-field checkbox (D09 A11, chosen [1]; D07 A11 multi, chosen [0, 1])
    M("chosen box unticked", "ff", "ff", lambda ed, b: ff_set(ed.at(b.slot(1)), False),
      lambda ed, b: not ff_is(ed.at(b.slot(1))), "fail"),
    M("tick moved to the neighbour", "ff", "ff", lambda ed, b: (ff_set(ed.at(b.slot(1)), False), ff_set(ed.at(b.slot(2)), True)),
      lambda ed, b: not ff_is(ed.at(b.slot(1))) and ff_is(ed.at(b.slot(2))), "fail"),
    M("two ticks for one single-choice answer", "ff", "ff", lambda ed, b: ff_set(ed.at(b.slot(0)), True),
      lambda ed, b: ff_is(ed.at(b.slot(0))) and ff_is(ed.at(b.slot(1))), "fail"),
    M("pre-ticked printed default left ticked", "ff", "ff", lambda ed, b: ff_default_on(ed.at(b.slot(0)), drop_checked=True),
      lambda ed, b: ff_is(ed.at(b.slot(0))), "fail",
      lambda ed, b: ff_default_on(ed.at(b.slot(0)), drop_checked=True), lambda ed, b: ff_is(ed.at(b.slot(0)))),
    M("multi: one of two chosen boxes unticked", "ff", "ff-multi", lambda ed, b: ff_set(ed.at(b.slot(1)), False),
      lambda ed, b: not ff_is(ed.at(b.slot(1))), "fail"),
    M("checked value outside the table", "ff", "ff",
      lambda ed, b: ff_box(ed.at(b.slot(1))).find(W + "checked").set(W + "val", "maybe"),
      lambda ed, b: ff_box(ed.at(b.slot(1))).find(W + "checked").get(W + "val") == "maybe", "unverifiable", note="fail-closed extra"),
    # printed glyph (D15 A16 Yes/No one slot per option; D35 A11 three options in one paragraph)
    M("chosen box unticked", "glyph", "glyph", lambda ed, b: glyph_set(ed.at(b.slot(1)), 0, "☐"),
      lambda ed, b: glyphs_of(ed.at(b.slot(1))) == "☐", "fail"),
    M("tick moved to the neighbour", "glyph", "glyph-text", lambda ed, b: (glyph_set(ed.at(b.slot(0)), 1, "☐"), glyph_set(ed.at(b.slot(0)), 2, "☒")),
      lambda ed, b: glyphs_of(ed.at(b.slot(0))) == "☐☐☒", "fail"),
    M("two ticks for one single-choice answer", "glyph", "glyph-text", lambda ed, b: glyph_set(ed.at(b.slot(0)), 0, "☒"),
      lambda ed, b: glyphs_of(ed.at(b.slot(0))) == "☒☒☐", "fail"),
    M("pre-ticked printed default left ticked", "glyph", "glyph", lambda ed, b: glyph_set(ed.at(b.slot(0)), 0, "☒"),
      lambda ed, b: glyphs_of(ed.at(b.slot(0))) == "☒", "fail",
      lambda ed, b: glyph_set(ed.at(b.slot(0)), 0, "☒"), lambda ed, b: glyphs_of(ed.at(b.slot(0))) == "☒"),
    # cell mark (D06 A11, chosen [1] = NO)
    M("chosen box unticked", "cell", "cell", lambda ed, b: cell_set(ed.at(b.slot(1)), None),
      lambda ed, b: cell_text(ed.at(b.slot(1))) == "", "fail"),
    M("tick moved to the neighbour", "cell", "cell", lambda ed, b: (cell_set(ed.at(b.slot(1)), None), cell_set(ed.at(b.slot(2)), "X")),
      lambda ed, b: cell_text(ed.at(b.slot(1))) == "" and cell_text(ed.at(b.slot(2))) == "X", "fail"),
    M("two ticks for one single-choice answer", "cell", "cell", lambda ed, b: cell_set(ed.at(b.slot(0)), "X"),
      lambda ed, b: cell_text(ed.at(b.slot(0))) == "X" and cell_text(ed.at(b.slot(1))) == "X", "fail"),
    M("pre-ticked printed default left ticked", "cell", "cell", lambda ed, b: cell_set(ed.at(b.slot(0)), "X"),
      lambda ed, b: cell_text(ed.at(b.slot(0))) == "X", "unverifiable",
      lambda ed, b: cell_set(ed.at(b.slot(0)), "X"), lambda ed, b: cell_text(ed.at(b.slot(0))) == "X",
      note="a cell mark is a cell EMPTY in the original, so a pre-marked cell is no box: the tie fails (unverifiable)"),
    M("cell holds two marks", "cell", "cell", lambda ed, b: cell_set(ed.at(b.slot(1)), "X"),
      lambda ed, b: cell_text(ed.at(b.slot(1))) == "XX", "unverifiable", note="fail-closed extra"),
    # inserted mark (D33 A1, YES / NO printed with no box, chosen [1] = NO)
    M("chosen box unticked", "mark", "mark", lambda ed, b: mark_remove(ed.at(b.slot(0))),
      lambda ed, b: "☒" not in para_text(ed.at(b.slot(0))), "fail"),
    M("tick moved to the neighbour", "mark", "mark", lambda ed, b: (mark_remove(ed.at(b.slot(0))), mark_insert(ed.at(b.slot(0)), "YES")),
      lambda ed, b: re.search(r"☒ YES", para_text(ed.at(b.slot(0)))) and para_text(ed.at(b.slot(0))).count("☒") == 1, "fail"),
    M("two ticks for one single-choice answer", "mark", "mark", lambda ed, b: mark_insert(ed.at(b.slot(0)), "YES"),
      lambda ed, b: para_text(ed.at(b.slot(0))).count("☒") == 2, "fail"),
    M("pre-ticked printed default left ticked", "mark", "mark", lambda ed, b: mark_insert(ed.at(b.slot(0)), "YES"),
      lambda ed, b: para_text(ed.at(b.slot(0))).count("☒") == 2, "unverifiable",
      lambda ed, b: mark_insert(ed.at(b.slot(0)), "YES"), lambda ed, b: "☒ YES" in para_text(ed.at(b.slot(0))),
      note="a printed ☒ before YES is a box, NO has none: a mixture under rule 2 (unverifiable)"),
    M("an inserted ☑ instead of ☒", "mark", "mark",
      lambda ed, b: [setattr(t, "text", t.text.replace("☒", "☑")) for t in ed.at(b.slot(0)).iter(W + "t") if "☒" in (t.text or "")],
      lambda ed, b: "☑ NO" in para_text(ed.at(b.slot(0))) and "☒" not in para_text(ed.at(b.slot(0))), "fail",
      note="the inserted mark is exactly ☒"),
    M("a box of no option ticked", "glyph", "orphan", lambda ed, b: glyph_set(ed.at(b.slot(0)), 2, "☒"),
      lambda ed, b: glyphs_of(ed.at(b.slot(0))) == "☐☒☒", "fail", note="rule 3: every box of no chosen option is unticked"),
    M("the inserted ☒ does not print (w:vanish)", "mark", "mark", lambda ed, b: hide_tick(ed.at(b.slot(0))),
      lambda ed, b: tick_hidden(ed.at(b.slot(0))), "fail", note="fail-closed extra"),
    M("the ticked glyph does not print (w:vanish)", "glyph", "glyph", lambda ed, b: hide_tick(ed.at(b.slot(1))),
      lambda ed, b: tick_hidden(ed.at(b.slot(1))), "unverifiable", note="fail-closed extra"),
    M("a mark beside no option", "mark", "mark", lambda ed, b: mark_append(ed.at(b.slot(0))),
      lambda ed, b: para_text(ed.at(b.slot(0))).rstrip().endswith("☒"), "fail", note="fail-closed extra"),
    # dropdown (D01 A17 right/left entries, chosen [1] = left; D01 A7, chosen [1])
    M("dropdown shows another entry", "dropdown", "dropdown2", lambda ed, b: dd_show(ed.at(b.slot(0)), b.area["options"][3]),
      lambda ed, b: dd_shown(ed.at(b.slot(0))) == b.area["options"][3], "fail"),
    M("left and right swapped", "dropdown", "dropdown", lambda ed, b: dd_show(ed.at(b.slot(0)), b.area["options"][0]),
      lambda ed, b: "right lower extremity" in dd_shown(ed.at(b.slot(0))), "fail"),
    M("chosen box unticked (placeholder shown)", "dropdown", "dropdown2", lambda ed, b: dd_placeholder(ed.at(b.slot(0))),
      lambda ed, b: dd_shown(ed.at(b.slot(0))) is None, "fail"),
    M("pre-ticked printed default left ticked", "dropdown", "dropdown2", lambda ed, b: dd_show(ed.at(b.slot(0)), b.area["options"][4]),
      lambda ed, b: dd_shown(ed.at(b.slot(0))) == b.area["options"][4], "fail",
      lambda ed, b: dd_show(ed.at(b.slot(0)), b.area["options"][4]), lambda ed, b: dd_shown(ed.at(b.slot(0))) == b.area["options"][4],
      note="the original shows entry 5 as its default; the export still shows it"),
    M("list entries changed", "dropdown", "dropdown2", lambda ed, b: dd_drop_entry(ed.at(b.slot(0)), b.area["options"][3]),
      lambda ed, b: b.area["options"][3] not in [li.get(W + "displayText") for li in ed.at(b.slot(0)).iter(W + "listItem")], "fail",
      note="fail-closed extra (declared: the list entries are unchanged)"),
    # ── v2.1 reading 2: a printed option with no box, one slot per option (D04 A3, synthesized base, chosen Female) ──
    M("chosen box unticked (mark removed)", "mark-slot", "mark-slot", lambda ed, b: mark_remove(ed.at(b.slot(1))),
      lambda ed, b: "☒" not in para_text(ed.at(b.slot(1))), "fail"),
    M("tick moved to the neighbour", "mark-slot", "mark-slot",
      lambda ed, b: (mark_remove(ed.at(b.slot(1))), mark_insert(ed.at(b.slot(0)), "Male")),
      lambda ed, b: "☒ Male" in para_text(ed.at(b.slot(0))) and "☒" not in para_text(ed.at(b.slot(1))), "fail"),
    M("two ticks for one single-choice answer", "mark-slot", "mark-slot", lambda ed, b: mark_insert(ed.at(b.slot(0)), "Male"),
      lambda ed, b: "☒ Male" in para_text(ed.at(b.slot(0))) and "☒ Female" in para_text(ed.at(b.slot(1))), "fail"),
    M("an inserted ☑ instead of ☒", "mark-slot", "mark-slot",
      lambda ed, b: [setattr(t, "text", t.text.replace("☒", "☑")) for t in ed.at(b.slot(1)).iter(W + "t") if "☒" in (t.text or "")],
      lambda ed, b: "☑ Female" in para_text(ed.at(b.slot(1))) and "☒" not in para_text(ed.at(b.slot(1))), "fail"),
    M("the mark after the option, not before it", "mark-slot", "mark-slot",
      lambda ed, b: (mark_remove(ed.at(b.slot(1))), mark_after(ed.at(b.slot(1)), "Female")),
      lambda ed, b: "Female ☒" in para_text(ed.at(b.slot(1))) and "☒ Female" not in para_text(ed.at(b.slot(1))), "fail"),
    M("pre-ticked printed default left ticked", "mark-slot", "mark-slot", lambda ed, b: mark_insert(ed.at(b.slot(0)), "Male"),
      lambda ed, b: "☒ Male" in para_text(ed.at(b.slot(0))), "fail",
      lambda ed, b: mark_insert(ed.at(b.slot(0)), "Male"), lambda ed, b: "☒ Male" in para_text(ed.at(b.slot(0))),
      note="the original prints '☒ Male': that slot now holds a box, left ticked", pretick_positive=False),
    M("the inserted ☒ does not print (w:vanish)", "mark-slot", "mark-slot", lambda ed, b: hide_tick(ed.at(b.slot(1))),
      lambda ed, b: tick_hidden(ed.at(b.slot(1))), "fail"),
    # ── v2.1 reading 3: Wingdings 2 radio circles carried as w:t text (D28 A7, synthesized base, "No" = U+F098 ●) ──
    M("chosen box unticked", "wt-glyph", "wt-circle", lambda ed, b: wt_circle_set(ed.at(b.slot(1)), 0, "\uf081"),
      lambda ed, b: wt_circles(ed.at(b.slot(1))) == "81", "fail"),
    M("tick moved to the neighbour", "wt-glyph", "wt-circle",
      lambda ed, b: (wt_circle_set(ed.at(b.slot(1)), 0, "\uf081"), wt_circle_set(ed.at(b.slot(0)), 0, "\uf098")),
      lambda ed, b: wt_circles(ed.at(b.slot(0))) == "98" and wt_circles(ed.at(b.slot(1))) == "81", "fail"),
    M("two ticks for one single-choice answer", "wt-glyph", "wt-circle", lambda ed, b: wt_circle_set(ed.at(b.slot(0)), 0, "\uf098"),
      lambda ed, b: wt_circles(ed.at(b.slot(0))) == "98" and wt_circles(ed.at(b.slot(1))) == "98", "fail"),
    M("pre-ticked printed default left ticked", "wt-glyph", "wt-circle", lambda ed, b: wt_circle_set(ed.at(b.slot(0)), 0, "\uf098"),
      lambda ed, b: wt_circles(ed.at(b.slot(0))) == "98", "fail",
      lambda ed, b: wt_circle_set(ed.at(b.slot(0)), 0, "\uf098"), lambda ed, b: wt_circles(ed.at(b.slot(0))) == "98"),
    M("a ☒ inserted beside the circle, which stays ○", "wt-glyph", "wt-circle",
      lambda ed, b: (wt_circle_set(ed.at(b.slot(1)), 0, "\uf081"), mark_insert(ed.at(b.slot(1)), "No")),
      lambda ed, b: wt_circles(ed.at(b.slot(1))) == "81" and "☒ No" in para_text(ed.at(b.slot(1))), "fail",
      note="reading 4's declared case, on a w:t circle"),
    M("the font table no longer declares Wingdings 2 a symbol font", "wt-glyph", "wt-circle",
      lambda ed, b: font_charset_set(ed.root("word/fontTable.xml"), "Wingdings 2", "00"),
      lambda ed, b: font_charset(ed.root("word/fontTable.xml"), "Wingdings 2") == ["00"], "unverifiable",
      where=lambda b: ["word/fontTable.xml#"], note="fail-closed: the configuration every entry was render-checked in"),
    M("the ticked circle's run names another hAnsi font", "wt-glyph", "wt-circle",
      lambda ed, b: run_font_set(wt_circle_run(ed.at(b.slot(1))), "hAnsi", "Arial"),
      lambda ed, b: run_font(wt_circle_run(ed.at(b.slot(1))), "hAnsi") == "Arial", "unverifiable",
      note="fail-closed: the drawing slots must name one font"),
    M("a code outside the table as the tick (U+F09C)", "wt-glyph", "wt-circle", lambda ed, b: wt_circle_set(ed.at(b.slot(1)), 0, "\uf09c"),
      lambda ed, b: wt_circles(ed.at(b.slot(1))) == "9C", "unverifiable"),
    # ── v2.1 reading 4: Unicode radio circles (D15 A16 redrawn with ○, synthesized base, "No" = ●) ──
    M("a ☒ inserted beside a circle that stays ○", "radio", "radio",
      lambda ed, b: (glyph_map(ed.at(b.slot(1)), {"●": "○"}), mark_insert(ed.at(b.slot(1)), "No")),
      lambda ed, b: glyphs_in(ed.at(b.slot(1)), "○●◉") == "○" and "☒ No" in para_text(ed.at(b.slot(1))), "fail",
      note="the declared case (D15 prints its box after the option: '☒ No ○')"),
    M("chosen box unticked (● back to ○)", "radio", "radio", lambda ed, b: glyph_map(ed.at(b.slot(1)), {"●": "○"}),
      lambda ed, b: glyphs_in(ed.at(b.slot(1)), "○●◉") == "○", "fail"),
    M("tick moved to the neighbour", "radio", "radio",
      lambda ed, b: (glyph_map(ed.at(b.slot(1)), {"●": "○"}), glyph_map(ed.at(b.slot(0)), {"○": "●"})),
      lambda ed, b: glyphs_in(ed.at(b.slot(0)), "○●◉") == "●" and glyphs_in(ed.at(b.slot(1)), "○●◉") == "○", "fail"),
    M("two ticks for one single-choice answer (◉ ◉)", "radio", "radio",
      lambda ed, b: (glyph_map(ed.at(b.slot(1)), {"●": "◉"}), glyph_map(ed.at(b.slot(0)), {"○": "◉"})),
      lambda ed, b: glyphs_in(ed.at(b.slot(0)), "○●◉") == "◉" and glyphs_in(ed.at(b.slot(1)), "○●◉") == "◉", "fail"),
    M("pre-ticked printed default left ticked", "radio", "radio", lambda ed, b: glyph_map(ed.at(b.slot(0)), {"○": "●"}),
      lambda ed, b: glyphs_in(ed.at(b.slot(0)), "○●◉") == "●", "fail",
      lambda ed, b: glyph_map(ed.at(b.slot(0)), {"○": "●"}), lambda ed, b: glyphs_in(ed.at(b.slot(0)), "○●◉") == "●"),
    M("a large circle ◯ as the tick", "radio", "radio", lambda ed, b: glyph_map(ed.at(b.slot(1)), {"●": "◯"}),
      lambda ed, b: glyphs_in(ed.at(b.slot(1)), "○●◉◯") == "◯", "unverifiable", note="only ○ ◉ ● are declared"),
    # ── v2.1 reading 5: two questions in one paragraph ──
    M("this question's non-chosen option marked", "two-q", "two-q-marks-a11", lambda ed, b: mark_insert(ed.at(b.slot(0)), "condition"),
      lambda ed, b: "☒ condition" in para_text(ed.at(b.slot(0))), "fail", note="D17 A11; A12 in the same paragraph still passes"),
    M("this question's non-chosen option marked", "two-q", "two-q-marks", lambda ed, b: mark_insert(ed.at(b.slot(0)), "he"),
      lambda ed, b: "☒ he/" in para_text(ed.at(b.slot(0))), "fail", note="D17 A12; A11 in the same paragraph still passes"),
    M("a mark beside a word of no question", "two-q", "two-q-marks", lambda ed, b: mark_insert(ed.at(b.slot(0)), "presented"),
      lambda ed, b: "☒ presented" in para_text(ed.at(b.slot(0))), "fail", note="a mark tied to no question fails both"),
    M("this question's non-chosen box ticked", "two-q", "two-q-boxes-a61", lambda ed, b: glyph_set(ed.at(b.slot(0)), 1, "☒"),
      lambda ed, b: glyphs_of(ed.at(b.slot(0)))[:4] == "☒☒☒☐", "fail", note="D03 A61 (Before ticked); A60 still passes"),
    M("a box tied to no question ticked", "two-q", "two-q-boxes-orphan", lambda ed, b: glyph_set(ed.at(b.slot(0)), 3, "☒"),
      lambda ed, b: glyphs_of(ed.at(b.slot(0)))[:4] == "☒☐☒☒", "fail",
      note="GT copy without A61's 'After': its box belongs to no question"),
    # ── v2.1 reading 6: an answer written into one empty cell (D06 A58, synthesized base, "No" written) ──
    M("chosen box unticked (cell left empty)", "celltext", "celltext", lambda ed, b: cell_text_set(ed.at(b.slot(0)), None),
      lambda ed, b: cell_text(ed.at(b.slot(0))) == "", "fail"),
    M("another option's label written", "celltext", "celltext", lambda ed, b: cell_text_set(ed.at(b.slot(0)), "Yes"),
      lambda ed, b: cell_text(ed.at(b.slot(0))) == "Yes", "fail"),
    M("the label in another case", "celltext", "celltext", lambda ed, b: cell_text_set(ed.at(b.slot(0)), "no"),
      lambda ed, b: cell_text(ed.at(b.slot(0))) == "no", "unverifiable", note="exactly: any other text is unreadable"),
    M("the label with punctuation added", "celltext", "celltext", lambda ed, b: cell_text_set(ed.at(b.slot(0)), "No."),
      lambda ed, b: cell_text(ed.at(b.slot(0))) == "No.", "unverifiable"),
    M("a cell mark instead of the label", "celltext", "celltext", lambda ed, b: cell_text_set(ed.at(b.slot(0)), "X"),
      lambda ed, b: cell_text(ed.at(b.slot(0))) == "X", "unverifiable"),
    M("two labels written", "celltext", "celltext", lambda ed, b: cell_text_set(ed.at(b.slot(0)), "No/NA"),
      lambda ed, b: cell_text(ed.at(b.slot(0))) == "No/NA", "unverifiable"),
    M("the written label does not print (w:vanish)", "celltext", "celltext", lambda ed, b: cell_text_set(ed.at(b.slot(0)), "No", hidden=True),
      lambda ed, b: ed.at(b.slot(0)).find(".//" + W + "vanish") is not None, "unverifiable"),
    M("pre-filled printed default left in place", "celltext", "celltext", lambda ed, b: cell_text_set(ed.at(b.slot(0)), "Yes"),
      lambda ed, b: cell_text(ed.at(b.slot(0))) == "Yes", "unverifiable",
      lambda ed, b: cell_text_set(ed.at(b.slot(0)), "Yes"), lambda ed, b: cell_text(ed.at(b.slot(0))) == "Yes",
      note="a cell that is not empty in the original is no cell-text box"),
]

# the mutants each positive pre-ticked case is paired with: the original pre-ticked, the export correctly unticked
PRETICK_POSITIVES = [m for m in MUTANTS if m["omutate"] and m["expect"] == "fail" and m["pretick_positive"]]


def _apply(data, fn, check, b):
    ed = Editable(data)
    fn(ed, b)
    out = ed.save()
    return out, bool(check(Editable(out), b))


def _targets(b, m=None):
    return m["where"](b) if m and m.get("where") else b.area["slots"]


class Mutants(unittest.TestCase):
    results = []

    def test_each_mutant_applies_and_fails(self):
        for m in MUTANTS:
            with self.subTest(kind=m["kind"], mutant=m["name"]):
                b = base(m["base"])
                passed0, q0 = b.verdict()
                self.assertEqual(q0["verdict"], "pass", ("base does not pass", m["base"], q0))
                export, ok = _apply(b.export, m["mutate"], m["applied"], b)
                # ⚠️ the mutant must prove it applied before its verdict is believed
                self.assertTrue(export != b.export, "mutated bytes identical")
                self.assertTrue(ok, "post-condition of the mutation does not hold")
                self.assertTrue(any(xml_of(export, s) != xml_of(b.export, s) for s in _targets(b, m)), "no targeted element changed")
                original = b.original
                if m["omutate"]:
                    original, ok0 = _apply(b.original, m["omutate"], m["oapplied"], b)
                    self.assertTrue(original != b.original, "mutated original bytes identical")
                    self.assertTrue(ok0, "original mutation post-condition does not hold")
                    self.assertTrue(any(xml_of(original, s) != xml_of(b.original, s) for s in _targets(b, m)))
                passed, q = b.verdict(original, export)
                self.assertFalse(passed, "the mutated document passed")
                self.assertEqual(q["verdict"], m["expect"], q)
                Mutants.results.append({"kind": m["kind"], "mutant": m["name"], "doc": b.stem[:3], "question": b.qid,
                                        "synthesized_base": b.synthesized, "verdict": q["verdict"], "reason": q["reason"][:160],
                                        "killed": (not passed) and q["verdict"] != "pass", "note": m["note"]})

    @classmethod
    def tearDownClass(cls):
        if cls.results and RESULTS_OUT.exists():
            data = json.loads(RESULTS_OUT.read_text())
            data["mutants"] = cls.results
            RESULTS_OUT.write_text(json.dumps(data, indent=1, ensure_ascii=False))
        for r in cls.results:
            print("  %-9s %-44s %s %s -> %s" % (r["kind"], r["mutant"], r["doc"], r["question"], r["verdict"]))


# ─── the fail-closed readings, pinned on dev originals (nothing answered, export = original) ─────────────────────

class FailClosedReadings(unittest.TestCase):
    # v2.1 changed three v2.0 pins deliberately (each now PASSES on identity, see V21IdentityReadings):
    #   D28 A155 "list bullet"   -> reading 3+4: its Wingdings 2 radio-circle list bullets are read (○ unticked)
    #   D04 A2   "holds 0 boxes" -> reading 2: a printed option with no box in its own slot is read by the inserted mark
    #   D06 A58  "not printed"   -> reading 6: one empty answer cell is the "cell text" box kind
    # and one pin's REASON text (verdict unchanged): D05 A6 now says "(w:t) outside the glyph table" - reading 3 reads
    # Wingdings 2 text through the w:sym table, and 0x2A is not in it (it renders as a fallback glyph in every form).
    PINS = [("D24", "A29", "also tied to A32"),            # one printed option tied to two questions
            ("D03", "A7", "U+20DD"),                      # a glyph outside the table (the combining enclosing circle)
            ("D05", "A6", "U+002A in symbol font Wingdings 2 (w:t) outside the glyph table"),   # Wingdings 2 text, code out
            ("D27", "A33", "U+25A1"),                     # □ is recognised as a box, not in the table
            ("D29", "A103", "not printed in its slot"),   # reading 2's fail-closed branch: no box and no printed option
            ("D03", "A20", "holds 3 boxes"),              # one slot per option, a slot with several boxes
            ("D20", "A12", "picture"),                    # a picture where the box is
            ("D03", "A34", "mixture"),                    # boxes before some options only
            ("D38", "A32", "mixture"),                    # boxes after some options only
            ("D35", "A15", "lists no options"),
            ("D29", "A117", "not printed"),               # an answer to be written into a NON-empty label cell: no box
            ("D29", "A46", "a typed bracket box")]        # '[  ] no': a box typed as brackets, unreadable (v2.1)

    def test_pinned_unverifiable(self):
        cache = {}
        for prefix, qid, why in self.PINS:
            with self.subTest(doc=prefix, question=qid):
                stem = stem_of(prefix)
                if stem not in cache:
                    b0 = original_bytes(stem)
                    cache[stem] = {q["id"]: q for q in ticked.check_document(b0, b0, groundtruth(stem), {})["questions"]}
                q = cache[stem][qid]
                self.assertEqual(q["verdict"], "unverifiable", q)
                self.assertIn(why, q["reason"])


def _tiny_docx(paragraphs_xml, fonts=None):
    """A minimal package; `fonts` = {font name: charset} writes a word/fontTable.xml declaring them."""
    doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/'
           'wordprocessingml/2006/main"><w:body>%s</w:body></w:document>' % "".join(paragraphs_xml))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        z.writestr("word/document.xml", doc)
        if fonts is not None:
            z.writestr("word/fontTable.xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:fonts xmlns:w="http://'
                       'schemas.openxmlformats.org/wordprocessingml/2006/main">%s</w:fonts>' % "".join(
                           '<w:font w:name="%s"><w:charset w:val="%s"/></w:font>' % (n, c) for n, c in fonts.items()))
    return out.getvalue()


def _sym_para(font, code, label):
    return ('<w:p><w:r><w:sym w:font="%s" w:char="%s"/></w:r><w:r><w:t xml:space="preserve"> %s</w:t></w:r></w:p>' % (font, code, label))


class SymTable(unittest.TestCase):
    """The w:sym part of the glyph table, on synthetic packages (no dev document carries a w:sym box)."""

    def run_case(self, orig, exp, chosen):
        gt = {"answer_areas": [{"id": "Q", "kind": "choice", "options": ["Yes", "No"],
                                "slots": ["word/document.xml#b/p[0]", "word/document.xml#b/p[1]"]}]}
        return ticked.check_document(_tiny_docx(orig), _tiny_docx(exp), gt, {"Q": chosen})["questions"][0]

    def test_wingdings_boxes_read(self):
        o = [_sym_para("Wingdings", "F0A8", "Yes"), _sym_para("Wingdings", "F0A8", "No")]
        self.assertEqual(self.run_case(o, [_sym_para("Wingdings", "F0A8", "Yes"), _sym_para("Wingdings", "F0FE", "No")], [1])["verdict"], "pass")
        self.assertEqual(self.run_case(o, [_sym_para("Wingdings", "F0FE", "Yes"), _sym_para("Wingdings", "F0A8", "No")], [1])["verdict"], "fail")
        o2 = [_sym_para("Wingdings 2", "F0A3", "Yes"), _sym_para("Wingdings 2", "F0A3", "No")]
        self.assertEqual(self.run_case(o2, [_sym_para("Wingdings 2", "F052", "Yes"), _sym_para("Wingdings 2", "F0A3", "No")], [0])["verdict"], "pass")
        self.assertEqual(self.run_case(o2, [_sym_para("Wingdings 2", "F053", "Yes"), _sym_para("Wingdings 2", "F054", "No")], [0])["verdict"], "fail")

    def test_codes_outside_the_table_are_unreadable(self):
        # v2.1 reading 4 moved Wingdings 2 F099 (○) INTO the table (test_radio_circle_codes_read); F09C (a heavy ring
        # with a dot) and F09B (a heavy ring) take its place here - they render as neither ○ nor ●
        for font, code in (("Wingdings", "F078"), ("Wingdings 2", "F02A"), ("Wingdings 2", "F09C"), ("Wingdings 2", "F09B"),
                           ("Wingdings", "F0A4"), ("Wingdings", "F0A2"), ("Webdings", "F063")):
            with self.subTest(font=font, code=code):
                o = [_sym_para(font, code, "Yes"), _sym_para("Wingdings", "F0A8", "No")]
                q = self.run_case(o, [_sym_para(font, code, "Yes"), _sym_para("Wingdings", "F0FE", "No")], [1])
                self.assertEqual(q["verdict"], "unverifiable", q)


class PrintedTextTie(unittest.TestCase):
    """Rule 2, second bullet, on synthetic packages: an option's printed text is word-bounded ('No' is not the start
    of 'Not sure'), so a tick on the wrong box can never be read as the option's."""
    GT = {"answer_areas": [{"id": "Q", "kind": "choice", "options": ["Yes", "No"], "slots": ["word/document.xml#b/p[0]"]}]}

    def para(self, a, b, c):
        return ['<w:p><w:r><w:t xml:space="preserve">%s Yes %s Not sure %s No</w:t></w:r></w:p>' % (a, b, c)]

    def test_bordered_blank_is_a_box(self):
        box = '<w:r><w:rPr><w:bdr w:val="single" w:sz="4"/></w:rPr><w:t xml:space="preserve">   </w:t></w:r>'
        o = _tiny_docx(['<w:p>%s<w:r><w:t xml:space="preserve"> Yes </w:t></w:r>%s<w:r><w:t xml:space="preserve"> No</w:t></w:r></w:p>' % (box, box)])
        e = _tiny_docx(['<w:p>%s<w:r><w:t xml:space="preserve"> ☒ Yes </w:t></w:r>%s<w:r><w:t xml:space="preserve"> No</w:t></w:r></w:p>' % (box, box)])
        q = ticked.check_document(o, e, self.GT, {"Q": [0]})["questions"][0]
        self.assertNotEqual(q["verdict"], "pass", q)
        self.assertIn("bordered blank run", q["reason"])

    def test_tick_on_not_sure_is_not_no(self):
        o = _tiny_docx(self.para("☐", "☐", "☐"))
        good = ticked.check_document(o, _tiny_docx(self.para("☐", "☐", "☒")), self.GT, {"Q": [1]})["questions"][0]
        self.assertEqual(good["verdict"], "pass", good)
        wrong = ticked.check_document(o, _tiny_docx(self.para("☐", "☒", "☐")), self.GT, {"Q": [1]})["questions"][0]
        self.assertEqual(wrong["verdict"], "fail", wrong)


class LegacyDropdown(unittest.TestCase):
    """FORMDROPDOWN occurs nowhere in dev: its reader is exercised on synthetic packages only."""
    GT = {"answer_areas": [{"id": "Q", "kind": "choice", "options": ["Yes", "No"], "slots": ["word/document.xml#b/p[0]/ff[0]"]}]}

    def para(self, result, entries=("Yes", "No"), cached=None):
        res = '<w:result w:val="%d"/>' % result if result is not None else ""
        ents = "".join('<w:listEntry w:val="%s"/>' % e for e in entries)
        sep = '<w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>%s</w:t></w:r>' % cached if cached else ""
        return ['<w:p><w:r><w:t xml:space="preserve">Consent: </w:t></w:r><w:r><w:fldChar w:fldCharType="begin"><w:ffData>'
                '<w:name w:val="D1"/><w:enabled/><w:ddList>%s%s</w:ddList></w:ffData></w:fldChar></w:r>'
                '<w:r><w:instrText xml:space="preserve"> FORMDROPDOWN </w:instrText></w:r>%s'
                '<w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>' % (res, ents, sep)]

    def q(self, orig, exp, chosen):
        return ticked.check_document(_tiny_docx(orig), _tiny_docx(exp), self.GT, {"Q": chosen} if chosen is not None else {})["questions"][0]

    def test_legacy_dropdown(self):
        o = self.para(None)
        self.assertEqual(self.q(o, self.para(1), [1])["verdict"], "pass")
        self.assertEqual(self.q(o, self.para(0), [1])["verdict"], "fail")                       # another entry
        self.assertEqual(self.q(o, self.para(1, ("Yes", "No", "Maybe")), [1])["verdict"], "fail")  # entries changed
        self.assertEqual(self.q(o, self.para(None), None)["verdict"], "pass")                   # unanswered, unchanged
        self.assertEqual(self.q(o, self.para(1), None)["verdict"], "fail")                      # unanswered, changed
        self.assertEqual(self.q(o, self.para(1, cached="Yes"), [1])["verdict"], "unverifiable")  # cached result disagrees
        self.assertEqual(self.q(o, self.para(5), [1])["verdict"], "unverifiable")               # index out of range


# ─── v2.1 readings on synthetic packages ─────────────────────────────────────────────────────────────────────────

SYMBOL_FONTS = {"Wingdings": "02", "Wingdings 2": "02"}


def _wt_para(font_attrs, ch, label, extra_rpr=""):
    """A paragraph: a box character carried as w:t text in a run with the given rFonts attributes, then the label."""
    fonts = " ".join('w:%s="%s"' % kv for kv in font_attrs.items())
    return ('<w:p><w:r><w:rPr>%s<w:rFonts %s/></w:rPr><w:t xml:space="preserve">%s</w:t></w:r><w:r><w:t xml:space="preserve"> %s'
            '</w:t></w:r></w:p>' % (extra_rpr, fonts, ch, label))


def _all4(font):
    return {"ascii": font, "hAnsi": font, "eastAsia": font, "cs": font}


class SymTableV21(unittest.TestCase):
    """v2.1 reading 4 on w:sym: the radio circles added to the table (each render-checked, symcheck/)."""

    def run_case(self, o, e, chosen):
        gt = {"answer_areas": [{"id": "Q", "kind": "choice", "options": ["Yes", "No"],
                                "slots": ["word/document.xml#b/p[0]", "word/document.xml#b/p[1]"]}]}
        return ticked.check_document(_tiny_docx(o), _tiny_docx(e), gt, {"Q": chosen})["questions"][0]

    def test_radio_circle_codes_read(self):
        for font, off, on in (("Wingdings 2", "F081", "F098"), ("Wingdings 2", "F099", "F097"), ("Wingdings 2", "F09A", "F098"),
                              ("Wingdings", "F0A1", "F06C")):
            with self.subTest(font=font, off=off, on=on):
                o = [_sym_para(font, off, "Yes"), _sym_para(font, off, "No")]
                self.assertEqual(self.run_case(o, [_sym_para(font, off, "Yes"), _sym_para(font, on, "No")], [1])["verdict"], "pass")
                self.assertEqual(self.run_case(o, [_sym_para(font, on, "Yes"), _sym_para(font, off, "No")], [1])["verdict"], "fail")


class WtTable(unittest.TestCase):
    """v2.1 reading 3: Wingdings / Wingdings 2 characters stored as TEXT, read through the w:sym table."""
    GT = {"answer_areas": [{"id": "Q", "kind": "choice", "options": ["Yes", "No"],
                            "slots": ["word/document.xml#b/p[0]", "word/document.xml#b/p[1]"]}]}

    def q(self, o, e, chosen=(1,), fonts=SYMBOL_FONTS, efonts="same"):
        efonts = fonts if efonts == "same" else efonts
        return ticked.check_document(_tiny_docx(o, fonts), _tiny_docx(e, efonts), self.GT, {"Q": list(chosen)})["questions"][0]

    def test_text_forms_read_like_w_sym(self):
        for font, off, on in (("Wingdings", 0xA8, 0xFE), ("Wingdings", 0x6F, 0xFD), ("Wingdings", 0xA1, 0x6C),
                              ("Wingdings 2", 0xA3, 0x52), ("Wingdings 2", 0x81, 0x98), ("Wingdings 2", 0x99, 0x97)):
            for enc in ("pua", "byte"):
                for attrs in (_all4(font), {"ascii": font, "hAnsi": font}):
                    with self.subTest(font=font, off=off, on=on, enc=enc, slots=len(attrs)):
                        c = (lambda x: chr(0xF000 + x)) if enc == "pua" else chr
                        o = [_wt_para(attrs, c(off), "Yes"), _wt_para(attrs, c(off), "No")]
                        self.assertEqual(self.q(o, [_wt_para(attrs, c(off), "Yes"), _wt_para(attrs, c(on), "No")])["verdict"], "pass")
                        self.assertEqual(self.q(o, [_wt_para(attrs, c(on), "Yes"), _wt_para(attrs, c(off), "No")])["verdict"], "fail")

    def fc(self, o_attrs, e_attrs=None, code=0xFE, fonts=SYMBOL_FONTS, extra=""):
        e_attrs = e_attrs or o_attrs
        o = [_wt_para(o_attrs, "", "Yes"), _wt_para(o_attrs, "", "No")]
        e = [_wt_para(o_attrs, "", "Yes"), _wt_para(e_attrs, chr(0xF000 + code), "No", extra)]
        return self.q(o, e, fonts=fonts)

    def test_fail_closed_text_forms(self):
        wd = _all4("Wingdings")
        cases = {
            "no font table": dict(o_attrs=wd, fonts=None),
            "font table charset 00": dict(o_attrs=wd, fonts={"Wingdings": "00", "Wingdings 2": "02"}),
            "font table declares it twice": dict(o_attrs=wd, fonts=None),
            "ascii and hAnsi disagree": dict(o_attrs=wd, e_attrs={"ascii": "Wingdings", "hAnsi": "Arial"}),
            "eastAsia hint, eastAsia another font": dict(o_attrs=wd, e_attrs={"ascii": "Wingdings", "hAnsi": "Wingdings", "eastAsia": "Calibri", "hint": "eastAsia"}),
            "a code outside the table (0x78)": dict(o_attrs=wd, code=0x78),
            "Wingdings 2 0x2A": dict(o_attrs=_all4("Wingdings 2"), code=0x2A),
            "the ticked run does not print": dict(o_attrs=wd, extra="<w:vanish/>"),
            "a symbol font outside the two": dict(o_attrs=_all4("Webdings")),
        }
        for name, kw in cases.items():
            with self.subTest(case=name):
                if name == "font table declares it twice":
                    o = [_wt_para(wd, "", "Yes"), _wt_para(wd, "", "No")]
                    e = [_wt_para(wd, "", "Yes"), _wt_para(wd, "", "No")]
                    fonts_xml = _tiny_docx(e, {"Wingdings": "02"})
                    ed = Editable(fonts_xml)
                    f = etree.SubElement(ed.root("word/fontTable.xml"), W + "font")
                    f.set(W + "name", "wingdings")
                    etree.SubElement(f, W + "charset").set(W + "val", "00")
                    q = ticked.check_document(_tiny_docx(o, {"Wingdings": "02"}), ed.save(), self.GT, {"Q": [1]})["questions"][0]
                else:
                    q = self.fc(**kw)
                self.assertEqual(q["verdict"], "unverifiable", (name, q))

    def test_a_ticked_text_glyph_in_another_font_is_not_read_as_ticked(self):
        # U+F0FE drawn in Calibri (no symbol font) is a private-use character: recognised, unreadable
        q = self.fc(_all4("Wingdings"), e_attrs=_all4("Calibri"))
        self.assertEqual(q["verdict"], "unverifiable", q)


class RadioCircles(unittest.TestCase):
    """v2.1 reading 4 on Unicode circles: ○ unticked, ◉ and ● ticked; a ☒ beside a circle that stays ○ fails."""
    GT = {"answer_areas": [{"id": "Q", "kind": "choice", "options": ["Yes", "No"], "slots": ["word/document.xml#b/p[0]"]}]}

    def q(self, o, e, chosen):
        para = '<w:p><w:r><w:t xml:space="preserve">%s</w:t></w:r></w:p>'
        return ticked.check_document(_tiny_docx([para % o]), _tiny_docx([para % e]), self.GT, {"Q": chosen})["questions"][0]

    def test_circles(self):
        base = "○ Yes   ○ No"
        self.assertEqual(self.q(base, "○ Yes   ● No", [1])["verdict"], "pass")
        self.assertEqual(self.q(base, "○ Yes   ◉ No", [1])["verdict"], "pass")
        self.assertEqual(self.q(base, "● Yes   ○ No", [1])["verdict"], "fail")
        self.assertEqual(self.q(base, "○ Yes   ○ ☒ No", [1])["verdict"], "fail")         # the declared case
        self.assertEqual(self.q(base, "○ Yes   ◯ No", [1])["verdict"], "unverifiable")   # ◯ is not declared
        self.assertEqual(self.q(base, base, None)["verdict"], "pass")
        self.assertEqual(self.q("⃝ Yes   ⃝ No", "⃝ Yes   ⃝ No", None)["verdict"], "unverifiable")  # U+20DD


class CellText(unittest.TestCase):
    """v2.1 reading 6 on synthetic cells: one empty answer cell; its exported text must equal the chosen label."""
    GT = {"answer_areas": [{"id": "Q", "kind": "choice", "options": ["Yes", "No", "N/A"],
                            "slots": ["word/document.xml#b/tbl[0]/tr[0]/tc[1]"]}]}

    def doc(self, answer, label="Question"):
        runs = '<w:r><w:t xml:space="preserve">%s</w:t></w:r>' % answer if answer else ""
        return _tiny_docx(['<w:tbl><w:tr><w:tc><w:p><w:r><w:t>%s</w:t></w:r></w:p></w:tc><w:tc><w:p>%s</w:p></w:tc></w:tr></w:tbl>' % (label, runs)])

    def q(self, o, e, chosen):
        return ticked.check_document(self.doc(o), self.doc(e), self.GT, {"Q": chosen} if chosen is not None else {})["questions"][0]

    def test_cell_text(self):
        self.assertEqual(self.q("", "No", [1])["verdict"], "pass")
        self.assertEqual(self.q("", "  N/A ", [2])["verdict"], "pass")                  # outer spaces aside
        self.assertEqual(self.q("", "Yes", [1])["verdict"], "fail")
        self.assertEqual(self.q("", "", [1])["verdict"], "fail")
        self.assertEqual(self.q("", "NO", [1])["verdict"], "unverifiable")
        self.assertEqual(self.q("", "N / A", [2])["verdict"], "unverifiable")
        self.assertEqual(self.q("", "☒", [1])["verdict"], "unverifiable")
        self.assertEqual(self.q("", "No", [0, 1])["verdict"], "unverifiable")           # one cell shows one answer
        self.assertEqual(self.q("", "", None)["verdict"], "pass")
        self.assertEqual(self.q("", "No", None)["verdict"], "fail")
        self.assertEqual(self.q("Yes", "Yes", [0])["verdict"], "unverifiable")          # not empty in the original
        q = self.q("", "No", [1])
        self.assertEqual((q["mode"], q["box_kinds"]), ("cell-text", ["cell text"]))


class Mapping(unittest.TestCase):
    """v2.1 reading 1 in the reader: a mapping failure FAILS the question, whatever the boxes show."""

    def test_mapping_fails_even_when_the_boxes_are_right(self):
        b = base("ff")
        chosen = dict(b.chosen, **{b.qid: {"mapping": "the matched field refused the label"}})
        r = ticked.check_document(b.original, b.export, b.gt, chosen)
        q = [x for x in r["questions"] if x["id"] == b.qid][0]
        self.assertFalse(r["passed"])
        self.assertEqual(q["verdict"], "fail")
        self.assertTrue(q["reason"].startswith("mapping: "), q)
        self.assertEqual(q["answered"], "mapping")

    def test_mapping_is_not_masked_by_the_conflict_guard(self):
        stem = stem_of("D24")
        b0 = original_bytes(stem)
        r = ticked.check_document(b0, b0, groundtruth(stem), {"A29": {"mapping": "no detected field matches"}})
        q = [x for x in r["questions"] if x["id"] == "A29"][0]
        self.assertEqual(q["verdict"], "fail", q)


class _FakeFailure(ValueError):
    def __init__(self, message, code="invalid_answer"):
        super().__init__(message)
        self.code = code


class _FakeEngine:
    """Stands in for the candidate's fill API: refuses a choice answer that is not one of the field's options (or two
    answers for a single choice), and records every fill it is asked for."""
    V3Failure = _FakeFailure

    def __init__(self):
        self.calls = []

    def fill(self, data, fields, answers):
        self.calls.append(dict(answers))
        by = {f["key"]: f for f in fields}
        for k, v in answers.items():
            f = by[k]
            vals = v if isinstance(v, list) else [v]
            if f["kind"] == "choice" and (len(vals) > 1 or vals[0] not in f["options"]):
                raise _FakeFailure("The answer is not one of the printed options.")
            if f["kind"] == "multi_choice" and any(x not in f["options"] for x in vals):
                raise _FakeFailure("The answer is not one of the printed options.")
            if f["kind"] == "checkbox" and v is not True:
                raise _FakeFailure("A checkbox answer must be checked or unchecked.")
        return b"export:" + json.dumps(answers, sort_keys=True).encode()


class Answering(unittest.TestCase):
    """v2.1 reading 1 in answering.py, with a stand-in engine (the real engine drives info_v21.py)."""

    def test_chosen_answers_and_mapping_failures(self):
        import answering
        gt = {"answer_areas": [
            {"id": "Q1", "kind": "choice", "options": ["Yes", "No"], "slots": ["s#1"]},
            {"id": "Q2", "kind": "multi_choice", "options": ["A", "B", "C"], "slots": ["s#2"]},
            {"id": "Q3", "kind": "checkbox", "options": [], "slots": ["s#3"]},
            {"id": "Q4", "kind": "choice", "options": [], "slots": ["s#4"]},
            {"id": "Q5", "kind": "choice", "options": ["x", "y"], "slots": ["s#5"]},
            {"id": "Q6", "kind": "multi_choice", "options": ["A", "B", "C"], "slots": ["s#6"]},
            {"id": "Q7", "kind": "checkbox_group", "options": ["p", "q", "r"], "slots": ["s#7"]},
            {"id": "T1", "kind": "text", "slots": ["s#8"]}]}
        det = {"fields": [{"key": "f1", "kind": "choice", "options": ["Yes", "No"]},
                          {"key": "f2", "kind": "choice", "options": ["A", "B", "C"]},
                          {"key": "f3", "kind": "checkbox", "options": []},
                          {"key": "f4", "kind": "text"},
                          {"key": "f5", "kind": "choice", "options": ["x", "y"]},
                          {"key": "f6", "kind": "text"},
                          {"key": "f7", "kind": "multi_choice", "options": ["A", "B", "C"]},
                          {"key": "f8", "kind": "choice", "options": ["p", "q", "r"]}]}
        match = {"Q1": "f1", "Q2": "f2", "Q3": "f3", "Q4": "f4", "Q6": "f7", "Q7": "f8", "T1": "f6"}

        def score_doc(g, d):
            return {"rows": [{"id": a["id"], "det": {"key": match[a["id"]]}} if a["id"] in match else {"id": a["id"]}
                             for a in g["answer_areas"]]}

        def answers_for(fields, profile):
            return {"f1": "No", "f2": "B", "f3": True, "f4": "Q4v", "f5": "y", "f6": "Q6v " + profile, "f7": ["A", "B"], "f8": "q"}

        eng = _FakeEngine()
        a = answering.answer_document(eng, b"orig", gt, det, "long", score_doc, answers_for)
        self.assertEqual(a["chosen"]["Q1"], [1])
        self.assertEqual(a["chosen"]["Q3"], [0])
        self.assertEqual(a["chosen"]["Q6"], [0, 1])
        self.assertEqual(a["chosen"]["Q7"], [1])
        self.assertIn("unknown", a["chosen"]["Q4"])                  # no options: no label to give
        self.assertIn("no detected field", a["chosen"]["Q5"]["mapping"])
        self.assertIn("did not accept", a["chosen"]["Q2"]["mapping"])  # two labels to a single-choice field
        self.assertEqual(a["answers"], {"f1": "No", "f3": True, "f6": "Q6v long", "f7": ["A", "B"], "f8": "q"})
        self.assertEqual(set(a["refused"]), {"f2"})
        self.assertNotIn("f5", eng.calls[-1])                         # an unmatched choice field is left unanswered
        self.assertEqual(a["export"], b"export:" + json.dumps(a["answers"], sort_keys=True).encode())

    def test_answers_for_is_v1s_own(self):
        import answering
        fn, _, _ = answering.load_answers_for(pathlib.Path(SCORE_PY).parent / "final_eval.py")
        fields = [{"key": "a", "kind": "choice", "options": ["x", "y", "z"]}, {"key": "b", "kind": "text", "max_chars": 3},
                  {"key": "c", "kind": "checkbox"}, {"key": "d", "kind": "signature"}]
        self.assertEqual(fn(fields, "ordinary"), {"a": "y", "b": "Q2v", "c": True})
        self.assertEqual(fn(fields, "empty"), {})


class TwoQuestionsInOneParagraph(unittest.TestCase):
    """v2.1 reading 5: a box (or mark) tied to another question's option is judged by that question only."""

    def test_both_questions_pass_and_v20_would_have_failed_them(self):
        for key, pair in (("two-q-marks", ("A11", "A12")), ("two-q-boxes", ("A60", "A61"))):
            with self.subTest(base=key):
                b = base(key)
                passed, qs = b.verdicts()
                self.assertEqual([qs[i]["verdict"] for i in pair], ["pass", "pass"], [qs[i] for i in pair])
                # control: without reading 5 (nothing tied elsewhere) the same export fails one of them
                region = ticked.Region(ticked.Package(b.original), ticked.Package(b.export), b.areas[pair[0]]["slots"])
                tie = ticked.tie_options(region, b.areas[pair[0]])
                v, why, _ = ticked.judge(region, tie, b.chosen[pair[0]], b.areas[pair[0]]["options"])
                self.assertEqual(v, "fail", why)

    def test_the_other_question_is_judged_by_itself_only(self):
        for mkey, other in (("this question's non-chosen option marked", "A12"), ("this question's non-chosen box ticked", "A60")):
            m = [x for x in MUTANTS if x["name"] == mkey and x["kind"] == "two-q"][0]
            with self.subTest(mutant=mkey):
                b = base(m["base"])
                export, ok = _apply(b.export, m["mutate"], m["applied"], b)
                self.assertTrue(ok and export != b.export)
                passed, qs = b.verdicts(export=export)
                self.assertFalse(passed)
                self.assertEqual(qs[b.qid]["verdict"], "fail")
                self.assertEqual(qs[other]["verdict"], "pass", qs[other])


class SlotMarks(unittest.TestCase):
    """v2.1 reading 2, one slot per option, on synthetic packages: an option with no box is read by the inserted mark
    before its printed text IN ITS OWN SLOT."""
    GT = {"answer_areas": [{"id": "Q", "kind": "choice", "options": ["Left", "Right"],
                            "slots": ["word/document.xml#b/p[0]", "word/document.xml#b/p[1]"]}]}

    def q(self, o, e, chosen, gt=None):
        para = '<w:p><w:r><w:t xml:space="preserve">%s</w:t></w:r></w:p>'
        return ticked.check_document(_tiny_docx([para % x for x in o]), _tiny_docx([para % x for x in e]), gt or self.GT,
                                     {"Q": chosen} if chosen is not None else {})["questions"][0]

    def test_option_read_in_its_own_slot(self):
        o = ["Left (not right)", "Right"]
        self.assertEqual(self.q(o, ["Left (not right)", "☒ Right"], [1])["verdict"], "pass")
        self.assertEqual(self.q(o, ["Left (not ☒ right)", "Right"], [1])["verdict"], "fail")
        self.assertEqual(self.q(o, ["☒ Left (not right)", "Right"], [1])["verdict"], "fail")
        self.assertEqual(self.q(o, o, None)["verdict"], "pass")

    def test_option_not_printed_or_inside_a_longer_option(self):
        self.assertEqual(self.q(["Left", "Up"], ["Left", "☒ Up"], [1])["verdict"], "unverifiable")
        gt = {"answer_areas": [{"id": "Q", "kind": "choice", "options": ["Left", "Left and Right"],
                                "slots": ["word/document.xml#b/p[0]", "word/document.xml#b/p[1]"]}]}
        o = ["Left and Right", "Left and Right"]
        self.assertEqual(self.q(o, ["☒ Left and Right", "Left and Right"], [0], gt)["verdict"], "unverifiable")


class MarkReadingFailClosed(unittest.TestCase):
    """The inserted-mark reading, tightened in v2.1 (fail-closed, where the declaration is silent): text inserted
    right before an option, a rewritten neighbour, or a broken option text makes the option UNREADABLE - neither a
    tick nor proof of no tick. Found on dev: the candidate typed the label over '[he/she]', and the letters of 'she'
    lined up with the printed option's, so v2.0's reading called it 'unticked'."""
    GT = {"answer_areas": [{"id": "Q", "kind": "choice", "options": ["he", "she"], "slots": ["word/document.xml#b/p[0]"]}]}
    GT2 = {"answer_areas": [{"id": "Q", "kind": "multi_choice", "options": ["Yes", "No", "Maybe"], "slots": ["word/document.xml#b/p[0]"]}]}

    def q(self, o, e, chosen, gt):
        para = '<w:p><w:r><w:t xml:space="preserve">%s</w:t></w:r></w:p>'
        return ticked.check_document(_tiny_docx([para % o]), _tiny_docx([para % e]), gt, {"Q": chosen})["questions"][0]

    def test_a_label_typed_over_bracketed_options_is_unreadable(self):
        q = self.q("that [he/she] presented", "that she presented", [1], self.GT)
        self.assertEqual(q["verdict"], "unverifiable", q)
        self.assertIn("changed in the export", q["reason"])
        self.assertEqual(self.q("that [he/she] presented", "that [he/☒ she] presented", [1], self.GT)["verdict"], "pass")

    def test_text_inserted_before_an_option_is_no_proof_of_no_tick(self):
        # a typed X before a NON-chosen option: v2.0 read it 'unticked' and passed the question
        q = self.q("Yes   No   Maybe", "☒ Yes   ☒ No   X Maybe", [0, 1], self.GT2)
        self.assertEqual(q["verdict"], "unverifiable", q)
        self.assertIn("text inserted right before", q["reason"])

    def test_a_broken_option_text_is_unreadable(self):
        # 'Yes' cannot be read, so the ☒ before it is no option's mark either: the question fails
        q = self.q("Yes   No   Maybe", "☒ Ye s   No   Maybe", [0], self.GT2)
        self.assertEqual(q["verdict"], "fail", q)
        self.assertIn("'Yes': the option's printed text changed in the export", q["reason"])


class TypedBoxes(unittest.TestCase):
    """A box typed as brackets around nothing but spaces is a box of unreadable state (fail-closed, v2.1): neither
    '[X] Yes' nor '[  ] ☒ Yes' can pass, and without the recognition '[  ] ☒ Yes' would pass by the inserted mark."""
    GT = {"answer_areas": [{"id": "Q", "kind": "choice", "options": ["Yes", "No"], "slots": ["word/document.xml#b/p[0]"]}]}

    def q(self, o, e, chosen):
        para = '<w:p><w:r><w:t xml:space="preserve">%s</w:t></w:r></w:p>'
        return ticked.check_document(_tiny_docx([para % o]), _tiny_docx([para % e]), self.GT,
                                     {"Q": chosen} if chosen is not None else {})["questions"][0]

    def test_typed_boxes(self):
        for o, e in (("[  ] Yes   [  ] No", "[  ] ☒ Yes   [  ] No"), ("[  ] Yes   [  ] No", "[X] Yes   [  ] No"),
                     ("[] Yes   [] No", "[] ☒ Yes   [] No"), ("( ) Yes   ( ) No", "( ) ☒ Yes   ( ) No")):
            with self.subTest(export=e):
                # never a pass: the typed box cannot be read (unverifiable) - or, when the alignment pairs the inserted
                # ☒ with the typed box (glyphs align by kind, not by shape), the displaced typed box reads as an
                # inserted box of no option (fail)
                q = self.q(o, e, [0])
                self.assertNotEqual(q["verdict"], "pass", q)
                self.assertTrue("typed bracket box" in q["reason"] or "not in the export" in q["reason"], q)
        self.assertEqual(self.q("[  ] Yes   [  ] No", "[  ] Yes   [  ] No", None)["verdict"], "unverifiable")
        # '()' with nothing inside is not a typed box: the options are read by the inserted mark
        self.assertEqual(self.q("() Yes   No", "() ☒ Yes   No", [0])["verdict"], "pass")


class ConflictedTiesAreNoOnes(unittest.TestCase):
    """v2.1 reading 5 keeps the conflict guard: a box tied to two questions ties neither, so a THIRD question sharing
    the paragraph still judges it as a box tied to no question (fail closed)."""

    def test_third_question(self):
        para = '<w:p><w:r><w:t xml:space="preserve">%s</w:t></w:r></w:p>'
        s = ["word/document.xml#b/p[0]"]
        gt = {"answer_areas": [{"id": "Q1", "kind": "choice", "options": ["Yes", "No"], "slots": s},
                               {"id": "Q2", "kind": "choice", "options": ["Yes", "No"], "slots": s},
                               {"id": "Q3", "kind": "checkbox_group", "options": ["Maybe", "Unsure"], "slots": s}]}
        o = _tiny_docx([para % "☐ Yes ☐ No ☐ Maybe ☐ Unsure"])
        e = _tiny_docx([para % "☒ Yes ☐ No ☒ Maybe ☐ Unsure"])
        qs = {q["id"]: q for q in ticked.check_document(o, e, gt, {"Q1": [0], "Q3": [0]})["questions"]}
        self.assertEqual(qs["Q1"]["verdict"], "unverifiable")
        self.assertEqual(qs["Q3"]["verdict"], "fail", qs["Q3"])


class V21IdentityReadings(unittest.TestCase):
    """The v2.0 pins that v2.1 turned from unverifiable to PASS (nothing answered, export = original), each read by
    the new reading's mode and box kind."""
    PINS = [("D04", "A2", "slot-per-option", ["inserted mark"]),      # reading 2
            ("D28", "A155", "slot-per-option", ["glyph"]),            # readings 3 + 4 (a numbering bullet circle)
            ("D28", "A7", "slot-per-option", ["glyph"]),              # readings 3 + 4 (w:t circles)
            ("D06", "A58", "cell-text", ["cell text"])]               # reading 6

    def test_pinned_now_pass(self):
        cache = {}
        for prefix, qid, mode, kinds in self.PINS:
            with self.subTest(doc=prefix, question=qid):
                stem = stem_of(prefix)
                if stem not in cache:
                    b0 = original_bytes(stem)
                    cache[stem] = {q["id"]: q for q in ticked.check_document(b0, b0, groundtruth(stem), {})["questions"]}
                q = cache[stem][qid]
                self.assertEqual((q["verdict"], q["mode"], q["box_kinds"]), ("pass", mode, kinds), q)


# ─── (c) positive controls ──────────────────────────────────────────────────────────────────────────────────────

class PositiveControls(unittest.TestCase):
    def test_unmutated_passing_exports_pass(self):
        for prefix in ("D01", "D07", "D09", "D15", "D33"):
            stem = stem_of(prefix)
            r = ticked.check_document(original_bytes(stem), export_path(stem, "ordinary").read_bytes(), groundtruth(stem),
                                      chosen_for(stem, "ordinary"))
            self.assertTrue(r["passed"], (prefix, [q for q in r["questions"] if q["verdict"] != "pass"][:3]))
            self.assertTrue(any(q["answered"] is True for q in r["questions"]), prefix)

    def test_every_mutant_base_passes_and_survives_a_null_rewrite(self):
        for key in BASES:
            with self.subTest(base=key):
                b = base(key)
                self.assertEqual(b.verdict()[1]["verdict"], "pass")
                self.assertTrue(b.chosen.get(b.qid), "the base question is answered")
                rewritten, _ = _apply(b.export, lambda ed, bb: [ed.root(p) for p in {s.partition("#")[0] for s in bb.area["slots"]}],
                                      lambda ed, bb: True, b)
                # re-serialized through lxml; byte-identical when the export was itself written by lxml
                self.assertEqual(b.verdict(export=rewritten)[1]["verdict"], "pass")

    def test_pre_ticked_default_correctly_unticked_passes(self):
        for m in PRETICK_POSITIVES:
            with self.subTest(kind=m["kind"]):
                b = base(m["base"])
                original, ok = _apply(b.original, m["omutate"], m["oapplied"], b)
                self.assertTrue(ok)
                self.assertEqual(b.verdict(original=original)[1]["verdict"], "pass")

    def test_pre_ticked_printed_default_correctly_unticked_beside_marks(self):
        # v2.1 reading 2: an original printing '☒ Male' (a box in that slot), an export showing '☐ Male' and a mark
        # before 'Female': the slots mix a box and a mark, each read on its own
        b = base("mark-slot")
        original, ok0 = _apply(b.original, lambda ed, bb: mark_insert(ed.at(bb.slot(0)), "Male"),
                               lambda ed, bb: "☒ Male" in para_text(ed.at(bb.slot(0))), b)
        export, ok1 = _apply(b.export, lambda ed, bb: (mark_insert(ed.at(bb.slot(0)), "Male"), glyph_set(ed.at(bb.slot(0)), 0, "☐")),
                             lambda ed, bb: "☐ Male" in para_text(ed.at(bb.slot(0))), b)
        self.assertTrue(ok0 and ok1)
        q = b.verdict(original=original, export=export)[1]
        self.assertEqual(q["verdict"], "pass", q)
        self.assertEqual(q["box_kinds"], ["glyph", "inserted mark"], q)

    def test_identity_unanswered_never_fails(self):
        for stem in stems():
            b0 = original_bytes(stem)
            r = ticked.check_document(b0, b0, groundtruth(stem), {})
            self.assertEqual(r["counts"]["fail"], 0, stem)


if __name__ == "__main__":
    unittest.main()
