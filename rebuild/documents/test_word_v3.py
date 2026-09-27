"""Contract v3 through the sandboxed worker, on synthetic blank forms built here (no patient data)."""

from copy import deepcopy
import io
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from lxml import etree

from .service import DocumentError, fill_template, inspect_template, locate_fields, outline_template

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W14 = "http://schemas.microsoft.com/office/word/2010/wordml"


def _sdt(kind, *, options=(), placeholder="Choose an item.", nested=None):
    sdt = OxmlElement("w:sdt")
    pr = OxmlElement("w:sdtPr")
    sdt.append(pr)
    if kind == "dropdown":
        dd = OxmlElement("w:dropDownList")
        for o in options:
            li = OxmlElement("w:listItem")
            li.set(qn("w:displayText"), o)
            li.set(qn("w:value"), o)
            dd.append(li)
        pr.append(dd)
        pr.append(OxmlElement("w:showingPlcHdr"))
    elif kind == "checkbox":
        cb = etree.SubElement(pr, "{%s}checkbox" % W14)
        etree.SubElement(cb, "{%s}checked" % W14).set("{%s}val" % W14, "0")
    content = OxmlElement("w:sdtContent")
    sdt.append(content)
    if nested is not None:
        content.append(nested)
    else:
        r = OxmlElement("w:r")
        t = OxmlElement("w:t")
        t.text = "☐" if kind == "checkbox" else placeholder
        r.append(t)
        content.append(r)
    return sdt


def build_form(path, *, nested_wrapper=False):
    doc = Document()
    doc.sections[0].header.paragraphs[0].text = "Patient name: ____________"
    doc.add_paragraph("Synthetic clinic intake")
    table = doc.add_table(rows=3, cols=2)
    table.cell(0, 0).text = "Referring physician"
    table.cell(1, 0).text = "Reason for visit"
    table.cell(2, 0).text = "Allergies"
    doc.add_paragraph("Date of visit: ____________")
    doc.add_paragraph("Smoker?  ☐ Yes  ☐ No")
    p = doc.add_paragraph("Laterality: ")
    p._p.append(_sdt("dropdown", options=["Choose an item.", "Left", "Right", "Bilateral"]))
    doc.add_paragraph("Clinician signature: ____________")
    if nested_wrapper:
        inner_p = OxmlElement("w:p")
        inner_r = OxmlElement("w:r")
        inner_t = OxmlElement("w:t")
        inner_t.text = "Side: "
        inner_r.append(inner_t)
        inner_p.append(inner_r)
        inner_p.append(_sdt("dropdown", options=["Left", "Right"]))
        wrapper = _sdt("rich", nested=inner_p)
        doc.element.body.insert(len(doc.element.body) - 1, wrapper)
    doc.save(path)


def fields_by_label(fields):
    return {f["label"]: f for f in fields}


def part_text(path, part="word/document.xml"):
    with ZipFile(path) as z:
        root = etree.fromstring(z.read(part))
    return "".join(t.text or "" for t in root.iter("{%s}t" % W))


