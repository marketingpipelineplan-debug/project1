"""Prepare a prompt offline, or explicitly run one hosted model request."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import brain

parser = argparse.ArgumentParser()
parser.add_argument('brief', type=Path)
parser.add_argument('--live', action='store_true', help='Send this brief to the hosted model; consumes API credits')
parser.add_argument('--model', choices=list(brain.MODELS.values()), default=brain.MODELS['primary'])
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
try:
    brief = json.loads(args.brief.read_text())
    result = brain.run(brief, args.model) if args.live else {
        'mode': 'offline_prompt_preview', 'model': args.model,
        'messages': brain.messages(brain.prepare(brief)), 'weight_training': False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print('Saved', args.output)
except Exception:
    # Do not echo HTTP errors, source content, tokens or provider response bodies.
    print('Workbench failed. Check input structure, credentials, model access and output validity.', file=sys.stderr)
    sys.exit(1)
