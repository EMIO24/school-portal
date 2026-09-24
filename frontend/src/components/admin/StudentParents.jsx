import React, {useCallback, useEffect, useState} from 'react';
import api from '../../services/api';
import '../../pages/admin/SchoolSetup.css';

export default function StudentParents({studentId}) {
  const url = `/api/students/${studentId}/parents/`;
  const [links,setLinks] = useState([]), [loading,setLoading] = useState(true), [busy,setBusy] = useState(false);
  const [error,setError] = useState(''), [notice,setNotice] = useState('');
  const [form,setForm] = useState({first_name:'',last_name:'',email:'',phone:'',relationship:'guardian'});
  const load = useCallback(async () => {
    setLoading(true);
    try {const {data}=await api.get(url);setLinks(data);} catch {setError('Could not load parent links. Retry before making changes.');}
    finally {setLoading(false);}
  },[url]);
  useEffect(() => {load();},[load]);
  async function save(e) {
    e.preventDefault();setBusy(true);setError('');setNotice('');
    try {await api.post(url,form);await load();setNotice('Parent linked. They can use their registered phone number on the parent sign-in page.');}
    catch(e) {const data=e.response?.data;setError(Array.isArray(data)?data.join(' '):'Could not link this parent. Check the email and registered phone number.');}
    finally {setBusy(false);}
  }
  async function unlink(link) {
    if(!window.confirm(`Remove ${link.name}'s access to this student's information?`)) return;
    setBusy(true);setError('');
    try {await api.delete(url,{params:{link:link.id}});await load();} catch {setError('Could not remove this link. Please retry.');} finally {setBusy(false);}
  }
  return <section className="school-setup" aria-label="Parent access"><h2>Parent access</h2>
    <p>Only explicitly linked parents can see this student. Verify the parent’s identity and phone before granting access. Guardian contact details do not grant portal access.</p>
    {error && <p role="alert">{error} <button onClick={load}>Retry</button></p>}{notice && <p role="status">{notice}</p>}
    {loading ? <p role="status">Loading parent links…</p> : <>
      {links.length ? <ul>{links.map(link => <li key={link.id}>{link.name} — {link.phone} ({link.relationship}) <button disabled={busy} onClick={() => unlink(link)}>Remove access</button></li>)}</ul> : <p>No parent has portal access to this student yet.</p>}
      <form onSubmit={save}><fieldset disabled={busy}><div className="setup-fields">{[['first_name','First name','text'],['last_name','Last name','text'],['email','Parent email','email'],['phone','Parent login phone','tel']].map(([key,label,type]) => <label key={key}>{label}<input type={type} required value={form[key]} onChange={e=>setForm({...form,[key]:e.target.value})}/></label>)}
      <label>Relationship<select value={form.relationship} onChange={e=>setForm({...form,relationship:e.target.value})}>{['guardian','father','mother'].map(value=><option key={value}>{value}</option>)}</select></label></div>
      <label><input type="checkbox" required/>I have verified this parent's identity and authorization to access the student's records.</label><button>Grant parent access</button></fieldset></form>
    </>}
  </section>;
}
