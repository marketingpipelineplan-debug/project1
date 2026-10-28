import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from server import app, brain, brain_studio as studio
from test_brain import answer


class BrainStudioTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.previous = app.DB_PATH
        app.DB_PATH = Path(self.temp.name)/'workspace.sqlite3'
        app.init_db()
    def tearDown(self):
        app.DB_PATH = self.previous
        self.temp.cleanup()
    def prepare(self, dataset='demo'):
        return studio.prepare(app, {'dataset':dataset, 'format':'video', 'constraints':'Phone only, two hours.'})
    def complete(self, run):
        result = answer()
        for c in result['candidates']: c['evidence_ids'] = []
        with patch.dict('os.environ', {'AI_GATEWAY_API_KEY':'test-only'}), patch.object(brain, 'run_prepared', return_value=result) as request:
            completed = studio.generate(app, {'id':run['id'], 'dataset':run['dataset'], 'consent':True})
        return completed, request
    def test_prepare_is_offline_and_excludes_secret_profile_fields(self):
        with patch.object(brain, 'run_prepared') as model, patch.object(studio.trend_client, 'latest') as trends:
            run = self.prepare()
        model.assert_not_called(); trends.assert_not_called()
        self.assertNotIn('model', run['context']['creator'])
        self.assertNotIn('name', run['context']['creator'])
        self.assertTrue(run['context']['constraints']['sample_data'])
        self.assertNotIn('prompt', run)
        self.assertTrue(all('YouTube' in e['id'] for e in run['context']['evidence']))
    def test_imported_context_never_contains_demo_posts(self):
        run = self.prepare('imported')
        self.assertEqual(run['context']['evidence'], [])
        self.assertEqual(run['context']['creator_memory'], [])
        self.assertFalse(run['context']['constraints']['sample_data'])
    def test_consent_and_missing_key_prevent_calls(self):
        run = self.prepare()
        with patch.object(brain, 'run_prepared') as request:
            with self.assertRaises(app.AppError): studio.generate(app, {'id':run['id'], 'dataset':'demo'})
            with patch.dict('os.environ', {}, clear=True), self.assertRaises(app.AppError):
                studio.generate(app, {'id':run['id'], 'dataset':'demo', 'consent':True})
        request.assert_not_called()
    def test_workspace_cannot_access_another_session(self):
        run = self.prepare()
        with patch.dict('os.environ', {'AI_GATEWAY_API_KEY':'test-only'}), self.assertRaises(app.AppError) as caught:
            studio.generate(app, {'id':run['id'],'dataset':'imported','consent':True})
        self.assertEqual(caught.exception.status,404)
        self.assertEqual(studio.status(app,'imported')['runs'],[])
    def test_exact_preview_used_and_completed_request_is_idempotent(self):
        run = self.prepare()
        completed, request = self.complete(run)
        self.assertEqual(request.call_args.args[0],run['context'])
        with patch.dict('os.environ', {'AI_GATEWAY_API_KEY':'test-only'}), patch.object(brain,'run_prepared') as again:
            replay=studio.generate(app, {'id':run['id'],'dataset':'demo','consent':True})
        again.assert_not_called()
        self.assertEqual(completed,replay)
    def test_failure_is_persisted_and_does_not_make_draft(self):
        run = self.prepare()
        with patch.dict('os.environ', {'AI_GATEWAY_API_KEY':'test-only'}), patch.object(brain,'run_prepared',side_effect=ValueError('secret')):
            with self.assertRaises(app.AppError) as caught:
                studio.generate(app, {'id':run['id'],'dataset':'demo','consent':True})
        self.assertNotIn('secret',caught.exception.message)
        self.assertEqual(studio.status(app,'demo')['runs'][0]['status'],'failed')
        self.assertEqual(len(app.bootstrap('demo')['drafts']),1)
    def test_pending_draft_has_provenance_and_normal_approval_gate(self):
        run,_ = self.complete(self.prepare())
        payload={'id':run['id'],'dataset':'demo','candidate_id':'A'}
        draft=studio.draft(app,payload)
        self.assertEqual(draft['status'],'pending')
        self.assertEqual(draft['brain_session']['id'],run['id'])
        self.assertEqual(studio.draft(app,payload)['id'],draft['id'])
        with self.assertRaises(app.AppError): app.export_draft(draft['id'])
        approved=app.change_draft(draft['id'],{'action':'approve','revision':1,'checks':{k:True for k in app.CHECKS}})
        self.assertIn('Human-approved',app.export_draft(approved['id'])['content'])
        app.change_draft(draft['id'],{'action':'edit','revision':approved['revision'],'title':approved['title'],'body':'Changed claim'})
        with self.assertRaises(app.AppError): app.export_draft(draft['id'])
    def test_stale_public_delivery_not_used(self):
        with patch.object(studio.trend_client,'latest',return_value={'latest':{'sources':[{'id':'bad'}]},'stale':True}):
            run=studio.prepare(app,{'dataset':'imported','format':'tweet','include_trends':True})
        self.assertEqual(run['context']['evidence'],[])
    def test_expired_preparation_cannot_generate(self):
        run=self.prepare()
        with app.connect() as db:
            raw=studio.load(app,db,run['id'],'demo');raw['created_at']='2020-01-01T00:00:00+00:00';studio.save(app,db,raw)
        with patch.dict('os.environ',{'AI_GATEWAY_API_KEY':'test-only'}), patch.object(brain,'run_prepared') as request:
            with self.assertRaises(app.AppError): studio.generate(app,{'id':run['id'],'dataset':'demo','consent':True})
        request.assert_not_called()
    def test_running_session_cannot_be_double_charged(self):
        run=self.prepare()
        with app.connect() as db:
            raw=studio.load(app,db,run['id'],'demo');raw['status']='running';studio.save(app,db,raw)
        with patch.dict('os.environ',{'AI_GATEWAY_API_KEY':'test-only'}), patch.object(brain,'run_prepared') as request:
            with self.assertRaises(app.AppError): studio.generate(app,{'id':run['id'],'dataset':'demo','consent':True})
        request.assert_not_called()
    def review(self, run, **changes):
        payload={'dataset':run['dataset'],'id':run['id'],'candidate_id':'A','scores':{k:4 for k in brain.RUBRIC},'notes':'The production plan fits my available equipment.','decision':'keep','use_in_briefs':True}
        payload.update(changes)
        return studio.feedback(app,payload)
    def test_feedback_reused_only_in_matching_workspace_and_format(self):
        run,_=self.complete(self.prepare())
        review=self.review(run)
        prepared=self.prepare()
        self.assertEqual(prepared['context']['creator_feedback'][0]['notes'],review['notes'])
        self.assertEqual(self.prepare('imported')['context']['creator_feedback'],[])
        self.assertEqual(studio.prepare(app,{'dataset':'demo','format':'tweet'})['context']['creator_feedback'],[])
        self.assertEqual(prepared['context']['creator_memory'],[])
        self.assertEqual(studio.draft(app,{'id':run['id'],'dataset':'demo','candidate_id':'A'})['status'],'pending')
    def test_feedback_revision_audit_and_opt_out(self):
        run,_=self.complete(self.prepare())
        review=self.review(run)
        with self.assertRaises(app.AppError) as caught: self.review(run)
        self.assertEqual(caught.exception.status,409)
        self.review(run,previous_id=review['id'],use_in_briefs=False,decision='reject')
        self.assertEqual(self.prepare()['context']['creator_feedback'],[])
        self.assertEqual(len(studio.status(app,'demo')['feedback']),1)
        with app.connect() as db: self.assertEqual(db.execute('SELECT COUNT(*) FROM brain_feedback').fetchone()[0],2)
    def test_invalid_feedback_and_cross_workspace_fail(self):
        run,_=self.complete(self.prepare())
        for changes in ({'scores':{k:True for k in brain.RUBRIC}}, {'notes':'ok'}, {'use_in_briefs':'yes'}, {'candidate_id':'unknown'}, {'dataset':'imported'}):
            with self.subTest(changes=changes), self.assertRaises(app.AppError): self.review(run,**changes)
        self.assertEqual(studio.status(app,'demo')['feedback'],[])
    def test_feedback_does_not_rewrite_prepared_context(self):
        run,_=self.complete(self.prepare())
        prepared=self.prepare()
        self.review(run)
        with app.connect() as db: frozen=studio.load(app,db,prepared['id'],'demo')
        self.assertEqual(frozen['context']['creator_feedback'],[])
        self.assertEqual(frozen['context_hash'],prepared['context_hash'])
    def test_unfinished_session_cannot_be_rated(self):
        with self.assertRaises(app.AppError): self.review(self.prepare())
