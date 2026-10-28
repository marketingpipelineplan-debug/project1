import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from server import app, intelligence as intel


class IntelligenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old = app.DB_PATH
        app.DB_PATH = Path(self.temp.name)/'workspace.sqlite3'
        app.init_db()
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        intel._research_cache.clear()
        intel._last_attempt = 0

    def tearDown(self):
        self.env.stop()
        app.DB_PATH = self.old
        self.temp.cleanup()

    def post(self, id, day, views=200, **kw):
        return dict(id=id,title=f'Video {id}',platform='YouTube',format='Video',
                    published_at=f'2026-01-{day:02d}T00:00:00+00:00',
                    observed_at=f'2026-01-{day+2:02d}T00:00:00+00:00',
                    observation_hours=48,views=views,likes=10,comments=4,**kw)

    def import_rows(self, rows):
        app.import_posts({'format':'json','content':json.dumps(rows)})

    def baseline(self):
        self.import_rows([self.post('base-a',1,100),self.post('base-b',3,200),self.post('base-c',5,300)])

    def approved(self,kind='Video idea'):
        d=app.generate({'dataset':'imported','kind':kind})
        return app.change_draft(d['id'],{'action':'approve','revision':d['revision'],'checks':{k:True for k in app.CHECKS}})

    def plan(self,prospective=True,**kw):
        d=self.approved()
        payload=dict(dataset='imported',draft_id=d['id'],draft_revision=d['revision'],platform='YouTube',format='Video',
                     factor='Result-first opening',hypothesis='A clearer promise may hold attention.',metric='views',target_hours=48,target_lift=20,**kw)
        if prospective:
            with patch.object(app,'now',return_value='2026-01-10T00:00:00+00:00'):
                return intel.create_experiment(app,payload)['id']
        return intel.create_experiment(app,payload)['id']

    def outcome(self,id):
        return next(e for e in intel.learning(app,'imported')['experiments'] if e['id']==id)

    def test_all_four_idea_types_have_format_and_review_gate(self):
        for kind,spec in intel.IDEAS.items():
            d=app.generate({'dataset':'demo','kind':kind})
            self.assertEqual(d['status'],'pending')
            self.assertEqual(d['strategy_context']['format_brief']['platform'],spec['platform'])
            self.assertIn('Experiment:',d['body'])
            self.assertIn('no completed prospective experiments',d['body'])
            with self.assertRaises(app.AppError): app.export_draft(d['id'])

    def test_history_retains_each_snapshot_and_does_not_roll_back_latest(self):
        old=self.post('target',11,260)
        new={**old,'views':800,'observation_hours':168,'observed_at':'2026-01-18T00:00:00+00:00'}
        self.import_rows([new]);self.import_rows([old]);self.import_rows([old])
        self.assertEqual(len(intel.observations(app,'imported')),2)
        self.assertEqual(app.get_posts('imported')[0]['views'],800)

    def test_conflicting_same_timestamp_rejected_atomically(self):
        p=self.post('target',11)
        self.import_rows([p])
        with self.assertRaises(app.AppError): self.import_rows([self.post('another',12),{**p,'views':999}])
        self.assertEqual(len(app.get_posts('imported')),1)
        self.assertEqual(len(intel.observations(app,'imported')),1)

    def test_experiment_requires_current_approval(self):
        self.baseline()
        d=app.generate({'dataset':'imported','kind':'Video idea'})
        with self.assertRaises(app.AppError): intel.create_experiment(app,dict(dataset='imported',draft_id=d['id'],draft_revision=1,platform='YouTube',format='Video',factor=intel.FACTORS[0],hypothesis='Test',metric='views'))

    def test_matched_outcome_updates_memory_and_next_generation(self):
        self.baseline();eid=self.plan()
        self.import_rows([self.post('target',11,260)])
        intel.link_experiment(app,eid,{'post_id':'target'})
        e=self.outcome(eid)
        self.assertEqual(e['status'],'above_target')
        self.assertEqual(e['baseline_value'],200)
        self.assertEqual(e['lift_percent'],30)
        self.assertFalse(e['retrospective'])
        report=intel.learning(app,'imported')
        self.assertEqual(report['summary']['above_target'],1)
        self.assertEqual(report['patterns'][0]['wins'],1)
        d=app.generate({'dataset':'imported','kind':'Video idea'})
        self.assertIn('1/1',d['body'])
        self.assertEqual(d['strategy_context']['creator_memory'][0]['experiment_ids'],[eid])
        reel=app.generate({'dataset':'imported','kind':'Reel idea'})
        self.assertEqual(reel['strategy_context']['creator_memory'],[])

    def test_supporting_metrics_are_observations_not_causal_claims(self):
        self.import_rows([self.post('a',1,100,retention=40,ctr=3),self.post('b',3,200,retention=50,ctr=4),self.post('c',5,300,retention=60,ctr=5)])
        eid=self.plan();self.import_rows([self.post('target',11,260,retention=70,ctr=6)])
        intel.link_experiment(app,eid,{'post_id':'target'})
        signals=self.outcome(eid)['supporting_signals']
        retention=next(s for s in signals if s['metric']=='retention')
        self.assertEqual(retention['delta'],20)
        self.assertEqual(retention['unit'],'percentage points')
        self.assertIn('does not establish why',self.outcome(eid)['caveat'])

    def test_failed_attempts_are_learned_not_dropped(self):
        self.baseline();eid=self.plan()
        self.import_rows([self.post('target',11,100)])
        intel.link_experiment(app,eid,{'post_id':'target'})
        report=intel.learning(app,'imported')
        self.assertEqual(report['summary']['below_target'],1)
        self.assertEqual(report['patterns'][0]['wins'],0)
        self.assertEqual(report['patterns'][0]['median_lift'],-50)

    def test_late_baselines_do_not_leak_into_plan(self):
        self.baseline();eid=self.plan()
        self.import_rows([self.post('late-backfill',2,100000)])
        self.import_rows([self.post('target',11,260)])
        intel.link_experiment(app,eid,{'post_id':'target'})
        self.assertEqual(self.outcome(eid)['baseline_value'],200)
        self.assertEqual(self.outcome(eid)['baseline_count'],3)

    def test_unknown_window_is_not_a_failure(self):
        self.baseline();eid=self.plan()
        p=self.post('target',11,999)
        p['observation_hours']=None
        self.import_rows([p]);intel.link_experiment(app,eid,{'post_id':'target'})
        self.assertEqual(self.outcome(eid)['status'],'awaiting')
        self.assertEqual(intel.learning(app,'imported')['summary']['below_target'],0)

    def test_later_observations_do_not_replace_target_window(self):
        self.baseline();eid=self.plan()
        p=self.post('target',11,260)
        self.import_rows([p]);intel.link_experiment(app,eid,{'post_id':'target'})
        self.import_rows([{**p,'observation_hours':168,'observed_at':'2026-01-18T00:00:00+00:00','views':9999}])
        e=self.outcome(eid)
        self.assertEqual(e['observed_value'],260)
        self.assertEqual(len(e['observations']),2)

    def test_historical_review_does_not_become_prospective_memory(self):
        self.baseline();self.import_rows([self.post('target',11,260)])
        eid=self.plan(prospective=False)
        intel.link_experiment(app,eid,{'post_id':'target'})
        e=self.outcome(eid)
        self.assertTrue(e['retrospective'])
        self.assertEqual(e['baseline_count'],3)
        self.assertEqual(intel.learning(app,'imported')['patterns'],[])

    def test_one_post_cannot_count_twice(self):
        self.baseline();eid=self.plan();other=self.plan()
        self.import_rows([self.post('target',11,260)])
        intel.link_experiment(app,eid,{'post_id':'target'})
        with self.assertRaises(app.AppError): intel.link_experiment(app,other,{'post_id':'target'})

    def test_changed_draft_cannot_be_linked_as_approved_plan(self):
        self.baseline();eid=self.plan()
        d=next(d for d in app.bootstrap('imported')['drafts'] if d['status']=='approved')
        app.change_draft(d['id'],{'action':'edit','revision':d['revision'],'title':d['title'],'body':'Changed after planning'})
        self.import_rows([self.post('target',11,260)])
        with self.assertRaises(app.AppError): intel.link_experiment(app,eid,{'post_id':'target'})

    def test_workspace_isolation_in_learning(self):
        self.baseline();self.plan()
        self.assertEqual(intel.learning(app,'demo')['experiments'],[])

    def test_reddit_missing_credentials_never_scrapes(self):
        with patch.object(intel,'reddit_open') as opened:
            with self.assertRaises(app.AppError) as ctx: intel.research_reddit_trends(app,{'communities':['popular']})
            self.assertEqual(ctx.exception.status,503)
            opened.assert_not_called()

    def test_reddit_rejects_arbitrary_destinations_and_sort(self):
        for payload in [{'communities':['https://evil.test']},{'communities':['../../private']},{'communities':['popular'],'sort':'random'}]:
            with self.subTest(payload=payload),patch.object(intel,'reddit_open') as opened:
                with self.assertRaises(app.AppError): intel.research_reddit_trends(app,payload)
                opened.assert_not_called()

    def test_reddit_normalization_filters_unsafe_stale_and_pinned(self):
        clock=1_800_000_000
        p={'id':'abc12','title':'A useful question','created_utc':clock-7200,'score':120,'num_comments':14,'subreddit':'productivity'}
        values=[p,{**p,'id':'pinned','stickied':True},{**p,'id':'adult','over_18':True},{**p,'id':'stale','created_utc':clock-9*86400},{**p,'id':'../bad'}]
        out=intel.normalize_reddit([{'data':p} for p in values],clock)
        self.assertEqual(len(out),1)
        self.assertEqual(out[0]['url'],'https://www.reddit.com/comments/abc12')
        self.assertEqual(out[0]['age_hours'],2)
        self.assertEqual(out[0]['momentum_score'],50)

    def test_authenticated_research_is_cached_and_secrets_not_returned(self):
        listing={'data':{'children':[{'data':{'id':'abc12','title':'A useful question','created_utc':intel.time.time()-3600,'score':120,'num_comments':12,'subreddit':'productivity'}}]}}
        with patch.dict(os.environ,{'GOODFORM_REDDIT_ACCESS_TOKEN':'test-token','GOODFORM_REDDIT_USER_AGENT':'goodform-tests/1'}),patch.object(intel,'reddit_open',return_value=io.BytesIO(json.dumps(listing).encode())) as opened:
            result=intel.research_reddit_trends(app,{'communities':['productivity'],'sort':'hot'})
            second=intel.research_reddit_trends(app,{'communities':['productivity'],'sort':'hot'})
            self.assertEqual(opened.call_count,1)
            self.assertTrue(second['cached'])
            self.assertNotIn('test-token',json.dumps(result))
            request=opened.call_args.args[0]
            self.assertTrue(request.full_url.startswith('https://oauth.reddit.com/r/productivity/hot?'))
            self.assertEqual(request.get_header('Authorization'),'Bearer test-token')
            draft=app.generate({'dataset':'demo','kind':'Reel idea','research':{'communities':['productivity'],'sort':'hot'}})
            self.assertIn('https://www.reddit.com/comments/abc12',draft['body'])
            self.assertEqual(draft['status'],'pending')
            self.assertNotIn('title',draft['strategy_context']['research']['sources'][0])

    def test_rate_limit_returns_error_without_secret_or_fallback(self):
        with patch.dict(os.environ,{'GOODFORM_REDDIT_ACCESS_TOKEN':'test-token','GOODFORM_REDDIT_USER_AGENT':'goodform-tests/1'}),patch.object(intel,'reddit_open',side_effect=HTTPError('url',429,'secret error',{},None)):
            with self.assertRaises(app.AppError) as ctx: intel.research_reddit_trends(app,{'communities':['popular']})
            self.assertEqual(ctx.exception.status,429)
            self.assertNotIn('secret',ctx.exception.message)

    def test_model_prompt_receives_research_and_memory_as_data(self):
        self.baseline();eid=self.plan();self.import_rows([self.post('target',11,260)]);intel.link_experiment(app,eid,{'post_id':'target'})
        responses=[io.BytesIO(b'{"capabilities":["completion"]}'),io.BytesIO(json.dumps({'message':{'content':json.dumps({'title':'An experiment','body':'Test the opening with one metric.'})}}).encode())]
        with patch.object(app,'urlopen',side_effect=responses) as opened:
            d=app.generate({'dataset':'imported','kind':'Video idea','use_ai':True})
            payload=json.loads(opened.call_args.args[0].data)
            context=json.loads(payload['messages'][1]['content'])
            self.assertEqual(context['creator_memory'][0]['wins'],1)
            self.assertIn('5–8 minute',context['format_brief']['structure'])
            self.assertEqual(d['status'],'pending')
