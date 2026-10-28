"""Package blind human reviews, then summarize completed ratings. No model calls."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server.brain_eval import package, summarize

parser=argparse.ArgumentParser()
sub=parser.add_subparsers(dest='command',required=True)
build=sub.add_parser('package')
build.add_argument('reports',type=Path,nargs='+')
build.add_argument('--directory',type=Path,required=True)
score=sub.add_parser('score')
score.add_argument('review',type=Path)
score.add_argument('mapping',type=Path)
score.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
if args.command=='package':
    review,mapping=package([json.loads(p.read_text()) for p in args.reports])
    args.directory.mkdir(parents=True,exist_ok=False)
    (args.directory/'review.json').write_text(json.dumps(review,indent=2)+'\n')
    (args.directory/'private-mapping.json').write_text(json.dumps(mapping,indent=2)+'\n')
    print('Give only review.json to the reviewer; keep private-mapping.json separate.')
else:
    result=summarize(json.loads(args.review.read_text()),json.loads(args.mapping.read_text()))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print('Saved human evaluation summary. No model configuration changed.')
