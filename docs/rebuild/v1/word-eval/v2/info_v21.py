"""Information pass of the v2.1 `ticked` check on the DEVELOPMENT set only (word-harness-v2.md, v2.1).

    /opt/meddoc-pro/rebuild/.venv/bin/python info_v21.py

For each development document: (1) the candidate engine is proven to be the frozen candidate's - its inspect() output
equals the frozen detection and its fill of v1's ordinary and long answers is byte-identical to the frozen v1 exports;
(2) answering.py answers the document with the v2.1 ground-truth-derived answers (reading 1) through the engine's
public fill API, for the ordinary and long profiles; (3) ticked.py reads each export. Information, not a gate.

Parameters (environment): TICKED_ENGINE - the engine file (default: the frozen candidate's word_v3.py extracted from
79a5b2ec6597 into the scratch directory); TICKED_OUT - where results are written (default: the scratch directory; a
directory inside a git work tree or the corpus is refused). Exports are kept in memory only: no filled document is
written anywhere. Reads only dev/ and results/dev-79a5b2ec6597-frozen/; never holdout/ or qual/.
"""
import collections
import hashlib
import importlib.util
import json
import os
import pathlib
import re
import sys
import time
import traceback

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import answering  # noqa: E402
import ticked  # noqa: E402

CORPUS = pathlib.Path("/opt/meddoc-pro/rebuild/.runtime/v1-word-corpus")
DEV = CORPUS / "dev"
FROZEN = CORPUS / "results" / "dev-79a5b2ec6597-frozen"
V1 = pathlib.Path("/opt/meddoc-pro/.worktrees/v1-release/docs/rebuild/v1/word-eval")
SCRATCH = pathlib.Path("/tmp/claude-1000/-opt-meddoc-pro/64d93580-8414-4553-b17d-ed04b0550ae1/scratchpad/v1/harness-v21")
ENGINE = pathlib.Path(os.environ.get("TICKED_ENGINE") or SCRATCH / "word_v3_79a5b2e.py")
PROFILES = ("ordinary", "long")


def output_dir():
    out = pathlib.Path(os.environ.get("TICKED_OUT") or SCRATCH / "out").resolve()
    for d in (out,) + tuple(out.parents):
        if (d / ".git").exists():
            raise SystemExit("refusing to write results inside a git work tree: %s" % out)
    if out == CORPUS or CORPUS in out.parents:
        raise SystemExit("refusing to write results inside the corpus: %s" % out)
    out.mkdir(parents=True, exist_ok=True)
    return out


def dev_only(path):
    p = pathlib.Path(path).resolve()
    rel = p.relative_to(CORPUS)
    if rel.parts[0] == "dev" or (rel.parts[0] == "results" and rel.parts[1] == FROZEN.name):
        if rel.parts[0] == "dev" and rel.parts[1] == "groundtruth" and p.name.endswith(".annotator.json"):
            raise AssertionError("the annotator file is not the ground truth: %s" % p)
        return p
    raise AssertionError("not a development path: %s" % p)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def reason_class(q):
    r = q["reason"]
    if r.startswith("mapping:"):
        m = r.split(" | ")[0]
        if "no detected field" in m:
            return "mapping: no detected field matches"
        if "did not accept" in m:
            return "mapping: the field refused the label (%s)" % re.sub(r".*\((\w+): .*", r"\1", m.split(" did not accept ")[1])[:40]
        return "mapping: " + re.sub(r"'[^']*'|\d+", "#", m[9:])[:60]
    if r.startswith("chosen set unknown"):
        return "chosen set unknown: " + r.split(" | ")[0][20:80]
    for pat, name in (("U+20DD", "unreadable glyph: U+20DD combining enclosing circle"),
                      ("(w:t) outside the glyph table", "unreadable glyph: symbol-font text outside the table"),
                      ("(w:t):", "unreadable glyph: symbol-font text, fonts or font table"),
                      ("outside the glyph table", "unreadable glyph: outside the table"),
                      ("list label that cannot be resolved", "unreadable list label"),
                      ("picture", "a picture in the slots"), ("not in the export", "a box is not in the export"),
                      ("holds 0 boxes", "an option slot holds no box"), ("mixture", "a mixture of before/after boxes"),
                      ("not printed in its slot", "an option is not printed in its own slot (no box)"),
                      ("not printed", "an option is not printed in the slots"),
                      ("also tied to", "a box or printed option tied to two questions"),
                      ("lists no options", "the ground truth lists no options"),
                      ("which is no option's label", "cell text is no option's label"),
                      ("a cell shows one written answer", "cell text: several options chosen"),
                      ("printed inside option", "an option printed inside a longer option"),
                      ("different paragraph structure", "the export's structure changed at a slot"),
                      ("printed text changed", "an option's printed text changed")):
        if pat in r:
            return name
    m = re.search(r"holds (\d+) boxes", r)
    if m:
        return "an option slot holds several boxes"
    return re.sub(r"'[^']*'|\d+", "#", r)[:80]


