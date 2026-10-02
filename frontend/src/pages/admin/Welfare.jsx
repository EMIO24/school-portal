import React,{useEffect,useState} from 'react';
import api from '../../services/api';
import './AssessmentCentre.css';

const rows=v=>v?.results??v??[];
const err=e=>e?.response?.data?.detail||JSON.stringify(e?.response?.data||{})||'Request failed.';

export default function Welfare(){
  const [cases,setCases]=useState([]),[students,setStudents]=useState([]);
  const [form,setForm]=useState({student:'',category:'attendance',severity:'low',title:'',details:''});
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
  const load=async()=>{try{const [c,s]=await Promise.all([api.get('/api/operations/welfare/'),api.get('/api/students/',{params:{status:'active'}})]);setCases(rows(c.data));setStudents(rows(s.data));}catch(e){setError(err(e));}};
  useEffect(()=>{load();},[]);
  const create=async e=>{e.preventDefault();setBusy(true);setError('');try{await api.post('/api/operations/welfare/',{...form,student:Number(form.student)});setForm({student:'',category:'attendance',severity:'low',title:'',details:''});setNotice('Welfare case opened.');await load();}catch(e){setError(err(e));}finally{setBusy(false);}};
  const update=async row=>{const note=window.prompt('Case update note');if(!note)return;const status=window.prompt('Status: open, monitoring or resolved',row.status)||row.status;setBusy(true);try{await api.post(`/api/operations/welfare/${row.id}/updates/`,{note,status});setNotice('Welfare case updated.');await load();}catch(e){setError(err(e));}finally{setBusy(false);}};
  return <main className="assessment-page"><header><h1>Student welfare</h1><p>Record concerns and follow-up without deleting history. Sensitive health and safeguarding cases remain restricted to school management.</p></header>
    {error&&<p role="alert" className="assessment-error">{error}</p>}{notice&&<p role="status">{notice}</p>}
    <form className="assessment-card" onSubmit={create}><h2>Open case</h2><div className="assessment-grid">
      <label>Student<select required value={form.student} onChange={e=>setForm({...form,student:e.target.value})}><option value="">Choose student</option>{students.map(s=><option key={s.id} value={s.id}>{s.full_name} · {s.current_class_name||'No class'}</option>)}</select></label>
      <label>Category<select value={form.category} onChange={e=>setForm({...form,category:e.target.value})}>{['attendance','behaviour','academic','health','safeguarding','other'].map(x=><option key={x} value={x}>{x}</option>)}</select></label>
      <label>Severity<select value={form.severity} onChange={e=>setForm({...form,severity:e.target.value})}>{['low','medium','high','critical'].map(x=><option key={x}>{x}</option>)}</select></label>
    </div><label>Title<input required maxLength="180" value={form.title} onChange={e=>setForm({...form,title:e.target.value})}/></label>
    <label>Details<textarea required value={form.details} onChange={e=>setForm({...form,details:e.target.value})}/></label><button disabled={busy}>Open case</button></form>
    <section className="assessment-card"><h2>Cases</h2>{!cases.length&&<p>No welfare cases in your scope.</p>}<div className="assessment-list">{cases.map(row=><article key={row.id} className="assessment-submission">
      <strong>{row.student_name} · {row.title}</strong><p>{row.category} · {row.severity} · {row.status} · {row.class_name}</p><p>{row.details}</p>
      {(row.updates||[]).map(u=><p key={u.id}><small>{new Date(u.created_at).toLocaleString()} · {u.status_after}</small><br/>{u.note}</p>)}
      <button disabled={busy} onClick={()=>update(row)}>Add update</button>
    </article>)}</div></section>
  </main>;
}
