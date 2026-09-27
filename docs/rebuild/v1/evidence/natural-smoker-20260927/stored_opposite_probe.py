"""Pure stored-draft counterexample; forged state, not an observed ordinary-note mutation."""
import json
from pathlib import Path
from core import generation as g
from core.tests.test_natural_smoker import FIELDS, QUOTE

notes = QUOTE + '\n\nThe patient smokes daily.'
answer = {'text': 'No', 'status': 'supported', 'evidence': [
    {'quote': QUOTE, 'start': 0, 'end': len(QUOTE)}], 'reviewed': True}
reading = g.governance_for(notes, FIELDS)
page = g.as_currently_governed(reading, notes, {**answer, 'label': 'Smoker'})
result = {'probe': 'forged stale supported value under opposite second paragraph',
          'page_status': page['status'], 'page_text': page['text'],
          'finalize_governed': g.governed_decisions(notes, FIELDS, {'smoker': answer}),
          'reachability': 'Ordinary note-save clears answers; this probe directly constructs stored state.'}
print(json.dumps(result, indent=2))
