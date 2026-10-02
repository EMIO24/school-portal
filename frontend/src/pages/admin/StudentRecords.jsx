import React,{useEffect,useState} from 'react';
import {Link,useParams} from 'react-router-dom';
import api from '../../services/api';
import './AssessmentCentre.css';

const err=e=>e?.response?.data?.detail||JSON.stringify(e?.response?.data||{})||'Request failed.';

export default function StudentRecords(){
  const {id}=useParams();const [student,setStudent]=useState(null),[records,setRecords]=useState([]),[form,setForm]=useState({kind:'note',title:'',details:'',document_url:'',effective_date:new Date().toISOString().slice(0,10),supersedes:''}),[error,setError]=useState(''),[notice,setNotice]=useState(''),[busy,setBusy]=useState(false);
  const load=async()=>{try{const [s,r]=await Promise.all([api.get(`/api/students/${id}/`),api.get(`/api/operations/student-records/${id}/`)]);setStudent(s.data);setRecords(r.data||[]);}catch(e){setError(err(e));}};
  useEffect(()=>{load();},[id]);
  const create=async e=>{e.preventDefault();setBusy(true);setError('');try{await api.post(`/api/operations/student-records/${id}/`,{...form,supersedes:form.supersedes?Number(form.supersedes):null});setForm({...form,title:'',details:'',document_url:'',supersedes:''});setNotice('Official record entry added.');await load();}catch(e){setError(err(e));}finally{setBusy(false);}};
  return <main className="assessment-page"><header><h1>Official student record</h1><p>{student?.full_name||'Student'} · append-only institutional notes and document references.</p><Link to={`/admin/students/${id}`}>Back to profile</Link></header>
    {error&&<p role="alert" className="assessment-error">{error}</p>}{notice&&<p role="status">{notice}</p>}
    <form className="assessment-card" onSubmit={create}><h2>Add record entry</h2><div className="assessment-grid">
      <label>Type<select value={form.kind} onChange={e=>setForm({...form,kind:e.target.value})}>{['identity','guardian','enrollment','document','note'].map(x=><option key={x}>{x}</option>)}</select></label>
      <label>Effective date<input required type="date" value={form.effective_date} onChange={e=>setForm({...form,effective_date:e.target.value})}/></label>
      <label>Corrects earlier entry<select value={form.supersedes} onChange={e=>setForm({...form,supersedes:e.target.value})}><option value="">No</option>{records.map(r=><option key={r.id} value={r.id}>#{r.id} {r.title}</option>)}</select></label>
    </div><label>Title<input required maxLength="180" value={form.title} onChange={e=>setForm({...form,title:e.target.value})}/></label><label>Details<textarea value={form.details} onChange={e=>setForm({...form,details:e.target.value})}/></label><label>Document URL<input type="url" value={form.document_url} onChange={e=>setForm({...form,document_url:e.target.value})}/></label><button disabled={busy}>Add entry</button></form>
    <section className="assessment-card"><h2>Record history</h2>{!records.length&&<p>No official record entries yet.</p>}{records.map(r=><article key={r.id} className="assessment-submission"><strong>{r.effective_date} · {r.title}</strong><p>{r.kind}{r.supersedes?` · correction of #${r.supersedes}`:''}</p><p>{r.details}</p>{r.document_url&&<a href={r.document_url} target="_blank" rel="noreferrer">Open document</a>}</article>)}</section>
  </main>;
}
