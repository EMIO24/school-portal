import React, {useEffect, useState} from 'react';
import api from '../../services/api';
import {useAuth} from '../../hooks/useAuth';

export default function StudentPresence() {
  const {user} = useAuth();
  const [settings,setSettings]=useState(null);
  const [classArm,setClassArm]=useState('');
  const [rows,setRows]=useState([]);
  const [loading,setLoading]=useState(false);
  const [error,setError]=useState('');
  const [message,setMessage]=useState('');

  async function loadSettings() {
    try {
      const {data}=await api.get('/api/attendance/presence/settings/');
      setSettings(data);
      if (!classArm && data.classes?.length) setClassArm(String(data.classes[0].id));
    } catch {
      setError('Could not load student presence settings.');
    }
  }

  async function loadPresence(selected=classArm) {
    if (!selected) return;
    setLoading(true); setError('');
    try {
      const {data}=await api.get('/api/attendance/presence/', {params:{class_arm:selected}});
      setRows(data.students || []);
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not load the class presence register.');
    } finally {setLoading(false);}
  }

  useEffect(()=>{loadSettings();},[]);
  useEffect(()=>{if(classArm) loadPresence(classArm);},[classArm]);

  async function recordArrival(student) {
    setError(''); setMessage('');
    try {
      await api.post('/api/attendance/presence/', {student});
      setMessage('Arrival recorded.');
      await loadPresence();
    } catch (err) {setError(err.response?.data?.detail || 'Could not record arrival.');}
  }

  async function clockOut(student) {
    setError(''); setMessage('');
    if (!window.confirm('Record this student as clocked out now?')) return;
    try {
      await api.post('/api/attendance/presence/clock-out/', {student});
      setMessage('Clock-out recorded.');
      await loadPresence();
    } catch (err) {setError(err.response?.data?.detail || 'Could not record clock-out.');}
  }

  async function saveSettings(e) {
    e.preventDefault();
    setError(''); setMessage('');
    try {
      const {data}=await api.patch('/api/attendance/presence/settings/', {
        arrival_cutoff_time: settings.arrival_cutoff_time || null,
        student_clockout_enabled: !!settings.student_clockout_enabled,
      });
      setSettings(prev=>({...prev,...data}));
      setMessage('Presence settings saved.');
    } catch (err) {setError(err.response?.data?.detail || 'Could not save presence settings.');}
  }

  if (!settings) return <main className="page-shell"><h1>Student Presence</h1><p>{error || 'Loading…'}</p></main>;

  return <main className="page-shell">
    <header><h1>Student Presence</h1>
      <p>Arrival and departure evidence is separate from the academic attendance register. No clock-out record means only that no departure has been recorded.</p>
    </header>

    {user?.role === 'school_admin' && <form onSubmit={saveSettings}>
      <h2>School settings</h2>
      <label>Late after <input type="time" value={settings.arrival_cutoff_time || ''} onChange={e=>setSettings(s=>({...s,arrival_cutoff_time:e.target.value}))}/></label>
      <label><input type="checkbox" checked={!!settings.student_clockout_enabled} onChange={e=>setSettings(s=>({...s,student_clockout_enabled:e.target.checked}))}/> Enable student clock-out</label>
      <button type="submit">Save presence settings</button>
    </form>}

    <section>
      <h2>Today's register</h2>
      <label>Class <select value={classArm} onChange={e=>setClassArm(e.target.value)}>
        {(settings.classes || []).map(c=><option key={c.id} value={c.id}>{c.name}</option>)}
      </select></label>
      {loading ? <p>Loading class…</p> : rows.length ? <div className="table-wrap"><table>
        <thead><tr><th>Student</th><th>Arrival</th><th>Status</th><th>Clock-out</th><th>Actions</th></tr></thead>
        <tbody>{rows.map(row=>{
          const p=row.presence;
          return <tr key={row.student_id}>
            <td>{row.student_name}<br/><small>{row.admission_number}</small></td>
            <td>{p?.arrival_time || 'Not recorded'}</td>
            <td>{p?.late ? 'Late' : p?.arrival_time ? 'Arrived' : '—'}</td>
            <td>{p?.departure_time || (settings.student_clockout_enabled ? 'Not recorded' : 'Disabled')}</td>
            <td>
              {!p?.arrival_time && <button type="button" onClick={()=>recordArrival(row.student_id)}>Record arrival</button>}
              {settings.student_clockout_enabled && p?.arrival_time && !p?.departure_time &&
                <button type="button" onClick={()=>clockOut(row.student_id)}>Clock out</button>}
            </td>
          </tr>
        })}</tbody>
      </table></div> : <p>No active students found in this class.</p>}
    </section>

    {message && <p role="status">{message}</p>}
    {error && <p role="alert">{error}</p>}
  </main>;
}
