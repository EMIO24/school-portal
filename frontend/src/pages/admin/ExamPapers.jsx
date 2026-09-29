import React, { useEffect, useState } from 'react';
import api from '../../services/api';
import './AssessmentCentre.css';

const rows = data => data?.results ?? data ?? [];
const message = error => {
  const data = error?.response?.data;
  return typeof data?.detail === 'string' ? data.detail : data ? JSON.stringify(data) : 'Connection failed. Retry when online.';
};

export default function ExamPapers() {
  const [terms, setTerms] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [levels, setLevels] = useState([]);
  const [papers, setPapers] = useState([]);
  const [modes, setModes] = useState([]);
  const [topics, setTopics] = useState([]);
  const [questions, setQuestions] = useState([]);
  const [scope, setScope] = useState({term:'', subject:'', class_level:''});
  const [form, setForm] = useState({title:'', instructions:'', duration_minutes:60, blueprint:[]});
  const [selected, setSelected] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const refresh = async () => {
    const [p, m] = await Promise.all([api.get('/api/cbt/papers/'), api.get('/api/cbt/modes/')]);
    setPapers(rows(p.data)); setModes(rows(m.data));
  };
  useEffect(() => {
    Promise.all([api.get('/api/terms/'), api.get('/api/subjects/'), api.get('/api/class-levels/')])
      .then(([t,s,l]) => {setTerms(rows(t.data));setSubjects(rows(s.data));setLevels(rows(l.data));})
      .catch(e => setError(message(e)));
    refresh().catch(e => setError(message(e)));
  }, []);
  useEffect(() => {
    if (!scope.term || !scope.subject || !scope.class_level) {setTopics([]);return;}
    api.get('/api/cbt/questions/curriculum-topics/', {params:scope})
      .then(({data}) => setTopics(rows(data))).catch(e => setError(message(e)));
  }, [scope]);
  useEffect(() => {
    if (!selected) return;
    api.get('/api/cbt/questions/', {params:{subject:selected.subject, class_level:selected.class_level, is_active:true}})
      .then(({data}) => setQuestions(rows(data))).catch(e => setError(message(e)));
  }, [selected]);

  const act = async (request, success) => {
    setBusy(true);setError('');setNotice('');
    try { const result = await request(); setNotice(success); await refresh(); return result?.data; }
    catch (e) {setError(message(e));return null;}
    finally {setBusy(false);}
  };
  const mode = modes.find(m => String(m.term) === scope.term && String(m.subject) === scope.subject && String(m.class_level) === scope.class_level);
  const saveMode = () => act(() => mode
    ? api.patch(`/api/cbt/modes/${mode.id}/`, {mode:'paper'})
    : api.post('/api/cbt/modes/', {...scope, mode:'paper'}), 'Paper assessment selected.');
  const addTopic = id => {
    if (!id || form.blueprint.some(row => String(row.topic_id) === String(id))) return;
    setForm(f => ({...f, blueprint:[...f.blueprint,{topic_id:Number(id),objective:1,theory:0}]}));
  };
  const updateRow = (index, key, value) => setForm(f => ({...f, blueprint:f.blueprint.map((r,i) => i === index ? {...r,[key]:Number(value)} : r)}));
  const create = async event => {
    event.preventDefault();
    const paper = await act(() => api.post('/api/cbt/papers/', {...scope,...form}), 'Draft paper saved.');
    if (paper) setSelected(paper);
  };
  const action = async (name, data) => {
    const paper = await act(() => api.post(`/api/cbt/papers/${selected.id}/${name}/`, data), `${name} complete.`);
    if (paper?.question_snapshot) setSelected(paper);
    else if (paper) setSelected({...selected,...paper});
  };
  const download = async marking => {
    setBusy(true);setError('');
    try {
      const response = await api.get(`/api/cbt/papers/${selected.id}/pdf/`, {params:{marking:marking ? 1 : 0}, responseType:'blob'});
      const url = URL.createObjectURL(response.data);
      const link = document.createElement('a');link.href=url;link.download=`${selected.title}${marking ? '-marking' : ''}.pdf`;link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {setError(message(e));} finally {setBusy(false);}
  };

  return <main className="assessment-page">
    <header><h1>Exam papers</h1><p>Build papers from this term’s scheme topics and reusable question bank.</p></header>
    {error && <p role="alert" className="assessment-error">{error}</p>}
    {notice && <p role="status">{notice}</p>}
    <section className="assessment-card"><h2>Subject assessment mode</h2>
      <div className="assessment-grid">
        <label>Term<select value={scope.term} onChange={e => setScope({...scope,term:e.target.value})}><option value="">Choose term</option>{terms.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select></label>
        <label>Subject<select value={scope.subject} onChange={e => setScope({...scope,subject:e.target.value})}><option value="">Choose subject</option>{subjects.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select></label>
        <label>Class level<select value={scope.class_level} onChange={e => setScope({...scope,class_level:e.target.value})}><option value="">Choose level</option>{levels.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select></label>
      </div>
      <p>Current mode: {mode?.mode || 'CBT (default)'}</p>
      <button disabled={busy || !scope.term || !scope.subject || !scope.class_level || mode?.mode === 'paper'} onClick={saveMode}>Use paper assessment</button>
    </section>
    {mode?.mode === 'paper' && <form className="assessment-card" onSubmit={create}><h2>New paper draft</h2>
      <label>Title<input required maxLength={200} value={form.title} onChange={e=>setForm({...form,title:e.target.value})}/></label>
      <label>Instructions<textarea value={form.instructions} onChange={e=>setForm({...form,instructions:e.target.value})}/></label>
      <label>Duration in minutes<input required type="number" min="1" value={form.duration_minutes} onChange={e=>setForm({...form,duration_minutes:Number(e.target.value)})}/></label>
      <label>Add scheme topic<select value="" onChange={e=>addTopic(e.target.value)}><option value="">Choose topic</option>{topics.map(t=><option key={t.id} value={t.id}>{t.title}</option>)}</select></label>
      {form.blueprint.map((row,i)=><div className="assessment-grid" key={row.topic_id}>
        <strong>{topics.find(t=>t.id===row.topic_id)?.title || 'Topic'}</strong>
        <label>Objective<input type="number" min="0" max="100" value={row.objective} onChange={e=>updateRow(i,'objective',e.target.value)}/></label>
        <label>Theory<input type="number" min="0" max="100" value={row.theory} onChange={e=>updateRow(i,'theory',e.target.value)}/></label>
        <button type="button" onClick={()=>setForm(f=>({...f,blueprint:f.blueprint.filter((_,j)=>j!==i)}))}>Remove</button>
      </div>)}
      <button disabled={busy || !form.blueprint.length}>Save draft</button>
    </form>}
    <section className="assessment-card"><h2>Saved papers</h2>
      {!papers.length && <p>No papers have been drafted.</p>}
      <div className="assessment-list">{papers.map(p=><button key={p.id} className={selected?.id===p.id?'selected':''} onClick={()=>setSelected(p)}>{p.title} · {p.status}</button>)}</div>
    </section>
    {selected && <section className="assessment-card"><h2>{selected.title} · {selected.status}</h2>
      <div className="assessment-actions">
        {selected.status==='draft' && <button disabled={busy} onClick={()=>action('generate')}>Generate questions</button>}
        {selected.status==='draft' && !!selected.question_snapshot?.length && <button disabled={busy} onClick={()=>action('submit')}>Submit for approval</button>}
        {selected.status==='submitted' && <button disabled={busy} onClick={()=>action('approve')}>Approve (school admin)</button>}
        {!!selected.question_snapshot?.length && <><button disabled={busy} onClick={()=>download(false)}>Download paper PDF</button><button disabled={busy} onClick={()=>download(true)}>Download marking copy</button></>}
      </div>
      {selected.status!=='approved' && <p role="note">Draft papers are marked DRAFT in the PDF.</p>}
      <ol>{(selected.question_snapshot||[]).map((q,i)=><li key={`${q.id}-${i}`}>
        <p>{q.question_text} ({q.section}, {q.marks} marks)</p>
        {selected.status==='draft' && <label>Replace from same topic and section<select value="" onChange={e=>{if(e.target.value) action('replace',{index:i,question_id:Number(e.target.value)});}}><option value="">Choose another question</option>
          {questions.filter(candidate=>candidate.curriculum_topic===q.blueprint_topic_id && candidate.id!==q.id &&
            !selected.question_snapshot.some(used=>used.id===candidate.id) &&
            (candidate.question_type==='theory')===(q.section==='theory')).map(candidate=><option key={candidate.id} value={candidate.id}>{candidate.question_text.slice(0,80)}</option>)}
        </select></label>}
      </li>)}</ol>
    </section>}
  </main>;
}
