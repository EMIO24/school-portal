import React, { useEffect, useState } from 'react';
import api from '../../services/api';
import '../admin/AssessmentCentre.css';

const rows = data => data?.results ?? data ?? [];
const errorText = e => e?.response?.data?.detail || (e?.response?.data ? JSON.stringify(e.response.data) : 'Connection failed. Your answer remains here; retry when online.');

export default function MyAssignments() {
  const [assignments,setAssignments]=useState([]);
  const [selected,setSelected]=useState(null);
  const [draft,setDraft]=useState({text:'',answers:{}});
  const [submission,setSubmission]=useState(null);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [notice,setNotice]=useState('');
  useEffect(()=>{
    api.get('/api/cbt/assignments/').then(({data})=>setAssignments(rows(data))).catch(e=>setError(errorText(e)));
  },[]);
  useEffect(()=>{
    if (!selected) return;
    setError('');setNotice('');
    api.get(`/api/cbt/assignments/${selected.id}/my-submission/`)
      .then(({data})=>{setSubmission(data);setDraft({text:data.text||'',answers:data.answers||{}});})
      .catch(e=>setError(errorText(e)));
  },[selected]);
  const save = async () => {
    setBusy(true);setError('');setNotice('');
    try {await api.post(`/api/cbt/assignments/${selected.id}/save-response/`,draft);setNotice('Response saved to the school server.');return true;}
    catch(e){setError(errorText(e));return false;}
    finally{setBusy(false);}
  };
  const submit = async () => {
    if (!window.confirm('Submit this assignment? You cannot change it afterward.')) return;
    setBusy(true);setError('');
    try {
      await api.post(`/api/cbt/assignments/${selected.id}/save-response/`,draft);
      await api.post(`/api/cbt/assignments/${selected.id}/submit/`);
      const {data}=await api.get(`/api/cbt/assignments/${selected.id}/my-submission/`);
      setSubmission(data);setNotice('Assignment submitted.');
    } catch(e){setError(errorText(e));}
    finally{setBusy(false);}
  };
  const editable=selected && !submission?.submitted_at && selected.status==='published' && new Date(selected.due_at)>new Date();
  return <main className="assessment-page"><header><h1>My assignments</h1><p>Save your response while working. The school server confirms each save.</p></header>
    {error && <p role="alert" className="assessment-error">{error}</p>}{notice && <p role="status">{notice}</p>}
    <section className="assessment-card"><h2>Available work</h2><div className="assessment-list">{assignments.map(a=><button key={a.id} className={selected?.id===a.id?'selected':''} onClick={()=>setSelected(a)}>{a.title} · {a.kind} · due {new Date(a.due_at).toLocaleString()}</button>)}</div>{!assignments.length && <p>No assignments are available for your class.</p>}</section>
    {selected && <section className="assessment-card"><h2>{selected.title}</h2><p>{selected.instructions}</p><p>Due {new Date(selected.due_at).toLocaleString()} · {selected.maximum} marks</p>
      <p>Status: {submission?.status==='submitted'?'Submitted':editable?'In progress':'Closed'}</p>
      {(selected.question_snapshot||[]).map(q=><div key={q.id} className="assessment-question"><strong>{q.question_text}</strong>
        {q.question_type==='mcq' || q.question_type==='true_false' ? <fieldset><legend>Choose answer</legend>{(q.options||[]).map(option=><label key={option.id}><input type="radio" name={`question-${q.id}`} disabled={!editable} checked={draft.answers[String(q.id)]===option.id} onChange={()=>setDraft(d=>({...d,answers:{...d.answers,[q.id]:option.id}}))}/>{option.text}</label>)}</fieldset>
          : <label>Your answer<textarea disabled={!editable} value={draft.answers[String(q.id)]||''} onChange={e=>setDraft(d=>({...d,answers:{...d.answers,[q.id]:e.target.value}}))}/></label>}
      </div>)}
      <label>Written response<textarea disabled={!editable} rows="8" maxLength="20000" value={draft.text} onChange={e=>setDraft({...draft,text:e.target.value})}/></label>
      {editable && <div className="assessment-actions"><button disabled={busy} onClick={save}>Save response</button><button disabled={busy} onClick={submit}>Submit assignment</button></div>}
      {submission?.score!==null && submission?.score!==undefined && <p>Released score: {submission.score} / {selected.maximum}</p>}
      {submission?.feedback && <p>Teacher feedback: {submission.feedback}</p>}
    </section>}
  </main>;
}
