import React, {useEffect, useRef, useState} from 'react';
import api from '../../services/api';
import {referenceOptions} from '../../services/referenceOptions';
import './CommunicationCentre.css';

const AUDIENCES = [
  ['all_parents', 'All linked parents'], ['class_parents', 'Parents of a class'],
  ['selected_parents', 'Selected parents'], ['all_staff', 'All active staff'],
  ['class_teachers', 'Teachers of a class'], ['selected_staff', 'Selected staff'],
  ['all_students', 'All active students'], ['class_students', 'Students of a class'],
  ['selected_students', 'Selected students'],
];

export default function CommunicationCentre() {
  const [audience, setAudience] = useState('all_parents');
  const [classId, setClassId] = useState('');
  const [selected, setSelected] = useState([]);
  const [classes, setClasses] = useState([]);
  const [options, setOptions] = useState([]);
  const [search, setSearch] = useState('');
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [preview, setPreview] = useState(null);
  const [history, setHistory] = useState({results: [], next: null});
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const key = useRef(null);
  const previewVersion = useRef(0);

  const classAudience = audience.startsWith('class_');
  const selectedAudience = audience.startsWith('selected_');
  const audienceData = {audience, ...(classAudience ? {class_arm_id: Number(classId)} : {}),
    ...(selectedAudience ? {recipient_ids: selected} : {})};

  useEffect(() => {
    referenceOptions('/api/class-arms/').then(({data}) => setClasses(data))
      .catch(() => setError('Could not load classes. Reload to retry.'));
    loadHistory();
  }, []);
  useEffect(() => { previewVersion.current += 1; setPreview(null); }, [audience, classId, selected]);
  useEffect(() => {
    if (!selectedAudience) return;
    let current = true;
    api.get('/api/communications/recipients/', {params: {audience, search}})
      .then(({data}) => { if (current) setOptions(data); })
      .catch(() => { if (current) setError('Could not load recipients. Retry the search.'); });
    return () => { current = false; };
  }, [audience, search, selectedAudience]);

  async function loadHistory(url = '/api/communications/history/', append = false) {
    setLoadingHistory(true);
    try {
      const {data} = await api.get(url);
      setHistory(old => ({...data, results: append ? [...old.results, ...data.results] : data.results}));
    } catch { setError('Could not load notice history. Retry.'); }
    finally { setLoadingHistory(false); }
  }

  async function loadPreview() {
    setBusy(true); setError(''); setPreview(null);
    const version = ++previewVersion.current;
    try {
      const {data} = await api.post('/api/communications/preview/', audienceData);
      if (version === previewVersion.current) setPreview(data);
    } catch (err) { if (version === previewVersion.current) setError(err.response?.data?.detail || 'Could not preview this audience. Retry.'); }
    finally { setBusy(false); }
  }

  async function send(event) {
    event.preventDefault();
    if (!preview?.recipient_count) { setError('Preview an audience with linked portal accounts first.'); return; }
    if (!window.confirm(`Publish this portal notice to ${preview.recipient_count} unique account${preview.recipient_count === 1 ? '' : 's'}?`)) return;
    setBusy(true); setError(''); setMessage('');
    if (!key.current) key.current = window.crypto.randomUUID();
    try {
      const {data} = await api.post('/api/communications/send/', {...audienceData, title, body, channels: ['portal']},
        {headers: {'Idempotency-Key': key.current}});
      setMessage(`Notice #${data.id} is available in ${data.recipient_count} portal account${data.recipient_count === 1 ? '' : 's'}. ${data.replayed ? 'This request was already published.' : ''}`);
      key.current = null; setTitle(''); setBody(''); setPreview(null);
      loadHistory();
    } catch (err) {
      if (err.response) {
        setError(err.response.data?.detail || 'Could not publish the notice.');
        if (err.response.status !== 500) key.current = null;
      } else {
        setError('The response was lost. Check history first, then retry this same notice with the same request key.');
        loadHistory();
      }
    } finally { setBusy(false); }
  }

  async function openDetail(id) {
    setError('');
    try { const {data} = await api.get(`/api/communications/history/${id}/`); setDetail(data); }
    catch { setError('Could not open this notice. Retry.'); }
  }

  return <main className="communication-page">
    <header><span className="workspace-eyebrow">SCHOOL COMMUNICATION</span><h1>Communication Centre</h1>
      <p>Publish a manual notice to linked school portal accounts. Portal notices do not send email or SMS.</p>
      <p><a href="/admin/notifications">Existing email and SMS tool</a> is separate and may require provider setup or a worker.</p></header>
    {error && <p role="alert" className="communication-error">{error}</p>}
    {message && <p role="status" className="communication-success">{message}</p>}
    <div className="communication-grid">
      <form className="communication-card" onSubmit={send}>
        <h2>Compose notice</h2>
        <label>Audience<select value={audience} onChange={e => {setAudience(e.target.value); setSelected([]); setSearch('');}}>
          {AUDIENCES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        {classAudience && <label>Class<select value={classId} onChange={e => setClassId(e.target.value)}>
          <option value="">Choose a class</option>{classes.map(c => <option key={c.id} value={c.id}>{c.full_name || `${c.class_level_name || ''} ${c.name}`}</option>)}
        </select></label>}
        {selectedAudience && <div><label>Find accounts<input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search by name" /></label>
          <div className="communication-options" aria-label="Recipient accounts">{options.map(row => <label key={row.id}>
            <input type="checkbox" checked={selected.includes(row.id)} onChange={e => setSelected(old => e.target.checked ? [...old, row.id] : old.filter(id => id !== row.id))}/>{row.name}
          </label>)}</div><small>{selected.length} selected</small></div>}
        <button type="button" onClick={loadPreview} disabled={busy || (classAudience && !classId) || (selectedAudience && !selected.length)}>Preview recipients</button>
        {preview && <div className="communication-preview" role="status"><strong>{preview.recipient_count} unique portal accounts</strong>
          <span>{preview.label}</span>{preview.students_without_linked_parent > 0 &&
            <p>{preview.students_without_linked_parent} active students have no linked parent portal account.</p>}
          {!preview.recipient_count && <p>No linked portal accounts in this audience.</p>}</div>}
        <label>Channel<input type="text" value="Portal notice" readOnly aria-label="Channel" /></label>
        <label>Title<input value={title} onChange={e => setTitle(e.target.value)} maxLength={160} required /></label>
        <label>Message<textarea value={body} onChange={e => setBody(e.target.value)} rows={6} maxLength={5000} required /></label>
        <button type="submit" disabled={busy || !preview?.recipient_count || !title.trim() || !body.trim()}>{busy ? 'Working…' : 'Publish portal notice'}</button>
      </form>
      <section className="communication-card"><h2>Published notices</h2>
        {loadingHistory && <p role="status">Loading history…</p>}
        {!loadingHistory && !history.results.length && <p>No notices published yet.</p>}
        <div className="communication-history">{history.results.map(row => <button key={row.id} type="button" onClick={() => openDetail(row.id)}>
          <strong>{row.title}</strong><span>{row.audience_label}</span><small>{row.recipient_count} available · {row.read_count} opened · {new Date(row.published_at).toLocaleString()}</small>
        </button>)}</div>
        {history.next && <button type="button" onClick={() => loadHistory(history.next, true)} disabled={loadingHistory}>Load more</button>}
        {!history.results.length && !loadingHistory && <button type="button" onClick={() => loadHistory()}>Retry history</button>}
        {detail && <article className="communication-detail"><h3>{detail.title}</h3><p>{detail.body}</p>
          <small>Published by {detail.sender_name} · {new Date(detail.published_at).toLocaleString()} · {detail.audience_label} · {detail.recipient_count} available · {detail.read_count} opened</small>
          <button type="button" onClick={() => setDetail(null)}>Close detail</button></article>}
      </section>
    </div>
  </main>;
}
