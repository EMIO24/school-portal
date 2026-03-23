/**
 * frontend/src/pages/teacher/TakeAttendance.jsx
 *
 * Teacher-facing attendance marking interface.
 *
 * Flow:
 *   1. Teacher selects class, term, date (± period in per-period mode).
 *   2. Click "Start Session" → POST sessions/start/ → pre-populated list.
 *   3. Per-student P/A/L/E toggle; remark field appears for A and L.
 *   4. "Mark All Present" bulk action.
 *   5. "Submit" → PATCH sessions/{id}/submit/ (idempotent, re-saves all rows).
 *   6. "Lock Register" → PATCH sessions/{id}/finalize/ → session frozen.
 *
 * If a session for today already exists the API returns it; the component
 * detects the 400 conflict and offers to reload the existing session.
 */

import React, { useState, useEffect, useReducer, useCallback } from 'react';
import api from '../../services/api';
import '../../styles/Attendance.css';

// ─── Status helpers ───────────────────────────────────────────────────────────

const STATUSES = [
  { key: 'present', label: 'P', title: 'Present' },
  { key: 'absent',  label: 'A', title: 'Absent'  },
  { key: 'late',    label: 'L', title: 'Late'     },
  { key: 'excused', label: 'E', title: 'Excused'  },
];

const STATUS_KEY = { present: 'P', absent: 'A', late: 'L', excused: 'E' };

// ─── Reducer for the per-student state map ────────────────────────────────────

