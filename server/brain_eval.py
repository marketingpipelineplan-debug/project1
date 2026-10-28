"""Offline blind review packages. Never calls models or changes their configuration."""
import hashlib
import json
import random
import statistics
import uuid
from . import brain


def fingerprint(context):
    return hashlib.sha256(json.dumps({k:v for k,v in context.items() if k != 'as_of'}, sort_keys=True).encode()).hexdigest()


def package(reports):
    if len(reports) < 2 or len({r['model'] for r in reports}) != len(reports):
        raise ValueError('Supply reports from at least two different models')
    cases = None
    items, mapping = [], {}
    for report in reports:
        rows = report['results']
        ids = {r['case_id'] for r in rows}
        if not rows or len(ids) != len(rows) or (cases is not None and cases != ids):
            raise ValueError('Reports must cover the same unique cases')
        cases = ids
        if report.get('live') is not True: raise ValueError('Offline prompt previews cannot be scored as model answers')
        for row in rows:
            if row.get('contract_check') != 'passed' or not row.get('context'):
                raise ValueError('Every case needs a successful output and frozen context')
            output = brain.validate(row['output'], row['context'])
            output.pop('status'); output.pop('validation')
            identity = uuid.uuid4().hex
            items.append({'id':identity, 'case_id':row['case_id'], 'context':row['context'],
                          'review_focus':row['expected_review'], 'output':output,
                          'scores':{k:None for k in brain.RUBRIC}, 'notes':'', 'unsupported_claim':None})
            mapping[identity] = {'model':report['model'], 'case_id':row['case_id'],
                'context_hash':fingerprint(row['context']), 'version':row['output'].get('brain_version'),
                'output_hash':hashlib.sha256(json.dumps(output, sort_keys=True).encode()).hexdigest()}
    for case in cases:
        entries = [v for v in mapping.values() if v['case_id']==case]
        if len({(e['context_hash'], e['version']) for e in entries}) != 1:
            raise ValueError('Compare models using identical context and prompt versions')
    random.SystemRandom().shuffle(items)
    return {'rubric':brain.RUBRIC, 'anchors':{'1':'Unusable','3':'Needs substantial edits','5':'Ready with minor edits'},
            'items':items}, mapping


def summarize(review, mapping):
    items=review['items']
    if len(items)!=len(mapping) or {i['id'] for i in items}!=set(mapping):
        raise ValueError('Review items must exactly match the private mapping')
    groups={}
    for item in items:
        source=mapping[item['id']]
        if (fingerprint(item['context']) != source['context_hash'] or
            hashlib.sha256(json.dumps(item['output'], sort_keys=True).encode()).hexdigest()!=source['output_hash'] or
            item['case_id']!=source['case_id']):
            raise ValueError('Frozen review context or output was changed')
        group=groups.setdefault(source['model'], {'expected':0,'reviewed':0,'unsupported_claims':0,'scores':{k:[] for k in brain.RUBRIC}})
        group['expected']+=1
        scores=item.get('scores',{})
        complete=(set(scores)==set(brain.RUBRIC) and all(type(v) is int and 1<=v<=5 for v in scores.values())
                  and type(item.get('unsupported_claim')) is bool and isinstance(item.get('notes'),str) and len(item['notes'].strip())>=10)
        if not complete: continue
        group['reviewed']+=1
        group['unsupported_claims']+=int(item['unsupported_claim'])
        for k,v in scores.items(): group['scores'][k].append(v)
    for group in groups.values():
        group['medians']={k:statistics.median(v) if v else None for k,v in group.pop('scores').items()}
        group['meets_development_target']=(group['reviewed']==group['expected'] and group['unsupported_claims']==0 and all(v is not None and v>=4 for v in group['medians'].values()))
    return {'models':groups, 'production_quality_validated':False,
            'note':'Synthetic development cases only. No automatic model promotion or weight training.'}
