import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../../services/api';
import { classifyRequestFailure } from '../../services/requestState';
import './TeachingOperations.css';

const today = () => {
  const parts = Object.fromEntries(new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Africa/Lagos', year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(new Date()).map(({ type, value }) => [type, value]));
  return [parts.year, parts.month, parts.day].join('-');
};
const label = outcome => outcome ? outcome[0].toUpperCase() + outcome.slice(1) : 'Outcome not recorded';

export default function TeachingOperations({ admin = false }) {
  const [day, setDay] = useState(today);
  const [rows, setRows] = useState([]);
  const [holiday, setHoliday] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [filters, setFilters] = useState({ class_arm: '', teacher: '', subject: '', outcome: '' });
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ outcome: 'delivered', note: '', actual_teacher: '' });
  const [teachers, setTeachers] = useState([]);
  const [saving, setSaving] = useState(false);
  const inFlight = useRef(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const { data } = await api.get('/api/timetable/lessons/', { params: { date: day } });
      setRows(data.lessons);
      setHoliday(data.holiday);
      return data.lessons;
    } catch (err) {
      setError(classifyRequestFailure(err).message);
      return null;
    } finally {
      setLoading(false);
    }
  }, [day]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!admin) return;
    api.get('/api/staff/?role=teacher&page_size=300').then(({ data }) => {
      setTeachers((data.results ?? data).filter(t => t.employment_status === 'active')
        .map(t => ({ id: t.user, name: t.full_name || t.name || t.email || `Teacher ${t.user}` })));
    }).catch(() => setTeachers([]));
  }, [admin]);

  const open = row => {
    setEditing(row);
    setForm({ outcome: row.outcome || 'delivered', note: row.note || '',
      actual_teacher: row.outcome === 'substituted' ? String(row.actual_teacher || '') : '' });
    setError('');
    setNotice('');
  };
  const save = async event => {
    event.preventDefault();
    if (inFlight.current || !editing) return;
    inFlight.current = true;
    setSaving(true);
    setError('');
    setNotice('');
    const payload = { outcome: form.outcome, note: form.note, revision: editing.revision };
    if (form.outcome === 'substituted') payload.actual_teacher = Number(form.actual_teacher);
    const url = `/api/timetable/lessons/${editing.slot_id}/${day}/`;
    try {
      await api.put(url, payload);
      const latest = await load();
      if (latest) { setEditing(null); setNotice('Lesson outcome saved.'); }
      else setError('The save may have completed, but the record could not be reloaded. Reconnect and check this date.');
    } catch (err) {
      if (!err.response || err.response.status >= 500) {
        try {
          const { data } = await api.get('/api/timetable/lessons/', { params: { date: day } });
          setRows(data.lessons);
          const current = data.lessons.find(row => row.slot_id === editing.slot_id);
          if (current?.outcome === payload.outcome && current?.note === payload.note &&
              (payload.outcome !== 'substituted' || current.actual_teacher === payload.actual_teacher)) {
            setEditing(null);
            setNotice('The lesson list confirms your save.');
          } else {
            setEditing(current || editing);
            setError('The save could not be confirmed. Review the current outcome before retrying.');
          }
        } catch {
          setError('The save could not be confirmed. Reconnect and reload this date before retrying.');
        }
      } else {
        setError(err.response?.data?.detail || err.response?.data?.outcome ||
          err.response?.data?.actual_teacher || classifyRequestFailure(err, { mutation: true }).message);
        if (err.response.status === 409) {
          const latest = await load();
          const current = latest?.find(row => row.slot_id === editing.slot_id);
          if (current) {
            setEditing(current);
            setForm({ outcome: current.outcome || 'delivered', note: current.note || '',
              actual_teacher: current.outcome === 'substituted' ? String(current.actual_teacher || '') : '' });
            setError('The lesson changed. Review its latest outcome before saving again.');
          }
        }
      }
    } finally {
      inFlight.current = false;
      setSaving(false);
    }
  };
  const choices = [...new Map(rows.map(r => [r.class_arm, r.class_name])).entries()];
  const subjects = [...new Map(rows.map(r => [r.subject, r.subject_name])).entries()];
  const shown = rows.filter(r => (!filters.class_arm || String(r.class_arm) === filters.class_arm)
    && (!filters.subject || String(r.subject) === filters.subject)
    && (!filters.teacher || String(r.scheduled_teacher) === filters.teacher || String(r.actual_teacher) === filters.teacher)
    && (!filters.outcome || (r.outcome || 'unresolved') === filters.outcome));

  return <main className="teaching-page">
    <header className="teaching-header">
      <div><h1>{admin ? 'Teaching records' : "Today's lessons"}</h1><p>Scheduled lessons and recorded outcomes for one school day.</p></div>
      <Link to={admin ? '/admin/timetable' : '/teacher/timetable'}>View timetable</Link>
    </header>
    <div className="teaching-controls">
      <label>Date <input aria-label="Lesson date" type="date" value={day} max={today()} onChange={e => setDay(e.target.value)} /></label>
      <button type="button" onClick={load} disabled={loading}>Refresh</button>
      {admin && <>
        <label>Class <select aria-label="Filter class" value={filters.class_arm} onChange={e => setFilters({ ...filters, class_arm: e.target.value })}><option value="">All</option>{choices.map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select></label>
        <label>Subject <select aria-label="Filter subject" value={filters.subject} onChange={e => setFilters({ ...filters, subject: e.target.value })}><option value="">All</option>{subjects.map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select></label>
        <label>Teacher <select aria-label="Filter teacher" value={filters.teacher} onChange={e => setFilters({ ...filters, teacher: e.target.value })}><option value="">All</option>{teachers.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}</select></label>
        <label>Outcome <select aria-label="Filter outcome" value={filters.outcome} onChange={e => setFilters({ ...filters, outcome: e.target.value })}><option value="">All</option>{['unresolved', 'delivered', 'missed', 'cancelled', 'substituted'].map(o => <option key={o} value={o}>{label(o)}</option>)}</select></label>
      </>}
    </div>
    {notice && <p role="status" className="teaching-notice">{notice}</p>}
    {error && <p role="alert" className="teaching-error">{error}</p>}
    {holiday && <p className="teaching-notice">This date includes a school holiday. No new lesson is inferred for that term.</p>}
    {loading ? <p>Loading lessons…</p> : shown.length === 0 ? <p>No scheduled lessons or recorded outcomes for this date.</p> :
      <div className="teaching-list">{shown.map(row => <article className="teaching-card" key={row.slot_id}>
        <div><strong>{row.class_name} · {row.subject_name}</strong><span>{row.period_name} · {row.period_start}–{row.period_end}</span></div>
        <p>Expected: {row.scheduled_teacher_name || 'Unassigned'}</p>
        {row.outcome === 'substituted' && <p>Substitute: {row.actual_teacher_name}</p>}
        <div className="teaching-card-footer"><span className={'teaching-status ' + (row.outcome || 'unresolved')}>{label(row.outcome)}</span>
          {(admin || (day === today() && row.scheduled_teacher)) && <button type="button" onClick={() => open(row)}>{row.outcome ? 'Review / correct' : 'Record outcome'}</button>}
        </div>
      </article>)}</div>}
    {editing && <form className="teaching-editor" onSubmit={save}>
      <h2>{editing.class_name} · {editing.subject_name}</h2>
      <p>{editing.period_name} on {day}</p>
      <label>Outcome <select aria-label="Lesson outcome" value={form.outcome} onChange={e => setForm({ ...form, outcome: e.target.value })}>
        <option value="delivered">Delivered</option><option value="missed">Missed</option>
        {admin && <><option value="cancelled">Cancelled</option><option value="substituted">Substituted</option></>}
      </select></label>
      {form.outcome === 'substituted' && <label>Substitute teacher <select required value={form.actual_teacher} onChange={e => setForm({ ...form, actual_teacher: e.target.value })}>
        <option value="">Choose teacher</option>{teachers.filter(t => t.id !== editing.scheduled_teacher).map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
      </select></label>}
      <label>Operational note (optional) <textarea maxLength={500} value={form.note} onChange={e => setForm({ ...form, note: e.target.value })} /></label>
      <div><button type="button" onClick={() => setEditing(null)} disabled={saving}>Cancel</button><button type="submit" disabled={saving}>{saving ? 'Saving…' : 'Save outcome'}</button></div>
    </form>}
  </main>;
}
