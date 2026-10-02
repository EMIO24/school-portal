import React, {useEffect, useMemo, useState} from 'react';
import api from '../../services/api';
import './AssessmentCentre.css';

const rows = value => value?.results ?? value ?? [];
const errorText = error => error?.response?.data?.detail || JSON.stringify(error?.response?.data || {}) || 'Request failed.';

export default function Admissions() {
  const [applications,setApplications]=useState([]);
  const [levels,setLevels]=useState([]);
  const [arms,setArms]=useState([]);
  const [campuses,setCampuses]=useState([]);
  const [form,setForm]=useState({first_name:'',last_name:'',guardian_name:'',guardian_phone:'',guardian_email:'',applying_class_level:'',preferred_campus:'',previous_school:'',notes:''});
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');

  const load=async()=>{
    setError('');
    try{
      const [a,l,c]=await Promise.all([
        api.get('/api/operations/admissions/'),
        api.get('/api/class-levels/'),
        api.get('/api/class-arms/'),
      ]);
      setApplications(rows(a.data)); setLevels(rows(l.data)); setArms(rows(c.data));
      try { const {data}=await api.get('/api/campuses/'); setCampuses(rows(data)); } catch { setCampuses([]); }
    }catch(e){setError(errorText(e));}
  };
  useEffect(()=>{load();},[]);

  const submit=async e=>{
    e.preventDefault();setBusy(true);setError('');setNotice('');
    try{
      const payload={...form,applying_class_level:Number(form.applying_class_level),preferred_campus:form.preferred_campus?Number(form.preferred_campus):null};
      await api.post('/api/operations/admissions/',payload);
      setForm({first_name:'',last_name:'',guardian_name:'',guardian_phone:'',guardian_email:'',applying_class_level:'',preferred_campus:'',previous_school:'',notes:''});
      setNotice('Admission application created.');await load();
    }catch(e){setError(errorText(e));}finally{setBusy(false);}
  };

  const decide=async(app,decision)=>{
    const payload={decision};
    if(decision==='admit'){
      const choices=arms.filter(a=>String(a.class_level)===String(app.applying_class_level));
      if(!choices.length){setError('Create the destination class before admitting this learner.');return;}
      if(choices.length===1) payload.class_arm=choices[0].id;
      else {
        const entered=window.prompt('Enter destination class ID:\n'+choices.map(a=>`${a.id}: ${a.full_name}`).join('\n'));
        if(!entered)return;
        payload.class_arm=Number(entered);
      }
      if(app.preferred_campus) payload.campus=app.preferred_campus;
    }
    if(!window.confirm(`Record decision "${decision}" for ${app.first_name} ${app.last_name}?`))return;
    setBusy(true);setError('');
    try{await api.post(`/api/operations/admissions/${app.id}/decision/`,payload);setNotice('Admission decision recorded.');await load();}
    catch(e){setError(errorText(e));}finally{setBusy(false);}
  };

  return <main className="assessment-page">
    <header><h1>Admissions</h1><p>Track applicants and convert approved applications into normal Paideia student records without bypassing enrollment history.</p></header>
    {error&&<p role="alert" className="assessment-error">{error}</p>}{notice&&<p role="status">{notice}</p>}
    <form className="assessment-card" onSubmit={submit}><h2>New application</h2>
      <div className="assessment-grid">
        <label>First name<input required value={form.first_name} onChange={e=>setForm({...form,first_name:e.target.value})}/></label>
        <label>Last name<input required value={form.last_name} onChange={e=>setForm({...form,last_name:e.target.value})}/></label>
        <label>Applying class<select required value={form.applying_class_level} onChange={e=>setForm({...form,applying_class_level:e.target.value})}><option value="">Choose class</option>{levels.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select></label>
        {campuses.length>0&&<label>Preferred campus<select value={form.preferred_campus} onChange={e=>setForm({...form,preferred_campus:e.target.value})}><option value="">No preference</option>{campuses.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select></label>}
        <label>Guardian name<input required value={form.guardian_name} onChange={e=>setForm({...form,guardian_name:e.target.value})}/></label>
        <label>Guardian phone<input required value={form.guardian_phone} onChange={e=>setForm({...form,guardian_phone:e.target.value})}/></label>
        <label>Guardian email<input type="email" value={form.guardian_email} onChange={e=>setForm({...form,guardian_email:e.target.value})}/></label>
        <label>Previous school<input value={form.previous_school} onChange={e=>setForm({...form,previous_school:e.target.value})}/></label>
      </div>
      <label>Notes<textarea value={form.notes} onChange={e=>setForm({...form,notes:e.target.value})}/></label>
      <button disabled={busy}>Create application</button>
    </form>
    <section className="assessment-card"><h2>Applications</h2>
      {!applications.length&&<p>No admission applications yet.</p>}
      <div className="assessment-list">{applications.map(app=><article key={app.id} className="assessment-submission">
        <strong>{app.application_number} · {app.first_name} {app.last_name}</strong>
        <p>{app.applying_class_level_name} · {app.status}{app.preferred_campus_name?` · ${app.preferred_campus_name}`:''}</p>
        <p>Guardian: {app.guardian_name} · {app.guardian_phone}</p>
        {!['admitted','rejected','withdrawn'].includes(app.status)&&<div className="assessment-actions">
          <button disabled={busy} onClick={()=>decide(app,'under_review')}>Under review</button>
          <button disabled={busy} onClick={()=>decide(app,'offered')}>Offer</button>
          <button disabled={busy} onClick={()=>decide(app,'admit')}>Admit</button>
          <button disabled={busy} onClick={()=>decide(app,'reject')}>Reject</button>
        </div>}
        {app.admitted_student&&<p>Student record #{app.admitted_student} created.</p>}
      </article>)}</div>
    </section>
  </main>;
}
