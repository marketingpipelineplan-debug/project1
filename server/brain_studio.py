"""Private local brain workflow. Not exposed by the public Vercel handler."""
from datetime import datetime, timezone
import json
import os
try:
    from . import brain, intelligence, trend_client
except ImportError:
    import brain, intelligence, trend_client

KINDS = {'video': ('Video idea', 'YouTube', 'Video'), 'reel': ('Reel idea', 'Instagram', 'Reel'),
         'tweet': ('Tweet idea', 'X', 'Post'), 'livestream': ('Livestream idea', 'Twitch', 'Stream'),
         'ad': ('Ad brief', None, None), 'collaboration': ('Collaboration brief', None, None)}


def init(db):
    db.execute('CREATE TABLE IF NOT EXISTS brain_feedback(id TEXT PRIMARY KEY, dataset TEXT NOT NULL, run_id TEXT NOT NULL, candidate_id TEXT NOT NULL, data TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS brain_runs(id TEXT PRIMARY KEY, dataset TEXT NOT NULL, data TEXT NOT NULL)')


def status(a, dataset):
    a.check_dataset(dataset)
    with a.connect() as db:
        runs = [json.loads(r[0]) for r in db.execute('SELECT data FROM brain_runs WHERE dataset=? ORDER BY rowid DESC LIMIT 10', (dataset,))]
        reviews = [json.loads(r[0]) for r in db.execute('SELECT data FROM brain_feedback WHERE dataset=? ORDER BY rowid DESC', (dataset,))]
    latest = {}
    for review in reviews: latest.setdefault((review['run_id'], review['candidate_id']), review)
    return {'feedback': list(latest.values()), 'rubric': brain.RUBRIC, 'configured': bool(os.environ.get('AI_GATEWAY_API_KEY')), 'models': brain.MODELS,
            'version': brain.VERSION, 'runs': [public(r) for r in runs]}


def public(run):
    return {k: v for k, v in run.items() if k not in ('prompt', 'draft_evidence')}


def load(a, db, identity, dataset):
    row = db.execute('SELECT data FROM brain_runs WHERE id=? AND dataset=?', (identity, dataset)).fetchone()
    if not row: raise a.AppError('Brain session not found in this workspace.', 404)
    return json.loads(row[0])


def save(a, db, run):
    db.execute('UPDATE brain_runs SET data=? WHERE id=?', (a.dumps(run), run['id']))