function recordsReducer(state, action) {
  switch (action.type) {
    case 'INIT':
      // Seed from API pre-populated list
      return Object.fromEntries(
        action.records.map(r => [r.student, { status: r.status, remark: r.remark || '' }])
      );
    case 'SET_STATUS':
      return { ...state, [action.studentId]: { ...state[action.studentId], status: action.status } };
    case 'SET_REMARK':
      return { ...state, [action.studentId]: { ...state[action.studentId], remark: action.remark } };
    case 'MARK_ALL_PRESENT':
      return Object.fromEntries(
        Object.keys(state).map(sid => [sid, { status: 'present', remark: '' }])
      );
    default:
      return state;
  }
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function TakeAttendance() {
  // Selectors
  const [terms,      setTerms]      = useState([]);
  const [classArms,  setClassArms]  = useState([]);
  const [periods,    setPeriods]    = useState([]);
  const [schoolMode, setSchoolMode] = useState('daily'); // from school settings

  const [selectedTerm,     setSelectedTerm]     = useState('');
  const [selectedClassArm, setSelectedClassArm] = useState('');
  const [selectedDate,     setSelectedDate]     = useState(
    () => new Date().toISOString().split('T')[0]
  );
  const [selectedPeriod, setSelectedPeriod]     = useState('');

  // Session state
  const [session,    setSession]    = useState(null);
  const [students,   setStudents]   = useState([]);   // ordered student objects
  const [records,    dispatch]      = useReducer(recordsReducer, {});

  // UI state
  const [loading,    setLoading]    = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [finalizing, setFinalizing] = useState(false);
  const [error,      setError]      = useState(null);
  const [success,    setSuccess]    = useState(null);

  // ── Boot ────────────────────────────────────────────────────────────────────
  useEffect(() => {
    Promise.all([
      api.get('/academics/terms/'),
      api.get('/academics/class-arms/'),
      api.get('/timetable/periods/'),
      api.get('/schools/settings/'),       // includes attendance_mode
    ]).then(([t, c, p, s]) => {
      const termList = t.data.results ?? t.data;
      setTerms(termList);
      setClassArms(c.data.results ?? c.data);
      setPeriods(p.data.results ?? p.data);
      setSchoolMode(s.data?.attendance_mode ?? 'daily');

      const active = termList.find(x => x.is_active);
      if (active) setSelectedTerm(String(active.id));
    });
  }, []);

  // ── Start / resume session ──────────────────────────────────────────────────
  const handleStartSession = async () => {
    if (!selectedTerm || !selectedClassArm) {
      setError('Please select a term and class before starting.');
      return;
    }
    setLoading(true);
    setError(null);
    setSuccess(null);

    const body = {
      class_arm: Number(selectedClassArm),
      term:      Number(selectedTerm),
      date:      selectedDate,
      mode:      schoolMode,
      ...(schoolMode === 'per_period' && selectedPeriod
        ? { period: Number(selectedPeriod) }
        : {}),
    };

    try {
      const { data } = await api.post('/attendance/sessions/start/', body);
      loadSession(data);
    } catch (err) {
      const detail = err?.response?.data?.detail ?? '';
      if (detail.includes('already exists')) {
        // Offer to load the existing session
        setError('A session already exists for this slot. Loading it now…');
        await loadExistingSession(body);
      } else {
        setError(detail || 'Failed to start session.');
      }
    } finally {
      setLoading(false);
    }
  };

  const loadExistingSession = async ({ class_arm, term, date, mode, period }) => {
    try {
      const params = new URLSearchParams({ class_arm, term, date_exact: date, mode });
      if (period) params.set('period', period);
      const { data } = await api.get(`/attendance/sessions/?${params}`);
      const existing = (data.results ?? data)[0];
      if (existing) {
        const full = await api.get(`/attendance/sessions/${existing.id}/`);
        loadSession(full.data);
        setError(null);
      }
    } catch {
      setError('Could not load the existing session.');
    }
  };

  const loadSession = (data) => {
    setSession(data);
    // Build ordered student list from records
    const ordered = [...data.records].sort((a, b) =>
      a.student_name.localeCompare(b.student_name)
    );
    setStudents(ordered);
    dispatch({ type: 'INIT', records: data.records });
  };

  // ── Submit ──────────────────────────────────────────────────────────────────
  const handleSubmit = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const payload = {
        records: Object.entries(records).map(([studentId, rec]) => ({
          student_id: Number(studentId),
          status:     rec.status,
          remark:     rec.remark,
        })),
      };
      const { data } = await api.patch(`/attendance/sessions/${session.id}/submit/`, payload);
      loadSession(data);
      setSuccess('Attendance saved successfully.');
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      setError(err?.response?.data?.detail ?? 'Failed to submit attendance.');
    } finally {
      setSubmitting(false);
    }
  };

  // ── Finalize ─────────────────────────────────────────────────────────────────
  const handleFinalize = async () => {
    if (!window.confirm('Lock this register? It cannot be edited by teachers after this.')) return;
    setFinalizing(true);
    setError(null);
    try {
      await api.patch(`/attendance/sessions/${session.id}/finalize/`);
      setSession(prev => ({ ...prev, is_finalized: true }));
      setSuccess('Register locked successfully.');
    } catch (err) {
      setError(err?.response?.data?.detail ?? 'Could not finalize session.');
    } finally {
      setFinalizing(false);
    }
  };

  // ── Derived counts ───────────────────────────────────────────────────────────
  const counts = Object.values(records).reduce(
    (acc, r) => { acc[r.status] = (acc[r.status] || 0) + 1; return acc; },
    { present: 0, absent: 0, late: 0, excused: 0 }
  );

  const isFinalized = session?.is_finalized ?? false;

  // ── Render ────────────────────────────────────────────────────────────────────
  return (
    <div className="att-page">
      {/* Header */}
      <div className="att-header">
        <h1 className="att-header__title">
          Take Attendance
          <span className="att-header__sub">Mark daily register for your class</span>
        </h1>
      </div>

      {/* Controls */}
      {!session && (
        <div className="att-controls">
          <div className="att-field-group">
            <label>Term</label>
            <select className="att-select" value={selectedTerm}
              onChange={e => setSelectedTerm(e.target.value)}>
              <option value="">— Select term —</option>
              {terms.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </div>

          <div className="att-field-group">
            <label>Class</label>
            <select className="att-select" value={selectedClassArm}
              onChange={e => setSelectedClassArm(e.target.value)}>
              <option value="">— Select class —</option>
              {classArms.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>

          <div className="att-field-group">
            <label>Date</label>
            <input type="date" className="att-input" value={selectedDate}
              onChange={e => setSelectedDate(e.target.value)} />
          </div>

          {schoolMode === 'per_period' && (
            <div className="att-field-group">
              <label>Period</label>
              <select className="att-select" value={selectedPeriod}
                onChange={e => setSelectedPeriod(e.target.value)}>
                <option value="">— Select period —</option>
                {periods.filter(p => !p.is_break).map(p => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            </div>
          )}

          <div className="att-field-group" style={{ justifyContent: 'flex-end' }}>
            <label>&nbsp;</label>
            <button
              className="att-btn att-btn--primary"
              onClick={handleStartSession}
              disabled={loading || !selectedTerm || !selectedClassArm}
            >
              {loading ? 'Loading…' : 'Open Register'}
            </button>
          </div>
        </div>
      )}

      {/* Alerts */}
      {error   && <div className="att-alert att-alert--error">⚠ {error}</div>}
      {success && <div className="att-alert att-alert--info">✓ {success}</div>}

      {/* Session view */}
      {session && (
        <>
          {/* Session meta */}
          <div className="att-card" style={{ marginBottom: 20 }}>
            <div className="att-card__head">
              <h2 className="att-card__title">
                📋 {session.class_name} — {session.date}
                {session.period && ` / ${session.period}`}
              </h2>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                {isFinalized
                  ? <span className="att-finalized-badge">🔒 Locked</span>
                  : (
                    <button
                      className="att-btn att-btn--ghost"
                      onClick={() => setSession(null)}
                    >← Back</button>
                  )}
              </div>
            </div>
          </div>

          {/* Stats strip */}
          <div className="att-stats-strip">
            {[
              { key: 'present', label: 'Present',  cls: '' },
              { key: 'absent',  label: 'Absent',   cls: 'is-absent' },
              { key: 'late',    label: 'Late',      cls: 'is-late' },
              { key: 'excused', label: 'Excused',   cls: 'is-excused' },
            ].map(s => (
              <div key={s.key} className="att-stat-chip">
                <span className={`att-stat-chip__num ${s.cls}`}>{counts[s.key] || 0}</span>
                <span className="att-stat-chip__label">{s.label}</span>
              </div>
            ))}
          </div>

          {/* Bulk bar */}
          {!isFinalized && (
            <div className="att-bulk-bar">
              <span>{students.length} students total</span>
              <button
                className="att-btn att-btn--ghost"
                onClick={() => dispatch({ type: 'MARK_ALL_PRESENT' })}
              >
                ✓ Mark all present
              </button>
            </div>
          )}

          {/* Student list */}
          <div className="att-card">
            <ul className="att-student-list">
              {students.map((student, idx) => {
                const rec      = records[student.student] || { status: 'present', remark: '' };
                const showRemark = !isFinalized && (rec.status === 'absent' || rec.status === 'late');

                return (
                  <li key={student.student}>
                    <div className="att-student-row">
                      <span className="att-student-row__num">{idx + 1}</span>
                      <span className="att-student-row__name">{student.student_name}</span>
                      <span className="att-student-row__adm">{student.student_admission}</span>

                      <div className="att-status-group">
                        {STATUSES.map(s => (
                          <button
                            key={s.key}
                            className={`att-status-btn is-${STATUS_KEY[s.key]}${rec.status === s.key ? ' active' : ''}`}
                            title={s.title}
                            disabled={isFinalized}
                            onClick={() => dispatch({
                              type: 'SET_STATUS',
                              studentId: student.student,
                              status: s.key,
                            })}
                          >{s.label}</button>
                        ))}
                      </div>
                    </div>

                    {showRemark && (
                      <div className="att-student-row" style={{ paddingTop: 0 }}>
                        <span /><span />
                        <input
                          className="att-remark-input"
                          placeholder="Remark (optional)…"
                          value={rec.remark}
                          onChange={e => dispatch({
                            type: 'SET_REMARK',
                            studentId: student.student,
                            remark: e.target.value,
                          })}
                        />
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>

          {/* Action footer */}
          {!isFinalized && (
            <div style={{ display: 'flex', gap: 12, marginTop: 20, justifyContent: 'flex-end' }}>
              <button
                className="att-btn att-btn--primary"
                onClick={handleSubmit}
                disabled={submitting}
              >
                {submitting ? 'Saving…' : '💾 Save Attendance'}
              </button>
              <button
                className="att-btn att-btn--lock"
                onClick={handleFinalize}
                disabled={finalizing || submitting}
              >
                🔒 {finalizing ? 'Locking…' : 'Lock Register'}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}