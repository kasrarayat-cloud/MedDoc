"""The steps of the ordinary-notes APP PATH that must stay identical wherever they are walked: the mocked walk
(app_path_walk.py, a quillmd_qa_diag_* test database) and the campaign's live ordinary_notes stage
(rebuild/ops/sonnet5_stages.py, the isolated QA process). ONE copy — both import this module; neither re-states it.

  PATH_FLAGS            the two send paths as settings (default: every contract flag off; field_relations: only
                        V3_FIELD_RELATIONS on). The caller supplies the model and rates.
  reference_selection   each field's REFERENCE selection (the first acceptable entry that applies on the path).
  reference_answer      the provider body a model returning the reference selection sends, built against the request
                        the application actually made (used only by mocked or fake providers).
  field_outcomes        the adopted status and text per field, as the review sees them (a conflict is "held").
  review_payload        the review SAVE a clinician makes without clinical edits: supported answers kept as drafted and
                        marked reviewed; held and missing fields left blank and marked reviewed; every requirement
                        confirmed.
  export_verification   the export's preservation: the same ZIP members, only word/document.xml changed, and every
                        adopted answer in its own field.

Needs Django configured (it imports the candidate's own core.generation / core.v3_field_relations / documents.word_v3
lazily). No socket, no environment file, no database of its own.
"""
import io
import json
from zipfile import ZipFile

PATHS = ('default', 'field_relations')
PATH_FLAGS = {'default': {'V3_HISTORY_CONTEXT': False, 'V3_FIELD_RELATIONS': False, 'V3_GENERATION_BATCHES': False,
                          'WM_NARRATIVE': False},
              'field_relations': {'V3_HISTORY_CONTEXT': False, 'V3_FIELD_RELATIONS': True, 'V3_GENERATION_BATCHES': False,
                                  'WM_NARRATIVE': False}}


def applies(selection, path):
    return path in selection.get('paths', PATHS)


def reference_selection(case, path):
    """{field key: the first acceptable selection that applies on `path`} — the case's reference model behaviour."""
    return {k: next(s for s in e['raw_model_expectation']['acceptable'] if applies(s, path))
            for k, e in case['fields'].items()}


def source_units(notes, fields):
    """The source units the application builds for these notes and fields (their quotes and ids)."""
    from core import generation as g
    asked, context, _ = g.v3_generation_fields(fields)
    return asked, g.source_units(notes, asked, context_labels=context)[0]


def reference_answer(notes, fields, payload, selection):
    """The provider body a model returning `selection` ({key: {units, conflict, options?, relations?}}) sends for this
    request `payload` (the JSON the application put in the user message). Field-relations requests carry a catalogue;
    the default request carries questions and source units. Returns (body, sent_units) — sent_units is None on the
    field-relations path, else {quote: id} as the request carried them."""
    asked, units = source_units(notes, fields)
    by_quote = {u['quote']: u['id'] for u in units}
    if 'catalogue' in payload:
        from core import v3_field_relations as rel
        body = []
        for f in asked:
            s = selection.get(f['key'], {})
            ids = [by_quote[q] for q in s.get('units', [])]
            options = {o['text']: o['id'] for o in rel.options(f)}
            body.append({'key': f['key'], 'unit_ids': ids, 'conflict': bool(s.get('conflict')),
                         'option_ids': [options[t] for t in s.get('options', [])],
                         'context': ['answer' if u['id'] in ids else
                                     s.get('relations', {}).get(u['quote'], 'independent') for u in units]})
        return {'fields': body}, None
    sent = {u['quote']: u['id'] for u in payload['source_units']}
    keys = [q['key'] for q in payload['questions']]
    return ({'fields': [{'key': k, 'unit_ids': [sent[q] for q in selection.get(k, {}).get('units', [])],
                         'conflict': bool(selection.get(k, {}).get('conflict'))} for k in keys]},
            {'sent': sent, 'expected': by_quote})


def field_outcomes(answers):
    """{key: {'status': supported | held | missing | …, 'text'}} — a `conflict` status is a hold."""
    state = {'conflict': 'held'}
    return {k: {'status': state.get(v['status'], v['status']), 'text': v.get('text', '')} for k, v in answers.items()}


def review_payload(fields, generated, controls, revision, requirements):
    """The SAVE of a review with no clinical edit: every answer control the page offers gets the drafted text of a
    supported answer (or nothing), every field is marked reviewed, a field left without text is marked 'Leave blank —
    reviewed', and every review requirement is confirmed. `controls`: the input names the review page's form carries."""
    payload = {'revision': revision}
    for f in fields:
        value = generated.get(f['key'], {})
        text = value.get('text', '') if value.get('status') == 'supported' else ''
        if 'answer_' + f['key'] in controls:
            payload['answer_' + f['key']] = text
        if 'reviewed_' + f['key'] in controls:
            payload['reviewed_' + f['key']] = 'on'
        if not text and 'blank_' + f['key'] in controls:
            payload['blank_' + f['key']] = 'on'
    for requirement in requirements:
        payload['requirement_' + requirement['key']] = 'on'
    return payload


def export_verification(original, exported, fields, outcomes):
    """Preservation of an export against its blank original: the same ZIP members, only word/document.xml changed, and
    every supported answer's text inside its own field's destination (a choice or checkbox is written as a mark)."""
    from documents import word_v3 as w
    with ZipFile(io.BytesIO(original)) as a, ZipFile(io.BytesIO(exported)) as b:
        members_unchanged = a.namelist() == b.namelist()
        changed_parts = [p for p in a.namelist() if p in b.namelist() and a.read(p) != b.read(p)]
    new = w.SlotIndex(w.open_package(exported))
    written = {}
    for f in fields:
        text = outcomes.get(f['key'], {}).get('text', '')
        if outcomes.get(f['key'], {}).get('status') != 'supported' or not text:
            continue
        target = new.by_id[f['locator']['part'] + '#' + f['locator']['slot']]
        exported_text = w.text_of(target.el)
        written[f['key']] = (text in exported_text) or (f['kind'] in ('choice', 'checkbox'))
    return {'zip_members_unchanged': members_unchanged, 'changed_parts': changed_parts,
            'supported_answers_in_their_fields': written,
            'workflow_success': (members_unchanged and set(changed_parts) <= {'word/document.xml'}
                                 and all(written.values()))}


def request_summary(wire):
    """What the walk and the stage record of the request the application built (never the notes)."""
    payload = json.loads(wire['messages'][0]['content'])
    return {'payload_keys': sorted(payload), 'relations_payload': 'catalogue' in payload,
            'questions': len(payload.get('questions') or []), 'source_units': len(payload.get('source_units') or []),
            'catalogue': len(payload.get('catalogue') or []), 'max_tokens': wire.get('max_tokens'),
            'model': wire.get('model'), 'request_bytes': len(json.dumps(wire).encode())}
