"""Desktop read-only public briefing subscriber. Never reads provider keys or a model."""
from pathlib import Path
import json
import os
import threading
import time
from urllib.parse import urlparse
from urllib.request import Request, HTTPRedirectHandler, ProxyHandler, build_opener
try:
    from . import trend_contract
except ImportError:
    import trend_contract

class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None

fetch_public=build_opener(ProxyHandler({}),NoRedirects()).open
_lock=threading.Lock()
_instances={}

def service_url():
    # Operator sets this once in the release. Users never enter platform keys.
    override=os.environ.get('GOODFORM_TREND_SERVICE_URL')
    if override is not None: value=override
    else:
        try: value=json.loads(Path(__file__).with_name('release_config.json').read_text()).get('trend_service_url','')
        except (OSError,ValueError,AttributeError): value=''
    if not value: return None
    p=urlparse(value)
    local=p.hostname in ('127.0.0.1','localhost','::1')
    if p.username or p.password or p.query or p.fragment or not p.hostname or not (p.scheme=='https' or (p.scheme=='http' and local)):
        return None
    return value.rstrip('/')+'/v1/briefing'

class Subscriber:
    def __init__(self,path,url):
        self.path=Path(path)
        self.url=url
        self.latest=None
        self.last_check=0
        self.online=False
        self.publisher_stale=False
        self.lock=threading.Lock()
        try:
            if self.path.stat().st_size<=trend_contract.MAX_BYTES:
                stored=json.loads(self.path.read_text())
                if stored.get('service_url')==url:
                    self.latest=trend_contract.validate(stored['latest'])
        except (OSError,ValueError,TypeError,KeyError,AttributeError): pass

    def read(self):
        with self.lock:
            if self.url and time.monotonic()-self.last_check>=60:
                self.last_check=time.monotonic()
                try:
                    # Only a fixed GET is sent: no workspace data, headers or user identifiers.
                    with fetch_public(Request(self.url,headers={'Accept':'application/json'}),timeout=5) as response:
                        raw=response.read(trend_contract.MAX_BYTES+1)
                    if len(raw)>trend_contract.MAX_BYTES: raise ValueError('Oversized response')
                    envelope=json.loads(raw)
                    if not isinstance(envelope,dict) or 'latest' not in envelope: raise ValueError('Invalid response')
                    if envelope['latest'] is not None:
                        report=trend_contract.validate(envelope['latest'])
                        # A stale proxy or rollback cannot replace newer evidence.
                        if not self.latest or trend_contract.timestamp(report['collected_at'])>=trend_contract.timestamp(self.latest['collected_at']):
                            self.latest=report
                            try:
                                self.path.parent.mkdir(parents=True,exist_ok=True)
                                tmp=self.path.with_suffix('.tmp')
                                tmp.write_text(json.dumps({'service_url':self.url,'latest':report}))
                                tmp.replace(self.path)
                            except OSError: pass  # Read-only disks still permit an in-memory briefing.
                    self.online=True
                    self.publisher_stale=bool(envelope.get('stale')) or envelope['latest'] is None
                except Exception:
                    self.online=False
            stale=bool(self.latest and (not self.online or self.publisher_stale or time.time()-trend_contract.timestamp(self.latest['collected_at'])>1800))
            return {'latest':self.latest,'stale':stale,'available':self.latest is not None,
                    'status':'current' if self.latest and not stale else 'cached' if self.latest else 'waiting',
                    'message': 'Showing the last available briefing. Updates will resume automatically.' if stale else
                               'The shared briefing is being prepared. No account connection is needed.' if not self.latest else
                               'Automatically updated public briefing. No social accounts required.',
                    'next_check_seconds':300}

def latest(db_path):
    url=service_url()
    path=Path(db_path).parent/'public-briefing-cache.json'
    key=(str(path),url)
    with _lock:
        if key not in _instances: _instances[key]=Subscriber(path,url)
        subscriber=_instances[key]
    return subscriber.read()
