import React, { useState } from 'react';
import api from '../../services/api';
import { downloadFile } from '../../services/download';

export default function DocxQuestionUpload({ defaults, onImported, onBusy }) {
  const [questions, setQuestions] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  function working(value) { setBusy(value); onBusy?.(value); }
  async function upload(event) {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    setError(''); setNotice(''); setQuestions([]);
    if (!file.name.toLowerCase().endsWith('.docx') || file.size > 5 * 1024 * 1024) {
      setError('Choose a Word .docx file of 5 MB or smaller.'); return;
    }
    working(true);
    try {
      const body = new FormData();
      body.append('file', file);
      const { data } = await api.post('/api/cbt/questions/docx-preview/', body, { headers: { 'Content-Type': 'multipart/form-data' } });
      setQuestions(data.questions);
      setNotice(data.questions.length + ' question forms filled automatically. Review them, then save all questions.');
    } catch (err) { setError(err.response?.data?.detail || 'Could not read the document. Try the Word template.'); }
    finally { working(false); }
  }
  async function saveAll() {
    if (!defaults.subject || !defaults.class_level) {
      setError('Choose Subject and Class Level in the form before importing.'); return;
    }
    const invalid = questions.findIndex(question => !question.question_text.trim() || !question.correct_answer.trim() ||
      (question.options.length && (question.options.some(option => !option.text.trim()) || !question.options.some(option => option.id === question.correct_answer))));
    if (invalid >= 0) { setError('Complete the text, options and correct answer for question ' + (invalid + 1) + '.'); return; }
    working(true); setError(''); setNotice('');
    try {
      const payload = questions.map(question => ({
        ...question, subject: Number(defaults.subject), class_level: Number(defaults.class_level),
        topic: defaults.topic || null, difficulty: defaults.difficulty, cognitive_level: defaults.cognitive_level,
        is_active: true,
      }));
      const { data } = await api.post('/api/cbt/questions/bulk-import/', payload);
      if (data.errors?.length) {
        setQuestions(questions.filter((_, index) => data.errors.some(item => item.index === index)));
        setError(data.imported + ' imported. Remaining questions need correction: ' + data.errors.map(item => JSON.stringify(item.detail)).join(' '));
      } else {
        setQuestions([]);
        setNotice(data.imported + ' questions imported.');
        onImported?.();
      }
    } catch {
      setError('Import could not be confirmed. Check the question bank before retrying to avoid duplicates.');
    } finally { working(false); }
  }
  return <section className="qe-field" aria-label="Word question upload">
    <h3>Upload questions from Word</h3>
    <p>Use text questions with A–D options and an Answer line. Images and equations must be added separately. Maximum 200 questions, 5 MB.</p>
    <button type="button" className="qe-btn qe-btn--ghost" disabled={busy}
      onClick={() => downloadFile('/api/cbt/questions/docx-template/', 'questions-template.docx')}>Download Word template</button>
    <label className="qe-label" htmlFor="question-docx">Upload Word (.docx)</label>
    <input id="question-docx" type="file" accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document" disabled={busy} onChange={upload} />
    {busy && <p role="status">Processing document...</p>}
    {error && <p role="alert">{error}</p>}
    {notice && <p role="status">{notice}</p>}
    {!!questions.length && <div>
      <h4>{questions.length} automatically filled question forms</h4>
      <p>Subject, class level, topic and difficulty come from the main form. Each item below becomes a separate question.</p>
      <button type="button" className="qe-btn qe-btn--navy" disabled={busy} onClick={saveAll}>Save all {questions.length} questions</button>
      {questions.map((question, index) => {
        const update = changes => setQuestions(prev => prev.map((item, i) => i === index ? { ...item, ...changes } : item));
        return <details key={index} open={index === 0} style={{ border: '1px solid #ddd', padding: 12, marginBottom: 8 }}>
          <summary>Question {index + 1}: {question.question_text.slice(0, 90)}</summary>
          <fieldset disabled={busy} style={{ border: 0, padding: 0, minWidth: 0 }}>
            <label className="qe-label" htmlFor={'import-question-' + index}>Question {index + 1} text</label>
            <textarea className="qe-textarea" id={'import-question-' + index} value={question.question_text} rows={3}
              onChange={event => update({ question_text: event.target.value })} />
            {question.options.map((option, optionIndex) => <label className="qe-label" key={option.id}>
              Question {index + 1} option {option.id}
              <input className="qe-input" value={option.text} onChange={event => update({
                options: question.options.map((item, i) => i === optionIndex ? { ...item, text: event.target.value } : item),
              })} />
            </label>)}
            <label className="qe-label">Question {index + 1} correct answer
              {question.options.length ? <select className="qe-select" value={question.correct_answer} onChange={event => update({ correct_answer: event.target.value })}>
                {question.options.map(option => <option key={option.id} value={option.id}>{option.id}</option>)}
              </select> : <input className="qe-input" maxLength={10} value={question.correct_answer} onChange={event => update({ correct_answer: event.target.value })} />}
            </label>
            <label className="qe-label">Question {index + 1} explanation
              <textarea className="qe-textarea" rows={2} value={question.explanation} onChange={event => update({ explanation: event.target.value })} />
            </label>
            <button type="button" onClick={() => setQuestions(prev => prev.filter((_, i) => i !== index))}>Remove question {index + 1}</button>
          </fieldset>
        </details>;
      })}

    </div>}
  </section>;
}