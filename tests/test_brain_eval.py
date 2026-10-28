import copy
import unittest
from server import brain, brain_eval
from test_brain import answer

class BlindReviewTests(unittest.TestCase):
    def reports(self):
        context=brain.prepare({'format':'video','creator':{'niche':'Cooking','voice':'Plain','goal':'Teach'},'evidence':[]})
        output=answer()
        for c in output['candidates']: c['evidence_ids']=[]
        output['brain_version']=brain.VERSION
        return [{'model':m,'live':True,'results':[{'case_id':'one','context':copy.deepcopy(context),'output':copy.deepcopy(output),'expected_review':'Specific advice','contract_check':'passed'}]} for m in brain.MODELS.values()]
    def test_blind_package_omits_model_metadata_and_blank_is_not_pass(self):
        review,mapping=brain_eval.package(self.reports())
        self.assertEqual(len(review['items']),2)
        self.assertNotIn('model',review['items'][0])
        self.assertNotIn('brain_version',review['items'][0]['output'])
        result=brain_eval.summarize(review,mapping)
        for row in result['models'].values():
            self.assertEqual(row['reviewed'],0)
            self.assertFalse(row['meets_development_target'])
            self.assertIsNone(row['medians']['grounding'])
    def test_human_scores_and_fabrication_gate(self):
        review,mapping=brain_eval.package(self.reports())
        for item in review['items']:
            item.update(scores={k:4 for k in brain.RUBRIC},notes='Clear and feasible; evidence checked.',unsupported_claim=False)
        self.assertTrue(all(g['meets_development_target'] for g in brain_eval.summarize(review,mapping)['models'].values()))
        review['items'][0]['unsupported_claim']=True
        self.assertFalse(brain_eval.summarize(review,mapping)['models'][mapping[review['items'][0]['id']]['model']]['meets_development_target'])
    def test_mismatched_context_offline_missing_case_rejected(self):
        for mode in ('context','offline','case','version'):
            reports=copy.deepcopy(self.reports())
            if mode=='context': reports[0]['results'][0]['context']['creator']['niche']='Other'
            if mode=='offline': reports[0]['live']=False
            if mode=='case': reports[0]['results']=[]
            if mode=='version': reports[0]['results'][0]['output']['brain_version']='old'
            with self.subTest(mode=mode),self.assertRaises(ValueError): brain_eval.package(reports)
    def test_edited_output_or_duplicate_review_rejected(self):
        review,mapping=brain_eval.package(self.reports())
        changed=copy.deepcopy(review)
        changed['items'][0]['output']['selection_reason']='Tampered'
        with self.assertRaises(ValueError): brain_eval.summarize(changed,mapping)
        review['items'].append(review['items'][0])
        with self.assertRaises(ValueError): brain_eval.summarize(review,mapping)
