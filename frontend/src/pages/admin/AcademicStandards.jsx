import React, { useCallback, useEffect, useState } from 'react';
import api from '../../services/api';
import { classifyRequestFailure } from '../../services/requestState';
import '../teacher/TeachingOperations.css';

const rows = data => data?.results || data || [];

export default function AcademicStandards() {
  const [sources, setSources] = useState([]);
  const [standards, setStandards] = useState([]);
  const [options, setOptions] = useState({ levels: [], subjects: [], sessions: [] });
  const [sourceForm, setSourceForm] = useState({ name: '', kind: 'government', jurisdiction: '', authority: '' });
  const [versionForm, setVersionForm] = useState({ source: '', label: '', reference: '' });
  const [standardForm, setStandardForm] = useState({ title: '', class_level: '', subject: '', curriculum_version: '' });
  const [topicForm, setTopicForm] = useState({ standard: '', term: 'first', title: '', position: 1, recommended_week: 1, requirement: 'required', objectives: '' });
  const [appForm, setAppForm] = useState({ session: '', class_level: '', subject: '', curriculum_version: '' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const load = useCallback(async () => {
    setError('');
    try {
      const [sourceRes, standardRes, levels, subjects, sessions] = await Promise.all([
        api.get('/api/curriculum/standards/sources/'),
        api.get('/api/curriculum/standards/'),
        api.get('/api/class-levels/'),
        api.get('/api/subjects/'),
        api.get('/api/sessions/'),
      ]);
      setSources(sourceRes.data.sources || []);
      setStandards(standardRes.data.standards || []);
      setOptions({ levels: rows(levels.data), subjects: rows(subjects.data), sessions: rows(sessions.data) });
    } catch (err) { setError(classifyRequestFailure(err).message); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const mutate = async work => {
    if (busy) return;
    setBusy(true); setError(''); setNotice('');
    try { await work(); await load(); }
    catch (err) { setError(err.response?.data?.detail || Object.values(err.response?.data || {})[0] || classifyRequestFailure(err, { mutation: true }).message); }
    finally { setBusy(false); }
  };

  const versions = sources.flatMap(source => (source.versions || []).map(version => ({ ...version, source_name: source.name })));
  const choice = (label, value, onChange, items, text) => <label>{label}<select aria-label={label} value={value} onChange={onChange}>
    <option value="">Choose {label.toLowerCase()}</option>
    {items.map(item => <option key={item.id} value={item.id}>{text ? text(item) : item.name}</option>)}
  </select></label>;

  return <main className="teaching-page">
    <header className="teaching-header"><div><h1>Academic Standards</h1>
      <p>Record curriculum provenance, approve the school academic standard, and preserve each revision across sessions.</p></div></header>
    {error && <p role="alert" className="teaching-error">{error}</p>}
    {notice && <p role="status" className="teaching-notice">{notice}</p>}

    <section className="teaching-card"><h2>1. Curriculum source</h2>
      <p>Record the source as the school obtained it. Paideia does not invent or label unverified material as official.</p>
      <div className="teaching-editor">
        <label>Name <input value={sourceForm.name} onChange={e => setSourceForm({ ...sourceForm, name: e.target.value })}/></label>
        <label>Type <select value={sourceForm.kind} onChange={e => setSourceForm({ ...sourceForm, kind: e.target.value })}>
          <option value="government">Government / regulator</option><option value="exam_body">Examination body</option>
          <option value="school">School-authored reference</option><option value="other">Other</option></select></label>
        <label>Jurisdiction <input value={sourceForm.jurisdiction} onChange={e => setSourceForm({ ...sourceForm, jurisdiction: e.target.value })}/></label>
        <label>Authority <input value={sourceForm.authority} onChange={e => setSourceForm({ ...sourceForm, authority: e.target.value })}/></label>
        <button disabled={busy || !sourceForm.name.trim()} onClick={() => mutate(async () => {
          await api.post('/api/curriculum/standards/sources/', sourceForm);
          setSourceForm({ name: '', kind: 'government', jurisdiction: '', authority: '' }); setNotice('Curriculum source recorded.');
        })}>Add source</button>
      </div>
      {sources.length > 0 && <ul>{sources.map(source => <li key={source.id}><strong>{source.name}</strong> · {source.kind}{source.jurisdiction ? ' · ' + source.jurisdiction : ''}</li>)}</ul>}
    </section>

    <section className="teaching-card"><h2>2. Curriculum version</h2>
      <div className="teaching-editor">
        {choice('Curriculum source', versionForm.source, e => setVersionForm({ ...versionForm, source: e.target.value }), sources)}
        <label>Version label <input value={versionForm.label} onChange={e => setVersionForm({ ...versionForm, label: e.target.value })}/></label>
        <label>Reference <input value={versionForm.reference} onChange={e => setVersionForm({ ...versionForm, reference: e.target.value })}/></label>
        <button disabled={busy || !versionForm.source || !versionForm.label.trim()} onClick={() => mutate(async () => {
          await api.post('/api/curriculum/standards/sources/' + versionForm.source + '/versions/', { label: versionForm.label, reference: versionForm.reference });
          setVersionForm({ source: '', label: '', reference: '' }); setNotice('Curriculum version recorded.');
        })}>Add version</button>
      </div>
    </section>

    <section className="teaching-card"><h2>3. Applicable curriculum for a session</h2>
      <p>This pins history: once term execution exists, the session cannot silently switch to another curriculum version.</p>
      <div className="teaching-editor">
        {choice('Academic session', appForm.session, e => setAppForm({ ...appForm, session: e.target.value }), options.sessions)}
        {choice('Class level', appForm.class_level, e => setAppForm({ ...appForm, class_level: e.target.value }), options.levels)}
        {choice('Subject', appForm.subject, e => setAppForm({ ...appForm, subject: e.target.value }), options.subjects)}
        {choice('Curriculum version', appForm.curriculum_version, e => setAppForm({ ...appForm, curriculum_version: e.target.value }), versions, item => item.source_name + ' · ' + item.label)}
        <button disabled={busy || Object.values(appForm).some(v => !v)} onClick={() => mutate(async () => {
          await api.put('/api/curriculum/standards/applicability/', appForm); setNotice('Applicable curriculum saved for the session.');
        })}>Save applicability</button>
      </div>
    </section>

    <section className="teaching-card"><h2>4. School academic standard</h2>
      <div className="teaching-editor">
        <label>Title <input value={standardForm.title} onChange={e => setStandardForm({ ...standardForm, title: e.target.value })}/></label>
        {choice('Class level', standardForm.class_level, e => setStandardForm({ ...standardForm, class_level: e.target.value }), options.levels)}
        {choice('Subject', standardForm.subject, e => setStandardForm({ ...standardForm, subject: e.target.value }), options.subjects)}
        {choice('Curriculum version', standardForm.curriculum_version, e => setStandardForm({ ...standardForm, curriculum_version: e.target.value }), versions, item => item.source_name + ' · ' + item.label)}
        <button disabled={busy || Object.values(standardForm).some(v => !v)} onClick={() => mutate(async () => {
          await api.post('/api/curriculum/standards/', standardForm);
          setStandardForm({ title: '', class_level: '', subject: '', curriculum_version: '' }); setNotice('Academic standard draft created.');
        })}>Create standard</button>
      </div>
      {standards.length > 0 && <div className="teaching-list">{standards.map(standard => <article key={standard.id} className="curriculum-topic">
        <strong>{standard.title}</strong> · {standard.class_level_name} · {standard.subject_name}
        <p>{standard.curriculum_source} · {standard.curriculum_version_label} · revision {standard.revision} · <strong>{standard.status}</strong></p>
        {standard.status === 'draft' && <button disabled={busy} onClick={() => mutate(async () => { await api.post('/api/curriculum/standards/' + standard.id + '/transition/', { action: 'submit' }); setNotice('Standard submitted for review.'); })}>Submit</button>}
        {standard.status === 'submitted' && <button disabled={busy} onClick={() => mutate(async () => { await api.post('/api/curriculum/standards/' + standard.id + '/transition/', { action: 'review' }); setNotice('Standard reviewed.'); })}>Mark reviewed</button>}
        {standard.status === 'reviewed' && <button disabled={busy} onClick={() => mutate(async () => { await api.post('/api/curriculum/standards/' + standard.id + '/transition/', { action: 'approve' }); setNotice('Standard approved.'); })}>Approve</button>}
        {standard.status === 'approved' && <button disabled={busy} onClick={() => mutate(async () => { await api.post('/api/curriculum/standards/' + standard.id + '/revise/', {}); setNotice('New draft revision created.'); })}>Create new revision</button>}
      </article>)}</div>}
    </section>

    <section className="teaching-card"><h2>5. Add standard topic</h2>
      <p>Required curriculum and school enrichment remain distinguishable.</p>
      <div className="teaching-editor">
        {choice('Draft standard', topicForm.standard, e => setTopicForm({ ...topicForm, standard: e.target.value }), standards.filter(s => s.status === 'draft'), item => item.title + ' · r' + item.revision)}
        <label>Term <select value={topicForm.term} onChange={e => setTopicForm({ ...topicForm, term: e.target.value })}><option value="first">First</option><option value="second">Second</option><option value="third">Third</option></select></label>
        <label>Topic title <input value={topicForm.title} onChange={e => setTopicForm({ ...topicForm, title: e.target.value })}/></label>
        <label>Position <input type="number" min="1" value={topicForm.position} onChange={e => setTopicForm({ ...topicForm, position: e.target.value })}/></label>
        <label>Recommended week <input type="number" min="1" max="52" value={topicForm.recommended_week} onChange={e => setTopicForm({ ...topicForm, recommended_week: e.target.value })}/></label>
        <label>Requirement <select value={topicForm.requirement} onChange={e => setTopicForm({ ...topicForm, requirement: e.target.value })}><option value="required">Required curriculum</option><option value="enrichment">School enrichment</option></select></label>
        <label>Objectives, one per line <textarea value={topicForm.objectives} onChange={e => setTopicForm({ ...topicForm, objectives: e.target.value })}/></label>
        <button disabled={busy || !topicForm.standard || !topicForm.title.trim()} onClick={() => mutate(async () => {
          await api.post('/api/curriculum/standards/' + topicForm.standard + '/topics/', {
            term: topicForm.term, title: topicForm.title, position: Number(topicForm.position),
            recommended_week: Number(topicForm.recommended_week), requirement: topicForm.requirement,
            objectives: topicForm.objectives.split('\n').map(x => x.trim()).filter(Boolean),
          });
          setTopicForm({ ...topicForm, title: '', position: Number(topicForm.position) + 1, objectives: '' }); setNotice('Standard topic added.');
        })}>Add topic</button>
      </div>
    </section>
  </main>;
}
