/**
 * frontend/src/pages/teacher/ScoreEntry.jsx
 *
 * Spreadsheet-style score entry for a class × subject × term.
 *
 * Layout:
 *   S/N | Student Name | 1st Test /10 | 2nd Test /10 | Assignment /10
 *   | Project /5 | Practical /5 | CA Total /40 | Exam /60 | Total | Grade | Remark
 *
 * UX:
 *   - Tab moves focus to next editable cell (left→right, wraps to next row)
 *   - CA Total and Grade/Remark update client-side as user types
 *   - Row background tinted green/amber/red by result band
 *   - "Save Draft"    → POST bulk-update/ (is_published stays false)
 *   - "Publish"       → Save + POST publish/
 *   - Unsaved dot on page title while there are pending changes
 *   - Per-cell error display for max exceeded violations
 */

import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import GradeCell, { GradeBadge, ComputedCell, rowClass } from '../../components/teacher/GradeCell';
import api from '../../services/api';
import '../../styles/ScoreEntry.css';

// ─── Constants ────────────────────────────────────────────────────────────────

const CA_FIELDS = [
  { key: 'first_test',  label: '1st Test',   max: 10 },
  { key: 'second_test', label: '2nd Test',   max: 10 },
  { key: 'assignment',  label: 'Assignment', max: 10 },
  { key: 'project',     label: 'Project',    max:  5 },
  { key: 'practical',   label: 'Practical',  max:  5 },
];
const MAX_CA   = 40;
const MAX_EXAM = 60;

// All editable columns in Tab order
const EDITABLE_KEYS = [...CA_FIELDS.map(f => f.key), 'exam_score'];

// ─── Grading helper (client-side, mirrors backend logic) ─────────────────────

function resolveGrade(total, bands) {
  if (!bands?.length) return { grade: '', remark: '' };
  const band = bands.find(b => total >= b.min_score && total <= b.max_score);
  return band ? { grade: band.grade, remark: band.remark } : { grade: 'F9', remark: 'Fail' };
}

