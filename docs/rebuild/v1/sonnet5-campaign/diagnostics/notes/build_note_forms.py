"""Real synthetic Word forms for the ordinary-notes cases (CHECK.md N6), so every case can run the app path:
upload -> inspect/mapping -> generate -> validation -> review -> finalize -> export.

Before this, every notes form was a hand-written field list with all-zero fingerprints and zero-length anchors, which
the application's own overlap rule rejects as a mapping; the cases could only run through the generation layer.
This generator writes one blank .docx per distinct field set, deterministically (the mapping set's Builder: fixed
core properties, fixed control ids, re-packed ZIP), with fresh wording. The case labels and kinds come from the
existing cases; the form around them (titles, headings, table structure) is new.

    python -B build_note_forms.py [--out DIR] [--check]            build (or: build twice in memory and compare)
    python -B build_note_forms.py --inspect [--json FILE]           inspect every form with the candidate (v3 and
                                                                    legacy) and compare with the case fields
    python -B build_note_forms.py --update-cases --state-dir DIR    write the inspected fields, form sha256, key map
                                                                    and cost bounds into cases.json

Inspection runs the candidate's isolated worker (documents.service.inspect_template), as an upload does. The cost
bound uses the application's own core.generation.maximum_cost per send path (default: 8,000 output tokens;
field_relations: 20,000), at the documented claude-sonnet-5 rates ($2 input / $10 output per million), then x1.1.
Sockets are denied in-process, the environment file and the database are never read.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import socket
import sys
from decimal import Decimal, ROUND_CEILING
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "mapping"))
from build_forms import Builder        # noqa: E402  (the mapping set's deterministic Builder)

WORKTREE = HERE.parents[5]
REBUILD = WORKTREE / "rebuild"
DEFAULT_OUT = Path("/opt/meddoc-pro/rebuild/.runtime/v1-sonnet5-campaign/diagnostics/notes")
CASES = HERE / "cases.json"
MARGIN = Decimal("1.1")
BUDGET_CAP = Decimal("10.00")


def _denied(*a, **k):
    raise PermissionError("network denied by build_note_forms.py")


socket.socket.connect = _denied
socket.socket.connect_ex = _denied
socket.create_connection = _denied
socket.getaddrinfo = _denied


# ─── the forms ─────────────────────────────────────────────────────────────────────────────────────────────────
# Item kinds:
#   ("cell", label, blanks)       one-cell table: "label:" then `blanks` empty paragraphs (1 -> the label's own kind,
#                                 2 -> long_text), a spacer paragraph after it
#   ("rows", [labels])            one two-column table, one row per label: label | empty answer cell (the label's
#                                 own kind); used for side labels, because a 'Right knee:' line is read as a side
#                                 HEADING and would become the next field's context
#   ("choice", label, options)    two-cell table: label | printed boxes, one per option
#   ("checkbox", label)           one-cell table: one printed box before the statement
#   ("signature", label)          body line "label: ____"
#   ("question_box", question)    body question, then an empty bordered one-cell answer table
#   ("h2", text) / ("h3", text)   headings
FORMS = {
    "r1-11": ("Clinic visit record", [
        ("cell", "Chief complaint", 1), ("cell", "History of present illness", 2), ("cell", "Past medical history", 2),
        ("cell", "Medications", 2), ("cell", "Allergies", 1), ("choice", "Smoker", ["Yes", "No"]),
        ("cell", "Examination", 2), ("cell", "Assessment", 2), ("cell", "Plan", 2),
        ("h2", "Sign-off"), ("checkbox", "Consent obtained"), ("signature", "Clinician signature")]),
    "n02-repeated-other": ("Headache questionnaire", [
        ("h2", "Section B"), ("h3", "How would you describe the pain? (tick all that apply)"), ("cell", "Other", 1),
        ("h3", "Do you notice anything before the headache begins? (tick all that apply)"), ("cell", "Other", 1),
        ("h2", "Section C"), ("h3", "What makes the pain worse? (tick all that apply)"), ("cell", "Other", 1)]),
    "n03-order-question": ("Community care review", [
        ("question_box", "Does a Community Treatment Order (CTO) currently apply to this person?"),
        ("cell", "Clinic attendance", 2)]),
    "n08-knee-and-findings": ("Knee review", [("rows", ["Right knee"]), ("rows", ["Clinical findings"])]),
    "n09-knee-pair": ("Knee review", [("rows", ["Right knee", "Left knee"])]),
    "n10-smoker-allergies": ("Lifestyle and allergies", [("choice", "Smoker", ["Yes", "No"]), ("cell", "Allergies", 1)]),
    "n11-n12-correction": ("Skin clinic record", [("cell", "Chief complaint", 1), ("cell", "Allergies", 1),
                                                  ("choice", "Smoker", ["Yes", "No"])]),
    "n13-risk-and-medication": ("Mental health review", [("cell", "Suicidal ideation", 2), ("cell", "Medication", 2)]),
    "n14-smoking-and-mental-state": ("Mental health review", [("cell", "Smoking status", 2), ("cell", "Mental state", 2)]),
    "n15-risk-and-arrangements": ("Risk review", [("cell", "Risk to self", 2), ("cell", "MAPPA status", 2)]),
    "n16-mood-and-allergies": ("Mental health review", [("cell", "Mental state", 2), ("cell", "Allergies", 2)]),
}
CASE_FORMS = {"N01": "r1-11", "N02": "n02-repeated-other", "N03": "n03-order-question", "N04": "r1-11",
              "N05": "r1-11", "N06": "r1-11", "N07": "r1-11", "N08": "n08-knee-and-findings", "N09": "n09-knee-pair",
              "N10": "n10-smoker-allergies", "N11": "n11-n12-correction", "N12": "n11-n12-correction",
              "N13": "n13-risk-and-medication", "N14": "n14-smoking-and-mental-state",
              "N15": "n15-risk-and-arrangements", "N16": "n16-mood-and-allergies"}
# Where the inspected field cannot carry the earlier synthetic definition, the inspected one is recorded (and why).
KNOWN_DIFFERENCES = {
    ("n08-knee-and-findings", "Clinical findings"): (
        "kind", "text", "long_text",
        "The candidate types every 'findings' label as long_text (documents/word_v3.py LONG_LABEL, kind_for); no Word "
        "structure yields a text field with this label. The case keeps the label; the kind is the inspected one."),
    ("n02-repeated-other", "Other"): (
        "label", "Other:", "Other",
        "The candidate strips the colon from a 'Label:' line; the three fields keep the repeated short label and differ "
        "only by their question context, which is what the case tests."),
}


def build(name) -> bytes:
    title, items = FORMS[name]
    b = Builder(title)
    b.doc.core_properties.comments = "Generated by build_note_forms.py for the Sonnet 5 notes diagnostics"
    b.para(title, style="Heading 1")
    for item in items:
        kind = item[0]
        if kind in ("h2", "h3"):
            b.para(item[1], style="Heading 2" if kind == "h2" else "Heading 3")
        elif kind == "cell":
            t = b.table(1, 1)
            cell = t.cell(0, 0)
            cell.paragraphs[0].add_run(item[1] + ":")
            for _ in range(item[2]):
                cell.add_paragraph()
            b.para()
        elif kind == "rows":
            t = b.table(len(item[1]), 2)
            for r, label in enumerate(item[1]):
                t.cell(r, 0).text = label
            b.para()
        elif kind == "choice":
            t = b.table(1, 2)
            t.cell(0, 0).text = item[1]
            b.inline_options("glyph", item[2], paragraph=t.cell(0, 1).paragraphs[0])
            b.para()
        elif kind == "checkbox":
            t = b.table(1, 1)
            b.option_line("glyph", item[1], paragraph=t.cell(0, 0).paragraphs[0])
            b.para()
        elif kind == "signature":
            b.para(item[1] + ": " + "_" * 30)
        elif kind == "question_box":
            b.para(item[1])
            b.table(1, 1)
            b.para()
        else:
            raise ValueError(kind)
    return b.bytes()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def case_fields(doc, case):
    form = case["form"]
    if isinstance(form, str):
        entry = doc["forms"][form]
        return entry["fields"] if isinstance(entry, dict) else entry
    return form


def inspect_all(out: Path):
    sys.path.insert(0, str(REBUILD))
    from documents import service
    result = {}
    for name in FORMS:
        path = out / (name + ".docx")
        v3 = service.inspect_template(str(path), engine="v3")
        try:
            legacy = service.inspect_template(str(path), engine="legacy")
            legacy_row = {"contract": legacy.get("contract", ""),
                          "fields": [(f.get("label"), f.get("kind")) for f in legacy["fields"]],
                          "warnings": legacy.get("warnings", [])}
        except service.DocumentError as exc:      # a refusal is a measured outcome
            legacy_row = {"refused": "%s: %s" % (exc.code, exc)}
        result[name] = {"sha256": sha(path.read_bytes()), "v3": v3, "legacy": legacy_row}
    return result


def compare(doc, inspected):
    """Each case's defined (label, kind, options) against the form's v3 inspection, in order."""
    rows = []
    for case in doc["cases"]:
        name = CASE_FORMS[case["id"]]
        got = [(f["label"], f["kind"], f.get("options") or []) for f in inspected[name]["v3"]["fields"]]
        want = []
        for f in case_fields(doc, case):
            label, kind = f["label"], f["kind"]
            diff = KNOWN_DIFFERENCES.get((name, label.rstrip(":")))
            if diff and diff[0] == "label" and label == diff[1]:
                label = diff[2]
            if diff and diff[0] == "kind" and kind == diff[1]:
                kind = diff[2]
            want.append((label, kind, f.get("options") or []))
        rows.append({"case": case["id"], "form": name, "matches": got == want, "inspected": got, "case_defines": want,
                     "notes": inspected[name]["v3"].get("notes") or inspected[name]["v3"].get("warnings") or [],
                     "legacy": inspected[name]["legacy"]})
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--inspect", action="store_true")
    ap.add_argument("--json", type=Path)
    ap.add_argument("--update-cases", action="store_true")
    ap.add_argument("--state-dir", type=Path)
    args = ap.parse_args(argv)
    if args.check:
        bad = [n for n in FORMS if build(n) != build(n)]
        for n in FORMS:
            print(("NOT DETERMINISTIC " if n in bad else "deterministic ") + n)
        return 1 if bad else 0
    if not (args.inspect or args.update_cases):
        args.out.mkdir(parents=True, exist_ok=True)
        lines = []
        for name in FORMS:
            data = build(name)
            path = args.out / (name + ".docx")
            path.write_bytes(data)
            assert path.read_bytes() == data
            lines.append("%s  %s.docx" % (sha(data), name))
            print("%s  %s.docx  (%d bytes)" % (sha(data), name, len(data)))
        (args.out / "SHA256SUMS").write_text("\n".join(lines) + "\n")
        return 0
    doc = json.loads(CASES.read_text())
    for name in FORMS:
        if (args.out / (name + ".docx")).read_bytes() != build(name):
            print("%s.docx differs from the generator; rebuild first" % name, file=sys.stderr)
            return 1
    inspected = inspect_all(args.out)
    rows = compare(doc, inspected)
    for r in rows:
        print("%s %-4s %-30s %s" % ("MATCH   " if r["matches"] else "MISMATCH", r["case"], r["form"],
                                     "" if r["matches"] else json.dumps({"inspected": r["inspected"],
                                                                         "case": r["case_defines"]})))
    if args.json:
        args.json.write_text(json.dumps({"schema": "quillmd-sonnet5-note-forms-inspection/1",
                                         "script_sha256": sha(Path(__file__).read_bytes()),
                                         "forms": {n: {"sha256": v["sha256"], "v3_fields": [
                                             {k: f.get(k) for k in ("key", "label", "kind", "options", "context")}
                                             for f in v["v3"]["fields"]],
                                             "v3_notes": v["v3"].get("notes", []),
                                             "legacy": v["legacy"]} for n, v in inspected.items()},
                                         "comparison": rows}, indent=1, ensure_ascii=False) + "\n")
    if not all(r["matches"] for r in rows):
        return 1
    if args.update_cases:
        return update_cases(doc, inspected, args)
    return 0


def update_cases(doc, inspected, args) -> int:
    """Forms by reference (sha256 + the inspected fields), case keys mapped to inspected keys, and cost bounds."""
    if not args.state_dir:
        print("--update-cases needs --state-dir (a scratch directory for the offline Django boot)", file=sys.stderr)
        return 1
    new_forms = {}
    for name, v in inspected.items():
        new_forms[name] = {"docx": name + ".docx", "sha256": v["sha256"],
                           "runtime_dir": str(DEFAULT_OUT), "generator": "notes/build_note_forms.py",
                           "inspected_with": "documents.service.inspect_template(path, engine='v3') at 8e3dcfd0",
                           "legacy_engine": v["legacy"],
                           "fields": v["v3"]["fields"]}
    changed = []
    for case in doc["cases"]:
        name = CASE_FORMS[case["id"]]
        old_fields = case_fields(doc, case)
        new_fields = new_forms[name]["fields"]
        assert len(old_fields) == len(new_fields), case["id"]
        key_map = {o["key"]: n["key"] for o, n in zip(old_fields, new_fields)}
        case["form"] = name
        case["case_keys"] = {n: o for o, n in key_map.items() if o != n}

        def rekey(obj):
            return {key_map.get(k, k): v for k, v in obj.items()}

        case["fields"] = rekey(case["fields"])
        for sim in case.get("adversarial_simulations", []) + case.get("offline_controls", []):
            sim["selection"] = rekey(sim["selection"])
            sim["expected"] = rekey(sim["expected"])
        for f_old, f_new in zip(old_fields, new_fields):
            diffs = {k: (f_old.get(k), f_new.get(k)) for k in ("label", "kind", "options")
                     if (f_old.get(k) or None) != (f_new.get(k) or None)}
            if diffs:
                changed.append({"case": case["id"], "key": f_new["key"], "differences": diffs})
    doc["forms"] = new_forms
    # cost bounds with the application's own function, per sent path, then x1.1
    sys.path.insert(0, str(HERE))
    import offline_replay
    offline_replay.boot(str(args.state_dir))
    from django.test import override_settings
    from core import generation as g, billing
    total = {"default": Decimal(0), "field_relations": Decimal(0)}
    for case in doc["cases"]:
        fields = new_forms[case["form"]]["fields"]
        bound = {}
        for path in case["send_paths"]:
            with override_settings(**offline_replay.path_settings()[path]):
                cost = g.maximum_cost(case["notes"], fields, g.configuration(fields))
            margin = (cost * MARGIN).quantize(Decimal("0.000001"), rounding=ROUND_CEILING)
            bound[path] = {"provider_cost_max": str(cost), "with_margin_x1_1": str(margin),
                           "customer_hold_max": str(cost * billing.MULTIPLIER)}
            total[path] += margin
        case["cost_bound_usd"] = bound
    all_paths = sum(total.values())
    doc["budget"].update({
        "bound_basis": ("per send: core.generation.maximum_cost for that path with the case's inspected fields = "
                        "(serialized request bytes + 12000) x $2/M input + profile max_output_tokens (8,000 default, "
                        "20,000 field_relations) x $10/M output, claude-sonnet-5; then x1.1. No retries are budgeted."),
        "planned_sends": {p: sum(1 for c in doc["cases"] if p in c["send_paths"]) for p in total},
        "cases": len(doc["cases"]),
        "total_with_margin_usd": {**{p: str(v) for p, v in total.items()}, "all": str(all_paths)},
        "within_cap": all_paths <= BUDGET_CAP and len(doc["cases"]) <= 16,
        "computed_by": "notes/build_note_forms.py --update-cases (before the freeze; deterministic, no provider)"})
    doc.setdefault("repairs", []).append(
        "N6: every case references a real synthetic .docx (sha256) and the fields the candidate's v3 inspect gives it; "
        "case keys mapped to inspected keys (case_keys); cost bound per case and in total recomputed with the inspected "
        "fields, x1.1")
    doc["inspected_field_differences"] = changed
    if not doc["budget"]["within_cap"]:
        print("budget bound exceeds the cap", file=sys.stderr)
        return 1
    CASES.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps({"total_with_margin_usd": doc["budget"]["total_with_margin_usd"],
                      "planned_sends": doc["budget"]["planned_sends"], "differences": changed}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
