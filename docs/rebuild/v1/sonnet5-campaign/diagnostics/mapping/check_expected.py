"""Engine-independent structural check of the expected maps against the generated forms.

This reads each .docx with zipfile + lxml ONLY (it never imports documents.word_v3 or any other QuillMD code) and
enumerates the body with the neutral slot grammar that the v3 contract documents for ground truth:

    b / p[n] | tbl[i] / tr[j] / tc[k] / p[n] / sdt[s] | ff[f] | glyphs#g

indices count same-kind children in document order; ff[f] counts legacy form fields (w:fldChar begin with
w:ffData) inside one paragraph; sdt[s] counts inline content controls that are direct children of the paragraph;
glyphs#g is the g-th printed ☐/☒ character of the paragraph's own text.

It then checks every expected map: each destination slot and control exists, each printed label/option is
really printed where the map says, controls are the kind the map says, and no control is claimed twice.

    python -B check_expected.py [--forms DIR] [--dump FORM]

Exit 0 = every expected map is consistent with the forms; 1 = at least one mismatch (each is printed).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path

from lxml import etree

HERE = Path(__file__).resolve().parent
DEFAULT_FORMS = Path("/opt/meddoc-pro/rebuild/.runtime/v1-sonnet5-campaign/diagnostics/mapping")
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W14 = "http://schemas.microsoft.com/office/word/2010/wordml"
BOXES = ("☐", "☒")


def q(tag):
    return "{%s}%s" % (W, tag)


def para_text(p):
    """Printed text of a paragraph: w:t text, tabs as \\t, each FORMCHECKBOX and checkbox control as ☐."""
    out = []
    in_field = False
    for el in p.iter():
        if el.tag == q("fldChar"):
            kind = el.get(q("fldCharType"))
            if kind == "begin" and el.find(q("ffData")) is not None \
                    and el.find(q("ffData") + "/" + q("checkBox")) is not None:
                out.append("☐")
            in_field = kind == "begin" or (in_field and kind != "end")
        elif el.tag == q("t") and el.text:
            out.append(el.text)
        elif el.tag == q("tab") and el.getparent() is not None and el.getparent().tag == q("r"):
            out.append("\t")
    return "".join(out)


def enumerate_slots(docx: Path) -> dict:
    """{slot path: {"kind": ..., "text": ...}} for the body, in the neutral grammar."""
    with zipfile.ZipFile(docx) as z:
        root = etree.fromstring(z.read("word/document.xml"))
    slots = {}

    def inside_control(t, p):
        """Whether text node `t` sits in a content control nested in paragraph `p`."""
        for a in t.iterancestors():
            if a is p:
                return False
            if a.tag == q("sdt"):
                return True
        return False

    def paragraph(p, path):
        slots[path] = {"kind": "p", "text": para_text(p)}
        for s, sdt in enumerate(p.findall(q("sdt"))):
            pr = sdt.find(q("sdtPr"))
            is_box = pr is not None and pr.find("{%s}checkbox" % W14) is not None
            slots["%s/sdt[%d]" % (path, s)] = {"kind": "sdt_checkbox" if is_box else "sdt", "text": ""}
        f = 0
        for fc in p.iter(q("fldChar")):
            if fc.get(q("fldCharType")) == "begin" and fc.find(q("ffData")) is not None:
                box = fc.find(q("ffData") + "/" + q("checkBox")) is not None
                slots["%s/ff[%d]" % (path, f)] = {"kind": "ff_checkbox" if box else "ff", "text": ""}
                f += 1
        g = 0
        for t in p.iter(q("t")):
            if inside_control(t, p):
                continue            # a content control's ☐ is the control, not a printed glyph
            for ch in t.text or "":
                if ch in BOXES:
                    slots["%s/glyphs#%d" % (path, g)] = {"kind": "glyph", "text": ch}
                    g += 1

    def container(el, path):
        counts = {}
        for child in el:
            local = etree.QName(child).localname if isinstance(child.tag, str) else None
            if local not in ("p", "tbl", "sdt"):
                continue
            i = counts.get(local, 0)
            counts[local] = i + 1
            sub = "%s/%s[%d]" % (path, local, i)
            if local == "p":
                paragraph(child, sub)
            elif local == "tbl":
                slots[sub] = {"kind": "tbl", "text": ""}
                for r, tr in enumerate(child.findall(q("tr"))):
                    for c, tc in enumerate(tr.findall(q("tc"))):
                        cpath = "%s/tr[%d]/tc[%d]" % (sub, r, c)
                        slots[cpath] = {"kind": "tc", "text": "\n".join(para_text(p) for p in tc.findall(q("p")))}
                        container(tc, cpath)
            else:
                slots[sub] = {"kind": "sdt", "text": ""}

    container(root.find(q("body")), "b")
    return slots


def norm(text):
    return re.sub(r"\s+", " ", (text or "").replace("☐", " ")).strip()


def check_form(expected_path: Path, forms_dir: Path) -> list:
    problems = []
    exp = json.loads(expected_path.read_text())
    docx = forms_dir / exp["docx"]
    if not docx.exists():
        return ["%s: form file missing: %s" % (expected_path.name, docx)]
    slots = enumerate_slots(docx)
    claimed = {}

    def need(slot, what, kinds=None):
        if slot not in slots:
            problems.append("%s: %s: slot %s does not exist" % (exp["form"], what, slot))
            return None
        if kinds and slots[slot]["kind"] not in kinds:
            problems.append("%s: %s: slot %s is %s, not %s" % (exp["form"], what, slot, slots[slot]["kind"], kinds))
        return slots[slot]

    def printed(slot, text, what):
        found = need(slot, what)
        if found is not None and norm(text) not in norm(found["text"]):
            problems.append("%s: %s: %r is not printed at %s (found %r)" % (exp["form"], what, text, slot,
                                                                              found["text"][:120]))

    def claim(control, owner):
        if control in claimed:
            problems.append("%s: control %s claimed by both %s and %s" % (exp["form"], control, claimed[control],
                                                                          owner))
        claimed[control] = owner

    for item in exp.get("areas", []) + exp.get("controls", []):
        ident = item["id"]
        dest = item.get("destination") or {}
        if dest.get("label_slot") and item.get("label"):
            printed(dest["label_slot"], item["label"], ident + " label")
        for slot in dest.get("slots", []):
            need(slot, ident + " destination")
        for p_slot, text in (dest.get("preserve") or {}).items():
            printed(p_slot, text, ident + " preserved text")
        controls = dest.get("controls") or []
        options = item.get("options") or (item.get("intent_if_representable") or {}).get("options") or []
        option_slots = dest.get("option_slots") or []
        if options and controls and len(options) != len(controls):
            problems.append("%s: %s has %d options but %d controls" % (exp["form"], ident, len(options), len(controls)))
        if option_slots and len(option_slots) != len(options):
            problems.append("%s: %s has %d options but %d option_slots" % (exp["form"], ident, len(options),
                                                                           len(option_slots)))
        for n, control in enumerate(controls):
            kind = "glyph" if "#" in control else ("ff_checkbox" if "/ff[" in control else "sdt_checkbox")
            need(control, ident + " control", {kind})
            claim(control, ident)
            if options:
                para = option_slots[n] if option_slots else control.rsplit("/", 1)[0]
                printed(para, options[n], ident + " option %d" % n)
        for region in ([dest["region"]] if dest.get("region") else []) + list(dest.get("regions") or []):
            need(region, ident + " region")
            if item.get("type") == "not_an_answer" and item.get("printed") and "<TAB>" not in item["printed"] \
                    and "/" not in item["printed"]:
                printed(region, item["printed"], ident + " printed")
        if dest.get("answer_at"):
            need(dest["answer_at"], ident + " answer_at")
        for printed_item in item.get("printed_on_form", []):
            printed(printed_item["slot"], printed_item["text"], ident + " printed")
    return problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--forms", type=Path, default=DEFAULT_FORMS)
    ap.add_argument("--dump", help="print the neutral slot enumeration of one form (name without .docx)")
    args = ap.parse_args(argv)
    if args.dump:
        for path, info in enumerate_slots(args.forms / (args.dump + ".docx")).items():
            print("%-40s %-12s %r" % (path, info["kind"], info["text"][:110]))
        return 0
    problems, checked = [], 0
    for expected in sorted(HERE.glob("*.expected.json")):
        problems += check_form(expected, args.forms)
        checked += 1
    for line in problems:
        print("MISMATCH " + line)
    print("%d expected maps checked, %d mismatches" % (checked, len(problems)))
    return 1 if problems or not checked else 0


if __name__ == "__main__":
    sys.exit(main())
