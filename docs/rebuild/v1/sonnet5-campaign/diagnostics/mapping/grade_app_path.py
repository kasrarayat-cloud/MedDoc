"""Grade the OUTPUT OF THE APP PATH for model-assisted mapping (CHECK.md M1).

What is graded is what the application keeps and shows after `core.mapping_assistance.validate_proposal`:

    {"fields": [...],                      # the proposed mapping version's fields (prior fields kept or replaced,
                                           #  additions located at their slots)
     "review": {"verdicts": {...},         # every field and slot verdict the model returned (expanded wire)
                "areas": [...],            # every outline slot with the model's slot verdict (the review table)
                "unresolved": [...],       # the areas a clinician must decide before the version can be confirmed
                ...}}

(A stored TemplateVersion is accepted too: `{"fields": version.fields, "assistance": version.assistance}`.)

The frozen grader (measure_baseline.py) reads only the field list, so a correct model HOLD and doing nothing looked
the same. Here each expected area and control of the frozen maps (*.expected.json, unchanged in clinical content)
is graded from the fields AND the review record:

  right        exactly one covering field that passes every measure_baseline.grade_area condition, and nothing
               holds the area;
  held_safe    the area is held for the clinician: a covering field carries a not_answer/uncertain FIELD verdict or
               any unresolved record with its key (a refused replacement leaves the prior field with such a record),
               or an unresolved record lies on the area's destination (an uncertain SLOT verdict, or a covered slot
               that nothing maps). Confirmation is refused while any record is open (core/views.py v3_confirm), and
               a clinician's "not an answer" decision on a record that carries a field key removes that field
               (core/mapping_views.py resolve). `field_grade_under_hold` records what the held field would have
               graded; `hold_reaches_field` is false when the only hold is a slot record, whose "not an answer"
               decision removes nothing;
  wrong        covered by an un-held field that fails a condition (kind, boxes, options, codes, identity,
               preservation, capacity, split, covers another area);
  missed       no covering field and no hold. `dismissed_by_model` marks an area whose destination slots the model
               called not_answer: validate_proposal creates NO unresolved record for a not_answer SLOT verdict
               (mapping_assistance.py:191-193), the clinician sees it only in the collapsed verdict table, and
               confirmation is not blocked, so a dismissal is not a hold;
  false_field  an answerable field that covers no expected area and sits in no control (false_field_held when a
               record holds it).

Controls: not_an_answer / must_refuse are right when no un-held answerable field is there, held_safe when every
offending field is held, wrong otherwise; must_hold is right when no un-held answerable field covers it (a hold is
its expected outcome).

Each area and control also carries `expressible`: whether the model-assisted path at this candidate can produce the
expected outcome at all, with the code reason when it cannot (`not_expressible_at_candidate`). It is derived from
the deterministic fields the request starts from and from the request's own outline rows.

    python -B grade_app_path.py --self-test [--out app-path-selftest.json] [--state-dir DIR]
        Offline, no provider: for every synthetic form, inspect it through the candidate's isolated worker, compile
        the real mapping request (compile_request), build hand-made wire responses (a correct model, a do-nothing
        model, a harmful model, and the app's own offline fixture), run the real validate_proposal on each, grade
        each output, and assert that they grade differently. Sockets, the environment file and the database are
        denied; the compiled request is never sent.
    python -B grade_app_path.py --grade OUTPUT.json --form NAME [--deterministic FIELDS.json]
        Grade one recorded app-path output (a live run) against the frozen map of NAME.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import os
import re
import socket
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import measure_baseline as mb        # noqa: E402  (denies sockets on import; reuses the frozen grading rules)

WORKTREE = HERE.parents[5]
REBUILD = WORKTREE / "rebuild"
DEFAULT_FORMS = mb.DEFAULT_FORMS
FORMS = mb.FORMS
PART = "word/document.xml#"
HOLD_VERDICTS = ("not_answer", "uncertain")

# Code reasons, quoted by file and line at candidate 8e3dcfd0.
NO_MULTI_CHOICE = ("no multi_choice kind in the model wire contract: core/mapping_wire.py:14 KINDS=('text','long_text',"
                   "'date','time','choice','checkbox','signature','initials') and core/mapping_assistance.py:38 "
                   "Target.kind; a multi-select is reachable only by KEEPING a deterministic multi_choice field")
OPTIONS_NOT_AT_SLOT = ("options must be printed at the target slot itself: core/mapping_assistance.py:143 builds the "
                       "source from that slot's text/heading/row_label/options and :148-149 refuses any option not in "
                       "it; the expected option words are printed only in another paragraph (a literal header line "
                       "or a row label)")
PRIOR_KEPT = ("a not_answer or uncertain verdict KEEPS the existing field (core/mapping_assistance.py:173-174) and a "
              "replacement must cover the prior destination (:177-178) with the kind the located slot has "
              "(:163-166, a legacy checkbox locates as 'checkbox', so a signing kind is refused); only the "
              "clinician's resolution can remove it (core/mapping_views.py:82)")


# ─── normalising the app output ──────────────────────────────────────────────────────────────────────────────
def neutral(slot: str) -> str:
    slot = slot or ""
    return slot.split("#", 1)[1] if "#" in slot else slot


def touches(record_slot: str, dest: str) -> bool:
    """A record on the destination, inside it, or on a container holding it."""
    return bool(record_slot) and (mb.inside(record_slot, dest) or mb.inside(dest, record_slot))


def review_of(output: dict) -> dict:
    return output.get("review") or output.get("assistance") or {}


def hold_index(output: dict) -> dict:
    review = review_of(output)
    verdicts = review.get("verdicts") or {}
    field_verdicts = {v["key"]: v["verdict"] for v in verdicts.get("fields") or []}
    slot_verdicts = {neutral(v["slot"]): v["verdict"] for v in verdicts.get("slots") or []}
    records = [{"slot": neutral(r.get("slot", "")), "key": r.get("key", ""), "reason": r.get("reason", ""),
                "text": r.get("text", "")} for r in review.get("unresolved") or []]
    held_keys = {k for k, v in field_verdicts.items() if v in HOLD_VERDICTS} | {r["key"] for r in records if r["key"]}
    return {"field_verdicts": field_verdicts, "slot_verdicts": slot_verdicts, "records": records,
            "held_keys": held_keys, "incomplete": bool(review.get("incomplete"))}


def destination_slots(item: dict) -> list:
    dest = item.get("destination") or {}
    slots = []
    for c in dest.get("controls") or []:
        slots.append(c.split("#")[0])                               # ff/sdt slot, or the glyph paragraph
        if "/ff[" in c or "/sdt[" in c:
            slots.append(c.rsplit("/", 1)[0])                         # the paragraph holding the control
    for key in ("region", "answer_at"):
        if dest.get(key):
            slots.append(dest[key])
    slots += list(dest.get("regions") or [])
    return sorted(set(slots))


# ─── expressibility at this candidate ────────────────────────────────────────────────────────────────────────
def source_of(row: dict) -> str:
    return "\n".join([row.get("text", ""), row.get("heading", ""), row.get("row_label", ""), *row.get("options", [])])


def expressibility(item: dict, is_area: bool, det_grade: dict | None, det_offending: list, rows: dict) -> dict:
    """Can ANY model response reach the expected outcome through validate_proposal at this candidate?"""
    if not is_area:
        ctype = item["type"]
        if ctype == "must_hold":
            return {"expected_outcome": "hold", "expressible": True,
                    "how": "no field there, or an uncertain slot verdict"}
        if det_offending:
            return {"expected_outcome": "no answerable field", "expressible": False,
                    "not_expressible_at_candidate": PRIOR_KEPT, "best_reachable": "held_safe",
                    "offending_deterministic_fields": det_offending}
        return {"expected_outcome": "no answerable field", "expressible": True, "how": "keep / not_answer"}
    if det_grade and det_grade.get("outcome") == "right":
        return {"expected_outcome": "right", "expressible": True, "how": "keep the deterministic field"}
    if item["kind"] == "multi_choice":
        return {"expected_outcome": "right", "expressible": False, "not_expressible_at_candidate": NO_MULTI_CHOICE,
                "best_reachable": "held_safe"}
    return {"expected_outcome": "right", "expressible": None,
            "how": "decided by the self-test's single-change probe (app-path-selftest.json 'expressibility'); "
                   "static reasoning alone cannot tell whether the locator accepts the slot"}


# ─── grading one app-path output ──────────────────────────────────────────────────────────────────────────────
def grade_output(expected: dict, output: dict, deterministic_fields: list | None = None,
                 expressible: dict | None = None) -> dict:
    fields = [mb.summarise(f) for f in output.get("fields") or []]
    holds = hold_index(output)
    rows = {neutral(r["slot"]): r for r in review_of(output).get("areas") or []}
    areas = expected.get("areas", [])
    controls = expected.get("controls", [])
    by_id = {a["id"]: a for a in areas}
    groups = expected.get("table_groups", {})
    det = [mb.summarise(f) for f in deterministic_fields] if deterministic_fields is not None else None

    def held_field(f):
        return f["key"] in holds["held_keys"]

    def dest_records(item):
        slots = destination_slots(item)
        return [r for r in holds["records"] if r["slot"] and any(touches(r["slot"], s) for s in slots)]

    def dismissed(item):
        slots = destination_slots(item)
        verdicts = [v for s, v in holds["slot_verdicts"].items() if any(touches(s, d) for d in slots)]
        return bool(verdicts) and all(v == "not_answer" for v in verdicts)

    def det_area_grade(area):
        return mb.grade_area(area, det, areas, groups, []) if det is not None else None

    area_results = []
    for area in areas:
        covering = [f for f in fields if mb.covers_area(f, area)]
        base = mb.grade_area(area, fields, areas, groups, [])
        records = dest_records(area)
        held_by_field = [f["key"] for f in covering if held_field(f)]
        res = {"id": area["id"], "label": area["label"], "expected_kind": area["kind"]}
        if covering:
            res["fields"] = base.get("fields")
        if held_by_field or records:
            res["outcome"] = "held_safe"
            res["hold"] = {"field_keys": held_by_field, "records": records,
                           "hold_reaches_field": bool(held_by_field) or not covering}
            if covering:
                res["field_grade_under_hold"] = base["outcome"]
                if base.get("problems"):
                    res["field_problems"] = base["problems"]
        elif covering:
            res["outcome"] = base["outcome"]
            if base.get("problems"):
                res["problems"] = base["problems"]
        else:
            res["outcome"] = "missed"
            if dismissed(area):
                res["dismissed_by_model"] = True
        dg = det_area_grade(area)
        res["expressible"] = (expressible or {}).get(area["id"]) or expressibility(area, True, dg, [], rows)
        if dg is not None:
            res["deterministic_outcome"] = dg["outcome"]
        area_results.append(res)

    control_results = []
    for ctl in controls:
        dest = ctl.get("destination") or {}
        regions = ([dest["region"]] if dest.get("region") else []) + list(dest.get("regions") or [])
        cboxes = dest.get("controls") or []
        res = {"id": ctl["id"], "type": ctl["type"], "printed": ctl.get("printed", "")[:120]}

        def offending_in(flist):
            if ctl.get("applies_to"):
                return []
            if ctl["type"] == "not_an_answer":
                return [f for f in flist if mb.answerable(f) and any(mb.anchored_in(f, r) for r in regions)]
            return [f for f in flist if mb.answerable(f) and (
                any(mb.box_covers(k, c) for k in f["boxes"] for c in cboxes) or any(mb.anchored_in(f, r) for r in regions))]

        if ctl.get("applies_to"):
            base = mb.grade_control(ctl, fields, by_id, [])
            covering = [f for i in ctl["applies_to"] for f in fields if mb.covers_area(f, by_id[i])]
            if base["outcome"] == "wrong" and covering and all(held_field(f) for f in covering):
                res["outcome"] = "held_safe"
                res["field_grade_under_hold"] = "wrong"
            else:
                res["outcome"] = base["outcome"]
            if base.get("problems"):
                res["problems"] = base["problems"]
            res["fields"] = base.get("fields")
            res["expressible"] = {"expected_outcome": "side-specific fields", "expressible": True,
                                  "how": "keep (the knee pair is right deterministically)"}
            control_results.append(res)
            continue
        offending = offending_in(fields)
        unheld = [f for f in offending if not held_field(f)]
        records = dest_records(ctl)
        if not offending:
            res["outcome"] = "right"
        elif not unheld:
            res["outcome"] = "right" if ctl["type"] == "must_hold" else "held_safe"
            res["hold"] = {"field_keys": [f["key"] for f in offending], "records": records}
        else:
            res["outcome"] = "wrong"
            res["offending_fields"] = [{k: f[k] for k in ("key", "label", "kind", "target_type", "slot", "options")}
                                       for f in unheld]
        if records and res["outcome"] == "right":
            res["records"] = records               # a review burden on a right control, recorded, not graded
        det_off = [f["key"] + " " + f["kind"] for f in offending_in(det)] if det is not None else []
        res["expressible"] = (expressible or {}).get(ctl["id"]) or expressibility(ctl, False, None, det_off, rows)
        control_results.append(res)

    def in_a_control(f):
        for ctl in controls:
            d = ctl.get("destination") or {}
            regions = ([d["region"]] if d.get("region") else []) + list(d.get("regions") or [])
            if any(mb.box_covers(k, c) for k in f["boxes"] for c in d.get("controls") or []) \
                    or any(mb.anchored_in(f, r) for r in regions):
                return True
        return False

    extras = []
    for f in fields:
        if any(mb.covers_area(f, a) for a in areas) or in_a_control(f) or not mb.answerable(f):
            continue
        extras.append({"key": f["key"], "label": f["label"], "kind": f["kind"], "slot": f["slot"],
                       "outcome": "false_field_held" if held_field(f) else "false_field"})

    tally = {}
    for r in area_results:
        tally["areas_" + r["outcome"]] = tally.get("areas_" + r["outcome"], 0) + 1
    for r in control_results:
        tally["controls_" + r["outcome"]] = tally.get("controls_" + r["outcome"], 0) + 1
    for e in extras:
        tally[e["outcome"]] = tally.get(e["outcome"], 0) + 1
    tally["areas"] = len(areas)
    tally["controls"] = len(controls)
    tally["not_expressible_at_candidate"] = sum(1 for r in area_results + control_results
                                                if r["expressible"]["expressible"] is False)
    return {"areas": area_results, "controls": control_results, "false_fields": extras,
            "summary": dict(sorted(tally.items())), "clinician_view": clinician_view(output)}


def clinician_view(output: dict) -> dict:
    """What the mapping-assistance page shows (templates/mapping_assistance.html via core/mapping_views.review)."""
    review = review_of(output)
    rows = {r["slot"]: r for r in review.get("areas") or []}

    def location(row):
        slot = row.get("slot", "")
        part = slot.partition("#")[0]
        kind = {"p": "Paragraph", "tc": "Table cell", "sdt": "Content control", "ff": "Legacy form field",
                "glyphs": "Printed box"}.get(row.get("kind"), "answer area")
        where = ({"word/document.xml": "Body"}.get(part, part or "Body")) + " · " + kind
        if type(row.get("row")) is int and type(row.get("column")) is int:
            where += " · row %d, column %d" % (row["row"] + 1, row["column"] + 1)
        return where

    unresolved = []
    for rec in review.get("unresolved") or []:
        shown = {**rows.get(rec.get("slot", ""), {}), **rec}
        unresolved.append({"location": location(shown), "text": shown.get("text") or "Blank answer space",
                           "reason": rec.get("reason", ""), "removes_field_if_not_answer": bool(rec.get("key"))})
    verdict_counts = {}
    for row in review.get("areas") or []:
        verdict_counts[row.get("verdict")] = verdict_counts.get(row.get("verdict"), 0) + 1
    return {"areas_requiring_review": unresolved, "confirm_blocked": bool(unresolved),
            "collapsed_verdict_table": verdict_counts,
            "fields": [{"label": f.get("label"), "kind": f.get("kind"),
                        "origin": {"manual": "Manual", "model_assisted": "Model proposal"}.get(f.get("origin"), "Automatic")}
                       for f in output.get("fields") or []]}


# ─── offline self-test on the real app path ──────────────────────────────────────────────────────────────────
def boot(state_dir: Path):
    """Django with sockets, the environment file and the database denied (the offline_replay.py boot)."""
    def deny(*a, **k):
        raise AssertionError("network denied (grade_app_path self-test)")
    socket.socket.connect = deny
    socket.socket.connect_ex = deny
    import dotenv
    dotenv.load_dotenv = lambda *a, **k: False
    for k in ("QUILLMD_V3_FIELD_RELATIONS", "QUILLMD_V3_HISTORY_CONTEXT", "QUILLMD_V3_GENERATION_BATCHES",
              "QUILLMD_WM_NARRATIVE", "QUILLMD_ENV_MANAGED"):
        os.environ.pop(k, None)
    os.environ.update(QUILLMD_SECRET_KEY="offline-diagnostic-only-no-external-access",
                      QUILLMD_DB_PASSWORD="unused-offline", QUILLMD_DB_NAME="none", QUILLMD_DB_USER="none",
                      QUILLMD_DB_HOST="/nonexistent-offline-socket-dir", QUILLMD_DB_PORT="1",
                      QUILLMD_AI_MODE="fixture", QUILLMD_ADMIN_SITE="0", QUILLMD_HTTPS="0",
                      QUILLMD_STATE_DIR=str(state_dir), DJANGO_SETTINGS_MODULE="quillmd.settings")
    sys.path.insert(0, str(REBUILD))
    import django
    django.setup()
    from django.db.backends.base import base as dbbase

    def nodb(self, *a, **k):
        raise AssertionError("database denied (grade_app_path self-test)")
    dbbase.BaseDatabaseWrapper.ensure_connection = nodb


LIVE_MAPPING = dict(AI_MODE="live", AI_PROVIDER="anthropic", AI_MODEL="claude-sonnet-5", AI_INPUT_RATE="2",
                    AI_OUTPUT_RATE="10", AI_CACHED_RATE="0.20", AI_THINKING="disabled", AI_EFFORT="medium",
                    AI_INFERENCE_GEO="", QUILLMD_WORD_ENGINE="v3", QUILLMD_MAPPING_ASSISTANCE=True,
                    V3_FIELD_RELATIONS=False, V3_HISTORY_CONTEXT=False, V3_GENERATION_BATCHES=False,
                    WM_NARRATIVE=False)


class Wire:
    """Hand-built compact wire responses (core/mapping_wire.py) against one compiled request payload."""

    def __init__(self, payload):
        from core import mapping_wire
        self.kinds = mapping_wire.KINDS
        self.p = payload
        self.refs = payload["text_refs"]
        self.sid = {neutral(row["slot"]): n for n, row in enumerate(payload["slots"])}
        self.fid = {f["key"]: n for n, f in enumerate(payload["fields"])}

    def span(self, sid, text):
        row = self.p["slots"][sid]
        for role, name in ((0, "text"), (2, "row_label"), (1, "heading")):
            src = row.get(name, "")
            if text and text in src:
                return [self.refs.index([sid, role, 0]), src.index(text), src.index(text) + len(text)]
        for i, option in enumerate(row.get("options", [])):
            if text in option:
                return [self.refs.index([sid, 3, i]), option.index(text), option.index(text) + len(text)]
        raise KeyError("%r is not printed at slot %s" % (text, self.p["slots"][sid]["slot"]))

    def change(self, prior, slot, kind, label, options=(), glyph=-1):
        sid = self.sid[slot]
        opts = []
        for o in options:
            opts += self.span(sid, o)
        return [-1 if prior is None else self.fid[prior], sid, self.kinds.index(kind), *self.span(sid, label), glyph, *opts]

    def response(self, field_verdicts=None, slot_verdicts=None, changes=(), default_slot=None, e=False):
        field_verdicts = field_verdicts or {}
        slot_verdicts = slot_verdicts or {}
        f = {"k": [], "r": [], "n": [], "u": []}
        for key, n in self.fid.items():
            f[field_verdicts.get(key, "k")].append(n)
        s = {"c": [], "n": [], "u": []}
        for n, row in enumerate(self.p["slots"]):
            slot = neutral(row["slot"])
            verdict = next((v for pat, v in slot_verdicts.items() if slot == pat or slot.startswith(pat + "/")), None)
            s[verdict or default_slot(row["slot"])].append(n)
        return {"f": f, "s": s, "x": list(changes), "e": e}


def mapped_default(payload, kept_keys):
    from core import v3_mapping
    mapped = {slot for f in payload["fields"] if f["key"] in kept_keys for slot in f["slots"]}
    return lambda slot: "c" if v3_mapping.is_mapped(slot, mapped) else "n"


def plans(name, det_fields):
    """The hand-built responses for one form: correct, do_nothing, harmful. Keys are checked against labels."""
    by_label = {f["label"]: f["key"] for f in det_fields}

    def key(label_start):
        hits = [k for label, k in by_label.items() if label.startswith(label_start)]
        assert len(hits) == 1, (name, label_start, list(by_label))
        return hits[0]

    correct, harmful = {}, {}
    if name == "f1-guidance-confirmation":
        # Fix the label that absorbed the other question's guidance: same slot, same kind, the printed question only.
        correct = {"changes": [("replace", key("Date the lead agency"), "b/tbl[0]/tr[1]/tc[1]", "date",
                                "Date the lead agency was last informed", ())]}
        # Re-anchor the confirmation answer ON the blue guidance paragraph.
        harmful = {"changes": [("replace", key("Does a formal offender"), "b/tbl[0]/tr[0]/tc[1]/p[0]", "text",
                                "Does a formal offender supervision scheme currently apply to this person?", ())]}
    elif name in ("f2-leave-checkboxes", "f2b-leave-checkboxes-owner"):
        if name == "f2b-leave-checkboxes-owner":
            correct = {"fields": {key("Leave arrangements"): "u"}}          # hold the one-choice leave list
        harmful = {"changes": [("add", None, "b/p[5]", "text", "Part B: Leave and discharge", ())]}   # a spacer field
    elif name == "f3-selection-instructions":
        hold = {s: "u" for s in ("b/p[4]", "b/p[5]", "b/p[6]", "b/p[7]", "b/p[8]", "b/p[10]", "b/p[11]",
                                 "b/p[13]", "b/p[14]", "b/p[15]", "b/p[16]", "b/p[17]", "b/p[18]", "b/tbl[0]")}
        correct = {"fields": {key("Recipient(s)"): "u"}, "slots": hold}
        harmful = {"slots": {s: "n" for s in hold},
                   "changes": [("add", None, "b/p[14]", "checkbox", "Pain relief", ()),
                               ("add", None, "b/p[15]", "checkbox", "Walking without help", ())]}
    elif name == "f4-exam-grid":
        hold = {"b/tbl[1]/tr[0]/tc[0]": "u", "b/tbl[1]/tr[2]/tc[0]": "u", "b/tbl[1]/tr[3]/tc[0]": "u",
                "b/tbl[1]/tr[4]/tc[0]": "u"}
        correct = {"slots": hold}
        harmful = {"changes": [("add", None, "b/tbl[1]/tr[2]/tc[0]/p[3]", "choice", "Skin colour", ("1", "2"))]}
    elif name == "f5-negative-controls":
        correct = {"fields": {key("I declare the person"): "n"}}
        harmful = {"changes": [("add", None, "b/p[1]", "text", "The reviewing clinician completes this page", ())]}
    elif name == "f6a-long-answer":
        harmful = {"changes": [("add", None, "b/p[2]", "text", "Discharge letter", ())]}
    elif name == "f6b-admin-missing":
        harmful = {"changes": [("add", None, "b/p[0]", "text", "Wound review", ())]}
    return {"correct": correct, "do_nothing": {}, "harmful": harmful}


def build_response(wire, payload, plan):
    field_verdicts = dict(plan.get("fields") or {})
    changes = []
    for kind, prior, slot, fkind, label, options in plan.get("changes") or []:
        if kind == "replace":
            field_verdicts[prior] = "r"
        changes.append(wire.change(prior, slot, fkind, label, options))
    kept = [k for k in wire.fid if field_verdicts.get(k, "k") != "r"]
    return wire.response(field_verdicts, plan.get("slots"), changes, default_slot=mapped_default(payload, kept))


def probe_area(area, expected, version, compiled, payload, wire, det_fields):
    """Can ONE wire change reach 'right' for this area? Every destination slot (and each container of it that the
    request lists) is tried with the expected kind, label and options, as a replacement of the deterministic field
    that covers the area or as an addition. Text the wire cannot reference at a slot cannot be sent at all."""
    from core import mapping_assistance
    kind = {"measurement": "text"}.get(area["kind"], area["kind"])
    if kind not in wire.kinds:
        return {"expected_outcome": "right", "expressible": False, "not_expressible_at_candidate": NO_MULTI_CHOICE,
                "best_reachable": "held_safe", "probe": "not attempted: the kind cannot be sent"}
    det = [mb.summarise(f) for f in det_fields]
    prior = next((f["key"] for f in det if mb.covers_area(f, area)), None)
    candidates = []
    for d in destination_slots(area):
        parts = d.split("/")
        for n in range(len(parts), 1, -1):
            s = "/".join(parts[:n])
            if s in wire.sid and s not in candidates:
                candidates.append(s)
    attempts = []
    for slot in candidates:
        try:
            change = wire.change(prior, slot, kind, area["label"], area.get("options") or ())
        except KeyError as exc:
            attempts.append({"slot": slot, "sent": False, "why": str(exc).strip('"')})
            continue
        plan = {"changes": []}
        response = build_response(wire, payload, plan)
        if prior:
            response["f"] = {k: [n for n in v if n != wire.fid[prior]] for k, v in response["f"].items()}
            response["f"]["r"].append(wire.fid[prior])
        response["x"] = [change]
        try:
            result = mapping_assistance.validate_proposal(version, compiled, response)
        except Exception as exc:
            attempts.append({"slot": slot, "sent": True, "refused_envelope": "%s: %s" % (type(exc).__name__, exc)})
            continue
        graded = grade_output(expected, result, det_fields)
        outcome = next(r for r in graded["areas"] if r["id"] == area["id"])
        refusals = [r["reason"] for r in result["review"]["unresolved"] if r.get("key") == prior
                    or neutral(r.get("slot", "")) == slot]
        attempts.append({"slot": slot, "sent": True, "outcome": outcome["outcome"],
                         **({"refused": refusals[0]} if refusals else {}),
                         **({"problems": outcome.get("problems") or outcome.get("field_problems")}
                            if outcome.get("problems") or outcome.get("field_problems") else {})})
        if outcome["outcome"] == "right":
            return {"expected_outcome": "right", "expressible": True,
                    "how": ("replacement of %s" % prior if prior else "addition") + " at " + slot, "attempts": attempts}
    why = sorted({a.get("why") or a.get("refused") or "; ".join(a.get("problems") or []) or a.get("outcome", "")
                  for a in attempts})
    return {"expected_outcome": "right", "expressible": False,
            "not_expressible_at_candidate": ("no single change reaches 'right': " + " | ".join(w for w in why if w)
                                             + ". " + OPTIONS_NOT_AT_SLOT if area.get("options") else
                                             "no single change reaches 'right': " + " | ".join(w for w in why if w)),
            "best_reachable": "held_safe", "attempts": attempts}


def probe_signing(ctl, expected, version, compiled, payload, wire, det_fields):
    """Can the answerable field on a signing/consent place be REPLACED by a protected signing kind? Tried at each
    destination slot with the printed words as the label; the application's own refusal is recorded."""
    from core import mapping_assistance
    det = [mb.summarise(f) for f in det_fields]
    dest = ctl.get("destination") or {}
    prior = next(f["key"] for f in det if mb.answerable(f) and any(
        mb.box_covers(k, c) for k in f["boxes"] for c in dest.get("controls") or []))
    attempts = []
    for slot in [s for s in destination_slots(ctl) if s in wire.sid]:
        for kind in ("initials", "signature"):
            label = next((t for t in (ctl.get("printed", ""), ctl.get("printed", "")[:60]) if t), "")
            try:
                change = wire.change(prior, slot, kind, label)
            except KeyError as exc:
                attempts.append({"slot": slot, "kind": kind, "sent": False, "why": str(exc).strip('"')})
                continue
            response = build_response(wire, payload, {})
            response["f"] = {k: [n for n in v if n != wire.fid[prior]] for k, v in response["f"].items()}
            response["f"]["r"].append(wire.fid[prior])
            response["x"] = [change]
            result = mapping_assistance.validate_proposal(version, compiled, response)
            refused = [r["reason"] for r in result["review"]["unresolved"] if r.get("key") == prior]
            graded = grade_output(expected, result, det_fields)
            outcome = next(r for r in graded["controls"] if r["id"] == ctl["id"])["outcome"]
            placed = next(({"kind": f["kind"], "target_type": ((f.get("locator") or {}).get("target") or {}).get("type"),
                            "slot": (f.get("locator") or {}).get("slot"), "write_protected": bool(f.get("write_protected"))}
                           for f in result["fields"] if f["key"] not in {x["key"] for x in det_fields}), None)
            attempts.append({"slot": slot, "kind": kind, "sent": True, "outcome": outcome,
                             **({"refused": refused[0]} if refused else {}), **({"placed": placed} if placed else {})})
    return {"reaches_right": any(a.get("outcome") == "right" for a in attempts), "attempts": attempts}


