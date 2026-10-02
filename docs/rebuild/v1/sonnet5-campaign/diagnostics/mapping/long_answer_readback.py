"""CHECK.md M5: fill f6a's large free-text cell with a 5,001+ character answer through the app's documents service
and read it back, offline.

The frozen grader only checked that f6a.A2 carries no max_chars below 5,001. This exercises the claim "a >5,000
character answer must be accepted whole" on the candidate's real write path:

  1. the synthetic answer is long-answer.txt (fresh wording, generated here deterministically, no patient, no
     development text; wording_check.py scans it);
  2. f6a is inspected through the isolated worker exactly as an upload is (documents.service.inspect_template,
     engine v3), giving the mapping a TemplateVersion would store;
  3. documents.service.fill_template writes a NEW export with that answer (the original is never touched);
  4. documents.service.effective_values reads the written value back through the engine's own source-bound reader;
  5. the export is opened with zipfile+lxml and the answer cell's text is compared with the answer, and the
     question cell (f6a.C1) with the printed question.

    python -B long_answer_readback.py [--write-answer] [--out long-answer-readback.json]

--write-answer regenerates long-answer.txt (deterministic) and exits. No network (sockets denied in-process), no
provider, no database; the export is written to a temporary directory and deleted with it.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import io
import json
import socket
import sys
import tempfile
import zipfile
from pathlib import Path

from lxml import etree

HERE = Path(__file__).resolve().parent
WORKTREE = HERE.parents[5]
REBUILD = WORKTREE / "rebuild"
FORM = Path("/opt/meddoc-pro/rebuild/.runtime/v1-sonnet5-campaign/diagnostics/mapping/f6a-long-answer.docx")
ANSWER = HERE / "long-answer.txt"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _denied(*a, **k):
    raise PermissionError("network denied by long_answer_readback.py")


socket.socket.connect = _denied
socket.socket.connect_ex = _denied
socket.create_connection = _denied
socket.getaddrinfo = _denied


def synthetic_answer() -> str:
    """A synthetic discharge narrative, written here: day-by-day progress for a fictional admission."""
    opening = ("Presentation: admitted from the emergency department with three days of worsening breathlessness, a "
               "productive cough and a temperature of 38.4 degrees. Oxygen saturation on arrival was 89 percent on room "
               "air and improved to 95 percent on two litres by nasal cannula. The chest radiograph showed right lower "
               "zone consolidation. Blood tests showed a raised white cell count and a C-reactive protein of 146.")
    days = []
    plans = ["intravenous antibiotics continued", "oxygen weaned by one litre", "encouraged to sit out in the chair",
             "physiotherapy reviewed chest clearance", "fluid balance charted", "observations every four hours",
             "diet and fluids tolerated", "blood tests repeated in the morning"]
    for n in range(1, 22):
        temp = 38.4 - 0.2 * n if n < 8 else 36.8
        sats = min(98, 89 + n)
        days.append("Day %d: temperature %.1f degrees, saturation %d percent, %s; %s. The team reviewed progress at "
                    "the bedside and the plan was explained again in plain words." % (
                        n, temp, sats, plans[n % len(plans)], plans[(n + 3) % len(plans)]))
    closing = ("Investigations: repeat radiograph on day ten showed partial clearing of the consolidation. Sputum "
               "culture grew a sensitive organism and the antibiotic was changed to an oral agent on day seven. "
               "Treatment and progress: mobility returned to the level before admission with a frame, and the "
               "occupational therapist confirmed safe transfers at home. Plan after discharge: complete the oral "
               "course, attend the respiratory clinic in six weeks with a repeat radiograph, and return urgently if "
               "breathlessness or fever comes back. The family doctor is asked to review the blood pressure "
               "medicines, which were reduced during the admission.")
    medicines = ("Medicines on discharge: the oral antibiotic until the course is complete, the usual inhaler twice "
                 "daily with the spacer, paracetamol when needed for discomfort, and the reduced dose of the blood "
                 "pressure tablet. The inhaler technique was checked by the ward pharmacist before discharge and a "
                 "written list of every change was given to the patient and to the carer.")
    return "\n".join([opening] + days + [medicines, closing])


def cell_text(tc) -> str:
    """Printed text of a cell: paragraphs joined by a newline, w:br as a newline, w:tab as a tab."""
    def para(p):
        out = []
        for el in p.iter("{%s}t" % W, "{%s}br" % W, "{%s}tab" % W):
            out.append(el.text or "" if el.tag == "{%s}t" % W else ("\n" if el.tag == "{%s}br" % W else "\t"))
        return "".join(out)
    return "\n".join(para(p) for p in tc.iter("{%s}p" % W))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write-answer", action="store_true")
    ap.add_argument("--out", type=Path, default=HERE / "long-answer-readback.json")
    args = ap.parse_args(argv)
    answer = synthetic_answer()
    if args.write_answer:
        ANSWER.write_text(answer)
        print("wrote %s: %d characters" % (ANSWER.name, len(answer)))
        return 0
    if ANSWER.read_text() != answer:
        print("long-answer.txt differs from the generator; run --write-answer", file=sys.stderr)
        return 1
    if len(answer) <= 5000:
        print("the synthetic answer is not longer than 5,000 characters", file=sys.stderr)
        return 1
    sys.path.insert(0, str(REBUILD))
    from documents import service
    result = {"schema": "quillmd-sonnet5-long-answer-readback/1",
              "recorded_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "form": FORM.name, "form_sha256": hashlib.sha256(FORM.read_bytes()).hexdigest(),
              "answer_file": ANSWER.name, "answer_sha256": hashlib.sha256(answer.encode()).hexdigest(),
              "answer_characters": len(answer), "answer_paragraphs": answer.count("\n") + 1,
              "network": "socket connect/create_connection/getaddrinfo denied in-process"}
    with tempfile.TemporaryDirectory(prefix="long-answer-") as tmp:
        original = Path(tmp) / "original.docx"
        original.write_bytes(FORM.read_bytes())
        inspected = service.inspect_template(str(original), engine="v3")
        fields = inspected["fields"]
        target = next(f for f in fields if f["label"].startswith("Full account of the admission"))
        result["field"] = {k: target.get(k) for k in ("key", "label", "kind", "max_chars")}
        result["field"]["target_type"] = target["locator"]["target"]["type"]
        answers = {target["key"]: answer}
        export = Path(tmp) / "export.docx"
        filled = service.fill_template(str(original), fields, answers, str(export))
        result["fill"] = {k: filled.get(k) for k in ("filled", "missing", "contract") if k in filled}
        states = service.effective_values(str(original), fields, answers)["states"]
        read_back = states.get(target["key"])
        result["effective_values"] = {"type": type(read_back).__name__,
                                      "characters": len(read_back) if isinstance(read_back, str) else None,
                                      "equals_answer": read_back == answer}
        with zipfile.ZipFile(export) as z:
            root = etree.fromstring(z.read("word/document.xml"))
            names_same = z.namelist() == zipfile.ZipFile(io.BytesIO(FORM.read_bytes())).namelist()
        cells = list(root.iter("{%s}tc" % W))
        written = cell_text(cells[1])
        result["export"] = {"answer_cell_characters": len(written), "answer_cell_equals_answer": written == answer,
                            "answer_cell_paragraphs": len(list(cells[1].iter("{%s}p" % W))),
                            "answer_cell_line_breaks": len(list(cells[1].iter("{%s}br" % W))),
                            "question_cell_unchanged": cell_text(cells[0]) == cell_text(
                                list(etree.fromstring(zipfile.ZipFile(io.BytesIO(FORM.read_bytes())).read(
                                    "word/document.xml")).iter("{%s}tc" % W))[0]),
                            "zip_members_unchanged": names_same,
                            "original_unchanged": hashlib.sha256(original.read_bytes()).hexdigest() == result["form_sha256"]}
    ok = (result["effective_values"]["equals_answer"] and result["export"]["answer_cell_equals_answer"]
          and result["export"]["question_cell_unchanged"] and result["export"]["original_unchanged"])
    result["verdict"] = "ACCEPTED WHOLE" if ok else "NOT ACCEPTED WHOLE"
    args.out.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps(result, indent=1, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