def main():
    out_dir = output_dir()
    # the hashes of the files this run executes, taken BEFORE it runs (an edit made while it runs cannot relabel it)
    hashes = {f: hashlib.sha256((HERE / f).read_bytes()).hexdigest() for f in ("ticked.py", "answering.py", "info_v21.py")}
    score = load("score_v1", V1 / "score.py")
    answers_for, fe_sha, fn_sha = answering.load_answers_for(V1 / "final_eval.py")
    engine, engine_sha = answering.load_engine(ENGINE)
    stems = sorted(p.stem for p in dev_only(DEV / "originals").iterdir())
    assert len(stems) == 40, len(stems)
    docs, identity = [], []
    t_all = time.time()
    for stem in stems:
        orig = [p for p in dev_only(DEV / "originals").iterdir() if p.stem == stem][0]
        src = dev_only(DEV / "converted" / (stem + ".docx") if orig.suffix == ".doc" else orig).read_bytes()
        gt = json.loads(dev_only(DEV / "groundtruth" / (stem + ".json")).read_text())
        det = json.loads(dev_only(FROZEN / "detect" / (stem + ".json")).read_text())
        t0 = time.time()
        # (1) the engine is the frozen candidate's: same detection, byte-identical v1 exports
        idn = {"stem": stem}
        try:
            live = json.loads(json.dumps(engine.inspect(src), ensure_ascii=False))
            idn["inspect_equals_frozen"] = live == det
        except Exception as e:                            # noqa: BLE001 - recorded, never skipped
            idn["inspect_equals_frozen"] = "crash: %r" % e
        for profile in PROFILES:
            frozen_export = dev_only(FROZEN / ("filled-" + profile) / (stem + ".docx"))
            if "fields" in det and frozen_export.exists():
                v1_answers = json.loads(dev_only(FROZEN / ("filled-" + profile) / (stem + ".answers.json")).read_text())
                idn["v1_answers_equal_" + profile] = answers_for(det["fields"], profile) == v1_answers
                try:
                    idn["v1_export_identical_" + profile] = engine.fill(src, det["fields"], v1_answers) == frozen_export.read_bytes()
                except Exception as e:                    # noqa: BLE001
                    idn["v1_export_identical_" + profile] = "crash: %r" % e
        identity.append(idn)
        # (2) + (3) the v2.1 answering, then the reader
        for profile in PROFILES:
            rec = {"stem": stem, "profile": profile}
            try:
                a = answering.answer_document(engine, src, gt, det, profile, score.score_doc, answers_for)
            except Exception as e:                        # noqa: BLE001 - a crash is a finding, recorded
                rec.update(doc="answering crashed", error=repr(e), trace=traceback.format_exc()[-800:], questions=[], counts={})
                docs.append(rec)
                continue
            rec["fills"] = a["notes"].get("fills")
            rec["refused_fields"] = len(a["refused"])
            rec["unmatched_choice_fields_left_unanswered"] = len(a["notes"].get("unmatched_choice_fields_left_unanswered", []))
            rec["field_matched_twice"] = a["notes"].get("field_matched_twice", [])
            if a["export"] is None:
                r = ticked.check_document(src, src, gt, a["chosen"])   # every question is a mapping failure here
                rec["doc_note"] = "no export: " + a["notes"].get("base_refused", "not inspected")
            else:
                r = ticked.check_document(src, a["export"], gt, a["chosen"])
                rec["export_sha256"] = hashlib.sha256(a["export"]).hexdigest()
            for q in r["questions"]:
                assert q["verdict"] in ("pass", "fail", "unverifiable"), (stem, q)
                if q["verdict"] != "pass":
                    assert q["reason"], (stem, q["id"])
            n = r["counts"]
            rec["doc"] = "n/a" if not r["questions"] else ("pass" if r["passed"] else ("fail" if n["fail"] else "unverifiable"))
            rec["counts"] = n
            rec["questions"] = [{k: q[k] for k in ("id", "kind", "verdict", "reason", "box_kinds", "mode", "answered")}
                                for q in r["questions"]]
            docs.append(rec)
        print("%s %5.1fs identity=%s %s" % (stem[:3], time.time() - t0,
              all(v is True for k, v in idn.items() if k != "stem"),
              " | ".join("%s %s %s" % (d["profile"], d.get("doc"), d.get("counts")) for d in docs[-2:])), flush=True)
    summary = {}
    for profile in PROFILES:
        d = [x for x in docs if x["profile"] == profile]
        qs = [q for x in d for q in x["questions"]]
        unv = [q for q in qs if q["verdict"] == "unverifiable"]
        summary[profile] = {
            "documents": dict(sorted(collections.Counter(x["doc"] for x in d).items())),
            "documents_by_verdict": {v: [x["stem"][:3] for x in d if x["doc"] == v] for v in ("pass", "fail", "unverifiable", "n/a")},
            "questions": dict(sorted(collections.Counter(q["verdict"] for q in qs).items())),
            "answered": dict(sorted(collections.Counter("%s/%s" % (q["answered"], q["verdict"]) for q in qs).items())),
            "box_kind": dict(sorted(collections.Counter("%s/%s" % ("+".join(q["box_kinds"]) or "(untied)", q["verdict"]) for q in qs).items())),
            "fail_reasons": dict(sorted(collections.Counter(reason_class(q) for q in qs if q["verdict"] == "fail").items(), key=lambda x: -x[1])),
            "unverifiable_reasons_by_box_kind": {
                k: dict(sorted(collections.Counter(reason_class(q) for q in unv if ("+".join(q["box_kinds"]) or "(untied)") == k).items(), key=lambda x: -x[1]))
                for k in sorted({"+".join(q["box_kinds"]) or "(untied)" for q in unv})},
            "unverifiable_questions": [(x["stem"][:3], q["id"], "+".join(q["box_kinds"]) or "(untied)", q["reason"][:220])
                                       for x in d for q in x["questions"] if q["verdict"] == "unverifiable"],
            "refused_fields": sum(x.get("refused_fields", 0) for x in d),
            "unmatched_choice_fields_left_unanswered": sum(x.get("unmatched_choice_fields_left_unanswered", 0) for x in d),
        }
    result = {"harness": ticked.VERSION, "set": "dev", "engine": str(ENGINE), "engine_sha256": engine_sha,
              "final_eval_sha256": fe_sha, "answers_for_sha256": fn_sha,
              "sha256": hashes,
              "identity": identity, "identity_all_true": all(v is True for i in identity for k, v in i.items() if k != "stem"),
              "seconds": round(time.time() - t_all, 1), "summary": summary, "documents": docs}
    (out_dir / "dev-results-v21.json").write_text(json.dumps(result, indent=1, ensure_ascii=False))
    print(json.dumps({p: {k: summary[p][k] for k in ("documents", "questions", "answered", "box_kind", "fail_reasons")} for p in PROFILES}, indent=1, ensure_ascii=False))
    print("identity all true:", result["identity_all_true"], "| engine", ENGINE.name, engine_sha[:16])


if __name__ == "__main__":
    main()