def self_test(forms_dir: Path, state_dir: Path, dump: Path | None = None) -> dict:
    boot(state_dir)
    from types import SimpleNamespace
    from django.test import override_settings
    from documents import service
    from core import mapping_assistance, mapping_wire, generation
    media = state_dir / "files" / "originals"
    media.mkdir(parents=True, exist_ok=True)
    out = {"forms": {}, "differences": {}}
    with override_settings(**LIVE_MAPPING):
        config = generation.configuration()
        for name in FORMS:
            data = (forms_dir / (name + ".docx")).read_bytes()
            (media / (name + ".docx")).write_bytes(data)
            digest = hashlib.sha256(data).hexdigest()
            inspected = service.inspect_template(str(media / (name + ".docx")), engine="v3")
            assert inspected["sha256"] == digest
            version = SimpleNamespace(template=SimpleNamespace(format="docx", original_path="originals/%s.docx" % name,
                                                               sha256=digest),
                                      contract="v3", document_backend={}, fields=inspected["fields"])
            compiled = mapping_assistance.compile_request(version, config)
            payload = json.loads(compiled["request"]["messages"][0]["content"])
            expected = json.loads((HERE / (name + ".expected.json")).read_text())
            wire = Wire(payload)
            det_graded = mb.grade(expected, [mb.summarise(f) for f in inspected["fields"]], [])
            expressible = {}
            for area_grade, area in zip(det_graded["areas"], expected["areas"]):
                if area_grade["outcome"] != "right":
                    expressible[area["id"]] = probe_area(area, expected, version, compiled, payload, wire,
                                                         inspected["fields"])
            by_id = {a["id"]: a for a in expected["areas"]}
            for ctl in expected["controls"]:
                if ctl.get("applies_to"):
                    continue
                dest = ctl.get("destination") or {}
                regions = ([dest["region"]] if dest.get("region") else []) + list(dest.get("regions") or [])
                offending = [f["key"] + " " + f["kind"] for f in (mb.summarise(x) for x in inspected["fields"])
                             if mb.answerable(f) and (any(mb.box_covers(k, c) for k in f["boxes"] for c in dest.get("controls") or [])
                                                      or any(mb.anchored_in(f, r) for r in regions))]
                expressible[ctl["id"]] = expressibility(ctl, False, None, offending, {})
                if offending and ctl["type"] == "must_refuse":
                    probe = probe_signing(ctl, expected, version, compiled, payload, wire, inspected["fields"])
                    expressible[ctl["id"]]["signing_kind_probe"] = probe
                    if probe["reaches_right"]:
                        # The static reason holds for not_answer/uncertain, but a signing-kind REPLACEMENT is accepted
                        # at the declaration paragraph: 'right' is reachable after all (CHECK.md M1 said otherwise
                        # because its probe used the checkbox slot, where the locator returns a checkbox).
                        how = next(a for a in probe["attempts"] if a.get("outcome") == "right")
                        expressible[ctl["id"]] = {"expected_outcome": "no answerable field", "expressible": True,
                                                  "how": "replacement of %s by a %s area at %s" % (
                                                      offending[0].split()[0], how["kind"], how["slot"]),
                                                  "not_by": PRIOR_KEPT, "signing_kind_probe": probe}
            form = {"sha256": digest, "request_sha256": compiled["request_sha256"],
                    "maximum_cost_usd": compiled["maximum_cost"], "input_token_bound": compiled["input_token_bound"],
                    "deterministic_fields": len(inspected["fields"]), "outline_slots": len(payload["slots"]),
                    "expressibility": expressible, "responses": {}}
            responses = {k: build_response(wire, payload, p) for k, p in plans(name, inspected["fields"]).items()}
            responses["app_fixture"] = mapping_wire.fixture(payload)
            for label, response in responses.items():
                try:
                    result = mapping_assistance.validate_proposal(version, compiled, copy.deepcopy(response))
                except Exception as exc:            # an envelope refusal is a measured outcome
                    form["responses"][label] = {"refused": "%s: %s" % (type(exc).__name__, exc)}
                    continue
                graded = grade_output(expected, result, inspected["fields"], expressible)
                if dump:
                    dump.mkdir(parents=True, exist_ok=True)
                    (dump / ("%s.%s.output.json" % (name, label))).write_text(json.dumps(result, ensure_ascii=False))
                    (dump / ("%s.deterministic.json" % name)).write_text(json.dumps(inspected["fields"], ensure_ascii=False))
                    (dump / ("%s.expressible.json" % name)).write_text(json.dumps(expressible, ensure_ascii=False))
                    (dump / ("%s.%s.graded.json" % (name, label))).write_text(json.dumps(graded, ensure_ascii=False))
                form["responses"][label] = {"wire_response": response, "graded": graded,
                                            "unresolved": len(result["review"]["unresolved"]),
                                            "changes": result["review"]["changes"]}
            out["forms"][name] = form
            outcomes = {label: {r["id"]: r["outcome"] for r in (form["responses"][label].get("graded") or {}).get("areas", [])
                                + (form["responses"][label].get("graded") or {}).get("controls", [])}
                        for label in form["responses"]}
            diff = {}
            for item in outcomes.get("correct", {}):
                row = {label: outcomes[label].get(item) for label in outcomes}
                if len(set(row.values())) > 1:
                    diff[item] = row
            out["differences"][name] = diff
    return out


