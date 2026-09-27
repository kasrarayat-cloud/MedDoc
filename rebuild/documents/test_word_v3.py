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


def ff_field(p, kind, options=(), checked=False, name="F"):
    """A legacy form field (FORMDROPDOWN or FORMCHECKBOX) appended to python-docx paragraph `p`."""
    def run(child):
        r = OxmlElement("w:r")
        r.append(child)
        p._p.append(r)
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    data = OxmlElement("w:ffData")
    n = OxmlElement("w:name")
    n.set(qn("w:val"), name)
    data.append(n)
    data.append(OxmlElement("w:enabled"))
    if kind == "dropdown":
        dd = OxmlElement("w:ddList")
        for o in options:
            e = OxmlElement("w:listEntry")
            e.set(qn("w:val"), o)
            dd.append(e)
        data.append(dd)
    else:
        cb = OxmlElement("w:checkBox")
        cb.append(OxmlElement("w:sizeAuto"))
        d = OxmlElement("w:default")
        d.set(qn("w:val"), "1" if checked else "0")
        cb.append(d)
        data.append(cb)
    begin.append(data)
    run(begin)
    instr = OxmlElement("w:instrText")
    instr.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    instr.text = " FORMDROPDOWN " if kind == "dropdown" else " FORMCHECKBOX "
    run(instr)
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run(end)


def ff_result(path):
    with ZipFile(path) as z:
        root = etree.fromstring(z.read("word/document.xml"))
    return [r.get("{%s}val" % W) for r in root.iter("{%s}result" % W)]


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


def docx_bytes(doc):
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def knee_form(path):
    """F1: dropdown options that differ only by an abbreviation a list-marker strip would remove."""
    doc = Document()
    doc.add_paragraph("Synthetic knee injection note")
    p = doc.add_paragraph("Injection site: ")
    p._p.append(_sdt("dropdown", options=["Choose an item.", "Rt. knee", "Lt. knee", "Bil. knees"]))
    Path(path).write_bytes(docx_bytes(doc))


