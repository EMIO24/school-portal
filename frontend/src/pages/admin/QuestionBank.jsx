/**
 * frontend/src/pages/admin/QuestionBank.jsx
 *
 * Admin question bank:
 *   - Filter sidebar (subject, class level, topic, difficulty, type)
 *   - Question cards grid with edit/delete
 *   - Stats chips (total, by difficulty)
 *   - Add Question → QuestionEditor modal
 */

import React, { useState, useEffect, useCallback } from 'react';
import api from '../../services/api';
import QuestionEditor from '../../components/cbt/QuestionEditor';
import '../../styles/QuestionBank.css';

const DIFFICULTY_LABELS = { easy: 'Easy', medium: 'Medium', hard: 'Hard' };
const TYPE_LABELS       = { mcq: 'MCQ', true_false: 'True/False', fill_blank: 'Fill Blank' };

export default function QuestionBank() {
  // Reference data
  const [subjects,     setSubjects]    = useState([]);
  const [classLevels,  setClassLevels] = useState([]);
  const [topics,       setTopics]      = useState([]);

  // Filter state
  const [filters, setFilters] = useState({
    subject: '', class_level: '', topic: '', difficulty: '', question_type: '',
  });
  const [search, setSearch] = useState('');

  // Questions
  const [questions, setQuestions] = useState([]);
  const [stats,     setStats]     = useState(null);
  const [loading,   setLoading]   = useState(false);

  // Editor modal
  const [editorOpen,     setEditorOpen]     = useState(false);
  const [editingQuestion, setEditingQuestion] = useState(null);

  // ── Boot ────────────────────────────────────────────────────────────────────
  useEffect(() => {
    Promise.all([
      api.get('/enrollment/subjects/'),
      api.get('/enrollment/class-levels/'),
      api.get('/cbt/questions/stats/'),
    ]).then(([s, c, st]) => {
      setSubjects(s.data.results    ?? s.data);
      setClassLevels(c.data.results ?? c.data);
      setStats(st.data);
    });
  }, []);

  // Load topics when subject + class_level filters change
  useEffect(() => {
    if (!filters.subject || !filters.class_level) { setTopics([]); return; }
    api.get(`/cbt/topics/?subject=${filters.subject}&class_level=${filters.class_level}`)
      .then(({ data }) => setTopics(data.results ?? data));
  }, [filters.subject, filters.class_level]);

  // ── Load questions ───────────────────────────────────────────────────────────
  const loadQuestions = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([k, v]) => { if (v) params.append(k, v); });
    if (search.trim()) params.append('search', search.trim());

    try {
      const { data } = await api.get(`/cbt/questions/?${params}`);
      setQuestions(data.results ?? data);
    } finally {
      setLoading(false);
    }
  }, [filters, search]);

  useEffect(() => { loadQuestions(); }, [loadQuestions]);

  // Refresh stats after any mutation
  const refreshStats = () => {
    api.get('/cbt/questions/stats/').then(({ data }) => setStats(data));
  };

  // ── Filter helpers ───────────────────────────────────────────────────────────
  const setFilter = (key, val) => {
    setFilters(f => {
      const next = { ...f, [key]: val };
      // Clear topic when subject or class_level changes
      if (key === 'subject' || key === 'class_level') next.topic = '';
      return next;
    });
  };

  const clearFilters = () => {
    setFilters({ subject: '', class_level: '', topic: '', difficulty: '', question_type: '' });
    setSearch('');
  };

  // ── Delete ───────────────────────────────────────────────────────────────────
  const handleDelete = async (id) => {
    if (!window.confirm('Delete this question? This cannot be undone.')) return;
    await api.delete(`/cbt/questions/${id}/`);
    setQuestions(qs => qs.filter(q => q.id !== id));
    refreshStats();
  };

  // ── Editor callbacks ─────────────────────────────────────────────────────────
  const openNew  = () => { setEditingQuestion(null); setEditorOpen(true); };
  const openEdit = (q) => { setEditingQuestion(q);   setEditorOpen(true); };

  const handleSaved = (saved) => {
    setQuestions(qs => {
      const idx = qs.findIndex(q => q.id === saved.id);
      if (idx >= 0) {
        const next = [...qs]; next[idx] = saved; return next;
      }
      return [saved, ...qs];
    });
    setEditorOpen(false);
    refreshStats();
  };

  // ── Render ────────────────────────────────────────────────────────────────────
  return (
    <div className="qb-page">

      {/* ── Sidebar ── */}
      <aside className="qb-sidebar">
        <div className="qb-sidebar-head"><h2>Filters</h2></div>

        <div className="qb-filter-group">
          <label className="qb-filter-label">Subject</label>
          <select className="qb-filter-select" value={filters.subject} onChange={e => setFilter('subject', e.target.value)}>
            <option value="">All subjects</option>
            {subjects.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </div>

        <div className="qb-filter-group">
          <label className="qb-filter-label">Class Level</label>
          <select className="qb-filter-select" value={filters.class_level} onChange={e => setFilter('class_level', e.target.value)}>
            <option value="">All levels</option>
            {classLevels.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>

        <div className="qb-filter-group">
          <label className="qb-filter-label">Topic</label>
          <select className="qb-filter-select" value={filters.topic} onChange={e => setFilter('topic', e.target.value)}
            disabled={!topics.length}>
            <option value="">All topics</option>
            {topics.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </div>

        <div className="qb-filter-group">
          <label className="qb-filter-label">Difficulty</label>
          <select className="qb-filter-select" value={filters.difficulty} onChange={e => setFilter('difficulty', e.target.value)}>
            <option value="">All</option>
            {Object.entries(DIFFICULTY_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>

        <div className="qb-filter-group">
          <label className="qb-filter-label">Type</label>
          <select className="qb-filter-select" value={filters.question_type} onChange={e => setFilter('question_type', e.target.value)}>
            <option value="">All types</option>
            {Object.entries(TYPE_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>

        <div style={{ padding: '0 16px' }}>
          <button className="qb-clear-btn" onClick={clearFilters}>✕ Clear Filters</button>
        </div>

        {/* Stats */}
        {stats && (
          <div className="qb-stats">
            <div className="qb-stat-chip">
              <span>Total Questions</span>
              <span className="qb-stat-chip__val">{stats.total}</span>
            </div>
            {['easy', 'medium', 'hard'].map(d => (
              <div key={d} className="qb-stat-chip">
                <span>{DIFFICULTY_LABELS[d]}</span>
                <span className="qb-stat-chip__val">{stats.by_difficulty?.[d] ?? 0}</span>
              </div>
            ))}
          </div>
        )}
      </aside>

      {/* ── Main ── */}
      <div className="qb-main">
        <div className="qb-toolbar">
          <input
            className="qb-search"
            placeholder="Search question text…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
          <span className="qb-count">
            {loading ? 'Loading…' : `${questions.length} question${questions.length !== 1 ? 's' : ''}`}
          </span>
          <button className="qb-add-btn" onClick={openNew}>+ Add Question</button>
        </div>

        <div className="qb-cards">
          {loading
            ? Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="qb-skeleton" style={{ height: 160 }} />
              ))
            : questions.length === 0
              ? (
                <div className="qb-empty">
                  <strong>No questions found</strong>
                  {Object.values(filters).some(Boolean) || search
                    ? 'Try adjusting your filters.'
                    : 'Click "Add Question" to create your first question.'}
                </div>
              )
              : questions.map(q => (
                  <QuestionCard
                    key={q.id}
                    question={q}
                    onEdit={() => openEdit(q)}
                    onDelete={() => handleDelete(q.id)}
                  />
                ))
          }
        </div>
      </div>

      {/* ── Editor modal ── */}
      {editorOpen && (
        <QuestionEditor
          question={editingQuestion}
          subjects={subjects}
          classLevels={classLevels}
          onSaved={handleSaved}
          onClose={() => setEditorOpen(false)}
        />
      )}
    </div>
  );
}

// ── Question card ─────────────────────────────────────────────────────────────
function QuestionCard({ question: q, onEdit, onDelete }) {
  const showOptions = q.question_type !== 'fill_blank' && q.options?.length > 0;

  return (
    <div className="qb-card">
      {/* Tags */}
      <div className="qb-card__tags">
        {q.subject_name     && <span className={`qb-tag qb-tag--subject`}>{q.subject_name}</span>}
        {q.class_level_name && <span className={`qb-tag qb-tag--level`}>{q.class_level_name}</span>}
        {q.topic_name       && <span className={`qb-tag qb-tag--topic`}>{q.topic_name}</span>}
        <span className={`qb-tag qb-tag--${q.difficulty}`}>{DIFFICULTY_LABELS[q.difficulty]}</span>
        <span className={`qb-tag qb-tag--${q.question_type}`}>{TYPE_LABELS[q.question_type]}</span>
      </div>

      {/* Question text */}
      <div className="qb-card__text">{q.question_text}</div>

      {/* Options preview (first 2) */}
      {showOptions && (
        <div className="qb-card__options">
          {q.options.slice(0, 4).map(opt => (
            <div
              key={opt.id}
              className={`qb-card__option${opt.id === q.correct_answer ? ' correct' : ''}`}
            >
              {opt.id === q.correct_answer ? '✓ ' : '○ '}{opt.id}. {opt.text}
            </div>
          ))}
        </div>
      )}

      {/* Actions */}
      <div className="qb-card__actions">
        <button className="qb-action-btn" onClick={onEdit}>✏ Edit</button>
        <button className="qb-action-btn qb-action-btn--delete" onClick={onDelete}>🗑 Delete</button>
      </div>
    </div>
  );
}
