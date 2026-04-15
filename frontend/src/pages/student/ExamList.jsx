/**
 * frontend/src/pages/student/ExamList.jsx
 *
 * Student exam lobby — shows available/upcoming/completed exams.
 * Clicking "Start" navigates into ExamRoom.
 */

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../../services/api';
import '../../styles/ExamList.css';

const STATUS_META = {
  null:        { label: 'Not Started', cls: 'el-badge--new' },
  not_started: { label: 'Not Started', cls: 'el-badge--new' },
  in_progress: { label: 'In Progress', cls: 'el-badge--progress' },
  submitted:   { label: 'Submitted',   cls: 'el-badge--done' },
  timed_out:   { label: 'Timed Out',   cls: 'el-badge--timeout' },
};

function statusMeta(s) {
  return STATUS_META[s] ?? STATUS_META['null'];
}

function formatDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-GB', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

export default function ExamList() {
  const [exams,   setExams]   = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    api.get('/cbt/exams/available/')
      .then(({ data }) => setExams(data))
      .finally(() => setLoading(false));
  }, []);

  const canStart = (exam) => {
    const s = exam.session_status;
    return s === null || s === 'not_started' || s === 'in_progress';
  };

  const handleAction = (exam) => {
    navigate(`/student/exam/${exam.id}`);
  };

  if (loading) {
    return (
      <div className="el-page">
        <div className="el-header"><h1>My Exams</h1></div>
        <div className="el-grid">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="el-skeleton" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="el-page">
      <div className="el-header">
        <h1>My Exams</h1>
        <p className="el-subtitle">
          {exams.length === 0
            ? 'No exams available at the moment.'
            : `${exams.length} exam${exams.length !== 1 ? 's' : ''} available`}
        </p>
      </div>

      {exams.length === 0 ? (
        <div className="el-empty">
          <div className="el-empty-icon">📋</div>
          <strong>No exams scheduled</strong>
          <span>Check back later or contact your teacher.</span>
        </div>
      ) : (
        <div className="el-grid">
          {exams.map(exam => {
            const meta    = statusMeta(exam.session_status);
            const done    = exam.session_status === 'submitted' || exam.session_status === 'timed_out';
            const started = exam.session_status === 'in_progress';

            return (
              <div key={exam.id} className={`el-card${done ? ' el-card--done' : ''}`}>
                <div className="el-card__top">
                  <span className="el-subject">{exam.subject_name}</span>
                  <span className={`el-badge ${meta.cls}`}>{meta.label}</span>
                </div>

                <h2 className="el-card__title">{exam.title}</h2>

                <div className="el-card__meta">
                  <span>⏱ {exam.duration_minutes} min</span>
                  <span>📅 {formatDate(exam.start_datetime)}</span>
                  {exam.class_arms_display?.length > 0 && (
                    <span>🏫 {exam.class_arms_display.join(', ')}</span>
                  )}
                </div>

                {exam.instructions && (
                  <p className="el-card__instructions">{exam.instructions}</p>
                )}

                {done && exam.score !== null && (
                  <div className="el-score-chip">
                    Score: <strong>{exam.score}%</strong>
                  </div>
                )}

                <div className="el-card__footer">
                  {done ? (
                    <span className="el-done-label">
                      {exam.session_status === 'timed_out' ? '⏰ Timed out' : '✓ Completed'}
                    </span>
                  ) : (
                    <button
                      className="el-start-btn"
                      onClick={() => handleAction(exam)}
                    >
                      {started ? '▶ Resume Exam' : '▶ Start Exam'}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
