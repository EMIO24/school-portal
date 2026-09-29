import React, { useEffect, useState } from 'react';
import api from '../../services/api';
import './AssessmentCentre.css';

const rows = value => value?.results ?? value ?? [];
const errorText = e => e?.response?.data?.detail || (e?.response?.data ? JSON.stringify(e.response.data) : 'Connection failed. Retry when online.');

export default function OnlineAssignments() {
  const [terms, setTerms] = useState([]);
  const [arms, setArms] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [topics, setTopics] = useState([]);
  const [questions, setQuestions] = useState([]);
  const [components, setComponents] = useState([]);
  const [assignments, setAssignments] = useState([]);
  const [selected, setSelected] = useState(null);
  const [submissions, setSubmissions] = useState([]);
  const [form, setForm] = useState({term:'',class_arm:'',subject:'',curriculum_topic:'',title:'',instructions:'',due_at:'',maximum:10,kind:'practice',component_key:'',question_ids:[]});
  const [marks, setMarks] = useState({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const refresh = () => api.get('/api/cbt/assignments/').then(({data})=>setAssignments(rows(data)));
  useEffect(()=>{
    Promise.all([api.get('/api/terms/'),api.get('/api/class-arms/'),api.get('/api/subjects/')])
      .then(([t,a,s])=>{setTerms(rows(t.data));setArms(rows(a.data));setSubjects(rows(s.data));})
      .catch(e=>setError(errorText(e)));
    refresh().catch(e=>setError(errorText(e)));
  },[]);
  const level = arms.find(a=>String(a.id)===String(form.class_arm))?.class_level;
  useEffect(()=>{
    if (!form.term || !form.subject || !level) {setTopics([]);setQuestions([]);return;}
    Promise.all([
      api.get('/api/cbt/questions/curriculum-topics/',{params:{term:form.term,subject:form.subject,class_level:level}}),
      api.get('/api/cbt/questions/',{params:{subject:form.subject,class_level:level,is_active:true}}),
      api.get('/api/gradebook/configuration/',{params:{term:form.term}}),
    ]).then(([t,q,c])=>{setTopics(rows(t.data));setQuestions(rows(q.data));setComponents(c.data.components||[]);})
      .catch(e=>setError(errorText(e)));
  },[form.term,form.subject,level]);
  useEffect(()=>{
    if (!selected) {setSubmissions([]);return;}
    api.get(`/api/cbt/assignments/${selected.id}/submissions/`).then(({data})=>setSubmissions(rows(data)))
      .catch(e=>setError(errorText(e)));
  },[selected]);
  const act = async (call, done) => {
    setBusy(true);setError('');setNotice('');
    try {const {data}=await call();setNotice(done);await refresh();return data;}
    catch(e){setError(errorText(e));return null;}
    finally{setBusy(false);}
  };
  const create = async event => {
    event.preventDefault();
    const payload = {...form,curriculum_topic:form.curriculum_topic || null,
      component_key:form.kind==='graded'?form.component_key:'',due_at:new Date(form.due_at).toISOString()};
    const created = await act(()=>api.post('/api/cbt/assignments/',payload),'Assignment draft created.');
    if(created) setSelected(created);
  };
  const publish = async()=>{
    const result=await act(()=>api.post(`/api/cbt/assignments/${selected.id}/publish/`),'Assignment published.');
    if(result) setSelected({...selected,...result});
  };
  const mark = async row => {
    const value=marks[row.id] || {score:row.score ?? '',feedback:row.feedback ?? ''};
    const result=await act(()=>api.post(`/api/cbt/assignments/${selected.id}/mark/`,{submission_id:row.id,...value}),'Mark released.');
    if(result) {
      const {data}=await api.get(`/api/cbt/assignments/${selected.id}/submissions/`);
      setSubmissions(rows(data));
    }
  };
  return <main className="assessment-page"><header><h1>Online assignments</h1><p>Practice work stays separate from the gradebook. Graded work fills one configured component after release.</p></header>
    {error && <p role="alert" className="assessment-error">{error}</p>}{notice && <p role="status">{notice}</p>}
    <form className="assessment-card" onSubmit={create}><h2>New assignment</h2>
      <div className="assessment-grid">
        <label>Term<select required value={form.term} onChange={e=>setForm({...form,term:e.target.value})}><option value="">Choose term</option>{terms.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select></label>
        <label>Class<select required value={form.class_arm} onChange={e=>setForm({...form,class_arm:e.target.value})}><option value="">Choose class</option>{arms.map(x=><option key={x.id} value={x.id}>{x.full_name||x.name}</option>)}</select></label>
        <label>Subject<select required value={form.subject} onChange={e=>setForm({...form,subject:e.target.value})}><option value="">Choose subject</option>{subjects.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select></label>
        <label>Scheme topic<select value={form.curriculum_topic} onChange={e=>setForm({...form,curriculum_topic:e.target.value})}><option value="">No topic link</option>{topics.map(x=><option key={x.id} value={x.id}>{x.title}</option>)}</select></label>
        <label>Due date and time<input required type="datetime-local" value={form.due_at} onChange={e=>setForm({...form,due_at:e.target.value})}/></label>
        <label>Maximum mark<input required type="number" min="0.01" step="0.01" value={form.maximum} onChange={e=>setForm({...form,maximum:e.target.value})}/></label>
        <label>Type<select value={form.kind} onChange={e=>setForm({...form,kind:e.target.value,component_key:''})}><option value="practice">Practice</option><option value="graded">Graded</option></select></label>
        {form.kind==='graded' && <label>Gradebook component<select required value={form.component_key} onChange={e=>setForm({...form,component_key:e.target.value})}><option value="">Choose component</option>{components.map(c=><option key={c.key} value={c.key}>{c.name} / {c.maximum}</option>)}</select></label>}
      </div>
      <label>Title<input required maxLength="200" value={form.title} onChange={e=>setForm({...form,title:e.target.value})}/></label>
      <label>Instructions<textarea value={form.instructions} onChange={e=>setForm({...form,instructions:e.target.value})}/></label>
      {!!questions.length && <fieldset><legend>Question bank questions (optional)</legend><div className="assessment-question-list">{questions.map(q=><label key={q.id}><input type="checkbox" checked={form.question_ids.includes(q.id)} onChange={e=>setForm(f=>({...f,question_ids:e.target.checked?[...f.question_ids,q.id]:f.question_ids.filter(id=>id!==q.id)}))}/>{q.question_text}</label>)}</div></fieldset>}
      <button disabled={busy}>Save draft</button>
    </form>
    <section className="assessment-card"><h2>Assignments</h2><div className="assessment-list">{assignments.map(a=><button key={a.id} className={selected?.id===a.id?'selected':''} onClick={()=>setSelected(a)}>{a.title} · {a.kind} · {a.status}</button>)}</div>{!assignments.length && <p>No assignments yet.</p>}</section>
    {selected && <section className="assessment-card"><h2>{selected.title}</h2><p>{selected.kind} · {selected.status} · Due {new Date(selected.due_at).toLocaleString()}</p>
      {selected.status==='draft' && <button disabled={busy} onClick={publish}>Publish to students</button>}
      <h3>Student submissions</h3>{!submissions.length && <p>No submissions yet.</p>}
      <div className="assessment-list">{submissions.map(row=><article key={row.id} className="assessment-submission"><strong>Student #{row.student} · {row.status}</strong><p>{row.text}</p>
        {Object.entries(row.answers||{}).map(([id,value])=><p key={id}>Question {id}: {value}</p>)}
        {row.status==='submitted' && <><label>Score / {selected.maximum}<input type="number" min="0" max={selected.maximum} step="0.01" value={marks[row.id]?.score ?? row.score ?? ''} onChange={e=>setMarks(m=>({...m,[row.id]:{...m[row.id],score:e.target.value}}))}/></label>
          <label>Feedback<textarea value={marks[row.id]?.feedback ?? row.feedback ?? ''} onChange={e=>setMarks(m=>({...m,[row.id]:{...m[row.id],feedback:e.target.value}}))}/></label>
          <button disabled={busy || !!row.released_at} onClick={()=>mark(row)}>{row.released_at?'Mark released':'Release mark'}</button></>}
      </article>)}</div>
    </section>}
  </main>;
}
