import {referenceOptions} from '../../services/referenceOptions';
import React, {useCallback, useEffect, useState} from 'react';
import {Link} from 'react-router-dom';
import api from '../../services/api';
import './SchoolSetup.css';
import ScoringConfiguration from './ScoringConfiguration';

function message(error) {
  const data = error.response?.data;
  if (typeof data?.detail === 'string') return data.detail;
  if (Array.isArray(data)) return data.join(' ');
  if (data && typeof data === 'object') return Object.entries(data).map(([key,value]) => `${key}: ${Array.isArray(value) ? value.join(' ') : String(value)}`).join(' ');
  return 'We could not save your changes. Check your connection and try again.';
}

export default function SchoolSetup() {
  const [setup,setSetup] = useState(null), [identity,setIdentity] = useState({});
  const [levels,setLevels] = useState([]), [arms,setArms] = useState([]);
  const [levelName,setLevelName] = useState(''), [level,setLevel] = useState(''), [armName,setArmName] = useState('');
  const [error,setError] = useState(''), [notice,setNotice] = useState(''), [loading,setLoading] = useState(true), [busy,setBusy] = useState(false);
  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const [s,l,a] = await Promise.all([api.get('/api/school/setup/'),referenceOptions('/api/class-levels/'),referenceOptions('/api/class-arms/')]);
      setSetup(s.data); setIdentity(s.data.identity); setLevels(l.data.results ?? l.data); setArms(a.data.results ?? a.data);
    } catch(e) {setError(message(e));} finally {setLoading(false);}
  },[]);
  useEffect(() => {load();},[load]);
  async function save(action, confirmation) {
    setBusy(true);setError('');setNotice('');
    try {await action();await load();setNotice(confirmation);} catch(e) {setError(message(e));} finally {setBusy(false);}
  }
  const completed = setup?.steps.filter(s => s.complete).length || 0;
  return <main className="school-setup">
    <header><p>GET YOUR SCHOOL READY</p><h1>School setup</h1><p>Work through these steps in order. Progress reflects your saved school records.</p></header>
    {error && <div role="alert">{error} <button onClick={load} disabled={busy}>Retry</button></div>}
    {notice && <p role="status">{notice}</p>}
    {loading ? <p role="status">Loading school setup…</p> : setup && <>
      <section aria-label="Setup progress"><h2>{completed} of {setup.steps.length} setup checks complete</h2>
        <progress max={setup.steps.length} value={completed} aria-label="Completed setup checks"/>
        <ol className="setup-steps">{setup.steps.map(step => <li key={step.key}><span>{step.complete ? 'Complete' : 'Needs attention'}</span><Link to={step.url}>{step.label}</Link></li>)}</ol>
        {!!setup.missing_assignments && <p>{setup.missing_assignments} class/subject combinations still need an active teacher for the current term.</p>}
      </section>
      <section id="identity"><h2>School identity</h2><form onSubmit={e => {e.preventDefault(); const {logo,...fields}=identity;save(() => api.patch('/api/school/setup/',fields),'School identity saved. Reload the portal to refresh its header.');}}>
        <fieldset disabled={busy}><div className="setup-fields">{[['name','School name'],['motto','Motto'],['address','Address'],['phone','Contact phone'],['email','Contact email']].map(([key,label]) => <label key={key}>{label}<input required={key==='name'} type={key==='email'?'email':'text'} value={identity[key] || ''} onChange={e => setIdentity({...identity,[key]:e.target.value})}/></label>)}</div><button>Save school identity</button></fieldset>
      </form>
      {identity.logo && <img className="setup-logo" src={identity.logo} alt="Current school logo"/>}
      <label>School logo<input type="file" disabled={busy} accept="image/png,image/jpeg,image/webp" onChange={e => {const file=e.target.files[0];if(!file)return;const form=new FormData();form.append('logo',file);save(() => api.post('/api/school/setup/logo/',form),'School logo saved.');e.target.value='';}}/></label><p>PNG, JPEG or WebP, up to 2 MB.</p>
      </section>
      <section id="classes"><h2>Classes and arms</h2><p>Create a level such as JSS1, then an arm such as A. Students are enrolled in a class arm.</p>
        <div className="setup-columns"><form onSubmit={e => {e.preventDefault();save(() => api.post('/api/class-levels/',{name:levelName}),'Class level added.');}}><fieldset disabled={busy}><label>New class level<select required value={levelName} onChange={e => setLevelName(e.target.value)}><option value="">Choose a level</option>{setup.class_level_choices.map(([value,label]) => <option key={value} value={value}>{label}</option>)}</select></label><button>Add class level</button></fieldset></form>
        <form onSubmit={e => {e.preventDefault();save(() => api.post('/api/class-arms/',{class_level:Number(level),name:armName}),'Class arm added.');}}><fieldset disabled={busy || !levels.length}><label>Class level<select required value={level} onChange={e => setLevel(e.target.value)}><option value="">Choose a level</option>{levels.map(l => <option key={l.id} value={l.id}>{l.name}</option>)}</select></label><label>Arm name<input required value={armName} onChange={e => setArmName(e.target.value)}/></label><button>Add class arm</button></fieldset></form></div>
        {arms.length ? <ul>{arms.map(a => <li key={a.id}>{a.full_name}</li>)}</ul> : <p>No class arms yet. Add one before enrolling students.</p>}
      </section>
      <ScoringConfiguration onSaved={load}/>
      <section><h2>Next: daily operations</h2><div className="setup-links"><Link to="/admin/students/new">Add students</Link><Link to="/admin/students/import">Import students</Link><Link to="/admin/attendance">Review attendance</Link><Link to="/admin/results">Review results</Link><Link to="/admin/fee-setup">Set up school fees</Link></div></section>
    </>}
  </main>;
}
