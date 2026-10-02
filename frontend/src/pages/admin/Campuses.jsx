import React,{useEffect,useState} from 'react';
import api from '../../services/api';
import './AssessmentCentre.css';

const rows=v=>v?.results??v??[];
const err=e=>e?.response?.data?.detail||JSON.stringify(e?.response?.data||{})||'Request failed.';

export default function Campuses(){
  const [items,setItems]=useState([]),[form,setForm]=useState({name:'',code:'',address:'',phone:'',email:'',is_primary:false}),[error,setError]=useState(''),[notice,setNotice]=useState(''),[busy,setBusy]=useState(false);
  const load=()=>api.get('/api/campuses/').then(({data})=>setItems(rows(data))).catch(e=>setError(err(e)));
  useEffect(()=>{load();},[]);
  const create=async e=>{e.preventDefault();setBusy(true);setError('');try{await api.post('/api/campuses/',form);setForm({name:'',code:'',address:'',phone:'',email:'',is_primary:false});setNotice('Campus created.');await load();}catch(e){setError(err(e));}finally{setBusy(false);}};
  const toggle=async row=>{setBusy(true);try{await api.patch(`/api/campuses/${row.id}/`,{is_active:!row.is_active});await load();}catch(e){setError(err(e));}finally{setBusy(false);}};
  return <main className="assessment-page"><header><h1>Campuses</h1><p>Enterprise schools can separate physical locations while keeping one institutional school record.</p></header>
    {error&&<p role="alert" className="assessment-error">{error}</p>}{notice&&<p role="status">{notice}</p>}
    <form className="assessment-card" onSubmit={create}><h2>Add campus</h2><div className="assessment-grid">
      <label>Name<input required value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/></label>
      <label>Code<input required value={form.code} onChange={e=>setForm({...form,code:e.target.value})}/></label>
      <label>Phone<input value={form.phone} onChange={e=>setForm({...form,phone:e.target.value})}/></label>
      <label>Email<input type="email" value={form.email} onChange={e=>setForm({...form,email:e.target.value})}/></label>
      <label><input type="checkbox" checked={form.is_primary} onChange={e=>setForm({...form,is_primary:e.target.checked})}/> Primary campus</label>
    </div><label>Address<textarea value={form.address} onChange={e=>setForm({...form,address:e.target.value})}/></label><button disabled={busy}>Add campus</button></form>
    <section className="assessment-card"><h2>School campuses</h2>{items.map(row=><article key={row.id} className="assessment-submission"><strong>{row.name} ({row.code})</strong><p>{row.is_primary?'Primary · ':''}{row.is_active?'Active':'Inactive'}</p>
      <p>{row.class_count ?? 0} classes · {row.student_count ?? 0} students · {row.staff_count ?? 0} staff</p>
      <p>{row.address}</p><button disabled={busy} onClick={()=>toggle(row)}>{row.is_active?'Mark inactive':'Reactivate'}</button></article>)}</section>
  </main>;
}
