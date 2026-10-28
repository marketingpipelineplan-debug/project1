"""Build an allowlisted public-service deployment, excluding all workspace data."""
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'dist' / 'vercel-trends'
if DEST.exists():
    shutil.rmtree(DEST)
(DEST / 'api').mkdir(parents=True)
for name in ('vercel_trends.py', 'public_trends.py', 'intelligence.py', 'trend_contract.py'):
    shutil.copyfile(ROOT / 'server' / name, DEST / name)
(DEST / 'api' / 'index.py').write_text('from vercel_trends import handler\n')
(DEST / 'requirements.txt').write_text('# Python standard library only.\n')
(DEST / '.python-version').write_text('3.12\n')
(DEST / 'vercel.json').write_text(json.dumps({
    'functions': {'api/index.py': {'maxDuration': 180}},
    'rewrites': [{'source': '/v1/briefing', 'destination': '/api/index'},
                 {'source': '/healthz', 'destination': '/api/index'},
                 {'source': '/api/refresh', 'destination': '/api/index'}],
    'crons': [{'path': '/api/refresh', 'schedule': '0 3 * * *'}],
}, indent=2) + '\n')
print(DEST)
