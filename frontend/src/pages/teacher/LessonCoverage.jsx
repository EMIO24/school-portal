import React, { useCallback, useEffect, useRef, useState } from 'react';
import api from '../../services/api';
import { classifyRequestFailure } from '../../services/requestState';

export default function LessonCoverage({ lessonId, slotId }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState({});
  const inFlight = useRef(false);
  const load = useCallback(async () => {
    try {
      const response = await api.get(lessonId ? `/api/curriculum/lessons/${lessonId}/` : `/api/curriculum/slots/${slotId}/`);
      setData(response.data);
      return response.data;
    } catch (err) {
      setError(classifyRequestFailure(err).message);
      return null;
    }
  }, [lessonId, slotId]);
  useEffect(() => { setData(null); setDraft({}); setError(''); load(); }, [load]);
  const save = async (topic, remove = false) => {
    if (inFlight.current) return;
    inFlight.current = true; setBusy(true); setError(''); setNotice('');
    const existing = data.coverage[topic.id];
    const state = draft[topic.id] || existing?.state || 'partial';
    const url = `/api/curriculum/lessons/${lessonId}/topics/${topic.id}/`;
    try {
      if (remove) await api.delete(url, { data: { revision: existing.revision } });
      else await api.put(url, { state, note: existing?.note || '', revision: existing?.revision || 0 });
      const latest = await load();
      if (latest) setNotice(remove ? 'Coverage removed.' : 'Coverage saved.');
      else setError('The save may have completed. Reconnect and refresh this lesson.');
    } catch (err) {
      if (!err.response || err.response.status >= 500 || err.response.status === 409) {
        const latest = await load();
        const current = latest?.coverage?.[topic.id];
        if (current && (remove ? !current.active : current.active && current.state === state))
          setNotice('The lesson record confirms your change.');
        else setError('The change could not be confirmed. Review the current coverage before retrying.');
      } else setError(err.response?.data?.detail || classifyRequestFailure(err, { mutation: true }).message);
    } finally { inFlight.current = false; setBusy(false); }
  };
  return <section className="lesson-curriculum" aria-label="Curriculum coverage">
    <h3>Curriculum coverage</h3>
    <p>{lessonId ? 'What was taught in this lesson. A topic can span several lessons.' : 'Planned topics for this assigned class. Record delivery before saving coverage.'}</p>
    {error && <p role="alert" className="teaching-error">{error}</p>}
    {notice && <p role="status" className="teaching-notice">{notice}</p>}
    {data?.holidays?.length > 0 && <p>Configured breaks: {data.holidays.map(h => `${h.name} (${h.start_date}–${h.end_date})`).join('; ')}. Breaks do not count as teaching.</p>}
    {!data ? <p>Loading curriculum…</p> : !data.plan ? <p>No curriculum plan has been set up for this term, level and subject.</p> :
      <>{data.plan.weeks.map(week => <div key={week.id}>
        <h4>{week.label || `Week ${week.number}`}</h4>
        {week.topics.filter(t => !t.archived || t.locked).map(topic => {
          const saved = data.coverage[topic.id];
          return <article className="curriculum-topic" key={topic.id}>
            <strong>{topic.title}</strong> <span>{topic.state.replace('_', ' ')}</span>
            {topic.objectives.length > 0 && <ul>{topic.objectives.map(o => <li key={o.id}>{o.text}</li>)}</ul>}
            {topic.evidence?.length > 0 && <p>Recorded lessons: {topic.evidence.map(e => `${e.date} (${e.state})`).join(', ')}</p>}
            {saved?.active && <p>This lesson: {saved.state}</p>}
            {lessonId && !topic.archived && <div className="curriculum-actions">
              <label>Coverage <select aria-label={`Coverage for ${topic.title}`} value={draft[topic.id] || (saved?.active ? saved.state : 'partial')} onChange={e => setDraft({ ...draft, [topic.id]: e.target.value })}>
                <option value="partial">Partial</option><option value="covered">Covered</option>
              </select></label>
              <button type="button" disabled={busy} onClick={() => save(topic)}>Save coverage</button>
              {saved?.active && <button type="button" disabled={busy} onClick={() => save(topic, true)}>Remove coverage</button>}
            </div>}
          </article>;
        })}
      </div>)}</>}
  </section>;
}
