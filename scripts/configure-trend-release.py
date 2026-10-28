"""Operator release step: bake a public service address into desktop builds."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlparse
parser=argparse.ArgumentParser()
parser.add_argument('--url',required=True,help='Deployed HTTPS public service origin, without /v1/briefing')
args=parser.parse_args()
p=urlparse(args.url)
if p.scheme!='https' or not p.hostname or p.username or p.password or p.query or p.fragment:
    parser.error('An HTTPS service URL without credentials, query or fragment is required')
path=Path(__file__).resolve().parents[1]/'server'/'release_config.json'
path.write_text(json.dumps({'trend_service_url':args.url.rstrip('/')})+'\n')
print('Public service URL configured for the next desktop build. No API keys are included.')
