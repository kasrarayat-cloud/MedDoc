"""Word evaluation harness v2.1, reading 1: the chosen answer fixed in ground-truth terms, and given to the candidate.

word-harness-v2.md, "v2.1 - seven readings", 1: for each ground-truth choice question the profile chooses option index
min(1, n - 1); for a multiple choice the first two; a checkbox is ticked. The harness gives that option's ground-truth
label, as text, to the candidate field the v1 scorer matches to the question. If no field matches, or the field does
not accept the label, the question FAILS (a mapping failure of the candidate), never "unverifiable". The text answers
of v1's profiles are unchanged.

This module is the ANSWERING step. It drives the candidate engine through its public fill API exactly as v1's
final_eval.py does (`engine.fill(original_bytes, fields, answers)`), and it is the only harness file that touches the
engine; the reader (ticked.py) never imports it, the engine or core/*. The engine is passed in (load_engine), never
imported here, so the pure parts of this file can be tested without it.

    answer_document(engine, original_bytes, groundtruth, detection, profile, score_doc, answers_for)
        -> {"export": bytes | None, "chosen": {area id: [...] | {"mapping": why} | {"unknown": why}},
            "answers": {field key: value given to fill}, "refused": {field key: why}, "notes": {...}}

Readings made here where the declaration is silent (each is listed in README.md):
  * checkbox_group is answered like a choice (one option, index min(1, n - 1)): one ticked option is a valid answer
    to a group read either as single or multiple choice, two are not.
  * A multiple choice's two labels are given as a list (the engine's shape for several answers). A checkbox is given
    its ground-truth label when it has one, else True (a ground-truth checkbox carries no label to give).
  * A ground-truth choice question with no options has no label to give: its chosen set is unknown (unverifiable)
    and its field gets no answer.
  * A detected choice-like field (choice / multi_choice / checkbox) that the v1 scorer matches to NO ground-truth
    choice question is left UNANSWERED: the choice answers are fixed in ground-truth terms and such a field has none;
    v1's profile would have answered it. Every other field gets v1's answer unchanged.
  * Refusals are found per question: the whole fill is tried first; if the engine refuses it, each ground-truth
    answer is tried alone on top of the unchanged v1 text answers, the refused ones are dropped (mapping failures),
    and the rest are filled together; an answer accepted alone but refused together with the others is dropped too
    (a mapping failure "refused in combination"). If the v1 text answers alone are refused, no export exists and every
    question fails as "fill refused".
"""
import ast
import hashlib
import importlib.util
import pathlib
import sys

CHOICE_KINDS = ("choice", "multi_choice", "checkbox", "checkbox_group")
CHOICE_FIELD_KINDS = ("choice", "multi_choice", "checkbox")


def load_engine(path, name="word_v3_candidate"):
    """The candidate engine loaded from a file (as final_eval.py loads word_v3), with its sha256."""
    path = pathlib.Path(path)
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod                          # dataclasses need the module registered while it executes
    spec.loader.exec_module(mod)
    return mod, hashlib.sha256(path.read_bytes()).hexdigest()


def load_answers_for(final_eval_path):
    """v1's `answers_for(fields, profile)`, taken from final_eval.py's own source (not re-typed), so the text answers
    are exactly v1's. final_eval.py itself is not imported: importing it loads an engine from a fixed path."""
    src = pathlib.Path(final_eval_path).read_text()
    tree = ast.parse(src)
    fn = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "answers_for"]
    if len(fn) != 1:
        raise ValueError("answers_for not found once in %s" % final_eval_path)
    ns = {}
    exec(compile(ast.Module(body=fn, type_ignores=[]), str(final_eval_path), "exec"), ns)
    return ns["answers_for"], hashlib.sha256(src.encode()).hexdigest(), hashlib.sha256(ast.unparse(fn[0]).encode()).hexdigest()


def chosen_indices(area):
    """The profile's choice in ground-truth option indices, or None when the ground truth gives no option."""
    kind, n = area.get("kind"), len(area.get("options") or [])
    if kind == "checkbox":
        return [0]
    if n == 0:
        return None
    if kind == "multi_choice":
        return list(range(min(2, n)))
    return [min(1, n - 1)]                             # choice, checkbox_group


def answer_value(area, idx):
    """The value given to the candidate field: the chosen option's ground-truth label, as text."""
    opts = list(area.get("options") or [])
    if area.get("kind") == "checkbox":
        return opts[0] if opts else True
    labels = [opts[i] for i in idx]
    return labels if area.get("kind") == "multi_choice" else labels[0]


