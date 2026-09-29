import React, { useCallback, useEffect, useState } from 'react';
import api from '../../services/api';
import { useAuth } from '../../hooks/useAuth';
import { classifyRequestFailure } from '../../services/requestState';
import '../teacher/TeachingOperations.css';

export default function AcademicPlanning() {
  const { user } = useAuth();
  const admin = user?.role === 'school_admin';
  const [assignments, setAssignments] = useState([]);
  const [plans, setPlans] = useState([]);
  const [resources, setResources] = useState([]);
  const [selected, setSelected] = useState('');
  const [scheme, setScheme] = useState(null);
  const [planForm, setPlanForm] = useState({ curriculum_topic: '', title: '', objectives: '', activities: '', assessment: '' });
  const [resourceForm, setResourceForm] = useState({ title: '', kind: 'note', content: '' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const load = useCallback(async () => {
    setError('');
    try {
      const [assignmentRes, planRes, resourceRes] = await Promise.all([
        api.get('/api/curriculum/assignments/'),
        api.get('/api/curriculum/lesson-plans/'),
        api.get('/api/curriculum/resources/'),
      ]);
      setAssignments(assignmentRes.data.assignments || []);
      setPlans(planRes.data.lesson_plans || []);
      setResources(resourceRes.data.resources || []);
    } catch (err) { setError(classifyRequestFailure(err).message); }
  }, []);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    const item = assignments[Number(selected)];
    if (!item) { setScheme(null); return; }
    api.get('/api/curriculum/plans/', { params: {
      term: item.term, class_level: item.class_level, subject: item.subject, class_arm: item.class_arm,
    }}).then(({ data }) => setScheme(data.plan))
      .catch(err => setError(classifyRequestFailure(err).message));
  }, [assignments, selected]);

  const mutate = async work => {
    if (busy) return;
    setBusy(true); setError(''); setNotice('');
    try { await work(); await load(); }
    catch (err) { setError(err.response?.data?.detail || Object.values(err.response?.data || {})[0] || classifyRequestFailure(err, { mutation: true }).message); }
    finally { setBusy(false); }
  };

  const assignment = assignments[Number(selected)];
  const topicOptions = (scheme?.weeks || []).flatMap(week => week.topics.filter(topic => !topic.archived).map(topic => ({
    id: topic.id, label: 'Week ' + week.number + ' · ' + topic.title,
  })));

  return <main className="teaching-page">
    <header className="teaching-header"><div><h1>{admin ? 'Lesson Planning & Academic Resources' : 'My Lesson Planning & Resources'}</h1>
      <p>Plan teaching and preserve reusable school-approved resources. Planning does not count as lesson delivery.</p></div></header>
    {error && <p role="alert" className="teaching-error">{error}</p>}
    {notice && <p role="status" className="teaching-notice">{notice}</p>}

    {!admin && <section className="teaching-card"><h2>Choose assignment</h2>
      <label>Assigned class and subject <select aria-label="Assigned class and subject" value={selected} onChange={e => setSelected(e.target.value)}>
        <option value="">Choose an assignment</option>
        {assignments.map((item, index) => <option key={item.term + '-' + item.class_arm + '-' + item.subject} value={index}>
          {item.class_name} · {item.subject_name} · {item.term_name}
        </option>)}
      </select></label>
    </section>}

    {!admin && assignment && <section className="teaching-card"><h2>Create lesson plan</h2>
      {!scheme ? <p>No scheme of work is configured for this assignment yet.</p> : <div className="teaching-editor">
        <label>Curriculum topic <select value={planForm.curriculum_topic} onChange={e => setPlanForm({ ...planForm, curriculum_topic: e.target.value })}>
          <option value="">Choose topic</option>{topicOptions.map(topic => <option key={topic.id} value={topic.id}>{topic.label}</option>)}
        </select></label>
        <label>Plan title <input value={planForm.title} onChange={e => setPlanForm({ ...planForm, title: e.target.value })}/></label>
        <label>Objectives <textarea value={planForm.objectives} onChange={e => setPlanForm({ ...planForm, objectives: e.target.value })}/></label>
        <label>Teaching activities <textarea value={planForm.activities} onChange={e => setPlanForm({ ...planForm, activities: e.target.value })}/></label>
        <label>Assessment approach <textarea value={planForm.assessment} onChange={e => setPlanForm({ ...planForm, assessment: e.target.value })}/></label>
        <button disabled={busy || !planForm.curriculum_topic || !planForm.title.trim()} onClick={() => mutate(async () => {
          await api.post('/api/curriculum/lesson-plans/', {
            term: assignment.term, class_arm: assignment.class_arm, subject: assignment.subject,
            curriculum_topic: planForm.curriculum_topic, title: planForm.title,
            objectives: planForm.objectives, activities: planForm.activities, assessment: planForm.assessment,
          });
          setPlanForm({ curriculum_topic: '', title: '', objectives: '', activities: '', assessment: '' });
          setNotice('Lesson plan draft created.');
        })}>Save draft</button>
      </div>}
    </section>}

    <section className="teaching-card"><h2>{admin ? 'Lesson-plan review queue' : 'My lesson plans'}</h2>
      {plans.length === 0 ? <p>No lesson plans yet.</p> : <div className="teaching-list">{plans.map(plan => <article className="curriculum-topic" key={plan.id}>
        <strong>{plan.title}</strong> · {plan.class_name} · {plan.subject_name}
        <p>{plan.curriculum_topic_title} · revision {plan.revision} · <strong>{plan.status}</strong></p>
        {!admin && plan.status === 'draft' && <button disabled={busy} onClick={() => mutate(async () => {
          await api.post('/api/curriculum/lesson-plans/' + plan.id + '/transition/', { action: 'submit' }); setNotice('Lesson plan submitted.');
        })}>Submit for review</button>}
        {admin && plan.status === 'submitted' && <button disabled={busy} onClick={() => mutate(async () => {
          await api.post('/api/curriculum/lesson-plans/' + plan.id + '/transition/', { action: 'review' }); setNotice('Lesson plan reviewed.');
        })}>Mark reviewed</button>}
        {admin && plan.status === 'reviewed' && <button disabled={busy} onClick={() => mutate(async () => {
          await api.post('/api/curriculum/lesson-plans/' + plan.id + '/transition/', { action: 'approve' }); setNotice('Lesson plan approved.');
        })}>Approve</button>}
      </article>)}</div>}
    </section>

    {!admin && assignment && <section className="teaching-card"><h2>Add academic resource</h2>
      <div className="teaching-editor">
        <label>Title <input value={resourceForm.title} onChange={e => setResourceForm({ ...resourceForm, title: e.target.value })}/></label>
        <label>Type <select value={resourceForm.kind} onChange={e => setResourceForm({ ...resourceForm, kind: e.target.value })}>
          <option value="note">Lesson note</option><option value="handout">Handout</option><option value="slide">Slide / presentation</option>
          <option value="worksheet">Worksheet</option><option value="other">Other</option>
        </select></label>
        <label>Content <textarea value={resourceForm.content} onChange={e => setResourceForm({ ...resourceForm, content: e.target.value })}/></label>
        <button disabled={busy || !resourceForm.title.trim()} onClick={() => mutate(async () => {
          await api.post('/api/curriculum/resources/', {
            class_level: assignment.class_level, subject: assignment.subject,
            title: resourceForm.title, kind: resourceForm.kind, content: resourceForm.content,
          });
          setResourceForm({ title: '', kind: 'note', content: '' }); setNotice('Academic resource draft created.');
        })}>Save resource draft</button>
      </div>
    </section>}

    <section className="teaching-card"><h2>{admin ? 'Academic resource review & continuity' : 'Academic resources'}</h2>
      <p>Approved resources become part of the school’s institutional academic memory and remain available when staff change.</p>
      {resources.length === 0 ? <p>No academic resources yet.</p> : <div className="teaching-list">{resources.map(resource => <article className="curriculum-topic" key={resource.id}>
        <strong>{resource.title}</strong> · {resource.class_level_name} · {resource.subject_name} · {resource.kind}
        <p>Revision {resource.revision} · <strong>{resource.status}</strong>{resource.supersedes ? ' · supersedes #' + resource.supersedes : ''}</p>
        {resource.content && <p>{resource.content}</p>}
        {!admin && resource.status === 'draft' && <button disabled={busy} onClick={() => mutate(async () => {
          await api.post('/api/curriculum/resources/' + resource.id + '/transition/', { action: 'submit' }); setNotice('Resource submitted for review.');
        })}>Submit for review</button>}
        {admin && resource.status === 'submitted' && <button disabled={busy} onClick={() => mutate(async () => {
          await api.post('/api/curriculum/resources/' + resource.id + '/transition/', { action: 'review' }); setNotice('Resource reviewed.');
        })}>Mark reviewed</button>}
        {admin && resource.status === 'reviewed' && <button disabled={busy} onClick={() => mutate(async () => {
          await api.post('/api/curriculum/resources/' + resource.id + '/transition/', { action: 'approve' }); setNotice('Resource approved.');
        })}>Approve</button>}
        {resource.status === 'approved' && <button disabled={busy} onClick={() => mutate(async () => {
          await api.post('/api/curriculum/resources/' + resource.id + '/revise/', {}); setNotice('New resource revision created without changing approved history.');
        })}>Create new revision</button>}
      </article>)}</div>}
    </section>
  </main>;
}
