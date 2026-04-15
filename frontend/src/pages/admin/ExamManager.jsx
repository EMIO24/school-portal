/**
 * frontend/src/pages/admin/ExamManager.jsx
 *
 * Admin exam management:
 *   - List of all exams with status badges + quick actions
 *   - Create / Edit exam modal:
 *       Basic info (title, subject, class arms, term, session, dates, duration)
 *       Selection mode: manual question picker OR random config builder
 *       Settings toggles (randomize, allow_review, show_score_immediately)
 *       Publish / save as draft
 */

import React, { useState, useEffect, useCallback } from 'react';
import api from '../../services/api';
import '../../styles/ExamManager.css';

const STATUS_META = {
  draft:     { label: 'Draft',     cls: 'em-badge--draft' },
  published: { label: 'Published', cls: 'em-badge--published' },
  ongoing:   { label: 'Ongoing',   cls: 'em-badge--ongoing' },
  completed: { label: 'Completed', cls: 'em-badge--completed' },
};

function formatDT(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-GB', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

// ── Random config rule row ────────────────────────────────────────────────────
function RandomRule({ rule, topics, onChange, onRemove }) {
  return (
    <div className="em-rule-row">
      <select
        className="em-select em-rule-select"
        value={rule.topic_id || ''}
        onChange={e => onChange({ ...rule, topic_id: e.target.value || null })}
      >
        <option value="">Any topic</option>
        {topics.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
      </select>
      <select
        className="em-select em-rule-select"
        value={rule.difficulty || ''}
        onChange={e => onChange({ ...rule, difficulty: e.target.value || null })}
      >
        <option value="">Any difficulty</option>
        <option value="easy">Easy</option>
        <option value="medium">Medium</option>
        <option value="hard">Hard</option>
      </select>
      <input
        type="number"
        className="em-input em-rule-count"
        min={1}
        max={100}
        value={rule.count}
        onChange={e => onChange({ ...rule, count: parseInt(e.target.value, 10) || 1 })}
        placeholder="Count"
      />
      <button className="em-rule-remove" onClick={onRemove}>✕</button>
    </div>
  );
}

// ── Exam form modal ────────────────────────────────────────────────────────────
function ExamModal({ exam, subjects, classArms, terms, sessions, onSaved, onClose }) {
  const isEdit = Boolean(exam?.id);

  const blank = {
    title: '', subject: '', class_arms: [], term: '', session: '',
    start_datetime: '', end_datetime: '', duration_minutes: 60,
    instructions: '', selection_mode: 'random_from_bank',
    manual_questions: [], random_config: [],
    randomize_questions: true, randomize_options: true,
    allow_review: true, show_score_immediately: true,
    status: 'draft',
  };

  const [form,    setForm]    = useState(() => exam ? { ...blank, ...exam,
    class_arms: exam.class_arms_ids ?? [],
  } : blank);
  const [topics,  setTopics]  = useState([]);
  const [questions, setQuestions] = useState([]);
  const [saving,  setSaving]  = useState(false);
  const [error,   setError]   = useState('');

  const set = (key, val) => setForm(f => ({ ...f, [key]: val }));

  // Load topics when subject changes
  useEffect(() => {
    if (!form.subject) { setTopics([]); return; }
    api.get(`/cbt/topics/?subject=${form.subject}`)
      .then(({ data }) => setTopics(data.results ?? data))
      .catch(() => setTopics([]));
  }, [form.subject]);

  // Load questions for manual picker
  useEffect(() => {
    if (form.selection_mode !== 'manual' || !form.subject) return;
    api.get(`/cbt/questions/?subject=${form.subject}&is_active=true`)
      .then(({ data }) => setQuestions(data.results ?? data))
      .catch(() => setQuestions([]));
  }, [form.selection_mode, form.subject]);

  const toggleArm = (id) => {
    set('class_arms', form.class_arms.includes(id)
      ? form.class_arms.filter(a => a !== id)
      : [...form.class_arms, id]);
  };

  const toggleQuestion = (id) => {
    set('manual_questions', form.manual_questions.includes(id)
      ? form.manual_questions.filter(q => q !== id)
      : [...form.manual_questions, id]);
  };

  const addRule = () => set('random_config', [
    ...form.random_config, { topic_id: null, difficulty: null, count: 5 },
  ]);

  const updateRule = (idx, val) => {
    const next = [...form.random_config];
    next[idx] = val;
    set('random_config', next);
  };

  const removeRule = (idx) => {
    set('random_config', form.random_config.filter((_, i) => i !== idx));
  };

  const handleSave = async (publishNow = false) => {
    if (!form.title.trim())     { setError('Title is required.');         return; }
    if (!form.subject)          { setError('Subject is required.');        return; }
    if (!form.term)             { setError('Term is required.');           return; }
    if (!form.session)          { setError('Session is required.');        return; }
    if (!form.start_datetime)   { setError('Start date/time required.');   return; }
    if (!form.end_datetime)     { setError('End date/time required.');     return; }

    setSaving(true);
    setError('');

    const payload = {
      ...form,
      status: publishNow ? 'published' : form.status,
    };

    try {
      const { data } = isEdit
        ? await api.patch(`/cbt/exams/${exam.id}/`, payload)
        : await api.post('/cbt/exams/', payload);
      onSaved(data);
    } catch (err) {
      const d = err?.response?.data;
      setError(typeof d === 'string' ? d : JSON.stringify(d));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="em-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="em-modal">

        <div className="em-modal-header">
          <h2>{isEdit ? 'Edit Exam' : 'New Exam'}</h2>
          <button className="em-close" onClick={onClose}>✕</button>
        </div>

        <div className="em-modal-body">

          {/* Title */}
          <div className="em-field">
            <label className="em-label">Title *</label>
            <input className="em-input" value={form.title}
              onChange={e => set('title', e.target.value)} placeholder="e.g. SS2 Chemistry Mid-Term" />
          </div>

          {/* Subject + Duration */}
          <div className="em-row">
            <div className="em-field">
              <label className="em-label">Subject *</label>
              <select className="em-select" value={form.subject} onChange={e => set('subject', e.target.value)}>
                <option value="">— select —</option>
                {subjects.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </div>
            <div className="em-field">
              <label className="em-label">Duration (min)</label>
              <input className="em-input" type="number" min={1} value={form.duration_minutes}
                onChange={e => set('duration_minutes', parseInt(e.target.value, 10) || 60)} />
            </div>
          </div>

          {/* Term + Session */}
          <div className="em-row">
            <div className="em-field">
              <label className="em-label">Term *</label>
              <select className="em-select" value={form.term} onChange={e => set('term', e.target.value)}>
                <option value="">— select —</option>
                {terms.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
            </div>
            <div className="em-field">
              <label className="em-label">Session *</label>
              <select className="em-select" value={form.session} onChange={e => set('session', e.target.value)}>
                <option value="">— select —</option>
                {sessions.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </div>
          </div>

          {/* Start + End datetime */}
          <div className="em-row">
            <div className="em-field">
              <label className="em-label">Start Date/Time *</label>
              <input className="em-input" type="datetime-local" value={form.start_datetime?.slice(0, 16) ?? ''}
                onChange={e => set('start_datetime', e.target.value)} />
            </div>
            <div className="em-field">
              <label className="em-label">End Date/Time *</label>
              <input className="em-input" type="datetime-local" value={form.end_datetime?.slice(0, 16) ?? ''}
                onChange={e => set('end_datetime', e.target.value)} />
            </div>
          </div>

          {/* Class arms */}
          <div className="em-field">
            <label className="em-label">Class Arms</label>
            <div className="em-checkbox-grid">
              {classArms.map(arm => (
                <label key={arm.id} className="em-checkbox-label">
                  <input type="checkbox"
                    checked={form.class_arms.includes(arm.id)}
                    onChange={() => toggleArm(arm.id)} />
                  {arm.full_name ?? arm.name}
                </label>
              ))}
            </div>
          </div>

          {/* Instructions */}
          <div className="em-field">
            <label className="em-label">Instructions</label>
            <textarea className="em-textarea" value={form.instructions}
              onChange={e => set('instructions', e.target.value)}
              placeholder="Optional instructions shown to students before they start…" rows={3} />
          </div>

          {/* Selection mode */}
          <div className="em-field">
            <label className="em-label">Question Selection</label>
            <div className="em-radio-group">
              {[
                { val: 'random_from_bank', label: 'Random from Question Bank' },
                { val: 'manual',           label: 'Manual — pick questions' },
              ].map(opt => (
                <label key={opt.val} className="em-radio-label">
                  <input type="radio" name="selection_mode" value={opt.val}
                    checked={form.selection_mode === opt.val}
                    onChange={() => set('selection_mode', opt.val)} />
                  {opt.label}
                </label>
              ))}
            </div>
          </div>

          {/* Random config builder */}
          {form.selection_mode === 'random_from_bank' && (
            <div className="em-field">
              <label className="em-label">Random Rules</label>
              <div className="em-rules-list">
                {form.random_config.map((rule, i) => (
                  <RandomRule
                    key={i}
                    rule={rule}
                    topics={topics}
                    onChange={val => updateRule(i, val)}
                    onRemove={() => removeRule(i)}
                  />
                ))}
              </div>
              <button className="em-add-rule-btn" onClick={addRule}>+ Add Rule</button>
              <p className="em-hint">
                Total questions = sum of all rule counts. Leave topic/difficulty blank to draw from all.
              </p>
            </div>
          )}

          {/* Manual question picker */}
          {form.selection_mode === 'manual' && (
            <div className="em-field">
              <label className="em-label">
                Select Questions ({form.manual_questions.length} selected)
              </label>
              <div className="em-q-picker">
                {questions.length === 0
                  ? <p className="em-hint">Select a subject above to load questions.</p>
                  : questions.map(q => (
                    <label key={q.id} className={`em-q-row${form.manual_questions.includes(q.id) ? ' em-q-row--selected' : ''}`}>
                      <input type="checkbox"
                        checked={form.manual_questions.includes(q.id)}
                        onChange={() => toggleQuestion(q.id)} />
                      <span className="em-q-text">{q.question_text.slice(0, 80)}{q.question_text.length > 80 ? '…' : ''}</span>
                      <span className={`em-q-diff em-q-diff--${q.difficulty}`}>{q.difficulty}</span>
                    </label>
                  ))
                }
              </div>
            </div>
          )}

          {/* Settings toggles */}
          <div className="em-field">
            <label className="em-label">Settings</label>
            <div className="em-toggles">
              {[
                { key: 'randomize_questions',    label: 'Randomize question order' },
                { key: 'randomize_options',      label: 'Randomize option order' },
                { key: 'allow_review',           label: 'Allow post-exam review' },
                { key: 'show_score_immediately', label: 'Show score immediately after submit' },
              ].map(({ key, label }) => (
                <label key={key} className="em-toggle-label">
                  <input type="checkbox"
                    checked={form[key]}
                    onChange={e => set(key, e.target.checked)} />
                  {label}
                </label>
              ))}
            </div>
          </div>

          {error && (
            <div className="em-error">⚠ {error}</div>
          )}
        </div>

        <div className="em-modal-footer">
          <button className="em-btn em-btn--ghost" onClick={onClose} disabled={saving}>Cancel</button>
          <button className="em-btn em-btn--ghost" onClick={() => handleSave(false)} disabled={saving}>
            {saving ? 'Saving…' : 'Save Draft'}
          </button>
          <button className="em-btn em-btn--navy" onClick={() => handleSave(true)} disabled={saving}>
            {saving ? 'Saving…' : isEdit ? 'Update & Publish' : 'Save & Publish'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────
export default function ExamManager() {
  const [exams,      setExams]      = useState([]);
  const [loading,    setLoading]    = useState(true);
  const [subjects,   setSubjects]   = useState([]);
  const [classArms,  setClassArms]  = useState([]);
  const [terms,      setTerms]      = useState([]);
  const [sessions,   setSessions]   = useState([]);
  const [modalOpen,  setModalOpen]  = useState(false);
  const [editingExam, setEditingExam] = useState(null);

  const loadAll = useCallback(() => {
    setLoading(true);
    Promise.all([
      api.get('/cbt/exams/'),
      api.get('/enrollment/subjects/'),
      api.get('/enrollment/class-arms/'),
      api.get('/academics/terms/'),
      api.get('/academics/sessions/'),
    ]).then(([e, s, a, t, ses]) => {
      setExams(e.data.results ?? e.data);
      setSubjects(s.data.results ?? s.data);
      setClassArms(a.data.results ?? a.data);
      setTerms(t.data.results ?? t.data);
      setSessions(ses.data.results ?? ses.data);
    }).finally(() => setLoading(false));
  }, []);

  useEffect(() => { loadAll(); }, [loadAll]);

  const openNew  = () => { setEditingExam(null); setModalOpen(true); };
  const openEdit = (exam) => { setEditingExam(exam); setModalOpen(true); };

  const handleSaved = (saved) => {
    setExams(prev => {
      const idx = prev.findIndex(e => e.id === saved.id);
      if (idx >= 0) { const n = [...prev]; n[idx] = saved; return n; }
      return [saved, ...prev];
    });
    setModalOpen(false);
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this exam? This cannot be undone.')) return;
    await api.delete(`/cbt/exams/${id}/`);
    setExams(prev => prev.filter(e => e.id !== id));
  };

  const handlePublish = async (exam) => {
    const { data } = await api.patch(`/cbt/exams/${exam.id}/`, { status: 'published' });
    setExams(prev => prev.map(e => e.id === data.id ? data : e));
  };

  return (
    <div className="em-page">

      <div className="em-header">
        <h1>Exam Manager</h1>
        <button className="em-new-btn" onClick={openNew}>+ New Exam</button>
      </div>

      {loading ? (
        <div className="em-grid">
          {Array.from({ length: 4 }).map((_, i) => <div key={i} className="em-skeleton" />)}
        </div>
      ) : exams.length === 0 ? (
        <div className="em-empty">
          <strong>No exams yet</strong>
          <span>Click "New Exam" to create your first exam.</span>
        </div>
      ) : (
        <div className="em-list">
          {exams.map(exam => {
            const meta = STATUS_META[exam.status] ?? STATUS_META.draft;
            return (
              <div key={exam.id} className="em-row-card">
                <div className="em-row-main">
                  <span className={`em-badge ${meta.cls}`}>{meta.label}</span>
                  <span className="em-row-title">{exam.title}</span>
                  <span className="em-row-subject">{exam.subject_name}</span>
                </div>
                <div className="em-row-meta">
                  <span>⏱ {exam.duration_minutes}min</span>
                  <span>📅 {formatDT(exam.start_datetime)}</span>
                  {exam.class_arms_display?.length > 0 && (
                    <span>🏫 {exam.class_arms_display.join(', ')}</span>
                  )}
                </div>
                <div className="em-row-actions">
                  {exam.status === 'draft' && (
                    <button className="em-action-btn em-action-btn--publish"
                      onClick={() => handlePublish(exam)}>
                      Publish
                    </button>
                  )}
                  <button className="em-action-btn" onClick={() => openEdit(exam)}>Edit</button>
                  <button className="em-action-btn em-action-btn--delete"
                    onClick={() => handleDelete(exam.id)}>
                    Delete
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {modalOpen && (
        <ExamModal
          exam={editingExam}
          subjects={subjects}
          classArms={classArms}
          terms={terms}
          sessions={sessions}
          onSaved={handleSaved}
          onClose={() => setModalOpen(false)}
        />
      )}
    </div>
  );
}
