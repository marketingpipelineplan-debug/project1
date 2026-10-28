import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys
import threading
from urllib.request import Request, urlopen
from urllib.error import HTTPError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server import app

class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.original=app.DB_PATH
        app.DB_PATH=Path(self.temp.name)/'test.sqlite3'
        app.init_db()
    def tearDown(self):
        app.DB_PATH=self.original
        self.temp.cleanup()
    def post(self,**changes):
        return {'id':'one','title':'A useful video','platform':'YouTube','format':'Video','published_at':'2026-01-01T00:00:00Z','observed_at':'2026-01-03T00:00:00Z','observation_hours':48,'views':1000,'likes':50,'comments':10,**changes}
    def draft(self): return app.generate({'dataset':'demo','kind':'Content idea','use_ai':False})
    def approve(self,d): return app.change_draft(d['id'],{'action':'approve','revision':d['revision'],'checks':{k:True for k in app.CHECKS}})
    def test_demo_and_imported_workspaces_are_isolated(self):
        self.assertEqual(len(app.bootstrap('demo')['posts']),12)
        self.assertEqual(app.bootstrap('imported')['posts'],[])
        app.import_posts({'format':'json','content':json.dumps([self.post()])})
        self.assertEqual(len(app.bootstrap('demo')['posts']),12)
        p=app.bootstrap('imported')['posts'][0]
        self.assertIsNone(p['retention'])
        self.assertIsNone(p['shares'])
        self.assertIsNone(p['score'])
    def test_bad_row_rolls_back_whole_import(self):
        for bad in [dict(views=-1),dict(retention=101),dict(likes=2.5),dict(views=float('nan')),dict(observation_hours=24),dict(published_at='not-a-date')]:
            with self.subTest(bad=bad),self.assertRaises(app.AppError):
                app.import_posts({'format':'json','content':json.dumps([self.post(),self.post(id='two',**bad)])})
            self.assertEqual(app.get_posts('imported'),[])
    def test_csv_and_upsert(self):
        content='id,title,platform,format,published_at,views,likes,comments,observed_at\none,Hello,YouTube,Video,2026-01-01,120,8,3,2026-01-02\n'
        app.import_posts({'format':'csv','content':content})
        app.import_posts({'format':'json','content':json.dumps([self.post()])})
        self.assertEqual(len(app.get_posts('imported')),1)
        self.assertEqual(app.get_posts('imported')[0]['views'],1000)
    def test_same_id_on_different_platforms(self):
        app.import_posts({'format':'json','content':json.dumps([self.post(),self.post(platform='Instagram')])})
        self.assertEqual(len(app.get_posts('imported')),2)
    def test_duplicate_id_is_rejected(self):
        with self.assertRaises(app.AppError): app.import_posts({'format':'json','content':json.dumps([self.post(),self.post()])})
    def test_missing_windows_do_not_get_scored(self):
        posts=[self.post(id=str(i),observation_hours=None) for i in range(4)]
        self.assertTrue(all(p['score'] is None for p in app.score_posts(posts)))
    def test_scores_compare_only_same_cohort(self):
        posts=[self.post(id=str(i),views=100*(i+1),likes=5*(i+1)) for i in range(3)]
        other=self.post(id='different',platform='TikTok',views=999999)
        scores=app.score_posts(posts+[other])
        self.assertEqual(scores[0]['cohort_size'],3)
        self.assertIsNone(next(p for p in scores if p['id']=='different')['score'])
        self.assertTrue(all(0<=p['score']<=100 for p in scores if p['score'] is not None))
    def test_cannot_export_pending_or_incompletely_approved(self):
        d=self.draft()
        with self.assertRaises(app.AppError): app.export_draft(d['id'])
        with self.assertRaises(app.AppError): app.change_draft(d['id'],{'action':'approve','revision':1,'checks':{'evidence':True}})
        self.assertEqual(app.get_events(d['id'])[0]['action'],'created')
    def test_approval_edit_invalidation_and_history(self):
        d=self.approve(self.draft())
        self.assertEqual(d['status'],'approved')
        self.assertIn('Human-approved revision 2',app.export_draft(d['id'])['content'])
        d=app.change_draft(d['id'],{'action':'edit','revision':d['revision'],'title':d['title'],'body':'An edited claim needs review.'})
        self.assertEqual(d['status'],'pending')
        self.assertNotIn('approved_hash',d)
        with self.assertRaises(app.AppError): app.export_draft(d['id'])
        self.assertEqual([e['action'] for e in app.get_events(d['id'])],['edit','approve','created'])
        self.assertNotEqual(app.get_events(d['id'])[0]['content_hash'],app.get_events(d['id'])[1]['content_hash'])
    def test_stale_approval_and_duplicate_decision_rejected(self):
        d=self.draft()
        self.approve(d)
        with self.assertRaises(app.AppError) as ctx: self.approve(d)
        self.assertEqual(ctx.exception.status,409)
    def test_rejection_requires_feedback(self):
        d=self.draft()
        with self.assertRaises(app.AppError): app.change_draft(d['id'],{'action':'reject','revision':1})
        d=app.change_draft(d['id'],{'action':'reject','revision':1,'note':'The product claim needs evidence.'})
        self.assertEqual(d['status'],'rejected')
        with self.assertRaises(app.AppError): app.export_draft(d['id'])
    def test_approved_content_tampering_blocks_export(self):
        d=self.approve(self.draft())
        d['body']='Changed without going through review'
        with app.connect() as db: db.execute('UPDATE drafts SET data=? WHERE id=?',(app.dumps(d),d['id']))
        with self.assertRaises(app.AppError): app.export_draft(d['id'])
    def test_ai_failure_does_not_silently_fall_back(self):
        with patch.object(app,'urlopen',side_effect=OSError('offline')):
            with self.assertRaises(app.AppError) as ctx: app.generate({'dataset':'demo','use_ai':True})
            self.assertEqual(ctx.exception.status,502)
    def test_cloud_model_is_rejected_before_generation(self):
        with patch.object(app,'get_profile',return_value={**app.DEFAULT_PROFILE,'model':'some-model:cloud'}), patch.object(app,'urlopen') as request:
            with self.assertRaises(app.AppError): app.generate({'dataset':'demo','use_ai':True})
            request.assert_not_called()
    def test_remote_model_alias_is_rejected(self):
        import io
        with patch.object(app,'urlopen',return_value=io.BytesIO(b'{"remote_host":"https://example.com","remote_model":"remote"}')):
            with self.assertRaises(app.AppError) as ctx: app.generate({'dataset':'demo','use_ai':True})
            self.assertEqual(ctx.exception.status,400)
    def test_ai_can_only_create_pending_drafts(self):
        import io
        responses=[io.BytesIO(b'{"capabilities":["completion"]}'),io.BytesIO(json.dumps({'message':{'content':json.dumps({'title':'A grounded idea','body':'Test one clear opening.','status':'approved'})}}).encode())]
        with patch.object(app,'urlopen',side_effect=responses):
            d=app.generate({'dataset':'demo','use_ai':True})
            self.assertEqual(d['status'],'pending')
            self.assertEqual(d['revision'],1)
            with self.assertRaises(app.AppError): app.export_draft(d['id'])
    def test_daily_brief_does_not_claim_daily_growth(self):
        d=app.generate({'dataset':'demo','kind':'Daily brief','use_ai':False})
        self.assertIn('not views gained today',d['body'])
        self.assertEqual(d['status'],'pending')
    def test_restart_preserves_drafts_and_decisions(self):
        d=self.approve(self.draft())
        app.init_db()
        saved=next(x for x in app.bootstrap('demo')['drafts'] if x['id']==d['id'])
        self.assertEqual(saved['status'],'approved')
        self.assertEqual(len(app.get_posts('demo')),12)

class HTTPTests(unittest.TestCase):
    setUp = PipelineTests.setUp
    tearDown = PipelineTests.tearDown
    def test_http_origin_and_json_boundary(self):
        server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        try:
            with urlopen(base+'/api/bootstrap?dataset=demo',timeout=5) as r: self.assertEqual(r.status,200)
            for headers,expected in [({'Origin':'https://evil.example','Content-Type':'application/json'},403),({'Content-Type':'text/plain'},415)]:
                with self.assertRaises(HTTPError) as ctx: urlopen(Request(base+'/api/generate',data=b'{}',headers=headers),timeout=5)
                self.assertEqual(ctx.exception.code,expected)
        finally:
            server.shutdown();server.server_close();thread.join()