function computeCA(row) {
  return CA_FIELDS.reduce((sum, f) => sum + (parseFloat(row[f.key]) || 0), 0);
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function ScoreEntry() {
  // Selectors
  const [terms,      setTerms]      = useState([]);
  const [sessions,   setSessions]   = useState([]);
  const [classArms,  setClassArms]  = useState([]);
  const [subjects,   setSubjects]   = useState([]);

  const [selTerm,     setSelTerm]     = useState('');
  const [selSession,  setSelSession]  = useState('');
  const [selClass,    setSelClass]    = useState('');
  const [selSubject,  setSelSubject]  = useState('');

  // Grade bands for client-side preview
  const [gradeBands,  setGradeBands]  = useState([]);

  // Row data keyed by studentId
  const [rows,       setRows]       = useState({});   // { studentId: rowObj }
  const [students,   setStudents]   = useState([]);   // ordered list
  const [dirty,      setDirty]      = useState(false);
  const [errors,     setErrors]     = useState({});   // { studentId: { field: msg } }

  const [loading,    setLoading]    = useState(false);
  const [saving,     setSaving]     = useState(false);
  const [alert,      setAlert]      = useState(null); // { type, msg }

  const cellRefs = useRef({});   // { `${studentId}_${field}` : ref }

  // ── Boot ────────────────────────────────────────────────────────────────────
  useEffect(() => {
    Promise.all([
      api.get('/academics/terms/'),
      api.get('/academics/sessions/'),
      api.get('/enrollment/class-arms/'),
      api.get('/enrollment/subjects/'),
      api.get('/gradebook/entries/grade-scale/'),
    ]).then(([t, s, c, sub, gs]) => {
      const termList = t.data.results ?? t.data;
      setTerms(termList);
      setSessions(s.data.results ?? s.data);
      setClassArms(c.data.results ?? c.data);
      setSubjects(sub.data.results ?? sub.data);
      setGradeBands(gs.data.bands ?? []);

      const active = termList.find(x => x.is_current);
      if (active) setSelTerm(String(active.id));
    });
  }, []);

  // ── Load scores when all selectors are set ──────────────────────────────────
  const loadScores = useCallback(async () => {
    if (!selTerm || !selClass || !selSubject) return;
    setLoading(true);
    setDirty(false);
    setErrors({});
    try {
      const { data } = await api.get(
        `/gradebook/entries/?class_arm=${selClass}&subject=${selSubject}&term=${selTerm}`
      );
      const entries = data.results ?? data;

      // Also fetch the full enrolled student list so ungraded students appear
      const { data: stuData } = await api.get(
        `/enrollment/students/?class_arm=${selClass}`
      );
      const allStudents = stuData.results ?? stuData;
      setStudents(allStudents);

      // Build row map — start from API data, fill blanks for ungraded students
      const rowMap = {};
      allStudents.forEach(stu => {
        const existing = entries.find(e => e.student === stu.id);
        rowMap[stu.id] = existing
          ? {
              first_test:  existing.first_test,
              second_test: existing.second_test,
              assignment:  existing.assignment,
              project:     existing.project,
              practical:   existing.practical,
              exam_score:  existing.exam_score,
              is_published: existing.is_published,
              entry_id:    existing.id,
            }
          : {
              first_test: '', second_test: '', assignment: '',
              project: '', practical: '', exam_score: '',
              is_published: false, entry_id: null,
            };
      });
      setRows(rowMap);
    } finally {
      setLoading(false);
    }
  }, [selTerm, selClass, selSubject]);

  useEffect(() => { loadScores(); }, [loadScores]);

  // ── Cell change ─────────────────────────────────────────────────────────────
  const handleChange = useCallback((studentId, field, value) => {
    setRows(prev => ({ ...prev, [studentId]: { ...prev[studentId], [field]: value } }));
    setDirty(true);
    // Clear per-cell error on change
    setErrors(prev => {
      if (!prev[studentId]?.[field]) return prev;
      const next = { ...prev };
      delete next[studentId][field];
      return next;
    });
  }, []);

  // ── Tab navigation ──────────────────────────────────────────────────────────
  const handleTab = useCallback((e, studentId, fieldKey) => {
    e.preventDefault();
    const forward = !e.shiftKey;
    const colIdx  = EDITABLE_KEYS.indexOf(fieldKey);
    const rowIdx  = students.findIndex(s => s.id === studentId);

    let nextCol = colIdx + (forward ? 1 : -1);
    let nextRow = rowIdx;

    if (nextCol >= EDITABLE_KEYS.length) { nextCol = 0; nextRow++; }
    if (nextCol < 0) { nextCol = EDITABLE_KEYS.length - 1; nextRow--; }
    if (nextRow < 0 || nextRow >= students.length) return;

    const nextKey = `${students[nextRow].id}_${EDITABLE_KEYS[nextCol]}`;
    cellRefs.current[nextKey]?.focus();
  }, [students]);

  // ── Save draft ──────────────────────────────────────────────────────────────
  const save = async (publish = false) => {
    if (!selSession) {
      setAlert({ type: 'error', msg: 'Please select an academic session before saving.' });
      return;
    }
    setSaving(true);
    setAlert(null);

    const scores = students.map(stu => ({
      student_id:  stu.id,
      first_test:  rows[stu.id]?.first_test  || 0,
      second_test: rows[stu.id]?.second_test || 0,
      assignment:  rows[stu.id]?.assignment  || 0,
      project:     rows[stu.id]?.project     || 0,
      practical:   rows[stu.id]?.practical   || 0,
      exam_score:  rows[stu.id]?.exam_score  || 0,
    }));

    try {
      const { data } = await api.post('/gradebook/entries/bulk-update/', {
        class_arm: Number(selClass),
        subject:   Number(selSubject),
        term:      Number(selTerm),
        session:   Number(selSession),
        scores,
      });

      if (Object.keys(data.errors || {}).length) {
        setErrors(data.errors);
        setAlert({ type: 'error', msg: 'Some rows have validation errors. Please correct them.' });
      } else {
        setDirty(false);
        if (publish) {
          await api.post(
            `/gradebook/entries/publish/?class_arm=${selClass}&subject=${selSubject}&term=${selTerm}`
          );
          setAlert({ type: 'success', msg: 'Scores saved and published to students.' });
        } else {
          setAlert({ type: 'success', msg: 'Scores saved as draft.' });
        }
        await loadScores();
      }
    } catch (err) {
      setAlert({ type: 'error', msg: err?.response?.data?.detail ?? 'Save failed.' });
    } finally {
      setSaving(false);
    }
  };

  // ── Derived per-row computed values ─────────────────────────────────────────
  const computed = useMemo(() => {
    const out = {};
    for (const stu of students) {
      const row  = rows[stu.id] || {};
      const ca   = computeCA(row);
      const exam = parseFloat(row.exam_score) || 0;
      const tot  = ca + exam;
      const { grade, remark } = resolveGrade(tot, gradeBands);
      out[stu.id] = { ca, total: tot, grade, remark };
    }
    return out;
  }, [rows, students, gradeBands]);

  // ── Stats ────────────────────────────────────────────────────────────────────
  const stats = useMemo(() => {
    const graded = students.filter(s => computed[s.id]?.total > 0);
    const avg    = graded.length
      ? graded.reduce((sum, s) => sum + computed[s.id].total, 0) / graded.length
      : 0;
    const pass   = graded.filter(s => computed[s.id].grade !== 'F9').length;
    return { total: students.length, graded: graded.length, avg: avg.toFixed(1), pass };
  }, [students, computed]);

  const canRender = selTerm && selClass && selSubject;
  const isPublished = students.length > 0 && students.every(s => rows[s.id]?.is_published);

  // ── Render ────────────────────────────────────────────────────────────────────
  return (
    <div className="gb-page">
      {/* Header */}
      <div className="gb-header">
        <h1 className="gb-header__title">
          Score Entry
          {dirty && <span className="gb-unsaved-dot" title="Unsaved changes" />}
          <span className="gb-header__sub">CA (40%) + Exam (60%) · WAEC A1–F9 grading</span>
        </h1>
      </div>

      {/* Controls */}
      <div className="gb-controls">
        {[
          { label: 'Term',    val: selTerm,    set: setSelTerm,    opts: terms,     labelKey: 'name' },
          { label: 'Session', val: selSession, set: setSelSession, opts: sessions,  labelKey: 'name' },
          { label: 'Class',   val: selClass,   set: setSelClass,   opts: classArms, labelKey: 'name' },
          { label: 'Subject', val: selSubject, set: setSelSubject, opts: subjects,  labelKey: 'name' },
        ].map(({ label, val, set, opts, labelKey }) => (
          <div key={label} className="gb-field-group">
            <label>{label}</label>
            <select className="gb-select" value={val} onChange={e => set(e.target.value)}>
              <option value="">— {label} —</option>
              {opts.map(o => <option key={o.id} value={o.id}>{o[labelKey]}</option>)}
            </select>
          </div>
        ))}

        <div className="gb-field-group" style={{ justifyContent: 'flex-end' }}>
          <label>&nbsp;</label>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              className="gb-btn gb-btn--draft"
              onClick={() => save(false)}
              disabled={saving || !canRender || !dirty}
            >
              {saving ? 'Saving…' : '💾 Save Draft'}
            </button>
            <button
              className="gb-btn gb-btn--publish"
              onClick={() => save(true)}
              disabled={saving || !canRender || isPublished}
            >
              {isPublished ? '✓ Published' : '🚀 Publish'}
            </button>
          </div>
        </div>
      </div>

      {/* Alert */}
      {alert && (
        <div className={`gb-alert gb-alert--${alert.type}`}>
          {alert.type === 'error' ? '❌' : '✓'} {alert.msg}
        </div>
      )}

      {/* Stats strip */}
      {canRender && !loading && students.length > 0 && (
        <div className="gb-stats-strip">
          {[
            { num: stats.total,   label: 'Students' },
            { num: stats.graded,  label: 'Entered'  },
            { num: stats.avg,     label: 'Class Avg' },
            { num: stats.pass,    label: 'Pass'      },
          ].map(s => (
            <div key={s.label} className="gb-stat-chip">
              <span className="gb-stat-chip__num">{s.num}</span>
              <span className="gb-stat-chip__label">{s.label}</span>
            </div>
          ))}
        </div>
      )}

      {/* Spreadsheet table */}
      {!canRender ? (
        <div className="gb-table-wrap">
          <div className="gb-empty">
            <strong>Nothing to display</strong>
            Select a term, session, class, and subject above.
          </div>
        </div>
      ) : loading ? (
        <div className="gb-table-wrap" style={{ padding: 24 }}>
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="gb-skeleton" style={{ height: 40, marginBottom: 6 }} />
          ))}
        </div>
      ) : (
        <div className="gb-table-wrap">
          <table className="gb-table">
            <thead>
              <tr>
                <th className="col-sn" rowSpan={2}>#</th>
                <th className="col-name" rowSpan={2}>Student Name</th>
                {CA_FIELDS.map(f => (
                  <th key={f.key} title={`Max ${f.max}`}>{f.label}<br /><small>/{f.max}</small></th>
                ))}
                <th rowSpan={2} style={{ background: 'rgba(0,0,0,.15)' }}>CA<br />/40</th>
                <th rowSpan={2}>Exam<br />/60</th>
                <th rowSpan={2} style={{ background: 'rgba(0,0,0,.15)' }}>Total</th>
                <th rowSpan={2}>Grade</th>
                <th rowSpan={2}>Remark</th>
              </tr>
              <tr className="gb-sub-header">
                {CA_FIELDS.map(f => <th key={f.key}>Continuous Assessment</th>)}
              </tr>
            </thead>
            <tbody>
              {students.map((stu, idx) => {
                const row  = rows[stu.id] || {};
                const comp = computed[stu.id] || {};
                const rc   = rowClass(comp.grade);
                const rowErrors = errors[stu.id] || {};

                return (
                  <tr key={stu.id} className={rc}>
                    <td className="col-sn">{idx + 1}</td>
                    <td className="col-name">{stu.full_name}</td>

                    {/* CA editable cells */}
                    {CA_FIELDS.map(f => (
                      <GradeCell
                        key={f.key}
                        value={row[f.key]}
                        max={f.max}
                        hasError={Boolean(rowErrors[f.key])}
                        fieldName={f.label}
                        onChange={v => handleChange(stu.id, f.key, v)}
                        onTab={e => handleTab(e, stu.id, f.key)}
                        inputRef={el => { cellRefs.current[`${stu.id}_${f.key}`] = el; }}
                      />
                    ))}

                    {/* CA Total (computed) */}
                    <td className="col-computed">
                      <ComputedCell value={comp.ca} />
                    </td>

                    {/* Exam */}
                    <GradeCell
                      value={row.exam_score}
                      max={MAX_EXAM}
                      hasError={Boolean(rowErrors.exam_score)}
                      fieldName="Exam"
                      onChange={v => handleChange(stu.id, 'exam_score', v)}
                      onTab={e => handleTab(e, stu.id, 'exam_score')}
                      inputRef={el => { cellRefs.current[`${stu.id}_exam_score`] = el; }}
                    />

                    {/* Total (computed) */}
                    <td className="col-computed">
                      <ComputedCell value={comp.total} />
                    </td>

                    {/* Grade badge */}
                    <td className="col-computed" style={{ textAlign: 'center' }}>
                      <GradeBadge grade={comp.grade} />
                    </td>

                    {/* Remark */}
                    <td style={{ fontSize: '.8rem', color: 'var(--gb-ink-mid)' }}>
                      {comp.remark || '—'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}