import React, { useEffect, useState } from 'react';
import api from '../../services/api';
import { classifyRequestFailure } from '../../services/requestState';
import './TeachingOperations.css';

export default function TeacherScheme() {
  const [assignments, setAssignments] = useState([]);
  const [selected, setSelected] = useState(null);
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    api.get('/api/curriculum/assignments/').then(({ data }) => setAssignments(data.assignments))
      .catch(err => setError(classifyRequestFailure(err).message));
  }, []);
  useEffect(() => {
    if (!selected) { setData(null); return; }
    setLoading(true); setError('');
    api.get('/api/curriculum/plans/', { params: { term: selected.term, class_level: selected.class_level,
      subject: selected.subject, class_arm: selected.class_arm } })
      .then(({ data: result }) => setData(result))
      .catch(err => setError(classifyRequestFailure(err).message))
      .finally(() => setLoading(false));
  }, [selected]);
  return <main className="teaching-page">
    <header className="teaching-header"><div><h1>My scheme of work</h1><p>Planned topics and actual coverage for your assigned classes.</p></div></header>
    {error && <p role="alert" className="teaching-error">{error}</p>}
    {assignments.length === 0 ? <p>No subject assignments are available yet.</p> : <div className="teaching-controls">
      <label>Assigned class and subject <select aria-label="Assigned class and subject" value={assignments.indexOf(selected)} onChange={e => setSelected(assignments[Number(e.target.value)] || null)}>
        <option value="-1">Choose an assignment</option>{assignments.map((a, i) => <option key={`${a.term}-${a.class_arm}-${a.subject}`} value={i}>{a.class_name} · {a.subject_name} · {a.term_name}</option>)}
      </select></label>
    </div>}
    {loading ? <p>Loading scheme…</p> : data && !data.plan ? <p>No scheme of work has been configured for this assignment.</p> : data?.plan && <>
      <p>{data.plan.summary.covered} of {data.plan.summary.total} topics covered · {data.plan.summary.partial} in progress · {data.plan.summary.not_started} not started</p>
      {data.holidays?.length > 0 && <p>Configured breaks: {data.holidays.map(h => `${h.name} (${h.start_date}–${h.end_date})`).join('; ')}. Breaks are not teaching evidence.</p>}
      <div className="teaching-list">{data.plan.weeks.map(week => <section className="teaching-card" key={week.id}>
        <h2>{week.label || `Week ${week.number}`}</h2>
        {week.topics.filter(t => !t.archived || t.locked).map(topic => <article className="curriculum-topic" key={topic.id}>
          <strong>{topic.title}</strong> · {topic.state.replace('_', ' ')}
          {topic.objectives.length > 0 && <ul>{topic.objectives.map(o => <li key={o.id}>{o.text}</li>)}</ul>}
        </article>)}
      </section>)}</div>
    </>}
  </main>;
}