class ContractV3(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.original = self.dir / "form.docx"
        build_form(self.original)

    def tearDown(self):
        self.tmp.cleanup()

    def test_inspect_finds_every_structure_through_the_sandbox(self):
        info = inspect_template(self.original, engine="v3")
        self.assertEqual(info.get("contract"), "v3")
        by = fields_by_label(info["fields"])
        self.assertEqual(by["Referring physician"]["locator"]["target"]["type"], "cell")
        self.assertEqual(by["Date of visit"]["kind"], "date")
        self.assertEqual(by["Smoker?"]["kind"], "choice")
        self.assertEqual(by["Smoker?"]["options"], ["Yes", "No"])
        self.assertEqual(by["Laterality"]["options"], ["Left", "Right", "Bilateral"])
        self.assertEqual(by["Clinician signature"]["kind"], "signature")
        self.assertIn("word/header1.xml", {f["locator"]["part"] for f in info["fields"]})

    def test_fill_writes_answers_and_copies_every_other_part(self):
        info = inspect_template(self.original, engine="v3")
        by = fields_by_label(info["fields"])
        answers = {by["Referring physician"]["key"]: "Dr Example", by["Date of visit"]["key"]: "03/14/2026",
                   by["Smoker?"]["key"]: "No", by["Laterality"]["key"]: "Left", by["Patient name"]["key"]: "Synthetic Person"}
        out = self.dir / "out.docx"
        result = fill_template(self.original, info["fields"], answers, out)
        self.assertEqual(result["filled"], 5)
        body = part_text(out)
        self.assertIn("Dr Example", body)
        self.assertIn("03/14/2026", body)
        self.assertIn("Left", body)
        self.assertIn("Synthetic Person", part_text(out, "word/header1.xml"))
        self.assertIn("☐ Yes", body)             # the unchosen option stays printed
        self.assertIn("☒", body)                 # the chosen box is ticked
        with ZipFile(self.original) as a, ZipFile(out) as b:
            changed = {"word/document.xml", "word/header1.xml"}
            self.assertEqual([i.filename for i in a.infolist()], [i.filename for i in b.infolist()])
            for name in a.namelist():
                if name not in changed:
                    self.assertEqual(a.read(name), b.read(name), name)

    def test_signature_is_never_filled_and_a_moved_anchor_is_stale(self):
        info = inspect_template(self.original, engine="v3")
        by = fields_by_label(info["fields"])
        with self.assertRaises(DocumentError) as sig:
            fill_template(self.original, info["fields"], {by["Clinician signature"]["key"]: "Dr X"}, self.dir / "s.docx")
        self.assertEqual(sig.exception.code, "invalid_answer")
        tampered = deepcopy(info["fields"])
        for f in tampered:
            if f["label"] == "Referring physician":
                f["locator"]["fingerprint"] = "0" * 64
        with self.assertRaises(DocumentError) as stale:
            fill_template(self.original, tampered, {by["Referring physician"]["key"]: "x"}, self.dir / "t.docx")
        self.assertEqual(stale.exception.code, "stale_mapping")

    def test_an_option_not_printed_is_refused(self):
        info = inspect_template(self.original, engine="v3")
        by = fields_by_label(info["fields"])
        with self.assertRaises(DocumentError) as bad:
            fill_template(self.original, info["fields"], {by["Smoker?"]["key"]: "Former"}, self.dir / "o.docx")
        self.assertEqual(bad.exception.code, "invalid_answer")

    def test_a_control_wrapping_other_controls_is_read_by_its_parts_and_never_overwritten(self):
        wrapped = self.dir / "wrapped.docx"
        build_form(wrapped, nested_wrapper=True)
        info = inspect_template(wrapped, engine="v3")
        side = [f for f in info["fields"] if f["label"] == "Side"]
        self.assertEqual(len(side), 1)
        self.assertEqual(side[0]["options"], ["Left", "Right"])
        out = self.dir / "wrapped-out.docx"
        fill_template(wrapped, info["fields"], {side[0]["key"]: "Right"}, out)
        with ZipFile(wrapped) as a, ZipFile(out) as b:
            count = lambda z: etree.fromstring(z.read("word/document.xml")).findall(".//{%s}sdt" % W)
            self.assertEqual(len(count(a)), len(count(b)))

    def test_manual_field_is_located_recorded_as_manual_and_filled(self):
        outline = outline_template(self.original)
        slot = next(r for r in outline["slots"] if r["kind"] == "p" and r["preview"] == "Synthetic clinic intake")
        added = locate_fields(self.original, [{"slot": slot["slot"], "kind": "text", "label": "Clinic"}])["fields"]
        self.assertEqual(added[0]["origin"], "manual")
        out = self.dir / "manual.docx"
        fill_template(self.original, added, {added[0]["key"]: "North"}, out)
        self.assertIn("Synthetic clinic intake North", part_text(out))
        with self.assertRaises(DocumentError):
            cell = next(r for r in outline["slots"] if r["kind"] == "tc" and r["preview"] == "Allergies")
            locate_fields(self.original, [{"slot": cell["slot"], "kind": "text", "label": "Overwrite"}])

    def test_legacy_engine_is_unchanged_for_new_inspections_when_selected(self):
        try:
            info = inspect_template(self.original, engine="legacy")
        except DocumentError:
            return                               # the legacy contract refuses content controls, as before
        self.assertNotEqual(info.get("contract"), "v3")


if __name__ == "__main__":
    unittest.main()