def assertions(result: dict) -> list:
    """What the self-test must show, stated before it ran (it fails the run if any is false)."""
    f = result["forms"]

    def o(form, label, item):
        g = f[form]["responses"][label].get("graded") or {}
        return next((r["outcome"] for r in g.get("areas", []) + g.get("controls", []) if r["id"] == item), None)

    checks = [
        ("do-nothing leaves f3.A4 (single choice for a plural owner) wrong", o("f3-selection-instructions", "do_nothing", "f3.A4") == "wrong"),
        ("the correct hold makes f3.A4 held_safe", o("f3-selection-instructions", "correct", "f3.A4") == "held_safe"),
        ("do-nothing leaves the consent declaration f5.C2 answerable (wrong)", o("f5-negative-controls", "do_nothing", "f5.C2") == "wrong"),
        ("the correct not_answer holds f5.C2 (held_safe)", o("f5-negative-controls", "correct", "f5.C2") == "held_safe"),
        ("do-nothing dismisses f3.A2 (missed)", o("f3-selection-instructions", "do_nothing", "f3.A2") == "missed"),
        ("the correct uncertain verdict holds f3.A2", o("f3-selection-instructions", "correct", "f3.A2") == "held_safe"),
        ("do-nothing keeps f1.A2's leaked label (wrong)", o("f1-guidance-confirmation", "do_nothing", "f1.A2") == "wrong"),
        ("the correct replacement makes f1.A2 right", o("f1-guidance-confirmation", "correct", "f1.A2") == "right"),
        ("do-nothing keeps the f2b one-choice leave list (wrong)", o("f2b-leave-checkboxes-owner", "do_nothing", "f2b.A2") == "wrong"),
        ("the correct hold makes f2b.A2 held_safe", o("f2b-leave-checkboxes-owner", "correct", "f2b.A2") == "held_safe"),
        ("the harmful goal checkboxes break the must_hold control f3.C1", o("f3-selection-instructions", "harmful", "f3.C1") == "wrong"),
        ("the harmful codes-as-options choice on a coded row is an answerable false field with options 1/2",
         any(e["outcome"] == "false_field" and e["slot"] == "b/tbl[1]/tr[2]/tc[0]/p[3]"
             for e in f["f4-exam-grid"]["responses"]["harmful"]["graded"]["false_fields"])),
        ("the harmful guidance field breaks f5.C1", o("f5-negative-controls", "harmful", "f5.C1") == "wrong"),
        ("the correct hold makes the f4 coded rows held_safe", all(o("f4-exam-grid", "correct", i) == "held_safe"
                                                                   for i in ("f4.A7", "f4.A9", "f4.A10", "f4.A11", "f4.A12", "f4.A13", "f4.A14"))),
        ("a signing-kind replacement at the declaration paragraph reaches 'right' for f5.C2 (the checker's probe at "
         "the checkbox slot is refused, as it reported)",
         f["f5-negative-controls"]["expressibility"]["f5.C2"]["signing_kind_probe"]["reaches_right"]
         and any(a.get("sent") is False or a.get("outcome") != "right"
                 for a in f["f5-negative-controls"]["expressibility"]["f5.C2"]["signing_kind_probe"]["attempts"]
                 if a["slot"].endswith("/ff[0]"))),
        ("f2.A2 is right under both correct and do-nothing (keep)", o("f2-leave-checkboxes", "correct", "f2.A2") == "right"
         and o("f2-leave-checkboxes", "do_nothing", "f2.A2") == "right"),
    ]
    totals = {}
    for label in ("correct", "do_nothing", "harmful", "app_fixture"):
        t = {}
        for form in f.values():
            for k, v in ((form["responses"].get(label) or {}).get("graded") or {}).get("summary", {}).items():
                t[k] = t.get(k, 0) + v
        totals[label] = t
    result["totals"] = totals
    checks.append(("the three responses have different totals",
                   len({json.dumps(totals[k], sort_keys=True) for k in ("correct", "do_nothing", "harmful")}) == 3))
    checks.append(("correct has no wrong area/control and no false field",
                   not totals["correct"].get("areas_wrong") and not totals["correct"].get("controls_wrong")
                   and not totals["correct"].get("false_field")))
    return [{"check": c, "passed": bool(ok)} for c, ok in checks]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--forms", type=Path, default=DEFAULT_FORMS)
    ap.add_argument("--state-dir", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--grade", type=Path, help="a recorded app-path output (validate_proposal result or version)")
    ap.add_argument("--form", help="form name for --grade")
    ap.add_argument("--deterministic", type=Path, help="the deterministic fields the request started from (JSON list)")
    ap.add_argument("--expressible", type=Path, help="per-item expressibility from the self-test (JSON object)")
    ap.add_argument("--dump-outputs", type=Path, help="self-test: also write every raw validate_proposal output here")
    args = ap.parse_args(argv)
    if args.grade:
        expected = json.loads((HERE / (args.form + ".expected.json")).read_text())
        det = json.loads(args.deterministic.read_text()) if args.deterministic else None
        table = json.loads(args.expressible.read_text()) if args.expressible else None
        graded = grade_output(expected, json.loads(args.grade.read_text()), det, table)
        text = json.dumps(graded, indent=1, ensure_ascii=False)
        (args.out.write_text(text + "\n") if args.out else print(text))
        return 0
    if not args.self_test:
        ap.error("choose --self-test or --grade")
    import tempfile
    state = args.state_dir or Path(tempfile.mkdtemp(prefix="app-path-state-"))
    state.mkdir(parents=True, exist_ok=True)
    result = self_test(args.forms, state.resolve(), args.dump_outputs)
    checks = assertions(result)
    result = {"schema": "quillmd-sonnet5-mapping-app-path-selftest/1",
              "recorded_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "candidate_head": mb.git("rev-parse", "HEAD"),
              "script_sha256": mb.sha256(Path(__file__)), "measure_baseline_sha256": mb.sha256(HERE / "measure_baseline.py"),
              "network": "socket connect/create_connection/getaddrinfo denied in-process; the compiled request is never sent",
              "checks": checks, **result}
    if args.out:
        args.out.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n")
    for c in checks:
        print(("PASS " if c["passed"] else "FAIL ") + c["check"])
    print(json.dumps(result["totals"], indent=1))
    return 0 if all(c["passed"] for c in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
