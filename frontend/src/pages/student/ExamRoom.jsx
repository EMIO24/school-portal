/**
 * frontend/src/pages/student/ExamRoom.jsx
 *
 * Full-screen CBT exam room.
 *
 * Features:
 *   - Countdown timer (turns red < 5 min, auto-submits on expiry)
 *   - Question navigator grid (green = answered, current = highlighted)
 *   - Auto-save answer on selection (debounced)
 *   - Tab-switch detection + warning overlay
 *   - Submit confirmation modal
 *   - Score display after submission
 */

import React, {
  useState, useEffect, useRef, useCallback,
} from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../../services/api';
import '../../styles/ExamRoom.css';

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatTime(seconds) {
  if (seconds <= 0) return '00:00';
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

// ── Tab-switch warning overlay ────────────────────────────────────────────────

function TabWarning({ count, onDismiss }) {
  return (
    <div className="er-tab-overlay">
      <div className="er-tab-modal">
        <div className="er-tab-icon">⚠️</div>
        <h3>Tab Switch Detected</h3>
        <p>
          You left the exam window. This has been logged.
          <br />
          <strong>Switches recorded: {count}</strong>
        </p>
        <button className="er-btn er-btn--navy" onClick={onDismiss}>
          Return to Exam
        </button>
      </div>
    </div>
  );
}

// ── Submit confirmation modal ─────────────────────────────────────────────────

function SubmitModal({ answered, total, onConfirm, onCancel, submitting }) {
  const unanswered = total - answered;
  return (
    <div className="er-overlay">
      <div className="er-modal">
        <h3>Submit Exam?</h3>
        <p>
          You have answered <strong>{answered}</strong> of{' '}
          <strong>{total}</strong> questions.
        </p>
        {unanswered > 0 && (
          <p className="er-modal-warn">
            ⚠ {unanswered} question{unanswered !== 1 ? 's' : ''} left unanswered.
          </p>
        )}
        <div className="er-modal-actions">
          <button className="er-btn er-btn--ghost" onClick={onCancel} disabled={submitting}>
            Cancel
          </button>
          <button className="er-btn er-btn--danger" onClick={onConfirm} disabled={submitting}>
            {submitting ? 'Submitting…' : 'Yes, Submit'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Score result screen ───────────────────────────────────────────────────────

function ScoreScreen({ score, total, correct, onLeave }) {
  const pct = score ?? 0;
  const grade =
    pct >= 70 ? { label: 'Pass', cls: 'pass' } :
    pct >= 50 ? { label: 'Average', cls: 'avg' } :
                { label: 'Below Average', cls: 'fail' };

  return (
    <div className="er-score-screen">
      <div className="er-score-card">
        <div className="er-score-icon">✅</div>
        <h2>Exam Submitted!</h2>
        <div className={`er-score-pct er-score-pct--${grade.cls}`}>{pct}%</div>
        <div className="er-score-meta">
          {correct !== undefined && (
            <span>{correct} / {total} correct</span>
          )}
          <span className={`er-grade er-grade--${grade.cls}`}>{grade.label}</span>
        </div>
        <button className="er-btn er-btn--navy" onClick={onLeave} style={{ marginTop: 24 }}>
          Back to Exam List
        </button>
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function ExamRoom() {
  const { examId }  = useParams();
  const navigate    = useNavigate();

  // ── Loading / error ──────────────────────────────────────────────────────────
  const [phase, setPhase] = useState('loading'); // loading | exam | result | error
  const [errorMsg, setErrorMsg] = useState('');

  // ── Exam data ────────────────────────────────────────────────────────────────
  const [questions,    setQuestions]    = useState([]);
  const [allowReview,  setAllowReview]  = useState(true);
  const [sessionId,    setSessionId]    = useState(null);

  // ── Current position ─────────────────────────────────────────────────────────
  const [currentIdx,   setCurrentIdx]   = useState(0);

  // ── Answers: {questionId: selectedOption} ────────────────────────────────────
  const [answers,      setAnswers]      = useState({});

  // ── Timer ────────────────────────────────────────────────────────────────────
  const [timeLeft,     setTimeLeft]     = useState(0);
  const timerRef = useRef(null);

  // ── UI state ─────────────────────────────────────────────────────────────────
  const [showSubmitModal, setShowSubmitModal] = useState(false);
  const [submitting,      setSubmitting]      = useState(false);
  const [showTabWarning,  setShowTabWarning]  = useState(false);
  const [tabSwitches,     setTabSwitches]     = useState(0);

  // ── Score result ─────────────────────────────────────────────────────────────
  const [scoreData, setScoreData] = useState(null);

  // ── Auto-save debounce ref ────────────────────────────────────────────────────
  const saveTimerRef = useRef(null);

  // ── Start exam ───────────────────────────────────────────────────────────────
  useEffect(() => {
    api.post(`/cbt/exams/${examId}/start/`)
      .then(({ data }) => {
        setQuestions(data.questions);
        setAllowReview(data.allow_review);
        setSessionId(data.session_id);
        setTimeLeft(data.time_remaining_seconds);
        setPhase('exam');

        // Restore any already-saved answers from /status/
        api.get(`/cbt/exams/${examId}/status/`).then(({ data: st }) => {
          const saved = {};
          (st.saved_answers || []).forEach(a => {
            if (a.selected_option) saved[a.question] = a.selected_option;
          });
          setAnswers(saved);
          setTabSwitches(st.tab_switch_count || 0);
        }).catch(() => {});
      })
      .catch(err => {
        const msg = err?.response?.data?.detail || 'Could not start exam.';
        setErrorMsg(msg);
        setPhase('error');
      });
  }, [examId]);

  // ── Countdown timer ───────────────────────────────────────────────────────────
  useEffect(() => {
    if (phase !== 'exam') return;
    timerRef.current = setInterval(() => {
      setTimeLeft(t => {
        if (t <= 1) {
          clearInterval(timerRef.current);
          handleAutoSubmit();
          return 0;
        }
        return t - 1;
      });
    }, 1000);
    return () => clearInterval(timerRef.current);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase]);

  // ── Tab-switch detection ──────────────────────────────────────────────────────
  useEffect(() => {
    if (phase !== 'exam') return;
    const onVisibilityChange = () => {
      if (document.hidden) {
        api.post(`/cbt/exams/${examId}/log-tab-switch/`).then(({ data }) => {
          setTabSwitches(data.tab_switch_count || 0);
        }).catch(() => {});
        setShowTabWarning(true);
      }
    };
    document.addEventListener('visibilitychange', onVisibilityChange);
    return () => document.removeEventListener('visibilitychange', onVisibilityChange);
  }, [phase, examId]);

  // ── Auto-save ─────────────────────────────────────────────────────────────────
  const saveAnswer = useCallback((questionId, option) => {
    clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => {
      api.post(`/cbt/exams/${examId}/save-answer/`, {
        question_id:     questionId,
        selected_option: option,
      }).catch(() => {});
    }, 400); // 400 ms debounce
  }, [examId]);

  // ── Select option ─────────────────────────────────────────────────────────────
  const handleSelect = (questionId, option) => {
    setAnswers(prev => ({ ...prev, [questionId]: option }));
    saveAnswer(questionId, option);
  };

  // ── Submit ────────────────────────────────────────────────────────────────────
  const doSubmit = useCallback(async () => {
    setSubmitting(true);
    clearInterval(timerRef.current);
    try {
      const { data } = await api.post(`/cbt/exams/${examId}/submit/`);
      let correct;
      if (data.answers) {
        correct = data.answers.filter(a => a.is_correct).length;
      }
      setScoreData({
        score:   data.score,
        total:   questions.length,
        correct,
      });
      setPhase('result');
    } catch (err) {
      const msg = err?.response?.data?.detail || 'Submission failed.';
      setErrorMsg(msg);
    } finally {
      setSubmitting(false);
      setShowSubmitModal(false);
    }
  }, [examId, questions.length]);

  const handleAutoSubmit = useCallback(() => {
    doSubmit();
  }, [doSubmit]);

  // ── Render: loading ───────────────────────────────────────────────────────────
  if (phase === 'loading') {
    return (
      <div className="er-loading">
        <div className="er-spinner" />
        <p>Preparing your exam…</p>
      </div>
    );
  }

  // ── Render: error ─────────────────────────────────────────────────────────────
  if (phase === 'error') {
    return (
      <div className="er-loading">
        <div className="er-error-icon">⚠️</div>
        <p>{errorMsg}</p>
        <button className="er-btn er-btn--navy" onClick={() => navigate('/student/exams')}>
          Back to Exam List
        </button>
      </div>
    );
  }

  // ── Render: result ────────────────────────────────────────────────────────────
  if (phase === 'result') {
    return (
      <ScoreScreen
        score={scoreData?.score}
        total={scoreData?.total}
        correct={scoreData?.correct}
        onLeave={() => navigate('/student/exams')}
      />
    );
  }

  // ── Render: exam ──────────────────────────────────────────────────────────────
  const q          = questions[currentIdx];
  const answeredCount = Object.keys(answers).length;
  const isUrgent   = timeLeft <= 300 && timeLeft > 0;
  const isWarning  = timeLeft <= 60  && timeLeft > 0;

  return (
    <div className="er-room">

      {/* ── Top bar ── */}
      <header className="er-topbar">
        <div className="er-topbar-left">
          <span className="er-exam-title">
            {/* Title not loaded here — we could add it to start payload later */}
            Question {currentIdx + 1} of {questions.length}
          </span>
          {tabSwitches > 0 && (
            <span className="er-tab-badge">⚠ {tabSwitches} tab switch{tabSwitches !== 1 ? 'es' : ''}</span>
          )}
        </div>
        <div
          className={`er-timer${isWarning ? ' er-timer--warning' : isUrgent ? ' er-timer--urgent' : ''}`}
        >
          ⏱ {formatTime(timeLeft)}
        </div>
        <div className="er-topbar-right">
          <span className="er-answered">{answeredCount}/{questions.length} answered</span>
          <button className="er-submit-btn" onClick={() => setShowSubmitModal(true)}>
            Submit
          </button>
        </div>
      </header>

      <div className="er-body">

        {/* ── Navigator sidebar ── */}
        <aside className="er-navigator">
          <div className="er-nav-title">Questions</div>
          <div className="er-nav-grid">
            {questions.map((qItem, idx) => (
              <button
                key={qItem.id}
                className={`er-nav-btn
                  ${idx === currentIdx   ? ' er-nav-btn--current' : ''}
                  ${answers[qItem.id]   ? ' er-nav-btn--answered' : ''}
                `}
                onClick={() => setCurrentIdx(idx)}
              >
                {idx + 1}
              </button>
            ))}
          </div>
          <div className="er-nav-legend">
            <span className="er-legend er-legend--answered" />Answered
            <span className="er-legend er-legend--current"  />Current
            <span className="er-legend er-legend--blank"    />Unanswered
          </div>
        </aside>

        {/* ── Question pane ── */}
        <main className="er-question-pane">
          {q && (
            <>
              {q.question_image && (
                <img src={q.question_image} alt="" className="er-question-img" />
              )}
              <div className="er-question-text">
                <span className="er-qnum">{currentIdx + 1}.</span>
                {q.question_text}
              </div>

              {/* MCQ / True-False options */}
              {q.question_type !== 'fill_blank' && (
                <div className="er-options">
                  {(q.options || []).map(opt => (
                    <label
                      key={opt.id}
                      className={`er-option${answers[q.id] === opt.id ? ' er-option--selected' : ''}`}
                    >
                      <input
                        type="radio"
                        name={`q_${q.id}`}
                        value={opt.id}
                        checked={answers[q.id] === opt.id}
                        onChange={() => handleSelect(q.id, opt.id)}
                        className="er-option-radio"
                      />
                      <span className="er-option-badge">{opt.id}</span>
                      <span className="er-option-text">{opt.text}</span>
                    </label>
                  ))}
                </div>
              )}

              {/* Fill-blank text input */}
              {q.question_type === 'fill_blank' && (
                <div className="er-fill-blank">
                  <input
                    className="er-fill-input"
                    placeholder="Type your answer here…"
                    value={answers[q.id] || ''}
                    onChange={e => handleSelect(q.id, e.target.value)}
                  />
                </div>
              )}
            </>
          )}

          {/* Navigation buttons */}
          <div className="er-nav-btns">
            <button
              className="er-btn er-btn--ghost"
              disabled={currentIdx === 0}
              onClick={() => setCurrentIdx(i => i - 1)}
            >
              ← Previous
            </button>
            <button
              className="er-btn er-btn--navy"
              disabled={currentIdx === questions.length - 1}
              onClick={() => setCurrentIdx(i => i + 1)}
            >
              Next →
            </button>
          </div>
        </main>
      </div>

      {/* ── Overlays ── */}
      {showTabWarning && (
        <TabWarning
          count={tabSwitches}
          onDismiss={() => setShowTabWarning(false)}
        />
      )}

      {showSubmitModal && (
        <SubmitModal
          answered={answeredCount}
          total={questions.length}
          submitting={submitting}
          onConfirm={doSubmit}
          onCancel={() => setShowSubmitModal(false)}
        />
      )}
    </div>
  );
}
