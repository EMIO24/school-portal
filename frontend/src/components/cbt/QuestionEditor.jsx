/**
 * frontend/src/components/cbt/QuestionEditor.jsx
 *
 * Modal for creating / editing a question.
 * Shows a live preview pane alongside the form.
 *
 * Props:
 *   question   — existing question object (null for new)
 *   subjects   — [{id, name}]
 *   classLevels— [{id, name}]
 *   onSaved    — callback(savedQuestion)
 *   onClose    — callback()
 */

import React, { useState, useEffect } from 'react';
import DocxQuestionUpload from './DocxQuestionUpload';
import api from '../../services/api';
import '../../styles/QuestionEditor.css';

const OPTION_IDS  = ['A', 'B', 'C', 'D'];
const DIFFICULTIES= ['easy', 'medium', 'hard'];
const COGNITIVES  = ['knowledge', 'comprehension', 'application', 'analysis', 'synthesis', 'evaluation'];
const Q_TYPES     = [
  { value: 'mcq',        label: 'Multiple Choice' },
  { value: 'true_false', label: 'True / False' },
  { value: 'fill_blank', label: 'Fill in the Blank' },
];

function cap(str) { return str.charAt(0).toUpperCase() + str.slice(1); }

// ── Default option list for MCQ ───────────────────────────────────────────────
function defaultOptions(type) {
  if (type === 'true_false') {
    return [
      { id: 'A', text: 'True',  image_url: null },
      { id: 'B', text: 'False', image_url: null },
    ];
  }
  return OPTION_IDS.map(id => ({ id, text: '', image_url: null }));
}