def prepare(a, payload):
    dataset = a.check_dataset(payload.get('dataset'))
    fmt = payload.get('format')
    if fmt not in KINDS: raise a.AppError('Choose a supported format.')
    model = payload.get('model', brain.MODELS['primary'])
    if model not in brain.MODELS.values(): raise a.AppError('Choose a configured strategy model.')
    constraints = payload.get('constraints', '')
    if not isinstance(constraints, str) or len(constraints) > 2500:
        raise a.AppError('Keep the production brief under 2,500 characters.')
    kind, platform, medium = KINDS[fmt]
    posts = a.get_posts(dataset)
    same_format = [p for p in posts if p['platform'] == platform and p['format'] == medium]
    # Most recent evidence, not only the winners. Cross-format examples are labeled.
    selected = sorted(same_format or posts, key=lambda p: p['observed_at'], reverse=True)[:8]
    evidence = []
    for p in selected:
        identity = 'post:' + p['platform'] + ':' + p['id']
        facts = {k: p.get(k) for k in ('title', 'platform', 'format', 'views', 'likes', 'comments', 'shares', 'retention', 'observation_hours')}
        evidence.append({'id': identity, 'kind': 'creator_result', 'observed_at': p['observed_at'],
                         'text': a.dumps(facts), 'sample': dataset == 'demo'})
        for i, comment in enumerate(p.get('comment_samples', [])[:3]):
            evidence.append({'id': identity + ':comment:' + str(i), 'kind': 'audience_comment',
                             'observed_at': p['observed_at'], 'text': comment, 'sample': dataset == 'demo'})
    learning = intelligence.learning(a, dataset)
    memory = [p for p in learning['patterns'] if platform is None or (p['platform'] == platform and p['format'] == medium)]
    delivery = trend_client.latest(a.DB_PATH) if payload.get('include_trends') is True else None
    if delivery and delivery.get('latest') and not delivery.get('stale'):
        for row in delivery['latest']['sources'][:20]:
            evidence.append({'id': 'trend:' + row['id'], 'kind': 'trend', 'text': a.dumps({k: row.get(k) for k in ('title', 'platform', 'metrics', 'category')}),
                             'observed_at': row['observed_at'], 'url': row['url']})
    profile = a.get_profile()
    feedback = []
    for review in status(a, dataset)['feedback']:
        if review['use_in_briefs'] and review['format'] == fmt and review['creator'] == {k: profile[k] for k in ('niche', 'voice', 'goal')}:
            feedback.append({k: review[k] for k in ('candidate_title', 'decision', 'scores', 'notes', 'created_at')})
    brief = {'creator_feedback': feedback[:6], 'format': fmt, 'creator': {k: profile[k] for k in ('niche', 'voice', 'goal')},
             'constraints': {'production_brief': constraints, 'dataset': dataset,
                 'sample_data': dataset == 'demo',
                 'reference_scope': 'Same platform and format' if same_format else 'Mixed formats or no history; not comparable baseline',
                 'trend_availability': 'Current public sources included' if any(e['kind']=='trend' for e in evidence) else 'No current trend evidence'},
             'evidence': evidence, 'creator_memory': memory}
    try:
        context = brain.prepare(brief)
        prompt = brain.messages(context)
    except (ValueError, KeyError, TypeError):
        raise a.AppError('Source context could not be prepared. Check imported observation dates and profile fields.') from None
    run = {'id': a.uid(), 'dataset': dataset, 'format': fmt, 'kind': kind, 'model': model,
           'created_at': a.now(), 'status': 'prepared', 'context': context, 'prompt': prompt,
           'draft_evidence': a.evidence_for(selected), 'draft_ids': {}, 'result': None,
           'context_hash': a.digest(a.dumps(context)), 'brain_version': brain.VERSION}
    with a.connect() as db:
        db.execute('INSERT INTO brain_runs VALUES (?,?,?)', (run['id'], dataset, a.dumps(run)))
    return public(run)


def generate(a, payload):
    dataset = a.check_dataset(payload.get('dataset'))
    if payload.get('consent') is not True:
        raise a.AppError('Confirm sending the displayed context to the hosted model before generating.')
    if not os.environ.get('AI_GATEWAY_API_KEY'):
        raise a.AppError('Configure AI_GATEWAY_API_KEY in the backend environment, then restart. Never enter it in the browser.', 503)
    with a.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        run = load(a, db, payload.get('id'), dataset)
        if run['status'] == 'complete': return public(run)
        if run['status'] != 'prepared': raise a.AppError('This session was already attempted. Prepare a new brief to retry.', 409)
        age = (datetime.now(timezone.utc) - brain.stamp(run['created_at'])).total_seconds()
        if age > 900: raise a.AppError('The prepared context expired. Prepare it again before generation.', 409)
        run['status'] = 'running'
        save(a, db, run)
    try:
        result = brain.run_prepared(run['context'], run['model'], run['prompt'])
        # Persist only contract-valid model output; never treat a provider status as approval.
        result.update(brain.validate(result, run['context']))
    except Exception:
        with a.connect() as db:
            run['status'] = 'failed'
            save(a, db, run)
        raise a.AppError('The strategy model did not return a valid result. Check model access and credits, then prepare a new brief. No draft was created.', 502) from None
    run['result'], run['status'] = result, 'complete'
    with a.connect() as db: save(a, db, run)
    return public(run)


