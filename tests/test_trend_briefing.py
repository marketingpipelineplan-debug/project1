import io
import json
import os
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from server import app, intelligence, public_trends as public

class UniversalBriefingTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        intelligence._briefing_cache = None
        intelligence._briefing_epoch = 0
        public._cache.clear()
        public._retry_at.clear()
        self.source = public.source('YouTube','abcdefghijk','Public discussion','https://www.youtube.com/watch?v=abcdefghijk',{'views':100},'2026-10-14T00:00:00Z')

    def tearDown(self):
        self.env.stop()
        intelligence._briefing_cache = None
        intelligence._briefing_epoch = 0
        public._cache.clear()
        public._retry_at.clear()

    def test_unavailable_sources_never_fabricate_summary_or_call_network(self):
        with patch.object(public,'public_open',side_effect=AssertionError('Unexpected request')):
            report = intelligence.universal_trends(app,{})
        self.assertIsNone(report['summary'])
        self.assertEqual(report['sources'],[])
        self.assertEqual(report['coverage'][1]['status'],'Setup needed')

    def test_summary_uses_only_public_context_and_cache(self):
        responses = [io.BytesIO(b'{}'), io.BytesIO(json.dumps({'message':{'content':'Discussion [youtube:abcdefghijk]; single-source evidence.'}}).encode())]
        with patch.object(public,'collect',return_value=(public.coverage(),[self.source])) as collect, patch.object(app,'urlopen',side_effect=responses) as request, patch.object(app,'get_profile',side_effect=AssertionError('Private profile read')), patch.object(app,'get_posts',side_effect=AssertionError('Private analytics read')):
            report = intelligence.universal_trends(app,{'dataset':'imported'})
            repeat = intelligence.universal_trends(app,{'dataset':'demo'})
        self.assertEqual(report['summary'],repeat['summary'])
        self.assertTrue(repeat['cached'])
        self.assertEqual(collect.call_count,1)
        context = json.loads(request.call_args.args[0].data)['messages'][1]['content']
        self.assertNotIn('creator',context)
        self.assertIn('youtube:abcdefghijk',context)

    def test_remote_model_is_rejected(self):
        with patch.object(public,'collect',return_value=([],[self.source])), patch.object(app,'urlopen',return_value=io.BytesIO(b'{"remote_host":"example.com"}')) as request:
            report = intelligence.universal_trends(app,{})
        self.assertIsNone(report['summary'])
        self.assertEqual(request.call_count,1)

    def test_fabricated_citations_reject_summary(self):
        responses = [io.BytesIO(b'{}'),io.BytesIO(b'{"message":{"content":"Fake [invented] source."}}')]
        with patch.object(public,'collect',return_value=([],[self.source])), patch.object(app,'urlopen',side_effect=responses):
            report = intelligence.universal_trends(app,{})
        self.assertIsNone(report['summary'])
        self.assertEqual(report['sources'],[self.source])

    def test_simultaneous_generation_is_bounded(self):
        intelligence._briefing_lock.acquire()
        try:
            with self.assertRaises(app.AppError) as error: intelligence.universal_trends(app,{})
            self.assertEqual(error.exception.status,409)
        finally: intelligence._briefing_lock.release()

    def test_youtube_normalization_keeps_missing_metrics_unknown_and_safe_urls(self):
        result = public.normalize('YouTube',{'items':[
            {'id':'abcdefghijk','snippet':{'title':'Video'},'statistics':{'viewCount':'123','likeCount':'NaN'}},
            {'id':'../../evil','snippet':{'title':'Bad'}},
            {'id':'abcdefghijk','snippet':{'title':'Video'},'statistics':{'viewCount':'123'}},
        ]},'now')
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['metrics'],{'views':123})
        self.assertEqual(result[0]['url'],'https://www.youtube.com/watch?v=abcdefghijk')

    def test_live_sources_use_concurrent_viewers(self):
        twitch = public.normalize('Twitch',{'data':[{'id':'123','user_login':'channel','title':'Live','viewer_count':12,'game_name':'Art'}]},'now')
        kick = public.normalize('Kick',{'data':[{'id':'abc-123','channel':{'slug':'channel'},'title':'Live','viewer_count':10,'category':{'name':'Art'}}]},'now')
        self.assertEqual(twitch[0]['metrics'],{'concurrent viewers':12})
        self.assertEqual(kick[0]['category'],'Art')
        self.assertEqual(kick[0]['url'],'https://kick.com/channel')

    def test_x_topics_have_safe_search_links_and_stable_ids(self):
        a = public.normalize('X / Twitter',{'data':[{'trend_name':'#art & design'}]},'now')[0]
        b = public.normalize('X / Twitter',{'data':[{'trend_name':'#art & design'}]},'later')[0]
        self.assertEqual(a['id'],b['id'])
        self.assertEqual(a['metrics'],{})
        self.assertIn('%23art',a['url'])

    def test_provider_429_honors_cooldown_and_redacts_secrets(self):
        with patch.dict(os.environ,{'GOODFORM_X_BEARER_TOKEN':'SECRET'}), patch.object(public,'public_open',side_effect=HTTPError('https://example.com/SECRET',429,'SECRET',{'Retry-After':'120'},None)) as request:
            one = public.fetch('X / Twitter')
            two = public.fetch('X / Twitter')
        self.assertEqual(two['status'],'Cooling down')
        self.assertEqual(request.call_count,1)
        self.assertNotIn('SECRET',json.dumps(one))

    def test_provider_success_uses_cache_and_exact_destination(self):
        data = {'items':[{'id':'abcdefghijk','snippet':{'title':'Public video'},'statistics':{'viewCount':'123'}}]}
        with patch.dict(os.environ,{'GOODFORM_YOUTUBE_API_KEY':'SECRET','GOODFORM_TREND_REGION':'IN'}), patch.object(public,'public_open',return_value=io.BytesIO(json.dumps(data).encode())) as request:
            result = public.fetch('YouTube')
            public.fetch('YouTube')
        self.assertEqual(request.call_count,1)
        self.assertTrue(request.call_args.args[0].full_url.startswith('https://www.googleapis.com/youtube/v3/videos?'))
        self.assertIn('regionCode=IN',request.call_args.args[0].full_url)
        self.assertNotIn('SECRET',json.dumps(result))

    def test_partial_source_failure_does_not_drop_success(self):
        with patch.dict(os.environ,{'GOODFORM_YOUTUBE_API_KEY':'configured','GOODFORM_X_BEARER_TOKEN':'configured'}), patch.object(public,'fetch',side_effect=lambda p: {'status':'Scanned','items':[self.source]} if p=='YouTube' else {'status':'Unavailable','items':[]}):
            coverage,sources = public.collect(lambda: None,False)
        self.assertEqual(sources,[self.source])
        self.assertEqual(next(c for c in coverage if c['platform']=='YouTube')['count'],1)
        self.assertEqual(next(c for c in coverage if c['platform']=='Instagram')['status'],'Not implemented')

    def test_expired_summary_is_not_returned_as_current(self):
        intelligence._briefing_cache={'summary':'old'}
        intelligence._briefing_epoch=1
        self.assertIsNone(intelligence.trend_status()['latest'])

    def test_redirects_cannot_forward_auth(self):
        self.assertIsNone(public.NoRedirects().redirect_request(None,None,302,None,None,'https://evil.example'))

if __name__=='__main__': unittest.main()