class OptionReader(unittest.TestCase):
    """F1: the engine chooses an option exactly as the review reads it: the stored label, trimmed, case only."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_the_reviewed_option_is_the_exported_option(self):
        knee_form(self.dir / "knee.docx")
        info = inspect_template(self.dir / "knee.docx", engine="v3")
        field = next(f for f in info["fields"] if f["kind"] == "choice")
        self.assertEqual(field["options"], ["Rt. knee", "Lt. knee", "Bil. knees"])
        for answer, shown in (("Lt. knee", "Injection site: Lt. knee"), (" lt. KNEE ", "Injection site: Lt. knee"),
                              ("Bil. knees", "Injection site: Bil. knees")):
            out = self.dir / ("out-%d.docx" % len(list(self.dir.iterdir())))
            fill_template(self.dir / "knee.docx", info["fields"], {field["key"]: answer}, out)
            self.assertIn(shown, part_text(out), answer)
        with self.assertRaises(DocumentError) as refused:
            fill_template(self.dir / "knee.docx", info["fields"], {field["key"]: "knee"}, self.dir / "never.docx")
        self.assertEqual(refused.exception.code, "invalid_answer")

    def test_options_that_differ_only_in_punctuation_stay_distinct(self):
        doc = Document()
        doc.add_paragraph("Synthetic follow-up")
        p = doc.add_paragraph("Imaging reviewed: ")
        p._p.append(_sdt("dropdown", options=["Choose an item.", "Yes", "Yes*", "No"]))
        (self.dir / "star.docx").write_bytes(docx_bytes(doc))
        info = inspect_template(self.dir / "star.docx", engine="v3")
        field = next(f for f in info["fields"] if f["kind"] == "choice")
        self.assertEqual(field["options"], ["Yes", "Yes*", "No"])
        fill_template(self.dir / "star.docx", info["fields"], {field["key"]: "Yes*"}, self.dir / "star-out.docx")
        self.assertIn("Imaging reviewed: Yes*", part_text(self.dir / "star-out.docx"))

    def test_list_markers_are_digits_single_letters_and_roman_numerals_only(self):
        from documents.word_v3 import clean_label
        kept = ["Rt. knee effusion", "Lt. knee", "Bil. knees", "Dr. Example", "No. of lesions", "Mr. Synthetic",
                "Hx. reviewed", "Pt. consent"]
        for text in kept:
            self.assertEqual(clean_label(text), text)
        stripped = {"1. Name": "Name", "12) Plan": "Plan", "a) Yes": "Yes", "B. No": "No", "(3) Dose": "Dose",
                    "(c) Route": "Route", "iv. Findings": "Findings", "(xii) Impression": "Impression",
                    "XXX. Item": "Item", "vii) Item": "Item"}
        for text, label in stripped.items():
            self.assertEqual(clean_label(text), label, text)

    def test_laterality_survives_in_detected_and_typed_labels(self):
        doc = Document()
        doc.add_paragraph("Synthetic joint exam")
        doc.add_paragraph("Rt. knee effusion: ____________")
        doc.add_paragraph("Lt. knee effusion: ____________")
        doc.add_paragraph("")
        (self.dir / "joint.docx").write_bytes(docx_bytes(doc))
        info = inspect_template(self.dir / "joint.docx", engine="v3")
        self.assertEqual([f["label"] for f in info["fields"]], ["Rt. knee effusion", "Lt. knee effusion"])
        added = locate_fields(self.dir / "joint.docx", [{"slot": "word/document.xml#b/p[3]", "kind": "text",
                                                          "label": "Rt. knee aspirate volume"}])["fields"]
        self.assertEqual(added[0]["label"], "Rt. knee aspirate volume")



def repeated_options_form(path):
    """F7: one question printing the same option twice (boxes, a dropdown, printed words)."""
    doc = Document()
    doc.add_paragraph("Synthetic swelling check")
    doc.add_paragraph("Swelling:  ☐ Left  ☐ Right  ☐ Left")
    p = doc.add_paragraph("Answer given: ")
    p._p.append(_sdt("dropdown", options=["Choose an item.", "Yes", "No", "Yes"]))
    doc.add_paragraph("Was the dressing changed?")
    doc.add_paragraph("YES\t\tNO\t\tYES")
    Path(path).write_bytes(docx_bytes(doc))


class RepeatedOptions(unittest.TestCase):
    """F7: every printed option can be chosen, even one printed twice; fill maps by position."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.form = self.dir / "repeated.docx"
        repeated_options_form(self.form)
        self.fields = inspect_template(self.form, engine="v3")["fields"]
        self.by = fields_by_label(self.fields)

    def tearDown(self):
        self.tmp.cleanup()

    def test_repeated_options_get_print_order_suffixes(self):
        self.assertEqual(self.by["Swelling"]["options"], ["Left", "Right", "Left (2)"])
        self.assertEqual(self.by["Answer given"]["options"], ["Yes", "No", "Yes (2)"])
        self.assertEqual(self.by["Was the dressing changed?"]["options"], ["YES", "NO", "YES (2)"])
        self.assertEqual(self.by["Swelling"]["locator"]["target"]["printed"], ["Left", "Right", "Left"])

    def test_the_second_printing_is_the_one_ticked(self):
        out = self.dir / "second.docx"
        fill_template(self.form, self.fields, {self.by["Swelling"]["key"]: "Left (2)",
                                               self.by["Answer given"]["key"]: "Yes (2)",
                                               self.by["Was the dressing changed?"]["key"]: "YES (2)"}, out)
        body = part_text(out)
        self.assertIn("Swelling:  ☐ Left  ☐ Right  ☒ Left", body)
        self.assertIn("Answer given: Yes", body)
        self.assertNotIn("Yes (2)", body, "the printed option is written, never the suffix")
        self.assertIn("YESNO☒ YES", body, "tabs are not text: the words read YES, NO, YES")

    def test_a_legacy_dropdown_selects_the_entry_at_its_printing(self):
        doc = Document()
        doc.add_paragraph("Synthetic legacy form")
        ff_field(doc.add_paragraph("Answer given: "), "dropdown", ["Yes", "No", "Yes"])
        form = self.dir / "legacy-dd.docx"
        form.write_bytes(docx_bytes(doc))
        fields = inspect_template(form, engine="v3")["fields"]
        self.assertEqual(fields[0]["options"], ["Yes", "No", "Yes (2)"])
        for answer, index in (("Yes (2)", "2"), ("Yes", "0"), ("No", "1")):
            out = self.dir / ("dd-%s.docx" % index)
            fill_template(form, fields, {fields[0]["key"]: answer}, out)
            self.assertEqual(ff_result(out), [index], answer)

    def test_the_first_printing_stays_the_first(self):
        out = self.dir / "first.docx"
        fill_template(self.form, self.fields, {self.by["Swelling"]["key"]: "Left",
                                               self.by["Was the dressing changed?"]["key"]: "YES"}, out)
        body = part_text(out)
        self.assertIn("Swelling:  ☒ Left  ☐ Right  ☐ Left", body)
        self.assertIn("☒ YESNOYES", body)
        self.assertEqual(body.count("☒"), 2)


if __name__ == "__main__":
    unittest.main()