def draft(a, payload):
    dataset = a.check_dataset(payload.get('dataset'))
    with a.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        run = load(a, db, payload.get('id'), dataset)
        if run['status'] != 'complete': raise a.AppError('Generate a valid strategy before creating a draft.', 409)
        candidate = next((c for c in run['result']['candidates'] if c['id'] == payload.get('candidate_id')), None)
        if candidate is None: raise a.AppError('Choose a candidate from this session.')
        identity = candidate['id']
        if identity in run['draft_ids']:
            return json.loads(db.execute('SELECT data FROM drafts WHERE id=?', (run['draft_ids'][identity],)).fetchone()[0])
        e = candidate['experiment']
        body = '\n\n'.join([
            'Hook: ' + candidate['hook'], 'Audience value: ' + candidate['audience_value'],
            'Outline:\n' + '\n'.join(candidate['outline']), 'Draft excerpt:\n' + candidate['publishable_text'],
            'Creator fit: ' + candidate['why_this_creator'], 'Production: ' + candidate['production_plan'],
            'Hypothesis: ' + candidate['hypothesis'],
            f"Experiment: {e['change']}\nPrimary metric: {e['primary_metric']}\nWindow: {e['window_hours']}h\nComparison: {e['comparison']}",
            'Alternative explanations: ' + '; '.join(e['confounders']),
            'Limitations: ' + '; '.join(candidate['limitations']),
            'Missing data: ' + '; '.join(run['result']['missing_data']),
            'Sources:\n' + '\n'.join(a.dumps(s) for s in run['context']['evidence'] if s['id'] in candidate['evidence_ids']),
            'Sample workspace: synthetic evidence; not real creator results.' if dataset == 'demo' else 'Based on imported observations; verify source claims.'])
        if len(body) > 12000: raise a.AppError('This candidate is too long for the review editor. Shorten the generation brief and retry.')
        d = {'id': a.uid(), 'dataset': dataset, 'kind': run['kind'], 'title': candidate['title'][:300],
             'body': body, 'status': 'pending', 'revision': 1, 'created_at': a.now(), 'updated_at': a.now(),
             'generator': 'Brain studio / ' + run['model'], 'evidence': run['draft_evidence'], 'review_note': '',
             'brain_session': {'id': run['id'], 'candidate_id': identity, 'context_hash': run['context_hash'], 'version': run['brain_version']}}
        db.execute('INSERT INTO drafts VALUES (?,?,?,?)', (d['id'], dataset, 1, a.dumps(d)))
        a.add_event(db, d, 'created', {'actor': d['generator']})
        run['draft_ids'][identity] = d['id']
        save(a, db, run)
        return d


def feedback(a, payload):
    """Append human judgment separately from approval and measured performance."""
    dataset = a.check_dataset(payload.get('dataset'))
    scores = payload.get('scores')
    if not isinstance(scores, dict) or set(scores) != set(brain.RUBRIC) or any(type(v) is not int or not 1 <= v <= 5 for v in scores.values()):
        raise a.AppError('Rate every quality dimension from 1 to 5.')
    notes = payload.get('notes')
    if not isinstance(notes, str) or not 10 <= len(notes.strip()) <= 2000:
        raise a.AppError('Explain your rating in 10 to 2,000 characters.')
    if payload.get('decision') not in ('keep', 'revise', 'reject'):
        raise a.AppError('Choose keep, revise or reject.')
    if type(payload.get('use_in_briefs')) is not bool:
        raise a.AppError('Choose whether to reuse this feedback in future briefs.')
    with a.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        run = load(a, db, payload.get('id'), dataset)
        if run['status'] != 'complete': raise a.AppError('Generate ideas before reviewing them.', 409)
        candidate = next((c for c in run['result']['candidates'] if c['id'] == payload.get('candidate_id')), None)
        if candidate is None: raise a.AppError('Choose an existing candidate.')
        latest = db.execute('SELECT id FROM brain_feedback WHERE run_id=? AND candidate_id=? ORDER BY rowid DESC LIMIT 1', (run['id'], candidate['id'])).fetchone()
        if payload.get('previous_id') != (latest[0] if latest else None):
            raise a.AppError('Feedback changed. Reload this workspace before saving.', 409)
        review = {'id': a.uid(), 'dataset': dataset, 'run_id': run['id'], 'candidate_id': candidate['id'],
                  'candidate_title': candidate['title'], 'format': run['format'], 'creator': run['context']['creator'],
                  'model': run['model'], 'brain_version': run['brain_version'], 'context_hash': run['context_hash'],
                  'created_at': a.now(), 'scores': scores, 'notes': notes.strip(), 'decision': payload['decision'],
                  'use_in_briefs': payload['use_in_briefs'], 'previous_id': payload.get('previous_id'),
                  'kind': 'human_preference_not_performance'}
        db.execute('INSERT INTO brain_feedback VALUES (?,?,?,?,?)', (review['id'], dataset, run['id'], candidate['id'], a.dumps(review)))
    return review
