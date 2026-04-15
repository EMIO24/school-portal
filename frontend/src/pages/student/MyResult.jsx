/**
 * frontend/src/pages/student/MyResult.jsx
 *
 * Browser-rendered result card for the logged-in student.
 * Fetches JSON from GET /api/results/slip-data/{student_id}/?term=
 * and renders a full-fidelity version of the result slip — no PDF download required.
 * Students can also trigger their own PDF download via the slip endpoint.
 */

import React, { useState, useEffect, useContext, useCallback } from 'react';
import api from '../../services/api';
import { AuthContext } from '../../context/AuthContext';
import '../../styles/Results.css';

// ─── Helpers ─────────────────────────────────────────────────────────────────

function ordinal(n) {
  if (!n) return '—';
  const s = ['th','st','nd','rd'];
  const v = n % 100;
  return n + (s[(v-20)%10] || s[v] || s[0]);
}

const RATING_DESC = { 1: 'Poor', 2: 'Below Avg', 3: 'Average', 4: 'Good', 5: 'Excellent' };

// ─── Rating pips ─────────────────────────────────────────────────────────────

function RatingPips({ value }) {
  return (
    <span style={{ display: 'inline-flex', gap: 3, alignItems: 'center' }}>
      {[1,2,3,4,5].map(i => (
        <span
          key={i}
          style={{
            width:        8,
            height:       8,
            borderRadius: '50%',
            background:   i <= value ? 'var(--res-navy)' : 'var(--res-rule)',
            display:      'inline-block',
          }}
        />
      ))}
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: '.75rem', marginLeft: 4 }}>
        {value} — {RATING_DESC[value]}
      </span>
    </span>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function MyResult() {
  const { user } = useContext(AuthContext);

  const [terms,        setTerms]        = useState([]);
  const [selectedTerm, setSelectedTerm] = useState('');
  const [data,         setData]         = useState(null);
  const [loading,      setLoading]      = useState(false);
  const [error,        setError]        = useState(null);

  // ── Boot ────────────────────────────────────────────────────────────────────
  useEffect(() => {
    api.get('/academics/terms/').then(({ data: d }) => {
      const list   = d.results ?? d;
      setTerms(list);
      const current = list.find(t => t.is_current);
      if (current) setSelectedTerm(String(current.id));
    });
  }, []);

  // ── Fetch slip data ──────────────────────────────────────────────────────────
  const load = useCallback(async () => {
    if (!selectedTerm || !user?.id) return;
    setLoading(true);
    setError(null);
    setData(null);
    try {
      const { data: d } = await api.get(
        `/results/slip-data/${user.id}/?term=${selectedTerm}`
      );
      setData(d);
    } catch (err) {
      if (err?.response?.status === 404) {
        setError('Results are not available yet for this term.');
      } else {
        setError('Could not load your result. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  }, [selectedTerm, user?.id]);

  useEffect(() => { load(); }, [load]);

  const apiBase = process.env.REACT_APP_API_BASE_URL || '';

  const downloadPDF = () => {
    window.open(
      `${apiBase}/api/results/slip/${user.id}/?term=${selectedTerm}`, '_blank'
    );
  };

  // ── Render ────────────────────────────────────────────────────────────────────
  return (
    <div className="res-page">
      {/* Controls */}
      <div className="res-controls" style={{ marginBottom: 24 }}>
        <div className="res-field-group">
          <label>Term</label>
          <select
            className="res-select"
            value={selectedTerm}
            onChange={e => setSelectedTerm(e.target.value)}
          >
            {terms.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </div>
        {data && (
          <div className="res-field-group" style={{ justifyContent: 'flex-end' }}>
            <label>&nbsp;</label>
            <button className="res-btn res-btn--navy" onClick={downloadPDF}>
              📄 Download PDF
            </button>
          </div>
        )}
      </div>

      {/* States */}
      {loading && (
        <div style={{ maxWidth: 860, margin: '0 auto' }}>
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="res-skeleton" style={{ height: 48, marginBottom: 10 }} />
          ))}
        </div>
      )}

      {error && !loading && (
        <div className="res-alert res-alert--info" style={{ maxWidth: 860, margin: '0 auto' }}>
          ℹ {error}
        </div>
      )}

      {/* Result card */}
      {data && !loading && (
        <div className="my-result-card">

          {/* Header */}
          <div className="my-result-header">
            {data.school_logo && (
              <img src={data.school_logo} className="school-logo" alt="" />
            )}
            <div className="school-info">
              <h2>{data.school_name}</h2>
              <p>{data.school_address}</p>
              <p style={{ marginTop: 4, opacity: .9, fontSize: '.82rem' }}>
                Student Academic Report — {data.term_name} | {data.session_name}
              </p>
            </div>
          </div>

          <div className="my-result-body">

            {/* Student bio */}
            <div style={{
              display: 'grid', gridTemplateColumns: 'auto 1fr',
              gap: 16, marginBottom: 20, alignItems: 'start',
            }}>
              {data.photo_url ? (
                <img
                  src={data.photo_url}
                  alt="Student"
                  style={{ width: 64, height: 80, objectFit: 'cover', borderRadius: 6, border: '1.5px solid var(--res-rule)' }}
                />
              ) : (
                <div style={{
                  width: 64, height: 80, background: 'var(--res-navy-pale)',
                  borderRadius: 6, display: 'flex', alignItems: 'center',
                  justifyContent: 'center', fontSize: '1.6rem',
                }}>👤</div>
              )}

              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px 20px' }}>
                {[
                  ['Name',          data.student_name],
                  ['Admission No.', data.admission_no],
                  ['Class',         data.class_name],
                  ['Gender',        data.gender],
                  ['Date of Birth', data.date_of_birth],
                ].map(([label, val]) => (
                  <div key={label}>
                    <div style={{ fontSize: '.65rem', textTransform: 'uppercase', letterSpacing: '.06em', color: 'var(--res-ink-light)' }}>{label}</div>
                    <div style={{ fontWeight: 600, fontSize: '.92rem', color: 'var(--res-navy)' }}>{val || '—'}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Summary chips */}
            <div className="result-summary-row">
              <div className="result-summary-chip">
                <span className="result-summary-chip__num pos">{ordinal(data.position)}</span>
                <span className="result-summary-chip__label">Position</span>
              </div>
              <div className="result-summary-chip">
                <span className="result-summary-chip__num">{data.class_size}</span>
                <span className="result-summary-chip__label">In Class</span>
              </div>
              <div className="result-summary-chip">
                <span className="result-summary-chip__num">{data.average_score?.toFixed(1)}</span>
                <span className="result-summary-chip__label">Average</span>
              </div>
              <div className="result-summary-chip">
                <span className="result-summary-chip__num">{data.num_subjects}</span>
                <span className="result-summary-chip__label">Subjects</span>
              </div>
              <div className="result-summary-chip">
                <span className="result-summary-chip__num">{data.att_percentage}%</span>
                <span className="result-summary-chip__label">Attendance</span>
              </div>
            </div>

            {/* Score table */}
            <table className="my-score-table">
              <thead>
                <tr>
                  <th className="left">Subject</th>
                  <th>1st Test</th>
                  <th>2nd Test</th>
                  <th>Assignment</th>
                  <th>CA /40</th>
                  <th>Exam /60</th>
                  <th>Total</th>
                  <th>Grade</th>
                  <th>Remark</th>
                </tr>
              </thead>
              <tbody>
                {data.score_rows.map(row => (
                  <tr key={row.subject}>
                    <td className="left">{row.subject}</td>
                    <td>{row.first_test}</td>
                    <td>{row.second_test}</td>
                    <td>{row.assignment}</td>
                    <td><strong>{row.ca_total}</strong></td>
                    <td>{row.exam_score}</td>
                    <td><strong>{row.total_score}</strong></td>
                    <td>
                      <span className={`grade-pill ${row.grade}`}>{row.grade}</span>
                    </td>
                    <td style={{ fontSize: '.8rem', color: 'var(--res-ink-mid)' }}>
                      {row.remark}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* Domains */}
            {(data.affective_rows?.length > 0 || data.psychomotor_rows?.length > 0) && (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>
                {data.affective_rows?.length > 0 && (
                  <div>
                    <div style={{ fontWeight: 700, fontSize: '.78rem', textTransform: 'uppercase', letterSpacing: '.07em', color: 'var(--res-navy)', marginBottom: 8, borderBottom: '2px solid var(--res-navy)', paddingBottom: 4 }}>
                      Affective Domain
                    </div>
                    {data.affective_rows.map(r => (
                      <div key={r.trait} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '5px 0', borderBottom: '1px solid var(--res-rule)' }}>
                        <span style={{ fontSize: '.84rem' }}>{r.trait}</span>
                        <RatingPips value={r.rating} />
                      </div>
                    ))}
                  </div>
                )}

                {data.psychomotor_rows?.length > 0 && (
                  <div>
                    <div style={{ fontWeight: 700, fontSize: '.78rem', textTransform: 'uppercase', letterSpacing: '.07em', color: 'var(--res-navy)', marginBottom: 8, borderBottom: '2px solid var(--res-navy)', paddingBottom: 4 }}>
                      Psychomotor Domain
                    </div>
                    {data.psychomotor_rows.map(r => (
                      <div key={r.skill} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '5px 0', borderBottom: '1px solid var(--res-rule)' }}>
                        <span style={{ fontSize: '.84rem' }}>{r.skill}</span>
                        <RatingPips value={r.rating} />
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Remarks */}
            {(data.class_teacher_remark || data.principal_remark) && (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 20 }}>
                {[
                  { label: "Class Teacher's Remark", text: data.class_teacher_remark },
                  { label: "Principal's Remark",      text: data.principal_remark },
                ].map(({ label, text }) => (
                  <div key={label} style={{
                    padding: '10px 14px', border: '1.5px solid var(--res-rule)',
                    borderRadius: 7, background: 'var(--res-navy-pale)',
                  }}>
                    <div style={{ fontSize: '.68rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.06em', color: 'var(--res-navy)', marginBottom: 5 }}>
                      {label}
                    </div>
                    <div style={{ fontSize: '.9rem', fontStyle: 'italic', color: 'var(--res-ink)' }}>
                      {text || '—'}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Next term */}
            {data.next_term_date && (
              <div style={{
                textAlign: 'center', padding: '8px 14px',
                background: 'var(--res-navy-pale)', borderRadius: 6,
                fontSize: '.86rem', fontWeight: 600, color: 'var(--res-navy)',
              }}>
                📅 Next Term Begins: {data.next_term_date}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}