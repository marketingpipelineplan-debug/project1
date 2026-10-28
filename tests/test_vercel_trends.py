import json
import os
import unittest
from unittest.mock import patch
from server import vercel_trends as v


def report():
    return {'collected_at': v.Runtime.now(), 'summary': 'A sampled discussion [reddit:abc].',
            'sources': [{'id': 'reddit:abc', 'platform': 'Reddit', 'title': 'Example',
                         'url': 'https://www.reddit.com/comments/abc', 'observed_at': v.Runtime.now(), 'metrics': {}}],
            'coverage': [], 'generator': 'test', 'limitations': []}


class MemoryStore:
    def __init__(self):
        self.data = {}
    def command(self, cmd, *args):
        if cmd == 'GET': return self.data.get(args[0])
        if cmd == 'MGET': return [self.data.get(k) for k in args]
        if cmd == 'SET':
            key, value, *options = args
            if 'NX' in options and key in self.data: return None
            self.data[key] = value
            return 'OK'
        if cmd == 'EVAL':
            script, count, *values = args
            keys, argv = values[:count], values[count:]
            if self.data.get(keys[0]) != argv[0]: return 0
            if count == 3:
                self.data[keys[1]], self.data[keys[2]] = argv[1:]
            else: del self.data[keys[0]]
            return 1
        raise AssertionError(cmd)


class VercelTrendsTests(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()
        self.service = v.Service(self.store, report)

    def test_cron_fails_closed_and_public_reads_never_build(self):
        self.service.build = lambda: self.fail('Public request generated a report')
        with patch.dict(os.environ, {'CRON_SECRET': ''}):
            self.assertEqual(self.service.route('GET', '/api/refresh', 'Bearer ')[0], 401)
        with patch.dict(os.environ, {'CRON_SECRET': 'secret'}):
            self.assertEqual(self.service.route('GET', '/api/refresh', 'Bearer wrong')[0], 401)
        self.assertFalse(self.service.route('GET', '/v1/briefing')[1]['available'])
        self.assertEqual(self.service.route('POST', '/api/refresh')[0], 405)
        self.assertEqual(self.service.route('GET', '/api/posts')[0], 404)

    def test_publish_durable_snapshot_and_cooldown(self):
        self.assertEqual(self.service.refresh()['status'], 'published')
        another = v.Service(self.store, lambda: self.fail('Repeated inference'))
        self.assertTrue(another.snapshot()['available'])
        self.assertFalse(another.snapshot()['stale'])
        self.assertEqual(another.refresh()['status'], 'cooldown')
        self.assertNotIn(v.LOCK, self.store.data)

    def test_invalid_output_preserves_last_good(self):
        self.service.refresh()
        old = self.store.data[v.KEY]
        self.store.data.pop(v.ATTEMPT)
        self.service.build = lambda: {**report(), 'summary': 'Invented [missing:id]'}
        with patch.dict(os.environ, {'CRON_SECRET': 'secret'}):
            self.assertEqual(self.service.route('GET', '/api/refresh', 'Bearer secret')[0], 503)
        self.assertEqual(self.store.data[v.KEY], old)
        self.assertTrue(self.service.snapshot()['stale'])
        self.assertNotIn(v.LOCK, self.store.data)

    def test_concurrent_refresh_does_not_generate(self):
        self.store.data[v.LOCK] = 'other invocation'
        self.service.build = lambda: self.fail('Duplicate inference')
        self.assertEqual(self.service.refresh()['status'], 'already_running')

    def test_expired_lease_cannot_publish_or_unlock_new_owner(self):
        def build():
            self.store.data[v.LOCK] = 'new owner'
            return report()
        self.service.build = build
        with self.assertRaises(ValueError): self.service.refresh()
        self.assertNotIn(v.KEY, self.store.data)
        self.assertEqual(self.store.data[v.LOCK], 'new owner')

    def test_missing_evidence_does_not_spend_model_tokens(self):
        with patch.object(v.public_trends, 'collect', return_value=([], [])), patch.object(v, 'request_json') as request:
            with self.assertRaises(ValueError): v.build_briefing()
            request.assert_not_called()

    def test_gateway_uses_only_public_evidence(self):
        evidence = report()['sources']
        with patch.object(v.public_trends, 'collect', return_value=([], evidence)), \
             patch.dict(os.environ, {'AI_GATEWAY_API_KEY': 'test-only-key'}), \
             patch.object(v, 'request_json', return_value={'choices': [{'message': {'content': report()['summary']}}]}) as request:
            result = v.build_briefing()
        self.assertTrue(result['version'])
        url, payload, token = request.call_args.args
        self.assertEqual(url, 'https://ai-gateway.vercel.sh/v1/chat/completions')
        self.assertEqual(json.loads(payload['messages'][1]['content']), {'sources': evidence, 'coverage': []})
        self.assertEqual(payload['max_tokens'], 1200)

    def test_storage_errors_are_sanitized(self):
        with patch.object(self.store, 'command', side_effect=ValueError('secret-value')):
            code, body = self.service.route('GET', '/v1/briefing')
        self.assertEqual(code, 503)
        self.assertNotIn('secret-value', json.dumps(body))


if __name__ == '__main__': unittest.main()