def plan(groundtruth, detection, profile, score_doc, answers_for):
    """-> (answers, gt_answers {field key: area id}, chosen, notes) before any fill."""
    fields = detection["fields"]
    rows = score_doc(groundtruth, detection)["rows"]
    matched = {r["id"]: r["det"]["key"] for r in rows if r.get("det")}
    kind_of = {f["key"]: f["kind"] for f in fields}
    v1 = answers_for(fields, profile)
    chosen, gt_answers, answers = {}, {}, {}
    notes = {"unmatched_choice_fields_left_unanswered": [], "field_matched_twice": []}
    for area in groundtruth.get("answer_areas", []):
        if area.get("kind") not in CHOICE_KINDS:
            continue
        idx = chosen_indices(area)
        key = matched.get(area["id"])
        if idx is None:
            chosen[area["id"]] = {"unknown": "the ground truth lists no options, so no label can be given"}
            if key is not None:
                gt_answers.setdefault(key, None)       # the field is this question's: no v1 answer either
            continue
        if key is None:
            chosen[area["id"]] = {"mapping": "no detected field matches the question (v1 scorer)"}
            continue
        value = answer_value(area, idx)
        if key in gt_answers:
            first = gt_answers[key]
            notes["field_matched_twice"].append((key, first, area["id"]))
            if first is not None and answers.get(key) == value:
                chosen[area["id"]] = idx               # the same answer serves both questions
            else:
                chosen[area["id"]] = {"mapping": "the matched field %s already answers %s" % (key, first)}
            continue
        gt_answers[key] = area["id"]
        answers[key] = value
        chosen[area["id"]] = idx
    for f in fields:
        k = f["key"]
        if k in gt_answers:
            continue
        if f["kind"] in CHOICE_FIELD_KINDS:
            if k in v1:
                notes["unmatched_choice_fields_left_unanswered"].append(k)
            continue
        if k in v1:
            answers[k] = v1[k]                         # v1's text answer, unchanged
    gt_answers = {k: v for k, v in gt_answers.items() if v is not None}
    return answers, gt_answers, chosen, notes, kind_of


def answer_document(engine, original_bytes, groundtruth, detection, profile, score_doc, answers_for):
    """Build the ground-truth-derived answers for the candidate's fields, fill through the engine as final_eval does,
    and return the export with the chosen sets (see the module docstring)."""
    if "fields" not in detection:
        chosen = {a["id"]: {"mapping": "the candidate did not inspect the document"}
                  for a in groundtruth.get("answer_areas", []) if a.get("kind") in CHOICE_KINDS}
        return {"export": None, "chosen": chosen, "answers": {}, "refused": {}, "notes": {"fills": 0}}
    fields = detection["fields"]
    answers, gt_answers, chosen, notes, kind_of = plan(groundtruth, detection, profile, score_doc, answers_for)
    fills = [0]

    def fill(ans):
        fills[0] += 1
        try:
            return engine.fill(original_bytes, fields, ans), None
        except engine.V3Failure as e:
            return None, "%s: %s" % (getattr(e, "code", "?"), e)

    refused = {}
    out, err = fill(answers)
    if err is not None:
        base = {k: v for k, v in answers.items() if k not in gt_answers}
        out_b, err_b = fill(base)
        if err_b is not None:
            for key, aid in gt_answers.items():
                chosen[aid] = {"mapping": "fill refused: the v1 text answers alone are refused (%s)" % err_b}
            notes.update(fills=fills[0], base_refused=err_b)
            return {"export": None, "chosen": chosen, "answers": answers, "refused": {}, "notes": notes}
        accepted = {}
        for key in gt_answers:                        # field order of the plan (ground-truth order)
            _, e = fill(dict(base, **{key: answers[key]}))
            if e is None:
                accepted[key] = answers[key]
            else:
                refused[key] = e
        out, err = fill(dict(base, **accepted))
        if err is not None:                           # accepted alone, refused together: add them one at a time
            kept = {}
            for key, value in accepted.items():
                _, e = fill(dict(base, **kept, **{key: value}))
                if e is None:
                    kept[key] = value
                else:
                    refused[key] = "refused in combination with the other answers (%s)" % e
            out, err = fill(dict(base, **kept))
            if err is not None:
                raise RuntimeError("a fill of individually and incrementally accepted answers was refused: %s" % err)
        for key, why in refused.items():
            aid = gt_answers[key]
            chosen[aid] = {"mapping": "the matched field %s (%s) did not accept the label %r (%s)" % (
                key, kind_of.get(key), answers[key] if not isinstance(answers[key], str) else answers[key][:60], why)}
        answers = {k: v for k, v in answers.items() if k not in refused}
    notes["fills"] = fills[0]
    return {"export": out, "chosen": chosen, "answers": answers, "refused": refused, "notes": notes}
