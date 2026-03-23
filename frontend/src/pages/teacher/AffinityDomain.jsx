/**
 * frontend/src/pages/teacher/AffinityDomain.jsx
 *
 * Combined Affective & Psychomotor domain rating table.
 *
 * Layout:
 *   Tabs: Affective | Psychomotor
 *   Table: Student rows × Trait columns
 *   Each cell: rating dropdown 1–5 (colour-coded)
 *   Column header: trait name + "Bulk set" button
 *
 * Bulk set: sets all students in that column to the chosen value.
 * Saves via PUT /api/gradebook/affective/student/{id}/term/{id}/
 *             or /api/gradebook/psychomotor/student/{id}/term/{id}/
 */

import React, { useState, useEffect, useCallback, useReducer } from 'react';
import api from '../../services/api';
import '../../styles/ScoreEntry.css';

// ─── Domain definitions ───────────────────────────────────────────────────────

const AFFECTIVE_TRAITS = [
  { key: 'punctuality',             label: 'Punctuality'          },
  { key: 'neatness',                label: 'Neatness'             },
  { key: 'honesty',                 label: 'Honesty'              },
  { key: 'attentiveness',           label: 'Attentiveness'        },
  { key: 'relationship_with_others',label: 'Relationship'         },
  { key: 'leadership',              label: 'Leadership'           },
  { key: 'creativity',              label: 'Creativity'           },
  { key: 'sport_games',             label: 'Sport & Games'        },
  { key: 'handling_of_tools',       label: 'Handling of Tools'    },
];

const PSYCHOMOTOR_TRAITS = [
  { key: 'handwriting',    label: 'Handwriting'    },
  { key: 'drawing',        label: 'Drawing'        },
  { key: 'verbal_fluency', label: 'Verbal Fluency' },
  { key: 'musical_skills', label: 'Musical Skills' },
];

const RATING_LABELS = { 1: 'Poor', 2: 'Below Average', 3: 'Average', 4: 'Good', 5: 'Excellent' };

// ─── Reducer ─────────────────────────────────────────────────────────────────

function ratingsReducer(state, action) {
  switch (action.type) {
    case 'INIT':
      return action.data; // { studentId: { trait: value, ... } }
    case 'SET':
      return {
        ...state,
        [action.studentId]: { ...(state[action.studentId] || {}), [action.trait]: action.value },
      };
    case 'BULK_COL':
      return Object.fromEntries(
        Object.entries(state).map(([sid, vals]) => [
          sid, { ...vals, [action.trait]: action.value }
        ])
      );
    default:
      return state;
  }
}

// ─── Rating select ────────────────────────────────────────────────────────────

