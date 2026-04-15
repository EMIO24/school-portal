/**
 * frontend/src/pages/admin/ExamResults.jsx
 *
 * Admin exam results view:
 *   - Exam selector
 *   - Per-student performance table (score, time taken, tab switches)
 *   - Score distribution bar chart (Recharts)
 *   - Per-question analysis table
 *   - 'Push to Gradebook' button
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from 'recharts';
import api from '../../services/api';
import '../../styles/ExamResults.css';

function formatTime(seconds) {
  if (!seconds) return '—';
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}m ${s}s`;
}

function scoreColor(pct) {
  if (pct >= 70) return '#16a34a';
  if (pct >= 50) return '#d97706';
  return '#dc2626';
}

// Build a 10-bucket distribution array from results
function buildDistribution(results) {
  const buckets = Array.from({ length: 10 }, (_, i) => ({
    range: `${i * 10}–${i * 10 + 9}`,
    count: 0,
  }));
  results.forEach(r => {
    if (r.score === null) return;
    const idx = Math.min(Math.floor(r.score / 10), 9);
    buckets[idx].count += 1;
  });
  return buckets;
}

export default function ExamResults() {
  const [exams,       setExams]       = useState([]);
  const [selectedId,  setSelectedId]  = useState('');
  const [results,     setResults]     = useState(null);
  const [analysis,    setAnalysis]    = useState(null);
  const [loading,     setLoading]     = useState(false);
  const [pushing,     setPushing]     = useState(false);
  const [pushResult,  setPushResult]  = useState(null);
  const [activeTab,   setActiveTab]   = useState('students'); // students | questions

  // Load exam list
  useEffect(() => {
    api.get('/cbt/exams/').then(({ data }) => {
      const list = data.results ?? data;
      setExams(list);
      if (list.length > 0) setSelectedId(String(list[0].id));
    });
  }, []);

  const loadResults = useCallback(() => {
    if (!selectedId) return;
    setLoading(true);
    setResults(null);
    setAnalysis(null);
    setPushResult(null);

    Promise.all([
      api.get(`/cbt/exams/${selectedId}/results/`),
      api.get(`/cbt/exams/${selectedId}/question-analysis/`),
    ]).then(([r, a]) => {
      setResults(r.data);
      setAnalysis(a.data);
    }).finally(() => setLoading(false));
  }, [selectedId]);

  useEffect(() => { loadResults(); }, [loadResults]);

  const handlePush = async () => {
    if (!window.confirm('Push CBT scores to the gradebook? This will overwrite existing exam scores for all students who completed this exam.')) return;
    setPushing(true);
    setPushResult(null);
    try {
      const { data } = await api.post(`/cbt/exams/${selectedId}/push-to-gradebook/`);
      setPushResult(data);
    } catch (err) {
      setPushResult({ error: err?.response?.data?.detail || 'Push failed.' });
    } finally {
      setPushing(false);
    }
  };

  const distribution = results ? buildDistribution(results.results) : [];

  return (
    <div className="exr-page">

      {/* ── Toolbar ── */}
      <div className="exr-toolbar">
        <div className="exr-toolbar-left">
          <h1 className="exr-title">Exam Results</h1>
          <select
            className="exr-exam-select"
            value={selectedId}
            onChange={e => setSelectedId(e.target.value)}
          >
            {exams.map(e => (
              <option key={e.id} value={e.id}>{e.title}</option>
            ))}
          </select>
        </div>

        <button
          className="exr-push-btn"
          onClick={handlePush}
          disabled={pushing || !results}
        >
          {pushing ? 'Pushing…' : '⇪ Push to Gradebook'}
        </button>
      </div>

      {/* Push feedback */}
      {pushResult && (
        <div className={`exr-push-feedback${pushResult.error ? ' exr-push-feedback--error' : ''}`}>
          {pushResult.error
            ? `⚠ ${pushResult.error}`
            : `✓ Updated ${pushResult.updated} score entries. Skipped: ${pushResult.skipped}.`}
        </div>
      )}

      {loading && (
        <div className="exr-loading">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="exr-skeleton" />
          ))}
        </div>
      )}

      {results && !loading && (
        <>
          {/* ── Stats strip ── */}
          <div className="exr-stats-strip">
            <div className="exr-stat">
              <span>Students</span>
              <strong>{results.total_students}</strong>
            </div>
            <div className="exr-stat">
              <span>Avg Score</span>
              <strong>
                {results.results.length
                  ? (
                      results.results
                        .filter(r => r.score !== null)
                        .reduce((s, r) => s + r.score, 0) /
                      (results.results.filter(r => r.score !== null).length || 1)
                    ).toFixed(1) + '%'
                  : '—'}
              </strong>
            </div>
            <div className="exr-stat">
              <span>Submitted</span>
              <strong>{results.results.filter(r => r.status === 'submitted').length}</strong>
            </div>
            <div className="exr-stat">
              <span>Timed Out</span>
              <strong>{results.results.filter(r => r.status === 'timed_out').length}</strong>
            </div>
          </div>

          {/* ── Score distribution chart ── */}
          <div className="exr-chart-card">
            <div className="exr-card-title">Score Distribution</div>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={distribution} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                <XAxis dataKey="range" tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="count" name="Students" radius={[4, 4, 0, 0]}>
                  {distribution.map((entry, i) => (
                    <Cell
                      key={i}
                      fill={i >= 7 ? '#16a34a' : i >= 5 ? '#d97706' : '#dc2626'}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* ── Tabs ── */}
          <div className="exr-tabs">
            <button
              className={`exr-tab${activeTab === 'students' ? ' exr-tab--active' : ''}`}
              onClick={() => setActiveTab('students')}
            >
              Student Results
            </button>
            <button
              className={`exr-tab${activeTab === 'questions' ? ' exr-tab--active' : ''}`}
              onClick={() => setActiveTab('questions')}
            >
              Question Analysis
            </button>
          </div>

          {/* ── Student results table ── */}
          {activeTab === 'students' && (
            <div className="exr-table-wrap">
              <table className="exr-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Student</th>
                    <th>Score</th>
                    <th>Time Taken</th>
                    <th>Tab Switches</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {results.results.map((r, idx) => (
                    <tr key={r.student_id}>
                      <td className="exr-td-num">{idx + 1}</td>
                      <td>{r.name}</td>
                      <td>
                        {r.score !== null ? (
                          <span
                            className="exr-score-pill"
                            style={{ background: scoreColor(r.score) }}
                          >
                            {r.score}%
                          </span>
                        ) : '—'}
                      </td>
                      <td>{formatTime(r.time_taken_seconds)}</td>
                      <td>
                        {r.tab_switches > 0
                          ? <span className="exr-tab-warn">{r.tab_switches}</span>
                          : '0'}
                      </td>
                      <td>
                        <span className={`exr-status exr-status--${r.status}`}>
                          {r.status.replace('_', ' ')}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* ── Question analysis table ── */}
          {activeTab === 'questions' && analysis && (
            <div className="exr-table-wrap">
              <table className="exr-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Question</th>
                    <th>Answered</th>
                    <th>% Correct</th>
                    <th>Most Wrong Option</th>
                  </tr>
                </thead>
                <tbody>
                  {analysis.map((q, idx) => (
                    <tr key={q.question_id}>
                      <td className="exr-td-num">{idx + 1}</td>
                      <td className="exr-question-cell">
                        {q.question_text.length > 90
                          ? q.question_text.slice(0, 90) + '…'
                          : q.question_text}
                      </td>
                      <td>{q.total_answered}</td>
                      <td>
                        <div className="exr-pct-bar-wrap">
                          <div
                            className="exr-pct-bar"
                            style={{
                              width: `${q.pct_correct}%`,
                              background: scoreColor(q.pct_correct),
                            }}
                          />
                          <span>{q.pct_correct}%</span>
                        </div>
                      </td>
                      <td>{q.most_chosen_wrong ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
