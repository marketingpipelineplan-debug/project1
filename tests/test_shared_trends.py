from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.request import Request, build_opener, ProxyHandler
from server import app, trend_client, trend_contract, trend_service


def report(age=0):
    date=(datetime.now(timezone.utc)-timedelta(seconds=age)).isoformat()
    return {'collected_at':date,'summary':'A test discussion [youtube:abcdefghijk].','generator':'Test model fixture',
            'sources':[{'id':'youtube:abcdefghijk','platform':'YouTube','title':'Fixture public source','url':'https://www.youtube.com/watch?v=abcdefghijk','observed_at':date,'category':'','metrics':{'views':100}}],
            'coverage':[{'platform':'YouTube','status':'Scanned','method':'Regional chart','error':'SECRET','credentials':'SECRET'}],
            'limitations':['Test data, not current trends.'],'operator_secret':'SECRET'}

class SharedTrendTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)
        self.env=patch.dict(os.environ,{},clear=True)
        self.env.start()
        trend_client._instances.clear()
    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()
        trend_client._instances.clear()

    def test_contract_is_public_only_and_idempotent(self):
        value=trend_contract.validate(report())
        self.assertNotIn('SECRET',json.dumps(value))
        self.assertEqual(value,trend_contract.validate(value))
        self.assertEqual(value['coverage'][0]['status'],'Included')

    def test_contract_rejects_unsafe_urls_and_unknown_citations(self):
        for url in ('javascript:alert(1)','https://evil.example/a','https://secret@www.youtube.com/watch?v=a','http://www.youtube.com/a'):
            value=report();value['sources'][0]['url']=url
            with self.assertRaises(ValueError):trend_contract.validate(value)
        value=report();value['summary']='Made up [unknown]'
        with self.assertRaises(ValueError):trend_contract.validate(value)

    def test_failed_refresh_preserves_last_good_across_restart(self):
        build=Mock(side_effect=[report(),{'summary':None}])
        publisher=trend_service.Publisher(self.path/'latest.json',build)
        self.assertTrue(publisher.refresh())
        version=publisher.snapshot()['latest']['version']
        self.assertFalse(publisher.refresh())
        self.assertEqual(publisher.snapshot()['latest']['version'],version)
        self.assertTrue(publisher.snapshot()['stale'])
        restored=trend_service.Publisher(self.path/'latest.json',build)
        self.assertEqual(restored.snapshot()['latest']['version'],version)

    def test_first_failure_does_not_publish_placeholder(self):
        publisher=trend_service.Publisher(self.path/'latest.json',lambda: {'summary':None})
        self.assertFalse(publisher.refresh())
        self.assertIsNone(publisher.snapshot()['latest'])
        self.assertFalse((self.path/'latest.json').exists())

    def test_background_worker_runs_without_readers(self):
        publisher=trend_service.Publisher(self.path/'latest.json',Mock(return_value=report()))
        stop=Mock();stop.is_set.side_effect=[False,False,True]
        publisher.run(stop,900)
        self.assertEqual(publisher.build.call_count,2)
        self.assertEqual(stop.wait.call_count,2)

    def test_client_persists_then_survives_outage_and_restart(self):
        envelope={'latest':report(),'stale':False}
        path=self.path/'cache.json'
        subscriber=trend_client.Subscriber(path,'https://public.example/v1/briefing')
        with patch.object(trend_client,'fetch_public',return_value=io.BytesIO(json.dumps(envelope).encode())) as fetch:
            first=subscriber.read()
            subscriber.read()
        self.assertEqual(fetch.call_count,1)
        request=fetch.call_args.args[0]
        self.assertIsNone(request.data)
        self.assertIsNone(request.get_header('Authorization'))
        restored=trend_client.Subscriber(path,subscriber.url)
        with patch.object(trend_client,'fetch_public',side_effect=OSError('offline')):
            cached=restored.read()
        self.assertTrue(cached['stale'])
        self.assertEqual(first['latest']['version'],cached['latest']['version'])

    def test_older_delivery_cannot_replace_newer_briefing(self):
        subscriber=trend_client.Subscriber(self.path/'cache.json','https://public.example/v1/briefing')
        subscriber.latest=trend_contract.validate(report())
        version=subscriber.latest['version']
        with patch.object(trend_client,'fetch_public',return_value=io.BytesIO(json.dumps({'latest':report(86400),'stale':True}).encode())):
            result=subscriber.read()
        self.assertEqual(result['latest']['version'],version)
        self.assertTrue(result['stale'])

    def test_oversized_response_and_corrupt_cache_are_safe(self):
        path=self.path/'cache.json';path.write_text('invalid json')
        subscriber=trend_client.Subscriber(path,'https://public.example/v1/briefing')
        with patch.object(trend_client,'fetch_public',return_value=io.BytesIO(b'x'*(trend_contract.MAX_BYTES+1))):
            result=subscriber.read()
        self.assertEqual(result['status'],'waiting')
        self.assertNotIn('API',result['message'])

    def test_no_service_config_does_not_use_local_credentials_or_model(self):
        with patch.dict(os.environ,{'GOODFORM_TREND_SERVICE_URL':'','GOODFORM_YOUTUBE_API_KEY':'SECRET'}), patch.object(trend_client,'fetch_public',side_effect=AssertionError('Network not expected')), patch.object(app,'get_posts',side_effect=AssertionError('No private analytics')):
            result=trend_client.latest(self.path/'workspace.db')
        self.assertIsNone(result['latest'])
        self.assertNotIn('SECRET',json.dumps(result))

    def test_service_address_rejects_insecure_remote_or_credentials(self):
        for value in ('http://example.com','https://secret@example.com','https://example.com?key=secret'):
            with patch.dict(os.environ,{'GOODFORM_TREND_SERVICE_URL':value}):self.assertIsNone(trend_client.service_url())
        with patch.dict(os.environ,{'GOODFORM_TREND_SERVICE_URL':'https://public.example'}):
            self.assertEqual(trend_client.service_url(),'https://public.example/v1/briefing')

    def test_public_http_reads_same_version_and_cannot_generate(self):
        publisher=trend_service.Publisher(self.path/'latest.json',Mock(return_value=report()))
        publisher.refresh()
        server=ThreadingHTTPServer(('127.0.0.1',0),trend_service.handler_for(publisher))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        opener=build_opener(ProxyHandler({}))
        try:
            with opener.open(base+'/v1/briefing') as response:one=json.load(response)
            with opener.open(base+'/v1/briefing') as response:two=json.load(response)
            reader=trend_client.Subscriber(self.path/'reader.json',base+'/v1/briefing')
            delivered=reader.read()
            self.assertEqual(delivered['latest']['version'],one['latest']['version'])
            self.assertEqual(one['latest']['version'],two['latest']['version'])
            self.assertEqual(publisher.build.call_count,1)
            with self.assertRaises(HTTPError) as error:opener.open(Request(base+'/v1/briefing',data=b'{}'))
            self.assertEqual(error.exception.code,405)
            with self.assertRaises(HTTPError) as error:opener.open(base+'/api/bootstrap')
            self.assertEqual(error.exception.code,404)
        finally:server.shutdown();server.server_close();thread.join()

    def test_desktop_routes_only_deliver_and_never_generate(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        opener=build_opener(ProxyHandler({}))
        expected={'latest':None,'status':'waiting'}
        try:
            with patch.object(trend_client,'latest',return_value=expected) as read, patch.object(app.intelligence,'universal_trends',side_effect=AssertionError('No desktop synthesis')):
                for path in ('/api/trends/latest','/api/trends/status'):
                    with opener.open(base+path) as response:self.assertEqual(json.load(response),expected)
                with opener.open(Request(base+'/api/trends/briefing',data=b'{}',headers={'Content-Type':'application/json'})) as response:self.assertEqual(json.load(response),expected)
                self.assertEqual(read.call_count,3)
        finally:server.shutdown();server.server_close();thread.join()
