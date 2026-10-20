"""Networkless, bounded preparation parser. No provider, credentials or database."""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from sandbox import isolate
from engine import DocumentFailure
from preparation import inventory, candidate, PROTOCOL
from signing_source_context import validate_context as validate_signing_context
from question_context import validate_context
# Load trusted source modules before Landlock restricts file access to this
# disposable document workspace. The sandbox remains networkless and intact.
import table_constraints
import preparation_roles

def main():
    workspace = Path(sys.argv[1]).resolve()
    try:
        isolate(workspace)
    except Exception:
        print(json.dumps({'error': 'The secure document sandbox is unavailable.', 'code': 'sandbox_unavailable'}))
        return
    try:
        request = json.loads((workspace/'request.json').read_text())
        if request['operation'] == 'inventory':
            if 'signing_context' in request:
                validate_signing_context(request['signing_context'])
            if 'question_context' in request:
                validate_context(request['question_context'])
            result = inventory(workspace/'input.docx', request.get('known'), protocol=request.get('protocol', PROTOCOL),
                               signing_context=request.get('signing_context'), question_context=request.get('question_context'))
        elif request['operation'] == 'candidate':
            result = candidate(workspace/'input.docx', workspace/'output.docx',
                               request['inventory'], request['selected'],request.get('placements'))
        else:
            raise DocumentFailure('Unsupported preparation operation.', 'invalid_operation')
    except DocumentFailure as exc:
        result = {'error': str(exc), 'code': exc.code}
    except Exception:
        result = {'error': 'The blank form has an unsupported structure.', 'code': 'invalid_document'}
    print(json.dumps(result, ensure_ascii=False))

if __name__ == '__main__':
    main()
