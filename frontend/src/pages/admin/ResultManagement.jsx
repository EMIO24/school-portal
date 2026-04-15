/**
 * frontend/src/pages/admin/ResultManagement.jsx
 *
 * Admin result management dashboard:
 *   - Class + Term selectors
 *   - "Compute Positions" button
 *   - Student table: position | name | average | remark status
 *   - Click row → inline remark editor expands (class teacher + principal)
 *   - "Download All Slips (ZIP)" + "Download Broadsheet (PDF)" buttons
 */

import React, { useState, useEffect, useCallback } from 'react';
import api from '../../services/api';
import '../../styles/Results.css';

// ─── Helpers ─────────────────────────────────────────────────────────────────

function ordinal(n) {
  if (!n) return '—';
  const s = ['th','st','nd','rd'];
  const v = n % 100;
  return n + (s[(v-20)%10] || s[v] || s[0]);
}

function posClass(pos) {
  if (pos === 1) return 'gold';
  if (pos === 2) return 'silver';
  if (pos === 3) return 'bronze';
  return '';
}

// ─── Inline remark editor ─────────────────────────────────────────────────────

function RemarkDrawer({ student, termId, onSaved, onClose }) {
  const [ctRemark,  setCtRemark]  = useState(student.class_teacher_remark || '');
  const [prinRemark, setPrinRemark] = useState(student.principal_remark    || '');
  const [saving,    setSaving]    = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.patch(
        `/results/remarks/${student.student}/?term=${termId}`,
        { class_teacher_remark: ctRemark, principal_remark: prinRemark }
      );
      onSaved(student.student, ctRemark, prinRemark);
    } catch (err) {
      alert('Save failed: ' + (err?.response?.data?.detail ?? 'Unknown error'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <tr>
      <td colSpan={6} style={{ padding: 0 }}>
        <div className="res-remark-drawer">
          <div className="res-remark-field">
            <label>Class Teacher's Remark</label>
            <textarea
              className="res-remark-textarea"
              value={ctRemark}
              onChange={e => setCtRemark(e.target.value)}
              placeholder="Enter class teacher's remark…"
            />
          </div>
          <div className="res-remark-field">
            <label>Principal's Remark</label>
            <textarea
              className="res-remark-textarea"
              value={prinRemark}
              onChange={e => setPrinRemark(e.target.value)}
              placeholder="Enter principal's remark…"
            />
          </div>
          <div className="res-remark-actions">
            <button className="res-btn res-btn--ghost" onClick={onClose}>Cancel</button>
            <button className="res-btn res-btn--navy" onClick={handleSave} disabled={saving}>
              {saving ? 'Saving…' : '💾 Save Remarks'}
            </button>
          </div>
        </div>
      </td>
    </tr>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function ResultManagement() {
  const [terms,      setTerms]      = useState([]);
  const [classArms,  setClassArms]  = useState([]);
  const [selTerm,    setSelTerm]    = useState('');
  const [selClass,   setSelClass]   = useState('');

  const [students,   setStudents]   = useState([]);
  const [loading,    setLoading]    = useState(false);
  const [computing,  setComputing]  = useState(false);
  const [alert,      setAlert]      = useState(null);

  // Which student row has the remark drawer open
  const [expandedId, setExpandedId] = useState(null);

  // ── Boot ────────────────────────────────────────────────────────────────────
  useEffect(() => {
    Promise.all([
      api.get('/academics/terms/'),
      api.get('/enrollment/class-arms/'),
    ]).then(([t, c]) => {
      const termList = t.data.results ?? t.data;
      setTerms(termList);
      setClassArms(c.data.results ?? c.data);
      const current = termList.find(x => x.is_current);
      if (current) setSelTerm(String(current.id));
    });
  }, []);

  // ── Load results table ───────────────────────────────────────────────────────
  const load = useCallback(async () => {
    if (!selTerm || !selClass) return;
    setLoading(true);
    setAlert(null);
    try {
      const { data } = await api.get(
        `/results/class-results/?class_arm=${selClass}&term=${selTerm}`
      );
      setStudents(data);
    } catch {
      setAlert({ type: 'error', msg: 'Failed to load results. Have positions been computed?' });
    } finally {
      setLoading(false);
    }
  }, [selTerm, selClass]);

  useEffect(() => { load(); }, [load]);

  // ── Compute positions ────────────────────────────────────────────────────────
  const handleComputePositions = async () => {
    if (!selClass || !selTerm) return;
    setComputing(true);
    setAlert(null);
    try {
      const { data } = await api.post(
        `/results/positions/compute/?class_arm=${selClass}&term=${selTerm}`
      );
      setAlert({ type: 'success', msg: `Positions computed for ${data.computed} students.` });
      await load();
    } catch (err) {
      setAlert({ type: 'error', msg: err?.response?.data?.detail ?? 'Compute failed.' });
    } finally {
      setComputing(false);
    }
  };

  // ── PDF/ZIP downloads ────────────────────────────────────────────────────────
  const apiBase = process.env.REACT_APP_API_BASE_URL || '';

  const downloadBroadsheet = () => {
    window.open(`${apiBase}/api/results/broadsheet/${selClass}/?term=${selTerm}`, '_blank');
  };

  const downloadAllSlips = () => {
    window.open(`${apiBase}/api/results/all-slips/${selClass}/?term=${selTerm}`, '_blank');
  };

  const downloadSlip = (studentId) => {
    window.open(`${apiBase}/api/results/slip/${studentId}/?term=${selTerm}`, '_blank');
  };

  // ── Remark saved callback ────────────────────────────────────────────────────
  const handleRemarkSaved = (studentId, ctRemark, prinRemark) => {
    setStudents(prev =>
      prev.map(s =>
        s.student === studentId
          ? { ...s, class_teacher_remark: ctRemark, principal_remark: prinRemark }
          : s
      )
    );
    setExpandedId(null);
    setAlert({ type: 'success', msg: 'Remarks saved.' });
    setTimeout(() => setAlert(null), 2500);
  };

  // ── Stats ────────────────────────────────────────────────────────────────────
  const remarked  = students.filter(s => s.class_teacher_remark || s.principal_remark).length;
  const avgClass  = students.length
    ? (students.reduce((sum, s) => sum + (parseFloat(s.average_score) || 0), 0) / students.length).toFixed(1)
    : '—';

  const canDownload = selClass && selTerm && students.length > 0;

  // ── Render ────────────────────────────────────────────────────────────────────
  return (
    <div className="res-page">
      {/* Header */}
      <div className="res-header">
        <h1 className="res-title">
          Result Management
          <small>Compute positions · Add remarks · Generate PDFs</small>
        </h1>
      </div>

      {/* Controls */}
      <div className="res-controls">
        <div className="res-field-group">
          <label>Term</label>
          <select className="res-select" value={selTerm} onChange={e => setSelTerm(e.target.value)}>
            <option value="">— Select term —</option>
            {terms.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </div>
        <div className="res-field-group">
          <label>Class</label>
          <select className="res-select" value={selClass} onChange={e => setSelClass(e.target.value)}>
            <option value="">— Select class —</option>
            {classArms.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>

        {/* Action buttons */}
        <div className="res-field-group" style={{ justifyContent: 'flex-end' }}>
          <label>&nbsp;</label>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button
              className="res-btn res-btn--amber"
              onClick={handleComputePositions}
              disabled={computing || !selClass || !selTerm}
            >
              {computing ? '⏳ Computing…' : '📊 Compute Positions'}
            </button>
            <button
              className="res-btn res-btn--ghost"
              onClick={downloadBroadsheet}
              disabled={!canDownload}
            >
              📋 Broadsheet PDF
            </button>
            <button
              className="res-btn res-btn--navy"
              onClick={downloadAllSlips}
              disabled={!canDownload}
            >
              📦 All Slips ZIP
            </button>
          </div>
        </div>
      </div>

      {/* Alert */}
      {alert && (
        <div className={`res-alert res-alert--${alert.type}`}>
          {alert.type === 'success' ? '✓' : '⚠'} {alert.msg}
        </div>
      )}

      {/* Stats chips */}
      {students.length > 0 && (
        <div className="res-stats-strip">
          {[
            { num: students.length, label: 'Students'      },
            { num: avgClass,        label: 'Class Average'  },
            { num: remarked,        label: 'Remarked'       },
            { num: students.length - remarked, label: 'Pending Remarks' },
          ].map(s => (
            <div key={s.label} className="res-stat-chip">
              <span className="res-stat-chip__num">{s.num}</span>
              <span className="res-stat-chip__label">{s.label}</span>
            </div>
          ))}
        </div>
      )}

      {/* Student table */}
      <div className="res-card">
        <div className="res-card__head">
          <h2 className="res-card__title">📋 Class Results</h2>
          <span style={{ fontSize: '.78rem', color: 'var(--res-ink-light)' }}>
            {loading ? 'Loading…' : `${students.length} students`}
          </span>
        </div>

        {!selTerm || !selClass ? (
          <div className="res-empty">
            <strong>Nothing to display</strong>
            Select a term and class to manage results.
          </div>
        ) : loading ? (
          <div style={{ padding: 24 }}>
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="res-skeleton" style={{ height: 44, marginBottom: 8 }} />
            ))}
          </div>
        ) : students.length === 0 ? (
          <div className="res-empty">
            <strong>No results yet</strong>
            Click "Compute Positions" after all scores have been published.
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="res-table">
              <thead>
                <tr>
                  <th className="center" style={{ width: 56 }}>Position</th>
                  <th>Student Name</th>
                  <th className="center">Subjects</th>
                  <th className="center">Average</th>
                  <th className="center">Remarks</th>
                  <th className="center">Actions</th>
                </tr>
              </thead>
              <tbody>
                {students.map(student => (
                  <React.Fragment key={student.student}>
                    <tr>
                      {/* Position */}
                      <td style={{ textAlign: 'center' }}>
                        <span className={`res-pos-badge ${posClass(student.computed_position)}`}>
                          {ordinal(student.computed_position)}
                        </span>
                      </td>

                      {/* Name */}
                      <td style={{ fontWeight: 600 }}>{student.student_name}</td>

                      {/* Subjects */}
                      <td style={{ textAlign: 'center', fontFamily: 'var(--font-mono)' }}>
                        {student.subjects_offered}
                      </td>

                      {/* Average */}
                      <td>
                        <div className="res-avg-bar">
                          <div className="res-avg-track">
                            <div
                              className="res-avg-fill"
                              style={{ width: `${Math.min(student.average_score, 100)}%` }}
                            />
                          </div>
                          <span className="res-avg-num">
                            {parseFloat(student.average_score || 0).toFixed(1)}
                          </span>
                        </div>
                      </td>

                      {/* Remark status */}
                      <td style={{ textAlign: 'center' }}>
                        <span className={`res-remark-status ${student.class_teacher_remark || student.principal_remark ? 'done' : 'empty'}`}>
                          {student.class_teacher_remark || student.principal_remark ? '✓ Added' : '— Pending'}
                        </span>
                      </td>

                      {/* Actions */}
                      <td style={{ textAlign: 'center' }}>
                        <div style={{ display: 'flex', gap: 6, justifyContent: 'center' }}>
                          <button
                            className="res-btn res-btn--ghost"
                            style={{ padding: '5px 10px', fontSize: '.78rem' }}
                            onClick={() => setExpandedId(
                              expandedId === student.student ? null : student.student
                            )}
                          >
                            {expandedId === student.student ? '▲ Close' : '✏ Remark'}
                          </button>
                          <button
                            className="res-btn res-btn--ghost"
                            style={{ padding: '5px 10px', fontSize: '.78rem' }}
                            onClick={() => downloadSlip(student.student)}
                          >
                            📄 Slip
                          </button>
                        </div>
                      </td>
                    </tr>

                    {/* Inline remark drawer */}
                    {expandedId === student.student && (
                      <RemarkDrawer
                        student={student}
                        termId={selTerm}
                        onSaved={handleRemarkSaved}
                        onClose={() => setExpandedId(null)}
                      />
                    )}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}