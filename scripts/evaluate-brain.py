"""Development scenarios, not a held-out benchmark. Offline unless --live is set."""
import argparse
import json
from pathlib import Path
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import brain

parser = argparse.ArgumentParser()
parser.add_argument('--live', action='store_true')
parser.add_argument('--model', choices=list(brain.MODELS.values()), default=brain.MODELS['primary'])
parser.add_argument('--output', type=Path, default=Path('.data/brain-evaluation.json'))
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
cases = json.loads((root/'evals/brain/cases.json').read_text())
results = []
for case in cases:
    row = {'case_id': case['id'], 'expected_review': case['expected_review'],
           'human_scores': {k: None for k in brain.RUBRIC}, 'human_notes': '',
           'quality_verdict': 'not_evaluated'}
    try:
        context = brain.prepare(case['brief'])
        row['context'] = context
        if args.live:
            started = time.monotonic()
            row['output'] = brain.run_prepared(context, args.model)
            row['latency_seconds'] = round(time.monotonic() - started, 3)
            row['contract_check'] = 'passed'
        else:
            row['prompt'] = brain.messages(context)
            row['contract_check'] = 'not_run'
    except Exception:
        row['contract_check'] = 'failed'
        # Stop on a failure instead of spending more credits on a broken setup.
        results.append(row)
        break
    results.append(row)
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps({'model': args.model, 'live': args.live,
    'suite': 'synthetic_development_scenarios', 'results': results,
    'quality_validated': False}, indent=2)+'\n')
print(f'Saved {len(results)} scenarios to {args.output}; human quality review remains required.')
if any(r['contract_check']=='failed' for r in results): sys.exit(1)
