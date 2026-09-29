import React, { useCallback, useEffect, useState } from 'react';
import api from '../../services/api';
import { Link } from 'react-router-dom';
import { classifyRequestFailure } from '../../services/requestState';
import '../teacher/TeachingOperations.css';

const rows = data => data?.results || data || [];
const fields = { term: '', class_level: '', subject: '', class_arm: '' };

export default function CurriculumManager() {
  const [options, setOptions] = useState({ terms: [], levels: [], subjects: [], arms: [] });
  const [selected, setSelected] = useState(() => {
    const query = new URLSearchParams(window.location.search);
    return Object.fromEntries(Object.keys(fields).map(key => [key, query.get(key) || '']));
  });
  const [plan, setPlan] = useState(null);
  const [holidays, setHolidays] = useState([]);
  const [form, setForm] = useState({ week: 1, week_label: '', position: 1, title: '', description: '', objectives: '' });
  const [editing, setEditing] = useState(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  useEffect(() => {
    Promise.all(['/api/terms/', '/api/class-levels/', '/api/subjects/', '/api/class-arms/'].map(url => api.get(url)))
      .then(result => setOptions({ terms: rows(result[0].data), levels: rows(result[1].data),
        subjects: rows(result[2].data), arms: rows(result[3].data) }))
      .catch(err => setError(classifyRequestFailure(err).message));
  }, []);
  const load = useCallback(async () => {
    if (!selected.term || !selected.class_level || !selected.subject) { setPlan(null); return; }
    setLoading(true); setError('');
    try {
      const { data } = await api.get('/api/curriculum/plans/', { params: selected });
      setPlan(data.plan);
      setHolidays(data.holidays || []);
      return data.plan;
    } catch (err) { setError(classifyRequestFailure(err).message); return null; }
    finally { setLoading(false); }
  }, [selected]);
  useEffect(() => { load(); }, [load]);
  const parsedObjectives = form.objectives.split('\n').map(s => s.trim()).filter(Boolean);
  const save = async event => {
    event.preventDefault(); if (busy) return;
    setBusy(true); setError(''); setNotice('');
    const payload = { title: form.title.trim(), description: form.description, position: Number(form.position), objectives: parsedObjectives };
    try {
      if (editing) await api.patch(`/api/curriculum/topics/${editing}/`, payload);
      else await api.post('/api/curriculum/plans/', { ...selected, ...payload, week: Number(form.week), week_label: form.week_label });
      const latest = await load();
      if (latest) { setNotice(editing ? 'Topic updated.' : 'Topic added.'); setEditing(null); setForm({ week: form.week, week_label: '', position: Number(form.position) + 1, title: '', description: '', objectives: '' }); }
      else setError('The save may have completed. Reconnect and reload this curriculum.');
    } catch (err) { setError(err.response?.data?.detail || err.response?.data?.position || err.response?.data?.objectives || classifyRequestFailure(err, { mutation: true }).message); }
    finally { setBusy(false); }
  };
  const edit = (topic, week) => {
    setEditing(topic.id);
    setForm({ week: week.number, week_label: week.label, position: topic.position, title: topic.title,
      description: topic.description, objectives: topic.objectives.map(o => o.text).join('\n') });
  };
  const archive = async topic => {
    if (busy || !window.confirm(`Archive ${topic.title}? It will remain in historical records.`)) return;
    setBusy(true); setError('');
    try { await api.patch(`/api/curriculum/topics/${topic.id}/`, { archived: !topic.archived }); await load(); }
    catch (err) { setError(err.response?.data?.detail || classifyRequestFailure(err, { mutation: true }).message); }
    finally { setBusy(false); }
  };
  const choice = (key, label, collection) => <label>{label}<select aria-label={label} value={selected[key]} onChange={e => setSelected({ ...selected, [key]: e.target.value, ...(key === 'class_level' ? { class_arm: '' } : {}) })}>
    <option value="">Choose {label.toLowerCase()}</option>{collection.map(item => <option key={item.id} value={item.id}>{item.name || item.full_name}</option>)}
  </select></label>;
  const arms = options.arms.filter(a => String(a.class_level) === selected.class_level);
  return <main className="teaching-page">
    <header className="teaching-header"><div><h1>Scheme of Work / Curriculum</h1><p>Plan topics by week, then compare them with recorded lesson coverage.</p></div><Link to="/admin/calendar">Manage holidays</Link></header>
    <div className="teaching-controls">
      {choice('term', 'Term', options.terms)}{choice('class_level', 'Class level', options.levels)}
      {choice('subject', 'Subject', options.subjects)}{choice('class_arm', 'Class arm for progress', arms)}
      <button type="button" onClick={load} disabled={loading}>Refresh</button>
    </div>
    {error && <p role="alert" className="teaching-error">{error}</p>}{notice && <p role="status" className="teaching-notice">{notice}</p>}
    {holidays.length > 0 && <p>Configured breaks: {holidays.map(h => `${h.name} (${h.start_date}–${h.end_date})`).join('; ')}. Breaks do not count as topic delivery.</p>}
    {loading ? <p>Loading curriculum…</p> : plan ? <>
      {selected.class_arm && <p aria-label="Curriculum progress">{plan.summary.covered} of {plan.summary.total} topics covered · {plan.summary.partial} partial · {plan.summary.not_started} not started</p>}
      {plan.weeks.map(week => <section className="teaching-card" key={week.id}><h2>{week.label || `Week ${week.number}`}</h2>
        {selected.class_arm && week.summary && <p>{week.summary.covered} of {week.summary.total} topics covered this week</p>}
        {week.topics.map(topic => <article className="curriculum-topic" key={topic.id}>
          <strong>{topic.title}</strong> · {topic.archived ? 'Archived' : topic.state.replace('_', ' ')}
          {topic.description && <p>{topic.description}</p>}
          {topic.objectives.length > 0 && <ol>{topic.objectives.map(o => <li key={o.id}>{o.text}</li>)}</ol>}
          {topic.evidence?.length > 0 && <p>Lesson evidence: {topic.evidence.map(e => `${e.date} (${e.state})`).join(', ')}</p>}
          <button type="button" disabled={topic.locked} onClick={() => edit(topic, week)}>Edit</button>
          {topic.locked && <span>Lesson history locks this topic’s content.</span>}
          <button type="button" disabled={busy} onClick={() => archive(topic)}>{topic.archived ? 'Restore' : 'Archive'}</button>
        </article>)}
      </section>)}
    </> : selected.term && selected.class_level && selected.subject && <p>No curriculum plan yet. Add the first topic below.</p>}
    {selected.term && selected.class_level && selected.subject && <form className="teaching-editor" onSubmit={save}>
      <h2>{editing ? 'Edit topic' : 'Add topic'}</h2>
      <label>Week <input aria-label="Week" type="number" min="1" max="52" required value={form.week} disabled={!!editing} onChange={e => setForm({ ...form, week: e.target.value })} /></label>
      {!editing && <label>Week label (optional) <input value={form.week_label} maxLength={80} onChange={e => setForm({ ...form, week_label: e.target.value })} /></label>}
      <label>Position in week <input aria-label="Topic position" type="number" min="1" max="100" required value={form.position} onChange={e => setForm({ ...form, position: e.target.value })} /></label>
      <label>Topic title <input aria-label="Topic title" required maxLength={180} value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} /></label>
      <label>Description (optional) <textarea maxLength={500} value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} /></label>
      <label>Learning objectives (one per line) <textarea aria-label="Learning objectives" value={form.objectives} onChange={e => setForm({ ...form, objectives: e.target.value })} /></label>
      <div>{editing && <button type="button" onClick={() => setEditing(null)}>Cancel edit</button>}<button type="submit" disabled={busy}>{busy ? 'Saving…' : editing ? 'Save topic' : 'Add topic'}</button></div>
    </form>}
  </main>;
}