function RatingSelect({ value, onChange, disabled }) {
  return (
    <select
      className={`gb-rating-select gb-rating-${value || 3}`}
      value={value || 3}
      onChange={e => onChange(Number(e.target.value))}
      disabled={disabled}
      title={RATING_LABELS[value] || ''}
    >
      {[1,2,3,4,5].map(n => (
        <option key={n} value={n}>{n} — {RATING_LABELS[n]}</option>
      ))}
    </select>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function AffinityDomain() {
  const [terms,     setTerms]     = useState([]);
  const [classArms, setClassArms] = useState([]);
  const [selTerm,   setSelTerm]   = useState('');
  const [selClass,  setSelClass]  = useState('');
  const [students,  setStudents]  = useState([]);

  const [activeTab, setActiveTab] = useState('affective'); // 'affective' | 'psychomotor'
  const [ratings,   dispatch]     = useReducer(ratingsReducer, {});
  const [dirty,     setDirty]     = useState(false);
  const [saving,    setSaving]    = useState(false);
  const [loading,   setLoading]   = useState(false);
  const [alert,     setAlert]     = useState(null);

  const traits = activeTab === 'affective' ? AFFECTIVE_TRAITS : PSYCHOMOTOR_TRAITS;
  const endpoint = activeTab === 'affective' ? 'affective' : 'psychomotor';

  // ── Boot ────────────────────────────────────────────────────────────────────
  useEffect(() => {
    Promise.all([
      api.get('/academics/terms/'),
      api.get('/enrollment/class-arms/'),
    ]).then(([t, c]) => {
      const termList = t.data.results ?? t.data;
      setTerms(termList);
      setClassArms(c.data.results ?? c.data);
      const active = termList.find(x => x.is_current);
      if (active) setSelTerm(String(active.id));
    });
  }, []);

  // ── Load domain data ─────────────────────────────────────────────────────────
  const loadData = useCallback(async () => {
    if (!selTerm || !selClass) return;
    setLoading(true);
    setDirty(false);
    try {
      // Students
      const { data: stuData } = await api.get(
        `/enrollment/students/?class_arm=${selClass}`
      );
      const stuList = stuData.results ?? stuData;
      setStudents(stuList);

      // Existing ratings
      const { data: ratingData } = await api.get(
        `/gradebook/${endpoint}/?class_arm=${selClass}&term=${selTerm}`
      );
      const existing = ratingData.results ?? ratingData;

      // Build initial rating map — default 3 for all
      const initialTraits = traits.reduce((o, t) => ({ ...o, [t.key]: 3 }), {});
      const initMap = {};
      stuList.forEach(stu => {
        const found = existing.find(r => r.student === stu.id);
        initMap[stu.id] = found
          ? traits.reduce((o, t) => ({ ...o, [t.key]: found[t.key] ?? 3 }), {})
          : { ...initialTraits };
      });
      dispatch({ type: 'INIT', data: initMap });
    } finally {
      setLoading(false);
    }
  }, [selTerm, selClass, endpoint, traits]);

  useEffect(() => { loadData(); }, [loadData]);

  // ── Cell change ─────────────────────────────────────────────────────────────
  const handleChange = (studentId, trait, value) => {
    dispatch({ type: 'SET', studentId, trait, value });
    setDirty(true);
  };

  // ── Bulk set column ─────────────────────────────────────────────────────────
  const handleBulkSet = (trait) => {
    const val = Number(window.prompt(`Set all students' "${trait}" rating to (1–5):`, '3'));
    if (!val || val < 1 || val > 5) return;
    dispatch({ type: 'BULK_COL', trait, value: val });
    setDirty(true);
  };

  // ── Save ─────────────────────────────────────────────────────────────────────
  const handleSave = async () => {
    setSaving(true);
    setAlert(null);
    let errorCount = 0;

    for (const stu of students) {
      try {
        await api.put(
          `/gradebook/${endpoint}/student/${stu.id}/term/${selTerm}/`,
          { ...ratings[stu.id], class_arm: Number(selClass) }
        );
      } catch {
        errorCount++;
      }
    }

    setSaving(false);
    if (errorCount === 0) {
      setDirty(false);
      setAlert({ type: 'success', msg: 'All ratings saved successfully.' });
    } else {
      setAlert({ type: 'error', msg: `${errorCount} student(s) failed to save. Please retry.` });
    }
  };

  const canRender = selTerm && selClass;

  // ── Render ────────────────────────────────────────────────────────────────────
  return (
    <div className="gb-page">
      {/* Header */}
      <div className="gb-header">
        <h1 className="gb-header__title">
          Domain Ratings
          {dirty && <span className="gb-unsaved-dot" title="Unsaved changes" />}
          <span className="gb-header__sub">Affective & Psychomotor domains · Rated 1 (Poor) – 5 (Excellent)</span>
        </h1>
      </div>

      {/* Selectors */}
      <div className="gb-controls">
        <div className="gb-field-group">
          <label>Term</label>
          <select className="gb-select" value={selTerm} onChange={e => setSelTerm(e.target.value)}>
            <option value="">— Select term —</option>
            {terms.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </div>
        <div className="gb-field-group">
          <label>Class</label>
          <select className="gb-select" value={selClass} onChange={e => setSelClass(e.target.value)}>
            <option value="">— Select class —</option>
            {classArms.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>

        <div className="gb-field-group" style={{ justifyContent: 'flex-end' }}>
          <label>&nbsp;</label>
          <button
            className="gb-btn gb-btn--publish"
            onClick={handleSave}
            disabled={saving || !canRender || !dirty}
          >
            {saving ? 'Saving…' : '💾 Save Ratings'}
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 0, marginBottom: 20, borderBottom: '2px solid var(--gb-rule)' }}>
        {['affective','psychomotor'].map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              padding:       '9px 22px',
              border:        'none',
              background:    activeTab === tab ? 'var(--gb-navy)' : 'transparent',
              color:         activeTab === tab ? '#fff' : 'var(--gb-ink-mid)',
              fontFamily:    'var(--font-ui)',
              fontSize:      '.86rem',
              fontWeight:    700,
              cursor:        'pointer',
              borderRadius:  '7px 7px 0 0',
              textTransform: 'capitalize',
              transition:    'background .14s',
            }}
          >
            {tab === 'affective' ? '🧠 Affective' : '✋ Psychomotor'}
          </button>
        ))}
      </div>

      {/* Alert */}
      {alert && (
        <div className={`gb-alert gb-alert--${alert.type}`} style={{ marginBottom: 14 }}>
          {alert.type === 'error' ? '❌' : '✓'} {alert.msg}
        </div>
      )}

      {/* Table */}
      {!canRender ? (
        <div className="gb-table-wrap">
          <div className="gb-empty">
            <strong>Nothing to display</strong>
            Select a term and class to enter domain ratings.
          </div>
        </div>
      ) : loading ? (
        <div style={{ padding: 24 }}>
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="gb-skeleton" style={{ height: 40, marginBottom: 6 }} />
          ))}
        </div>
      ) : (
        <div className="gb-table-wrap">
          <table className="gb-domain-table">
            <thead>
              <tr>
                <th style={{ position: 'sticky', left: 0, zIndex: 25 }}>#</th>
                <th style={{ position: 'sticky', left: 44, zIndex: 25, minWidth: 180 }}>Student</th>
                {traits.map(trait => (
                  <th key={trait.key}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, alignItems: 'center' }}>
                      {trait.label}
                      <button
                        className="gb-bulk-btn"
                        onClick={() => handleBulkSet(trait.key)}
                        title={`Set all to same value`}
                      >
                        ⬇ Bulk set
                      </button>
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {students.map((stu, idx) => (
                <tr key={stu.id}>
                  <td style={{
                    position: 'sticky', left: 0, background: 'inherit',
                    fontFamily: 'var(--font-mono)', fontSize: '.72rem',
                    color: 'var(--gb-ink-light)', textAlign: 'center', zIndex: 10,
                  }}>
                    {idx + 1}
                  </td>
                  <td style={{
                    position: 'sticky', left: 44, background: 'inherit',
                    fontWeight: 600, zIndex: 10, paddingLeft: 12,
                  }}>
                    {stu.full_name}
                  </td>
                  {traits.map(trait => (
                    <td key={trait.key} style={{ textAlign: 'center' }}>
                      <RatingSelect
                        value={ratings[stu.id]?.[trait.key] ?? 3}
                        onChange={v => handleChange(stu.id, trait.key, v)}
                      />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}