import { useState } from 'react';
import { api } from './api';
import type { Dataset } from './types';

export type Feedback = {id:string;run_id:string;candidate_id:string;scores:Record<string,number>;notes:string;decision:string;use_in_briefs:boolean};
const dimensions = {grounding:'Evidence supports the claims',creator_fit:'Fits your audience and constraints',originality:'Distinct and useful concept',execution_detail:'Clear enough to produce',measurement:'A meaningful, fair test',voice:'Sounds like you'};

export function BrainFeedback({dataset,runId,candidateId,saved,onSave}:{dataset:Dataset;runId:string;candidateId:string;saved?:Feedback;onSave:(review:Feedback)=>void}) {
  const [scores,setScores]=useState<Record<string,number>>(saved?.scores||{});
  const [notes,setNotes]=useState(saved?.notes||'');
  const [decision,setDecision]=useState(saved?.decision||'revise');
  const [reuse,setReuse]=useState(saved?.use_in_briefs||false);
  const [busy,setBusy]=useState(false),[error,setError]=useState('');
  async function submit(){setBusy(true);setError('');try{
    const review=await api<Feedback>('/brain/feedback',{dataset,id:runId,candidate_id:candidateId,scores,notes,decision,use_in_briefs:reuse,previous_id:saved?.id||null});
    onSave(review);
  }catch(e){setError((e as Error).message)}finally{setBusy(false)}}
  return <details className="brain-feedback"><summary>{saved?'Edit saved quality review':'Rate this direction'}</summary>
    <p className="fine-print">1 = unusable · 3 = substantial edits · 5 = ready with minor edits. This review does not approve publication.</p>
    {Object.entries(dimensions).map(([key,label])=><label key={key}>{label}<select value={scores[key]||''} disabled={busy} onChange={e=>setScores({...scores,[key]:Number(e.target.value)})}><option value="" disabled>Choose a rating</option>{[1,2,3,4,5].map(n=><option key={n} value={n}>{n}</option>)}</select></label>)}
    <label>Your verdict<select value={decision} disabled={busy} onChange={e=>setDecision(e.target.value)}><option value="keep">Keep</option><option value="revise">Revise</option><option value="reject">Reject</option></select></label>
    <label>What worked, and what should change?<textarea value={notes} disabled={busy} maxLength={2000} onChange={e=>setNotes(e.target.value)} placeholder="Point to a specific claim, hook or production choice."/></label>
    <label className="model-toggle"><input type="checkbox" disabled={busy} checked={reuse} onChange={e=>setReuse(e.target.checked)}/><span>Include this feedback in future briefs for this creator and format. It will appear in the context preview before any model call.</span></label>
    {error&&<p role="alert" className="form-error">{error}</p>}
    {saved&&<p role="status" className="fine-print">Review saved. {saved.use_in_briefs?'Available to future briefs.':'Excluded from future briefs.'}</p>}
    <button className="button secondary" disabled={busy||Object.keys(scores).length!==6||notes.trim().length<10} onClick={()=>void submit()}>{busy?'Saving…':'Save quality review'}</button>
  </details>;
}
