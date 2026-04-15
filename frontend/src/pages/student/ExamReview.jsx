/**
 * frontend/src/pages/student/ExamReview.jsx
 *
 * Post-exam review — shows each question with:
 *   - The student's chosen answer (blue)
 *   - The correct answer (green)
 *   - Explanation below
 *   - Score summary card at the top
 */

import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../../services/api';
import '../../styles/ExamReview.css';

function ScoreBadge({ score }) {
  const cls =
    score >= 70 ? 'er2-score--pass' :
    score >= 50 ? 'er2-score--avg'  :
                  'er2-score--fail';
  return <span className={`er2-score-badge ${cls}`}>{score}%</span>;
}

export default function ExamReview() {
  const { examId } = useParams();
  const navigate   = useNavigate();

  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState('');

  useEffect(() => {
    api.get(`/cbt/exams/${examId}/review/`)
      .then(({ data }) => setData(data))
      .catch(err => setError(err?.response?.data?.detail || 'Could not load review.'))
      .finally(() => setLoading(false));
  }, [examId]);

  if (loading) {
    return (
      <div className="er2-page">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="er2-skeleton" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="er2-page">
        <div className="er2-error">
          <strong>⚠ {error}</strong>
          <button className="er2-back-btn" onClick={() => navigate('/student/exams')}>
            Back to Exams
          </button>
        </div>
      </div>
    );
  }

  const { score, questions } = data;
  const correct   = questions.filter(q => q.is_correct).length;
  const total     = questions.length;

  return (
    <div className="er2-page">

      {/* ── Summary card ── */}
      <div className="er2-summary">
        <div className="er2-summary-left">
          <h1>Exam Review</h1>
          <p>{correct} of {total} correct</p>
        </div>
        <ScoreBadge score={score} />
        <button className="er2-back-btn" onClick={() => navigate('/student/exams')}>
          ← Back to Exams
        </button>
      </div>

      {/* ── Questions ── */}
      {questions.map((q, idx) => {
        const isCorrect  = q.is_correct;
        const isFill     = q.question_type === 'fill_blank';

        return (
          <div
            key={q.id}
            className={`er2-card${isCorrect ? ' er2-card--correct' : isCorrect === false ? ' er2-card--wrong' : ''}`}
          >
            <div className="er2-card-header">
              <span className="er2-qnum">Q{idx + 1}</span>
              {isCorrect === true  && <span className="er2-verdict er2-verdict--correct">✓ Correct</span>}
              {isCorrect === false && <span className="er2-verdict er2-verdict--wrong">✗ Incorrect</span>}
              {isCorrect === null  && <span className="er2-verdict er2-verdict--skip">— Not answered</span>}
            </div>

            {q.question_image && (
              <img src={q.question_image} alt="" className="er2-question-img" />
            )}

            <div className="er2-question-text">{q.question_text}</div>

            {/* MCQ / True-False options */}
            {!isFill && (
              <div className="er2-options">
                {(q.options || []).map(opt => {
                  const isSelected = opt.id === q.selected_option;
                  const isAnswer   = opt.id === q.correct_option;
                  let cls = 'er2-option';
                  if (isAnswer)            cls += ' er2-option--correct';
                  else if (isSelected)     cls += ' er2-option--wrong';
                  return (
                    <div key={opt.id} className={cls}>
                      <span className="er2-option-badge">{opt.id}</span>
                      <span className="er2-option-text">{opt.text}</span>
                      {isAnswer   && <span className="er2-tag er2-tag--correct">Correct answer</span>}
                      {isSelected && !isAnswer && <span className="er2-tag er2-tag--wrong">Your answer</span>}
                    </div>
                  );
                })}
              </div>
            )}

            {/* Fill-blank answer display */}
            {isFill && (
              <div className="er2-fill-display">
                <div className={`er2-fill-row${isCorrect ? ' er2-fill-row--correct' : ' er2-fill-row--wrong'}`}>
                  <span className="er2-fill-label">Your answer:</span>
                  <span>{q.selected_option || <em>Not answered</em>}</span>
                </div>
                {!isCorrect && (
                  <div className="er2-fill-row er2-fill-row--correct">
                    <span className="er2-fill-label">Correct answer:</span>
                    <span>{q.correct_option}</span>
                  </div>
                )}
              </div>
            )}

            {/* Explanation */}
            {q.explanation && (
              <div className="er2-explanation">
                <strong>Explanation:</strong> {q.explanation}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
