"""Public-only wire contract shared by the publisher and desktop reader."""
from datetime import datetime, timezone
import hashlib
import json
import math
import re
from urllib.parse import urlparse

MAX_BYTES = 2_000_000
HOSTS = {'www.reddit.com', 'www.youtube.com', 'www.twitch.tv', 'kick.com', 'x.com'}

def timestamp(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None: raise ValueError('Timezone required')
    if parsed.timestamp() > datetime.now(timezone.utc).timestamp()+300: raise ValueError('Future timestamp')
    return parsed.timestamp()

def string(value, maximum):
    if not isinstance(value,str) or not value.strip() or len(value)>maximum: raise ValueError('Invalid text')
    return value

def validate(report):
    """Allowlist fields; never distribute operator configuration or raw provider errors."""
    if not isinstance(report,dict): raise ValueError('Invalid briefing')
    summary = string(report.get('summary'),12000)
    collected = string(report.get('collected_at'),60)
    timestamp(collected)
    raw_sources = report.get('sources')
    if not isinstance(raw_sources,list) or not 1<=len(raw_sources)<=100: raise ValueError('Missing sources')
    sources=[]
    for row in raw_sources:
        identity=string(row.get('id'),150)
        url=string(row.get('url'),2000)
        parsed=urlparse(url)
        if parsed.scheme!='https' or parsed.hostname not in HOSTS or parsed.username or parsed.password or parsed.port not in (None,443): raise ValueError('Invalid source URL')
        observed=string(row.get('observed_at'),60)
        timestamp(observed)
        metrics=row.get('metrics',{})
        if not isinstance(metrics,dict) or len(metrics)>10: raise ValueError('Invalid metrics')
        if any(not isinstance(k,str) or len(k)>80 or isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for k,v in metrics.items()): raise ValueError('Invalid metrics')
        sources.append({'id':identity,'platform':string(row.get('platform'),40),'title':string(row.get('title'),500),'url':url,'observed_at':observed,'category':str(row.get('category',''))[:100],'metrics':metrics})
    ids={s['id'] for s in sources}
    cited=re.findall(r'\[([^\[\]]+)\]',summary)
    if len(ids)!=len(sources) or not cited or any(c not in ids for c in cited): raise ValueError('Invalid citations')
    coverage=[]
    for row in report.get('coverage',[])[:20]:
        status=row.get('status')
        public_status='Included' if status in ('Scanned','Included') else 'No signals' if status in ('No usable signals','No signals') else 'Not covered'
        coverage.append({'platform':string(row.get('platform'),40),'status':public_status,'method':string(row.get('method'),500),'scope':str(row.get('scope',''))[:150]})
    limitations=report.get('limitations',[])
    if not isinstance(limitations,list): raise ValueError('Invalid limitations')
    result={'schema_version':1,'collected_at':collected,'summary':summary,'sources':sources,'coverage':coverage,
            'generator':string(report.get('generator'),150),'limitations':[string(s,1000) for s in limitations[:10]]}
    result['version']=hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()[:20]
    return result
