import React, { useEffect, useState } from 'react';
import api from '../../services/api';
import { downloadFile } from '../../services/download';

const sections = [
  ['show_comments', 'Teacher and principal comments'],
  ['show_attendance', 'Finalized attendance'],
  ['show_position', 'Class position'],
  ['show_skills', 'Affective and psychomotor ratings'],
  ['show_next_term', 'Next term date'],
];

export default function ReportConfiguration() {
  const [form, setForm] = useState(null);
  const [saved, setSaved] = useState(null);
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [student, setStudent] = useState('');
  const [term, setTerm] = useState('');
  const [preview, setPreview] = useState(null);

  useEffect(() => {
    api.get('/api/results/report-configuration/').then(({ data }) => {
      setForm(data); setSaved(data);
    }).catch(() => setNotice('Could not load report settings. Retry this page.'));
  }, []);

  async function save(event) {
    event.preventDefault(); setBusy(true); setNotice('');
    try {
      const { data } = await api.patch('/api/results/report-configuration/', form);
      setForm(data); setSaved(data); setNotice('Report settings saved for future publications.');
    } catch (error) {
      setNotice(error?.response?.data?.detail || 'Could not save. Review the options and retry.');
    } finally { setBusy(false); }
  }

  async function loadPreview() {
    if (!/^\d+$/.test(student) || !/^\d+$/.test(term)) {
      setNotice('Enter a student user ID and term ID for this school.'); return;
    }
    setNotice(''); setPreview(null);
    try {
      const { data } = await api.get(`/api/results/slip-data/${student}/?term=${term}&preview=1`);
      setPreview(data);
    } catch { setNotice('No authorized result preview is available for that student and term.'); }
  }

  if (!form) return <main style={{ padding: 24 }}><h1>Report cards</h1><p role="status">{notice || 'Loading report settings…'}</p></main>;
  return <main className="res-page" style={{ maxWidth: 960, margin: 'auto' }}>
    <h1>Report cards</h1>
    <p>Choose a layout and sections. Assessment columns, grades and branding come from existing school records.</p>
    <p>Published terms keep the presentation captured when their first result was published.</p>
    <form onSubmit={save} style={{ display: 'grid', gap: 16 }}>
      <label>Layout <select value={form.layout} onChange={event => setForm({ ...form, layout: event.target.value })}>
        <option value="classic">Classic Academic</option><option value="modern">Modern</option><option value="compact">Compact</option>
      </select></label>
      <label>Report title <input value={form.title} maxLength={80} onChange={event => setForm({ ...form, title: event.target.value })} /></label>
      <label>Watermark <select value={form.watermark} onChange={event => setForm({ ...form, watermark: event.target.value })}>
        <option value="none">None</option><option value="official">Official</option><option value="school">School name</option>
      </select></label>
      <fieldset><legend>Sections</legend>{sections.map(([key, label]) =>
        <label key={key} style={{ display: 'block', margin: '8px 0' }}>
          <input type="checkbox" checked={form[key]} onChange={event => setForm({ ...form, [key]: event.target.checked })} /> {label}
        </label>)}</fieldset>
      <button className="res-btn res-btn--navy" disabled={busy || JSON.stringify(form) === JSON.stringify(saved)}>{busy ? 'Saving…' : 'Save report settings'}</button>
    </form>
    <section style={{ marginTop: 32 }} aria-label="Unpublished result preview">
      <h2>Preview an authorized result</h2>
      <p>Use a student user ID and term ID from Result Management. Preview may include unpublished scores.</p>
      <label>Student user ID <input inputMode="numeric" value={student} onChange={event => setStudent(event.target.value)} /></label>{' '}
      <label>Term ID <input inputMode="numeric" value={term} onChange={event => setTerm(event.target.value)} /></label>{' '}
      <button type="button" onClick={loadPreview}>Load preview</button>
      {preview && <div className="res-card" style={{ padding: 20, marginTop: 16 }}>
        <strong>UNPUBLISHED PREVIEW — NOT AN OFFICIAL RESULT</strong>
        <h3>{preview.school_name}: {preview.student_name}</h3>
        <p>{preview.title} · {preview.term_name} · {preview.layout}</p>
        <table><thead><tr><th>Subject</th><th>Assessments</th><th>Total</th><th>Grade</th></tr></thead><tbody>
          {preview.score_rows.map((row, index) => <tr key={index}><td>{row.subject}</td>
            <td>{row.components.map(part => `${part.name}: ${part.score}/${part.maximum}`).join(', ')}</td>
            <td>{row.total_score}</td><td>{row.grade}</td></tr>)}
        </tbody></table>
        <button type="button" onClick={() => downloadFile(`/api/results/slip/${student}/?term=${term}&preview=1`, 'unpublished-report-preview.pdf')}>Download preview PDF</button>
      </div>}
    </section>
    {notice && <p role="status">{notice}</p>}
  </main>;
}
