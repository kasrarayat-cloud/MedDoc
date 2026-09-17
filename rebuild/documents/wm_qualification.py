"""Repeatable private qualification of the accepted blank WM IOV fixture.

XML is inspected for evidence only. All document changes use Aspose.Words FOSS.
This does not enable uploads, clinical generation, finalization, or exports.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import zipfile

from lxml import etree

ORIGINAL_SHA256 = "c1852a492221cfa0d144c9c0a60b700a7363a2cca7630aa988ee8b6329e1868b"
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
W = "{" + NS["w"] + "}"


def text(node):
    return "".join(node.xpath(".//w:t/text()", namespaces=NS))


def inspect(path):
    """Read-only metadata, controls, stable anchors, and preservation evidence."""
    result = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "parts": {}, "media": {}}
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if name.startswith("word/media/"):
                result["media"][name] = hashlib.sha256(archive.read(name)).hexdigest()
            if not (name.startswith("word/") and name.endswith(".xml") and
                    any(x in name for x in ("document", "header", "footer"))):
                continue
            root = etree.fromstring(archive.read(name), etree.XMLParser(resolve_entities=False, no_network=True))
            controls = []
            for ordinal, control in enumerate(root.xpath(".//w:sdt", namespaces=NS)):
                props = control.find("w:sdtPr", NS)
                parent = control.getparent()
                context = parent if parent.tag == W + "p" else control
                controls.append({
                    "ordinal": ordinal,
                    "id": props.find("w:id", NS).get(W + "val"),
                    "alias": props.find("w:alias", NS).get(W + "val") if props.find("w:alias", NS) is not None else None,
                    "tag": props.find("w:tag", NS).get(W + "val") if props.find("w:tag", NS) is not None else None,
                    "context": text(context),
                    "parent_type": etree.QName(parent).localname,
                    "nested_controls": len(control.xpath(".//w:sdt", namespaces=NS)),
                    "text": text(control),
                    "placeholder_active": props.find("w:showingPlcHdr", NS) is not None,
                    "options": [{etree.QName(k).localname: v for k, v in item.attrib.items()}
                                for item in props.findall("w:dropDownList/w:listItem", NS)],
                })
            paragraphs = root.xpath(".//w:body/w:p", namespaces=NS)
            tables = root.xpath(".//w:tbl", namespaces=NS)
            result["parts"][name] = {
                "controls": controls,
                "paragraph_count": len(root.xpath(".//w:p", namespaces=NS)),
                "body_paragraphs": [{"ordinal": i, "text": text(p)} for i, p in enumerate(paragraphs)],
                "non_control_text": "".join(root.xpath(".//w:t[not(ancestor::w:sdt)]/text()", namespaces=NS)),
                "paragraph_style_ids": root.xpath(".//w:pStyle/@w:val", namespaces=NS),
                "table_cells": [[[text(cell) for cell in row.findall("w:tc", NS)]
                                 for row in table.findall("w:tr", NS)] for table in tables],
                "section_geometry": [[(etree.QName(c).localname, dict(sorted(c.attrib.items())))
                                      for c in s if etree.QName(c).localname in {"pgSz", "pgMar", "cols", "docGrid", "pgNumType"}]
                                     for s in root.xpath(".//w:sectPr", namespaces=NS)],
            }
    return result


def clinical_manifest(source):
    part = source["parts"]["word/document.xml"]
    paragraphs = part["body_paragraphs"]
    assertions = []
    for i in (9, 11, 19, 23, 27, 30, 31, 32, 34, 35, 36, 39, 45, 46):
        value = paragraphs[i]["text"]
        assertions.append({"anchor": f"body:p:{i}", "original_text": value,
                           "text_sha256": hashlib.sha256(value.encode()).hexdigest(),
                           "export_gate": "Explicit source evidence plus clinician review; identity/signature fields must come from authenticated finalization, never model inference."})
    measurements = []
    locations = []
    for row, cells in enumerate(part["table_cells"][0]):
        if row in (0, 14):
            continue
        for column, unit in ((1, "mm"), (2, "ms")):
            measurements.append({"anchor": f"table:0:row:{row}:cell:{column}",
                                 "side": "right" if row < 14 else "left", "question": cells[0],
                                 "unit": unit, "original_text": cells[column],
                                 "export_gate": "Documented numeric value and explicit unit; never convert missing information into zero/normal."})
        if "<<insert location>>" in cells[0]:
            locations.append({"anchor": f"table:0:row:{row}:cell:0", "original_text": cells[0],
                              "export_gate": "Documented anatomical location and side; review duplicate unnamed tributaries individually."})
    return {"original_sha256": ORIGINAL_SHA256,
            "dropdown_gate": "Select only an existing option supported by source evidence. Unselected/missing/conflicting choices must remain explicit review blockers; longest-option fixture is deliberately clinically inconsistent.",
            "demographics": [{"anchor": f"body:p:{i}", "question": paragraphs[i]["text"]}
                             for i in (4, 5, 6, 7)],
            "measurements": measurements, "tributary_locations": locations,
            "prewritten_assertions_and_identity": assertions,
            "unclassified_blank_paragraphs": [p["ordinal"] for p in paragraphs if not p["text"]],
            "blank_paragraph_gate": "Layout spacing is not automatically an answer field. Bind any narrative field explicitly to a reviewed mapping version.",
            "signature_marker": {"anchor": "body:p:45", "marker": "<<insert date and time>>",
                                 "gate": "Finalization timestamp and actual authorized signer, never synthetic inference or preprinted identity."}}


def qualify(original, output, dotnet, assembly):
    if hashlib.sha256(original.read_bytes()).hexdigest() != ORIGINAL_SHA256:
        raise ValueError("Only the accepted blank fixture is allowed.")
    if ".runtime" not in output.parts or output.exists():
        raise ValueError("Use a new directory beneath private .runtime.")
    os.umask(0o077)
    output.mkdir(mode=0o700, parents=True)
    source = inspect(original)
    (output / "inventory.json").write_text(json.dumps(source, indent=2))
    (output / "clinical-mapping-manifest.json").write_text(json.dumps(clinical_manifest(source), indent=2))
    subprocess.run([str(dotnet), str(assembly), str(original), str(output)], check=True,
                   timeout=90, cwd=output, env={**os.environ, "DOTNET_CLI_TELEMETRY_OPTOUT": "1"})
    filled = inspect(output / "dropdowns.docx")
    sdk = json.loads((output / "sdk-evidence.json").read_text())
    checks = {}
    for name, old in source["parts"].items():
        new = filled["parts"][name]
        for key in ("paragraph_count", "non_control_text", "paragraph_style_ids", "table_cells", "section_geometry"):
            checks[f"{name}:{key}"] = old[key] == new[key]
        checks[f"{name}:control_ids"] = [c["id"] for c in old["controls"]] == [c["id"] for c in new["controls"]]
        checks[f"{name}:control_options"] = [c["options"] for c in old["controls"]] == [c["options"] for c in new["controls"]]
    choices = {x["id"]: x["display"] for x in sdk["selected"]}
    checks["all_28_selected_values"] = len(choices) == 28 and all(
        c["text"] == choices[c["id"]] and not c["placeholder_active"]
        for c in filled["parts"]["word/document.xml"]["controls"])
    checks["all_embedded_media_hashes_preserved"] = sorted(source["media"].values()) == sorted(filled["media"].values())
    checks["no_foss_watermark"] = "aspose" not in "".join(p["non_control_text"] for p in filled["parts"].values()).lower()
    full = inspect(output / "all-blanks.docx")["parts"]["word/document.xml"]
    checks["all_52_measurements"] = all(full["table_cells"][0][v["row"]][v["column"]] == v["value"] for v in sdk["measurements"])
    checks["all_6_locations"] = all(v["value"] in full["table_cells"][0][v["row"]][v["column"]] for v in sdk["locations"])
    checks["all_4_demographics"] = all(value in full["non_control_text"] for value in sdk["demographics"].values())
    checks["synthetic_signature_marker"] = "2026-09-17T12:00:00Z (SYNTHETIC)" in full["non_control_text"]
    long = inspect(output / "long-answer.docx")["parts"]["word/document.xml"]
    checks["full_19931_character_answer"] = sdk["long_answer"] in long["non_control_text"]
    checks["original_unchanged"] = hashlib.sha256(original.read_bytes()).hexdigest() == ORIGINAL_SHA256
    report = {"sdk": "Aspose.Words.FOSS26.3.0", "license": "MIT; no commercial SDK license used",
              "checks": checks, "all_structural_checks_pass": all(checks.values()),
              "long_answer_characters": sdk["long_answer_characters"],
              "visual_qualification": "Separate renderer evidence required; FOSS does not render pages.",
              "clinical_integration": "Not integrated; default assertions, identity, missing and contradictory choices remain explicit release gates."}
    (output / "qualification.json").write_text(json.dumps(report, indent=2))
    for path in output.iterdir():
        if path.is_file():
            path.chmod(0o600)
    print(json.dumps({"report": str(output / "qualification.json"), "passed": report["all_structural_checks_pass"], "checks": len(checks)}))
    if not report["all_structural_checks_pass"]:
        raise SystemExit(1)


def render_evaluation(original, output):
    """Optional proprietary evaluation renderer: artifacts are NOT deliverables."""
    import aspose.words as aw
    import pymupdf

    sdk = json.loads((output / "sdk-evidence.json").read_text())
    report = {"renderer": "Aspose.Words Python.NET26.9.0 commercial evaluation ONLY",
              "production_export_approved": False, "results": [],
              "font_limit": "VPS fontconfig substitutes Liberation Serif for Times New Roman and DejaVu Sans for Aptos/Aptos Display; native-font Word comparison remains unverified."}
    for name in ("blank", "dropdowns.docx", "all-blanks.docx", "long-answer.docx"):
        source = original if name == "blank" else output / name
        pdf = output / (name + ".evaluation.pdf")
        aw.Document(str(source)).save(str(pdf))
        doc = pymupdf.open(pdf)
        pages = [page.get_text() for page in doc]
        normal = "".join("\n".join(pages).split())
        signature_page = next((i for i, value in enumerate(pages) if "Electronically Signed On" in value), None)
        signature_together = (signature_page is not None and
                              "Maged S. Mikhail, MD, RPVI, RVT" in pages[signature_page])
        complete = name in {"all-blanks.docx", "long-answer.docx"}
        report["results"].append({
            "source": name, "pages": len(doc), "watermark_present": "aspose" in normal.lower(),
            "truncation_warning": "truncated" in normal.lower(),
            "all_dropdown_values_visible": all("".join(x["display"].split()) in normal for x in sdk["selected"]) if name != "blank" else None,
            "all_demographics_visible": all("".join(v.split()) in normal for v in sdk["demographics"].values()) if complete else None,
            "all_measurement_values_visible": all(v["value"] in "\n".join(pages) for v in sdk["measurements"]) if complete else None,
            "all_location_values_visible": all("".join(v["value"].split()) in normal for v in sdk["locations"]) if complete else None,
            "signature_label_and_signer_same_page": signature_together,
            "long_end_visible": "ENDOFSYNTHETICLONGANSWER" in normal if name == "long-answer.docx" else None,
            "long_sentence_ending_count": normal.count("retaineveryword.") if name == "long-answer.docx" else None,
        })
        for index, page in enumerate(doc):
            page.get_pixmap(matrix=pymupdf.Matrix(1, 1)).save(output / f"{name}.evaluation-{index+1}.png")
    report["dropdown_unchanged_page_images"] = [page for page in (2, 3) if
        (output / f"blank.evaluation-{page}.png").read_bytes() ==
        (output / f"dropdowns.docx.evaluation-{page}.png").read_bytes()]
    (output / "render-evidence.json").write_text(json.dumps(report, indent=2))
    for path in output.iterdir():
        if path.is_file():
            path.chmod(0o600)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--dotnet", required=True, type=Path)
    parser.add_argument("--assembly", required=True, type=Path)
    parser.add_argument("--render-evaluation", action="store_true", help="Private watermarked evaluation only; requires separately installed optional commercial SDK and PyMuPDF.")
    args = parser.parse_args()
    qualify(args.original.resolve(), args.output.resolve(), args.dotnet.resolve(), args.assembly.resolve())
    if args.render_evaluation:
        render_evaluation(args.original.resolve(), args.output.resolve())
