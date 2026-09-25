import React, {useEffect, useState} from 'react';
import api from '../../services/api';
import {scoringError} from './ScoringConfiguration';

export default function ResultReview({classArm,term}) {
  const [subjects,setSubjects]=useState([]), [subject,setSubject]=useState(''), [sheet,setSheet]=useState(null);
  const [error,setError]=useState(''), [busy,setBusy]=useState(false), [reason,setReason]=useState(''), [revision,setRevision]=useState(0);
  useEffect(()=>{api.get('/api/subjects/').then(r=>setSubjects(r.data.results ?? r.data)).catch(e=>setError(scoringError(e)));},[]);
  useEffect(()=>{
    let active=true;setSheet(null);setError('');
    if(classArm && term && subject) api.get(`/api/gradebook/entries/sheet/?class_arm=${classArm}&term=${term}&subject=${subject}`).then(r=>{if(active)setSheet(r.data);}).catch(e=>{if(active)setError(scoringError(e));});
    return ()=>{active=false;};
  },[classArm,term,subject,revision]);
  async function act(action) {
    if(action==='publish' && !window.confirm('Publish these reviewed scores? Linked parents and students will be able to view them.'))return;
    if(action==='reopen' && !window.confirm('Reopen these scores for correction? They will be hidden from parents and students until reviewed and published again.'))return;
    setBusy(true);setError('');
    try {await api.post(`/api/gradebook/entries/${action}/`,action==='reopen'?{entry_ids:sheet.entries.map(e=>e.id),reason}:{class_arm:Number(classArm),term:Number(term),subject:Number(subject)});setRevision(r=>r+1);}
    catch(e){setError(scoringError(e));}finally{setBusy(false);}
  }
  const allState=state=>sheet?.entries.length && sheet.students.every(s=>sheet.entries.some(e=>e.student===s.user)) && sheet.entries.every(e=>!e.is_published && e.review_state===state);
  return <section className="res-card" style={{padding:16,marginBottom:20}} aria-label="Result review"><h2>Review and publish scores</h2><p>Select a class and term above, then a subject. Check every student before approving.</p>
    <label>Review subject<select className="res-select" value={subject} onChange={e=>setSubject(e.target.value)}>{[<option key="" value="">Choose subject</option>,...subjects.map(s=><option key={s.id} value={s.id}>{s.name}</option>)]}</select></label>
    {error && <p role="alert">{error}</p>}
    {sheet && <><div style={{overflowX:'auto'}}><table className="res-table"><thead><tr><th>Student</th><th>Assessment scores</th><th>Total</th><th>Grade</th><th>Status</th></tr></thead><tbody>{sheet.students.map(s=>{const row=sheet.entries.find(e=>e.student===s.user);return <tr key={s.user}><td>{s.full_name}</td><td>{sheet.configuration.components.map(c=><div key={c.key}>{c.name}: {row?.policy ? row.component_scores[c.key] ?? 'Missing' : row?.[c.key] ?? 'Missing'} / {c.maximum}</div>)}</td><td>{row?.total_score ?? '—'}</td><td>{row?.grade || 'Incomplete'}</td><td>{row?.is_published?'Published / locked':row?.review_state || 'No scores'}</td></tr>;})}</tbody></table></div>
      <button className="res-btn res-btn--navy" disabled={busy || !allState('submitted')} onClick={()=>act('approve')}>Approve reviewed scores</button>
      <button className="res-btn res-btn--navy" disabled={busy || !allState('approved')} onClick={()=>act('publish')}>Publish approved scores</button>
      <label>Reason for correction<textarea value={reason} onChange={e=>setReason(e.target.value)} /></label>
      <button className="res-btn res-btn--navy" disabled={busy || reason.trim().length<10 || !sheet.entries.length} onClick={()=>act('reopen')}>Reopen for correction</button>
    </>}
  </section>;
}
