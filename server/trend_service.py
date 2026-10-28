"""Operator-owned public service. Never imports the private workspace app/database."""
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import os
import threading
from urllib.request import ProxyHandler, build_opener
from urllib.parse import urlparse
try:
    from . import intelligence, trend_contract
except ImportError:
    import intelligence, trend_contract

class Runtime:
    model_base=os.environ.get('GOODFORM_TREND_MODEL_ENDPOINT','http://127.0.0.1:11434').rstrip('/')
    class AppError(Exception):
        def __init__(self,message,status=400): self.message,self.status=message,status
    urlopen=staticmethod(build_opener(ProxyHandler({})).open)
    @staticmethod
    def now(): return datetime.now(timezone.utc).isoformat()

class Publisher:
    def __init__(self,path,build=None):
        self.path=Path(path)
        self.build=build or (lambda:intelligence.universal_trends(Runtime,{}))
        self.lock=threading.Lock()
        self.latest=None
        self.last_attempt=None
        self.last_success=False
        try:
            if self.path.stat().st_size<=trend_contract.MAX_BYTES:
                self.latest=trend_contract.validate(json.loads(self.path.read_text()))
        except (OSError,ValueError,TypeError,KeyError,AttributeError): pass

    def refresh(self):
        # Called by the operator worker only, never by a public HTTP request.
        try:
            latest=trend_contract.validate(self.build())
            self.path.parent.mkdir(parents=True,exist_ok=True)
            tmp=self.path.with_suffix('.tmp')
            tmp.write_text(json.dumps(latest))
            tmp.replace(self.path)
            with self.lock: self.latest=latest
            success=True
        except Exception:
            # Keep the last good briefing. No raw exception/credential logging.
            success=False
        with self.lock:
            self.last_attempt=Runtime.now()
            self.last_success=success
        return success

    def snapshot(self):
        with self.lock:
            latest=self.latest
            age=datetime.now(timezone.utc).timestamp()-trend_contract.timestamp(latest['collected_at']) if latest else 0
            return {'latest':latest,'stale':bool(latest and (age>1800 or not self.last_success)),
                    'available':latest is not None,'next_check_seconds':300}

    def run(self,stop,interval):
        while not stop.is_set():
            self.refresh()
            stop.wait(interval)

def handler_for(publisher):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_GET(self):
            if self.path=='/healthz':
                self.respond(200,{'service':'public-trends','ready':publisher.snapshot()['available']})
            elif self.path=='/v1/briefing':
                self.respond(200,publisher.snapshot())
            else: self.respond(404,{'error':'Not found'})
        def do_POST(self): self.respond(405,{'error':'Read-only service'})
        def respond(self,status,data):
            body=json.dumps(data).encode()
            self.send_response(status)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','public, max-age=60')
            self.send_header('X-Content-Type-Options','nosniff')
            self.end_headers()
            self.wfile.write(body)
    return Handler

def main():
    endpoint=urlparse(Runtime.model_base)
    if endpoint.scheme not in ('http','https') or not endpoint.hostname or endpoint.username or endpoint.password or endpoint.query or endpoint.fragment:
        raise ValueError('Invalid operator model endpoint')
    interval=max(900,int(os.environ.get('GOODFORM_TREND_INTERVAL','900')))
    publisher=Publisher(os.environ.get('GOODFORM_PUBLIC_TREND_STORE','.data/publisher/briefing.json'))
    stop=threading.Event()
    worker=threading.Thread(target=publisher.run,args=(stop,interval),daemon=True)
    worker.start()
    server=ThreadingHTTPServer((os.environ.get('GOODFORM_PUBLIC_BIND','127.0.0.1'),int(os.environ.get('GOODFORM_PUBLIC_PORT','4320'))),handler_for(publisher))
    print('Public Trend desk service started; collection runs independently of readers.',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: stop.set();server.server_close()

if __name__=='__main__': main()
