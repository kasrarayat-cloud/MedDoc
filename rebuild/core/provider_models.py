"""Bounded provider-returned identity, kept separate from configured aliases."""
import re


def transcription_models(metadata):
    """Only identify models explicitly referenced by this transcription response.

    Missing or malformed identity never invents a model or discards billable
    usage. The receipt records that uncertainty separately from the alias.
    """
    result = {'configured_model': 'nova-3-medical', 'returned_models': [],
              'model_metadata_status': 'not_returned'}
    if not isinstance(metadata, dict):
        return result
    ids, info = metadata.get('models'), metadata.get('model_info')
    if ids is None and info is None:
        return result
    result['model_metadata_status'] = 'incomplete'
    if not isinstance(ids, list) or not isinstance(info, dict) or not 0 < len(ids) <= 16:
        return result
    seen = set()
    for model_id in ids:
        if (not isinstance(model_id, str) or not re.fullmatch(r'[a-fA-F0-9]{8}(?:-[a-fA-F0-9]{4}){3}-[a-fA-F0-9]{12}', model_id)
                or model_id in seen):
            continue
        seen.add(model_id)
        entry = info.get(model_id)
        if not isinstance(entry, dict):
            continue
        values = {key: entry.get(key) for key in ('name', 'version', 'arch')}
        if not all(isinstance(value, str) and 0 < len(value) <= 200
                   and not any(ord(char) < 32 for char in value) for value in values.values()):
            continue
        result['returned_models'].append({'uuid': model_id, **values})
    if len(result['returned_models']) == len(ids):
        result['model_metadata_status'] = 'returned'
    return result
