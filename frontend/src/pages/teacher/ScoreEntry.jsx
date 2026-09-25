/** Term-configured score sheet. Saved totals and grades are authoritative. */
import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import GradeCell, { GradeBadge, ComputedCell, rowClass } from '../../components/teacher/GradeCell';
import api from '../../services/api';
import {scoringError} from '../admin/ScoringConfiguration';
import '../../styles/ScoreEntry.css';

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

  // Components loaded from the selected term.
  const [components, setComponents] = useState([]);
  const EDITABLE_KEYS = useMemo(() => components.map(c=>c.key),[components]);

  // Row data keyed by studentId
  const [rows,       setRows]       = useState({});   // { studentId: rowObj }
  const [students,   setStudents]   = useState([]);   // ordered list
  const [dirty,      setDirty]      = useState(false);
  const [errors,     setErrors]     = useState({});   // { studentId: { field: msg } }

  const [loading,    setLoading]    = useState(false);
  const [saving,     setSaving]     = useState(false);
  const [alert,      setAlert]      = useState(null); // { type, msg }

  const loadVersion = useRef(0);
  const cellRefs = useRef({});   // { `${studentId}_${field}` : ref }

  // ── Boot ────────────────────────────────────────────────────────────────────
  useEffect(() => {
    Promise.all([
      api.get('/api/terms/'),
      api.get('/api/sessions/'),
      api.get('/api/class-arms/'),
      api.get('/api/subjects/'),
    ]).then(([t, s, c, sub]) => {
      const termList = t.data.results ?? t.data;
      setTerms(termList);
      setSessions(s.data.results ?? s.data);
      setClassArms(c.data.results ?? c.data);
      setSubjects(sub.data.results ?? sub.data);

      const active = termList.find(x => x.is_current);
      if (active) setSelTerm(String(active.id));
    }).catch(() => setAlert({type:'error',msg:'Could not load score-entry options. Reload this page to retry.'}));
  }, []);

  // ── Load scores when all selectors are set ──────────────────────────────────
  const loadScores = useCallback(async () => {
    const version = ++loadVersion.current;
    if (!selTerm || !selClass || !selSubject) {setStudents([]);setRows({});setDirty(false);return;}
    setLoading(true);
    setDirty(false);
    setErrors({});
    try {
      const { data } = await api.get(
        '/api/gradebook/entries/sheet/?class_arm=' + selClass + '&subject=' + selSubject + '&term=' + selTerm
      );
      if(version !== loadVersion.current)return;
      const entries = data.entries;
      setComponents(data.configuration.components);
      const allStudents = data.students.map(stu => ({...stu, id:stu.user}));
      setSelSession(String(data.session));
      setStudents(allStudents);

      // Build row map — start from API data, fill blanks for ungraded students
      const rowMap = {};
      allStudents.forEach(stu => {
        const existing = entries.find(e => e.student === stu.id);
        rowMap[stu.id] = {...existing,...Object.fromEntries(data.configuration.components.map(c=>[c.key,existing?.policy ? (existing.component_scores[c.key] ?? '') : (existing?.[c.key] ?? '')])),review_state:existing?.review_state || 'draft',is_published:existing?.is_published || false};
      });
      setRows(rowMap);
    } catch {
      if(version !== loadVersion.current)return;
      setStudents([]); setRows({});
      setAlert({type:'error',msg:'Could not load this score sheet. Check your class, subject and term assignment.'});
    } finally {
      if(version === loadVersion.current)setLoading(false);
    }
  }, [selTerm, selClass, selSubject]);

  useEffect(() => { loadScores(); }, [loadScores]);

  // ── Cell change ─────────────────────────────────────────────────────────────
  const handleChange = useCallback((studentId, field, value) => {
    setRows(prev => ({ ...prev, [studentId]: { ...prev[studentId], [field]: value, grade:"", remark:"Save to calculate grade" } }));
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
  }, [students, EDITABLE_KEYS]);

  // ── Save draft ──────────────────────────────────────────────────────────────
  const save = async () => {
    if (!selSession) {
      setAlert({ type: 'error', msg: 'Please select an academic session before saving.' });
      return;
    }
    setSaving(true);
    setAlert(null);

    const scores = students.filter(stu => !rows[stu.id]?.is_published && rows[stu.id]?.review_state === 'draft').map(stu => ({student_id:stu.id,component_scores:Object.fromEntries(components.map(c=>[c.key,rows[stu.id]?.[c.key] === '' ? null : rows[stu.id]?.[c.key]]))}));

    try {
      const { data } = await api.post('/api/gradebook/entries/bulk-update/', {
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
        setAlert({ type: 'success', msg: 'Draft saved. Your school administrator can review and publish these scores.' });
        await loadScores();
      }
    } catch (err) {
      setAlert({ type: 'error', msg: scoringError(err) });
    } finally {
      setSaving(false);
    }
  };

  // ── Derived per-row computed values ─────────────────────────────────────────
  const computed = useMemo(() => {
    const out = {};
    for (const stu of students) {
      const row  = rows[stu.id] || {};
      const total = components.reduce((sum,c)=>sum+Math.round(Number(row[c.key] || 0)*100),0)/100;
      out[stu.id] = {total,grade:row.grade,remark:row.remark};
    }
    return out;
  }, [rows, students, components]);

  // ── Stats ────────────────────────────────────────────────────────────────────
  const stats = useMemo(() => {
    const graded = students.filter(s => computed[s.id]?.total > 0);
    const avg    = graded.length
      ? graded.reduce((sum, s) => sum + computed[s.id].total, 0) / graded.length
      : 0;
    const pass = students.filter(s=>rows[s.id]?.is_published).length;
    return { total: students.length, graded: graded.length, avg: avg.toFixed(1), pass };
  }, [students, computed, rows]);

  const canRender = selTerm && selSession && selClass && selSubject;

  // ── Render ────────────────────────────────────────────────────────────────────
  return (
    <div className="gb-page">
      {/* Header */}
      <div className="gb-header">
        <h1 className="gb-header__title">
          Score Entry
          {dirty && <span className="gb-unsaved-dot" title="Unsaved changes" />}
          <span className="gb-header__sub">Term assessment structure. Grades calculated when saved.</span>
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
            <select aria-label={label} disabled={saving} className="gb-select" value={val} onChange={e => set(e.target.value)}>
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
            <button className="gb-btn gb-btn--draft" disabled={saving || dirty || !students.length || students.some(s=>rows[s.id]?.review_state !== 'draft' || rows[s.id]?.is_published)} onClick={async()=>{setSaving(true);try{await api.post('/api/gradebook/entries/submit/',{class_arm:Number(selClass),subject:Number(selSubject),term:Number(selTerm)});await loadScores();setAlert({type:'success',msg:'Submitted for administrator review. Scores are locked.'});}catch(e){setAlert({type:'error',msg:scoringError(e)});}finally{setSaving(false);}}}>Submit for review</button>
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
            { num: stats.pass,    label: 'Published'      },
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
                {components.map(f => (
                  <th key={f.key} title={`Max ${f.maximum}`}>{f.name}<br /><small>/{f.maximum}</small></th>
                ))}
                <th rowSpan={2} style={{ background: 'rgba(0,0,0,.15)' }}>Total</th>
                <th rowSpan={2}>Grade</th>
                <th rowSpan={2}>Remark / Status</th>
              </tr>
              <tr className="gb-sub-header">
                {components.map(f => <th key={f.key}>Continuous Assessment</th>)}
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
                    {components.map(f => (
                      <GradeCell
                        key={f.key}
                        value={row[f.key]}
                        disabled={row.is_published || row.review_state !== 'draft'}
                        max={f.maximum}
                        hasError={Boolean(rowErrors[f.key])}
                        fieldName={f.name}
                        onChange={v => handleChange(stu.id, f.key, v)}
                        onTab={e => handleTab(e, stu.id, f.key)}
                        inputRef={el => { cellRefs.current[`${stu.id}_${f.key}`] = el; }}
                      />
                    ))}

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
                      {comp.remark || '—'}<br />{row.is_published ? 'Published / locked' : row.review_state}
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
