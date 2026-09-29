import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import WorkspaceHome from '../../components/common/WorkspaceHome';
import api from '../../services/api';
import { classifyRequestFailure } from '../../services/requestState';
import './AdminDashboard.css';

const sections = ['attendance', 'teaching', 'curriculum', 'results', 'finance'];
const titles = { attendance: 'Student attendance', teaching: 'Teaching operations',
  curriculum: 'Curriculum coverage', results: 'Result workflow', finance: 'Recorded school fees' };
const today = () => {
  const parts = Object.fromEntries(new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Africa/Lagos', year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(new Date()).map(({ type, value }) => [type, value]));
  return [parts.year, parts.month, parts.day].join('-');
};
const params = (section, date, term) => ({ params: { section, date, ...(term ? { term } : {}) } });

function Section({ name, data, error, loading, retry, children }) {
  return <section className="principal-section" aria-label={titles[name]}>
    <div className="principal-section-heading"><h2>{titles[name]}</h2>
      <button type="button" onClick={() => retry(name)} disabled={loading}>Retry</button></div>
    {loading ? <p role="status">Loading {titles[name].toLowerCase()}…</p>
      : error ? <p role="alert">{titles[name]} unavailable — {error}</p>
      : data ? children(data) : <p>Choose an academic term to inspect this section.</p>}
  </section>;
}

export default function AdminDashboard() {
  const [day, setDay] = useState(today);
  const [term, setTerm] = useState('');
  const [snapshot, setSnapshot] = useState(null);
  const [snapshotError, setSnapshotError] = useState('');
  const [data, setData] = useState({});
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState({ snapshot: true });
  const generation = useRef(0);
  const [snapshotRetry, setSnapshotRetry] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(prev => ({ ...prev, snapshot: true }));
    api.get('/api/principal/', params('snapshot', day, ''))
      .then(({ data: result }) => {
        if (!active) return;
        setSnapshot(result);
        setSnapshotError('');
        setTerm(current => current || String(result.term || ''));
      })
      .catch(error => { if (active) { setSnapshot(null); setSnapshotError(classifyRequestFailure(error).message); } })
      .finally(() => { if (active) setLoading(prev => ({ ...prev, snapshot: false })); });
    return () => { active = false; };
  }, [day, snapshotRetry]);

  const loadSection = useCallback((name, selectedDay, selectedTerm, token) => {
    setLoading(prev => ({ ...prev, [name]: true }));
    setErrors(prev => ({ ...prev, [name]: '' }));
    return api.get('/api/principal/', params(name, selectedDay, selectedTerm))
      .then(({ data: result }) => {
        if (generation.current === token) setData(prev => ({ ...prev, [name]: result }));
      })
      .catch(error => {
        if (generation.current !== token) return;
        setData(prev => ({ ...prev, [name]: null }));
        setErrors(prev => ({ ...prev, [name]: classifyRequestFailure(error).message }));
      })
      .finally(() => {
        if (generation.current === token) setLoading(prev => ({ ...prev, [name]: false }));
      });
  }, []);

  useEffect(() => {
    const token = ++generation.current;
    setData({});
    setErrors({});
    if (term) sections.forEach(name => loadSection(name, day, term, token));
    return () => { generation.current += 1; };
  }, [day, term, loadSection]);

  const retry = name => loadSection(name, day, term, generation.current);
  const selectedTerm = snapshot?.terms?.find(t => String(t.id) === term);
  const dated = `date=${encodeURIComponent(day)}&term=${encodeURIComponent(term)}`;
  const teachingLink = outcome => `/admin/teaching?${dated}&outcome=${outcome}`;
  const attendanceLink = classArm => `/admin/attendance?term=${term}${classArm ? `&class_arm=${classArm}` : ''}`;
  const resultLink = (classArm, subject) => `/admin/results?term=${term}${classArm ? `&class_arm=${classArm}` : ''}${subject ? `&subject=${subject}` : ''}`;
  const curriculumLink = row => `/admin/curriculum?term=${term}&class_level=${row.class_level}&subject=${row.subject}&class_arm=${row.class_arm}`;

  return <main className="page-shell admin-dash">
    <WorkspaceHome compact />
    <header className="dash-header-row"><div><h1 className="page-title">Principal Command Centre</h1>
      <p>Live operational records for your school.</p></div>
      <div className="dash-controls"><label>School date <input aria-label="School date" type="date" max={today()} value={day}
        onChange={event => {
          const next = event.target.value;
          setDay(next);
          const matching = snapshot?.terms?.find(t => t.start_date <= next && next <= t.end_date);
          setTerm(matching ? String(matching.id) : '');
        }} /></label>
        <label>Academic term <select aria-label="Academic term" value={term} onChange={event => setTerm(event.target.value)}>
          <option value="">Choose a term</option>
          {(snapshot?.terms || []).map(t => <option key={t.id} value={t.id}>{t.session__name} · {t.name} term</option>)}
        </select></label></div></header>
    {loading.snapshot ? <p>Loading school snapshot…</p> : snapshotError ?
      <p role="alert">School snapshot unavailable — {snapshotError} <button onClick={() => setSnapshotRetry(x => x + 1)} type="button">Retry</button></p> :
      <div className="kpi-row"><Link to="/admin/students" className="kpi-card"><span>Active students</span><strong>{snapshot?.active_students}</strong></Link>
        <Link to="/admin/staff" className="kpi-card"><span>Active teachers</span><strong>{snapshot?.active_teachers}</strong></Link></div>}
    <p className="principal-context">{selectedTerm ? `Academic context: ${selectedTerm.session__name} · ${selectedTerm.name} term. Attendance and teaching use ${day}; curriculum, results and fees use the selected term.`
      : 'No term selected for this date. Choose a term to inspect term operations.'}</p>
    <div className="principal-grid">
      <Section name="attendance" data={data.attendance} error={errors.attendance} loading={loading.attendance} retry={retry}>{item =>
        item.state === 'non_teaching' ? <p>{item.holiday} — no attendance expected.</p> : item.state === 'outside_term' ? <p>Selected date is outside this term.</p> : <>
          <p>{item.state === 'no_records' ? 'No attendance marks recorded for this date.' :
            `${item.marks.present} present · ${item.marks.late} late · ${item.marks.absent} absent · ${item.marks.excused} excused marks`}</p>
          <p>{item.classes_with_records} of {item.classes_expected} classes with active students have finalized attendance registers. Per-period schools may record multiple marks per student.</p>
          {item.classes_without_records.length > 0 && <><h3>Classes without finalized registers</h3><ul>{item.classes_without_records.map(row =>
            <li key={row.id}><Link to={attendanceLink(row.id)}>{row.name}</Link></li>)}</ul></>}
          {['absent', 'late'].map(status => item.examples?.[status]?.length > 0 &&
            <div key={status}><h3>{status === 'absent' ? 'Absent' : 'Late'} students (first 8)</h3><ul>
              {item.examples[status].map(row => <li key={`${row.student__student_profile__id}-${row.attendance_session__class_arm_id}`}>
                <Link to={attendanceLink(row.attendance_session__class_arm_id)}>{row.student__first_name} {row.student__last_name}</Link>
              </li>)}</ul></div>)}
          <Link to={attendanceLink()}>Inspect attendance</Link>
        </>}
      </Section>
      <Section name="teaching" data={data.teaching} error={errors.teaching} loading={loading.teaching} retry={retry}>{item =>
        item.state === 'non_teaching' ? <p>{item.holiday} — no scheduled lessons expected.</p>
          : item.state === 'outside_term' ? <p>Selected date is outside this term.</p>
          : <><p>{item.state === 'recorded_history' ? 'Recorded historical outcomes only; the old timetable is not versioned.' :
            item.state === 'no_lessons' ? 'No lessons scheduled or recorded for this date.' : `${item.scheduled} dated lessons`}</p>
            <div className="principal-facts">{Object.entries(item.counts).map(([state, count]) =>
              <Link key={state} to={teachingLink(state)}>{state === 'unresolved' ? 'Outcome not recorded' : state}: {count}</Link>)}</div>
            {item.queue?.length > 0 && <><h3>Outcomes to record</h3><ul>{item.queue.map(row =>
              <li key={row.slot_id}>{row.class_name} · {row.subject_name} · {row.period_name} <Link to={teachingLink('unresolved')}>Inspect</Link></li>)}</ul></>}
          </>}
      </Section>
      <Section name="curriculum" data={data.curriculum} error={errors.curriculum} loading={loading.curriculum} retry={retry}>{item =>
        item.state === 'unconfigured' ? <p>No curriculum plan is configured for this term. <Link to="/admin/curriculum">Set up a scheme of work</Link>.</p> :
        item.state === 'no_term' ? <p>Select a term first.</p> : <><p>Only explicit lesson-linked topic coverage is counted.</p>
          <ul>{item.groups.map(row => <li key={`${row.class_arm}-${row.subject}`}><Link to={curriculumLink(row)}>{row.class_name} · {row.subject_name}</Link>
            {' '}{row.covered}/{row.planned} covered · {row.partial} partial · {row.not_started} not started</li>)}</ul>
          {item.groups.length === 0 && <p>No classes have a plan yet.</p>}</>}
      </Section>
      <Section name="results" data={data.results} error={errors.results} loading={loading.results} retry={retry}>{item =>
        item.state === 'no_term' ? <p>Select a term first.</p> : <><p>{item.state === 'no_submissions' ? 'No submitted, approved or published score entries.' :
          `${item.counts.submitted} score entries submitted for review · ${item.counts.approved} approved but unpublished · ${item.counts.published} published`}</p>
          <ul>{item.groups.filter(row => row.submitted || row.approved).map(row =>
            <li key={`${row.class_arm}-${row.subject}`}><Link to={resultLink(row.class_arm, row.subject)}>{row.class_name} · {row.subject_name}</Link>: {row.submitted} submitted, {row.approved} approved</li>)}</ul>
          <Link to={resultLink()}>Inspect results</Link></>}
      </Section>
      <Section name="finance" data={data.finance} error={errors.finance} loading={loading.finance} retry={retry}>{item =>
        item.state === 'unconfigured' ? <p>No fee schedules configured for this term. <Link to="/admin/fee-setup">Set up fees</Link>.</p>
          : item.state === 'no_term' ? <p>Select a term first.</p>
          : <><p>{item.configured_schedules} configured schedules · {item.recorded_payments} recorded payments</p>
            <p>₦{Number(item.recorded_amount).toLocaleString('en-NG')} recorded against those schedules. This is not a receivables or cash ledger total.</p>
            <p>{item.debtor_count} verified debtor accounts · ₦{Number(item.known_outstanding).toLocaleString('en-NG')} known outstanding across their full accounts.</p>
            {!!item.unknown_accounts && <p role="status">{item.unknown_accounts} student accounts still need charge generation or opening-balance verification; the known total excludes them.</p>}
            <Link to="/admin/fee-collection">Inspect payments and balances</Link></>}
      </Section>
    </div>
  </main>;
}
