"""Self-tests of ticked.py on the DEVELOPMENT set only (word-harness-v2.md, "Order of work", step 1).

    /opt/meddoc-pro/rebuild/.venv/bin/python -m unittest -v test_ticked

(a) DevInformation   ticked over the frozen candidate's dev ORDINARY and LONG exports; the counts are recorded in
                     dev-results.json. Information, not a gate: the only assertions are that every document and every
                     question got a verdict and every non-pass verdict carries a reason.
(b) Mutants          planted mutants on in-memory COPIES of exports, one or more per box kind present in dev. Each
                     mutant first proves it applied (the bytes differ, the targeted element's XML differs, and a
                     kind-specific post-condition holds) and only then is its verdict believed.
(c) PositiveControls unmutated passing exports pass; every mutant base passes (also after a null rewrite).
Also: Resolver       every slot listed by the corpus slot tool resolves to the element it names (independent check of
                     ticked.resolve against the tool that wrote the ground-truth slot ids).

Reads only: the dev corpus, the frozen dev results, and the v1 scorer (for the field-level GT <-> field join).
Never opens holdout/ or qual/. Writes only dev-results.json next to this file.
"""
import collections
import importlib.util
import io
import json
import pathlib
import re
import sys
import unittest
import zipfile

from lxml import etree

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ticked  # noqa: E402

CORPUS = pathlib.Path("/opt/meddoc-pro/rebuild/.runtime/v1-word-corpus")
DEV = CORPUS / "dev"
FROZEN = CORPUS / "results" / "dev-79a5b2ec6597-frozen"
SCORE_PY = "/opt/meddoc-pro/.worktrees/v1-release/docs/rebuild/v1/word-eval/score.py"
RESULTS_OUT = HERE / "dev-results.json"
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
        RESULTS_OUT.write_text(json.dumps({"harness": ticked.VERSION, "set": "dev", "results": FROZEN.name,
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
        return locate(self.root(part), path)

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


# ─── (b) the mutant table ───────────────────────────────────────────────────────────────────────────────────────

class Base:
    """A mutant base: an original, an export, the chosen sets, and the question under test."""

    def __init__(self, prefix, qid, profile="ordinary", synth=None, chosen_override=None, gt_edit=None):
        self.stem = stem_of(prefix)
        self.qid = qid
        self.gt = groundtruth(self.stem)
        self.area = [a for a in self.gt["answer_areas"] if a["id"] == qid][0]
        if gt_edit:
            gt_edit(self.area)                          # a copy: groundtruth() re-reads the file every call
        self.original = original_bytes(self.stem)
        self.chosen = dict(chosen_for(self.stem, profile))
        self.export = export_path(self.stem, profile).read_bytes()
        self.synthesized = synth is not None
        if synth:
            ed = Editable(self.export)
            synth(ed, self.area)
            self.export = ed.save()
        if chosen_override:
            self.chosen.update(chosen_override)

    def slot(self, i):
        return self.area["slots"][i]

    def verdict(self, original=None, export=None):
        r = ticked.check_document(original or self.original, export or self.export, self.gt, self.chosen)
        q = [x for x in r["questions"] if x["id"] == self.qid][0]
        return r["passed"], q


_BASES = {}


def base(key):
    if key not in _BASES:
        spec = BASES[key]
        _BASES[key] = Base(*spec[0], **spec[1])
    return _BASES[key]


def _tick_first(ed, area):                         # synthesized: the first option's content-control box ticked
    sdt_set(ed.at(area["slots"][0]), True)


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
    "orphan": (("D35", "A11"), {"gt_edit": lambda a: a.__setitem__("options", a["options"][:2])}),
}


def M(name, kind, base_key, mutate, applied, expect, original_mutate=None, original_applied=None, note=""):
    return {"name": name, "kind": kind, "base": base_key, "mutate": mutate, "applied": applied, "expect": expect,
            "omutate": original_mutate, "oapplied": original_applied, "note": note}


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
]

# the mutants each positive pre-ticked case is paired with: the original pre-ticked, the export correctly unticked
PRETICK_POSITIVES = [m for m in MUTANTS if m["omutate"] and m["expect"] == "fail"]


def _apply(data, fn, check, b):
    ed = Editable(data)
    fn(ed, b)
    out = ed.save()
    return out, bool(check(Editable(out), b))


def _targets(b):
    return b.area["slots"]


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
                self.assertTrue(any(xml_of(export, s) != xml_of(b.export, s) for s in _targets(b)), "no targeted element changed")
                original = b.original
                if m["omutate"]:
                    original, ok0 = _apply(b.original, m["omutate"], m["oapplied"], b)
                    self.assertTrue(original != b.original, "mutated original bytes identical")
                    self.assertTrue(ok0, "original mutation post-condition does not hold")
                    self.assertTrue(any(xml_of(original, s) != xml_of(b.original, s) for s in _targets(b)))
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
    PINS = [("D24", "A29", "also tied to A32"),            # one printed option tied to two questions
            ("D28", "A155", "list bullet"),               # a numbering bullet (Wingdings 2 radio) is a box, unreadable
            ("D03", "A7", "U+20DD"),                      # a glyph outside the table
            ("D05", "A6", "w:t, not w:sym"),              # a symbol-font character carried as text
            ("D04", "A2", "holds 0 boxes"),               # one slot per option, a slot without a box
            ("D20", "A12", "picture"),                    # a picture where the box is
            ("D03", "A34", "mixture"),                    # boxes before some options only
            ("D35", "A15", "lists no options"),
            ("D06", "A58", "not printed")]                # an option written as text is no box

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


def _tiny_docx(paragraphs_xml):
    doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/'
           'wordprocessingml/2006/main"><w:body>%s</w:body></w:document>' % "".join(paragraphs_xml))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        z.writestr("word/document.xml", doc)
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
        for font, code in (("Wingdings", "F078"), ("Wingdings 2", "F02A"), ("Wingdings 2", "F099"), ("Webdings", "F063")):
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

    def test_identity_unanswered_never_fails(self):
        for stem in stems():
            b0 = original_bytes(stem)
            r = ticked.check_document(b0, b0, groundtruth(stem), {})
            self.assertEqual(r["counts"]["fail"], 0, stem)


if __name__ == "__main__":
    unittest.main()