// ── Live preview ──────────────────────────────────────────────────────────────
function Preview({ form }) {
  const showOptions = form.question_type !== 'fill_blank';

  return (
    <div className="qe-preview-card">
      {form.question_image && (
        <img src={form.question_image} alt="" className="qe-preview-img" />
      )}
      <div className="qe-preview-question">
        {form.question_text || <span style={{ color: '#9ca3af' }}>Question text will appear here…</span>}
      </div>

      {showOptions && form.options.map(opt => (
        <div
          key={opt.id}
          className={`qe-preview-option${opt.id === form.correct_answer ? ' correct' : ''}`}
        >
          <span className="qe-preview-option-badge">{opt.id}</span>
          <span>{opt.text || <span style={{ color: '#d1d5db' }}>Option {opt.id}</span>}</span>
        </div>
      ))}

      {form.question_type === 'fill_blank' && form.correct_answer && (
        <div style={{ marginTop: 8, fontSize: '.82rem', color: '#374151' }}>
          <strong>Answer:</strong> {form.correct_answer}
        </div>
      )}

      {form.explanation && (
        <div className="qe-preview-explanation">
          <strong>Explanation:</strong> {form.explanation}
        </div>
      )}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
export default function QuestionEditor({ question, subjects, classLevels, onSaved, onImported, onClose }) {
  const [importBusy, setImportBusy] = useState(false);
  const isEdit = Boolean(question?.id);

  const [topics,  setTopics]  = useState([]);
  const [saving,  setSaving]  = useState(false);
  const [imageBusy, setImageBusy] = useState(false);
  const [imageName, setImageName] = useState('');
  const [error,   setError]   = useState(null);

  const [form, setForm] = useState(() => {
    if (isEdit) {
      return {
        subject:        question.subject       ?? '',
        class_level:    question.class_level   ?? '',
        topic:          question.topic         ?? '',
        question_text:  question.question_text ?? '',
        question_image: question.question_image?? '',
        question_type:  question.question_type ?? 'mcq',
        difficulty:     question.difficulty    ?? 'medium',
        cognitive_level:question.cognitive_level ?? 'knowledge',
        options:        question.options?.length ? question.options : defaultOptions(question.question_type),
        correct_answer: question.correct_answer ?? '',
        explanation:    question.explanation   ?? '',
        is_active:      question.is_active     ?? true,
      };
    }
    return {
      subject: '', class_level: '', topic: '',
      question_text: '', question_image: '',
      question_type: 'mcq', difficulty: 'medium', cognitive_level: 'knowledge',
      options: defaultOptions('mcq'),
      correct_answer: '', explanation: '', is_active: true,
    };
  });

  // Load topics when subject + class_level change
  useEffect(() => {
    if (!form.subject || !form.class_level) { setTopics([]); return; }
    api.get(`/api/cbt/topics/?subject=${form.subject}&class_level=${form.class_level}`)
      .then(({ data }) => setTopics(data.results ?? data))
      .catch(() => setTopics([]));
  }, [form.subject, form.class_level]);

  // Rebuild options when question_type changes
  const handleTypeChange = type => {
    setForm(f => ({ ...f, question_type: type, options: defaultOptions(type), correct_answer: '' }));
  };

  const setField = (key, val) => setForm(f => ({ ...f, [key]: val }));

  const setOptionText = (id, text) => {
    setForm(f => ({
      ...f,
      options: f.options.map(o => o.id === id ? { ...o, text } : o),
    }));
  };

  const chooseImage = async event => {
    const file = event.target.files?.[0];
    if (!file) return;
    if (!['image/png','image/jpeg','image/webp'].includes(file.type) || file.size > 2 * 1024 * 1024) {
      setError('Choose a PNG, JPEG or WebP image up to 2 MB.'); event.target.value = ''; return;
    }
    setImageBusy(true); setError(null);
    try {
      const body = new FormData(); body.append('image', file);
      const { data } = await api.post('/api/cbt/questions/image/', body, { headers: { 'Content-Type': 'multipart/form-data' } });
      setField('question_image', data.url); setImageName(file.name);
    } catch (err) { setError(JSON.stringify(err?.response?.data || 'Image upload failed.')); }
    finally { setImageBusy(false); }
  };

  const handleSave = async () => {
    if (!form.question_text.trim()) { setError('Question text is required.'); return; }
    if (!form.subject)             { setError('Subject is required.');        return; }
    if (!form.class_level)         { setError('Class level is required.');     return; }
    if (form.question_type !== 'fill_blank' && !form.correct_answer) {
      setError('Select the correct answer.'); return;
    }

    setSaving(true);
    setError(null);

    const payload = {
      ...form,
      topic: form.topic || null,
      options: form.question_type === 'fill_blank' ? [] : form.options,
    };

    try {
      const { data } = isEdit
        ? await api.patch(`/api/cbt/questions/${question.id}/`, payload)
        : await api.post('/api/cbt/questions/', payload);
      onSaved(data);
    } catch (err) {
      const detail = err?.response?.data;
      setError(typeof detail === 'string' ? detail : JSON.stringify(detail));
    } finally {
      setSaving(false);
    }
  };

  const showOptions = form.question_type !== 'fill_blank';

  return (
    <div className="qe-overlay" onClick={e => e.target === e.currentTarget && !importBusy && !saving && onClose()}>
      <div className="qe-modal">

        {/* Header */}
        <div className="qe-header">
          <h2>{isEdit ? 'Edit Question' : 'New Question'}</h2>
          <button className="qe-close" onClick={onClose} disabled={importBusy || saving}>✕</button>
        </div>

        <div className="qe-body">

          {/* ── Form pane ── */}
          <div className="qe-form-pane">

            {/* Tags row 1: subject + class level */}
            <div className="qe-tags-row">
              <div className="qe-field">
                <label className="qe-label">Subject *</label>
                <select className="qe-select" value={form.subject} onChange={e => setField('subject', e.target.value)}>
                  <option value="">— select —</option>
                  {subjects.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              </div>
              <div className="qe-field">
                <label className="qe-label">Class Level *</label>
                <select className="qe-select" value={form.class_level} onChange={e => setField('class_level', e.target.value)}>
                  <option value="">— select —</option>
                  {classLevels.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              </div>
            </div>

            {/* Tags row 2: topic + difficulty */}
            <div className="qe-tags-row">
              <div className="qe-field">
                <label className="qe-label">Topic</label>
                <select className="qe-select" value={form.topic} onChange={e => setField('topic', e.target.value)}>
                  <option value="">— none —</option>
                  {topics.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                </select>
              </div>
              <div className="qe-field">
                <label className="qe-label">Difficulty</label>
                <select className="qe-select" value={form.difficulty} onChange={e => setField('difficulty', e.target.value)}>
                  {DIFFICULTIES.map(d => <option key={d} value={d}>{cap(d)}</option>)}
                </select>
              </div>
            </div>

            {/* Tags row 3: type + cognitive level */}
            <div className="qe-tags-row">
              <div className="qe-field">
                <label className="qe-label">Question Type</label>
                <select className="qe-select" value={form.question_type} onChange={e => handleTypeChange(e.target.value)}>
                  {Q_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
              </div>
              <div className="qe-field">
                <label className="qe-label">Cognitive Level</label>
                <select className="qe-select" value={form.cognitive_level} onChange={e => setField('cognitive_level', e.target.value)}>
                  {COGNITIVES.map(c => <option key={c} value={c}>{cap(c)}</option>)}
                </select>
              </div>
            </div>

            {!isEdit && <DocxQuestionUpload defaults={form} onBusy={setImportBusy} onImported={onImported} />}
            {!isEdit && <h3>Or add a question manually</h3>}
            {/* Question text */}
            <div className="qe-field">
              <label className="qe-label">Question Text *</label>
              <textarea
                className="qe-textarea"
                value={form.question_text}
                onChange={e => setField('question_text', e.target.value)}
                placeholder="Type the question here…"
                rows={4}
              />
            </div>

            {/* Question image */}
            <div className="qe-field">
              <label className="qe-label">Choose question image (optional)
                <input type="file" accept="image/png,image/jpeg,image/webp" onChange={chooseImage} disabled={imageBusy} />
              </label>
              {imageName && <span>{imageName}</span>}
              {form.question_image && <button type="button" className="btn btn-ghost" onClick={()=>{setField('question_image','');setImageName('');}}>Remove image</button>}
              <small>PNG, JPEG or WebP, up to 2 MB.</small>
            </div>

            {/* Options (MCQ / True-False) */}
            {showOptions && (
              <div className="qe-field">
                <label className="qe-label">Options — click radio to mark correct</label>
                <div className="qe-options-list">
                  {form.options.map(opt => (
                    <div key={opt.id} className={`qe-option-row${form.correct_answer === opt.id ? ' is-correct' : ''}`}>
                      <span className="qe-option-letter">{opt.id}</span>
                      <input
                        type="radio"
                        className="qe-option-radio"
                        name="correct_answer"
                        checked={form.correct_answer === opt.id}
                        onChange={() => setField('correct_answer', opt.id)}
                        title="Mark as correct"
                      />
                      <input
                        className="qe-option-input"
                        value={opt.text}
                        onChange={e => setOptionText(opt.id, e.target.value)}
                        placeholder={`Option ${opt.id}`}
                        disabled={form.question_type === 'true_false'}
                      />
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Fill-blank correct answer */}
            {form.question_type === 'fill_blank' && (
              <div className="qe-field">
                <label className="qe-label">Correct Answer</label>
                <input
                  className="qe-input"
                  value={form.correct_answer}
                  onChange={e => setField('correct_answer', e.target.value)}
                  placeholder="Expected answer text"
                />
              </div>
            )}

            {/* Explanation */}
            <div className="qe-field">
              <label className="qe-label">Explanation (shown after submission)</label>
              <textarea
                className="qe-textarea"
                value={form.explanation}
                onChange={e => setField('explanation', e.target.value)}
                placeholder="Optional explanation…"
                rows={3}
              />
            </div>

            {error && (
              <div style={{ background: '#fee2e2', color: '#991b1b', padding: '10px 12px', borderRadius: 6, fontSize: '.84rem' }}>
                ⚠ {error}
              </div>
            )}
          </div>

          {/* ── Preview pane ── */}
          <div className="qe-preview-pane">
            <div className="qe-preview-title">Live Preview</div>
            <Preview form={form} />
          </div>
        </div>

        {/* Footer */}
        <div className="qe-footer">
          <button className="qe-btn qe-btn--ghost" onClick={onClose} disabled={importBusy || saving}>Cancel</button>
          <button className="qe-btn qe-btn--navy" onClick={handleSave} disabled={saving || importBusy}>
            {saving ? 'Saving…' : isEdit ? 'Update Question' : 'Save Question'}
          </button>
        </div>
      </div>
    </div>
  );
}
