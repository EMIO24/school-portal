/**
 * frontend/src/pages/public/CheckResult.jsx
 *
 * Public scratch-card PIN result checker — no login required.
 * User enters: Admission Number + Serial Number + PIN
 * On success: renders full result slip in the browser with a Print button.
 */

import React, { useState } from 'react';
import axios from 'axios';
import '../../styles/CheckResult.css';

const API_BASE = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';

const RATING_DESC = { 1: 'Poor', 2: 'Below Avg', 3: 'Average', 4: 'Good', 5: 'Excellent' };

function ordinal(n) {
  if (!n) return '—';
  const s = ['th', 'st', 'nd', 'rd'];
  const v = n % 100;
  return n + (s[(v - 20) % 10] || s[v] || s[0]);
}

function RatingPips({ value }) {
  return (
    <span style={{ display: 'inline-flex', gap: 3, alignItems: 'center' }}>
      {[1, 2, 3, 4, 5].map(i => (
        <span
          key={i}
          style={{
            width: 8, height: 8, borderRadius: '50%', display: 'inline-block',
            background: i <= value ? 'var(--cr-navy)' : 'var(--cr-rule)',
          }}
        />
      ))}
      <span style={{ fontSize: '.75rem', marginLeft: 4, color: 'var(--cr-ink-mid)' }}>
        {value} — {RATING_DESC[value]}
      </span>
    </span>
  );
}

export default function CheckResult() {
  const [form, setForm]       = useState({ admission_number: '', serial_number: '', pin: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState(null);
  const [result, setResult]   = useState(null);

  const handleChange = e => {
    setForm(f => ({ ...f, [e.target.name]: e.target.value }));
    setError(null);
  };

  const handleSubmit = async e => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const { data } = await axios.post(
        `${API_BASE}/api/results/check/`,
        {
          admission_number: form.admission_number.trim().toUpperCase(),
          serial_number:    form.serial_number.trim().toUpperCase(),
          pin:              form.pin.trim(),
        }
      );
      setResult(data);
    } catch (err) {
      const detail = err?.response?.data?.detail;
      if (err?.response?.status === 403 && detail?.includes('already been used')) {
        setError('This scratch card has already been used. Each card can only be used once.');
      } else if (err?.response?.status === 403) {
        setError('Incorrect PIN. Please check and try again.');
      } else if (err?.response?.status === 404) {
        setError(detail || 'No record found. Check your admission number or serial number.');
      } else {
        setError('Something went wrong. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handlePrint = () => window.print();

  const handleCheckAnother = () => {
    setResult(null);
    setForm({ admission_number: '', serial_number: '', pin: '' });
  };

  return (
    <div className="cr-page">

      {/* ── Checker form (hidden after success) ── */}
      {!result && (
        <div className="cr-card">
          <div className="cr-logo-wrap">
            <div className="cr-logo-placeholder">🏫</div>
          </div>

          <h1 className="cr-title">Result Checker</h1>
          <p className="cr-subtitle">
            Enter your scratch card details to view your academic result.
          </p>

          <form className="cr-form" onSubmit={handleSubmit}>
            <div className="cr-field">
              <label htmlFor="admission_number">Admission Number</label>
              <input
                id="admission_number"
                name="admission_number"
                className="cr-input"
                placeholder="e.g. GHS-2024-0042"
                value={form.admission_number}
                onChange={handleChange}
                autoComplete="off"
                required
              />
            </div>

            <div className="cr-field">
              <label htmlFor="serial_number">Serial Number</label>
              <input
                id="serial_number"
                name="serial_number"
                className="cr-input"
                placeholder="e.g. GHS-A1B2-C3D4"
                value={form.serial_number}
                onChange={handleChange}
                autoComplete="off"
                required
              />
            </div>

            <div className="cr-field">
              <label htmlFor="pin">PIN</label>
              <input
                id="pin"
                name="pin"
                type="password"
                className="cr-input"
                placeholder="10-digit PIN"
                value={form.pin}
                onChange={handleChange}
                autoComplete="off"
                maxLength={10}
                required
              />
            </div>

            {error && (
              <div className="cr-alert cr-alert--error">⚠ {error}</div>
            )}

            <button
              type="submit"
              className="cr-btn cr-btn--navy"
              disabled={loading}
            >
              {loading ? 'Checking…' : 'Check Result'}
            </button>
          </form>
        </div>
      )}

      {/* ── Result slip ── */}
      {result && (
        <div className="cr-result-wrap">
          <div className="cr-result-actions">
            <button className="cr-btn cr-btn--ghost" onClick={handleCheckAnother}>
              ← Check Another
            </button>
            <button className="cr-btn cr-btn--navy" onClick={handlePrint}>
              🖨 Print Result
            </button>
          </div>

          <div className="cr-result-card">
            {/* Header */}
            <div className="cr-result-header">
              {result.school_logo
                ? <img src={result.school_logo} className="school-logo" alt="" />
                : <div style={{ fontSize: '2rem' }}>🏫</div>
              }
              <div className="school-info">
                <h2>{result.school_name}</h2>
                <p>{result.school_address}</p>
                <p style={{ marginTop: 4, opacity: 0.85, fontSize: '.78rem' }}>
                  Student Academic Report — {result.term_name} | {result.session_name}
                </p>
              </div>
            </div>

            <div className="cr-result-body">

              {/* Student bio */}
              <div style={{
                display: 'grid', gridTemplateColumns: 'auto 1fr',
                gap: 16, marginBottom: 20, alignItems: 'start',
              }}>
                {result.photo_url
                  ? <img src={result.photo_url} alt="Student"
                      style={{ width: 64, height: 80, objectFit: 'cover', borderRadius: 6, border: '1.5px solid var(--cr-rule)' }} />
                  : <div style={{
                      width: 64, height: 80, background: 'var(--cr-navy-pale)',
                      borderRadius: 6, display: 'flex', alignItems: 'center',
                      justifyContent: 'center', fontSize: '1.6rem',
                    }}>👤</div>
                }
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px 20px' }}>
                  {[
                    ['Name',          result.student_name],
                    ['Admission No.', result.admission_no],
                    ['Class',         result.class_name],
                    ['Gender',        result.gender],
                    ['Date of Birth', result.date_of_birth],
                  ].map(([label, val]) => (
                    <div key={label}>
                      <div style={{ fontSize: '.65rem', textTransform: 'uppercase', letterSpacing: '.06em', color: 'var(--cr-ink-mid)' }}>{label}</div>
                      <div style={{ fontWeight: 600, fontSize: '.92rem', color: 'var(--cr-navy)' }}>{val || '—'}</div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Summary chips */}
              <div className="cr-summary-row">
                {[
                  { num: ordinal(result.position), label: 'Position',   pos: true },
                  { num: result.class_size,         label: 'In Class'   },
                  { num: result.average_score?.toFixed?.(1) ?? result.average_score, label: 'Average' },
                  { num: result.num_subjects,       label: 'Subjects'   },
                  { num: `${result.att_percentage}%`, label: 'Attendance' },
                ].map(({ num, label, pos }) => (
                  <div key={label} className="cr-summary-chip">
                    <span className={`cr-summary-chip__num${pos ? ' pos' : ''}`}>{num}</span>
                    <span className="cr-summary-chip__label">{label}</span>
                  </div>
                ))}
              </div>

              {/* Score table */}
              <table className="cr-score-table">
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
                  {result.score_rows.map(row => (
                    <tr key={row.subject}>
                      <td className="left">{row.subject}</td>
                      <td>{row.first_test}</td>
                      <td>{row.second_test}</td>
                      <td>{row.assignment}</td>
                      <td><strong>{row.ca_total}</strong></td>
                      <td>{row.exam_score}</td>
                      <td><strong>{row.total_score}</strong></td>
                      <td><span className={`grade-pill ${row.grade}`}>{row.grade}</span></td>
                      <td style={{ fontSize: '.8rem', color: 'var(--cr-ink-mid)' }}>{row.remark}</td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {/* Domain ratings */}
              {(result.affective_rows?.length > 0 || result.psychomotor_rows?.length > 0) && (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>
                  {result.affective_rows?.length > 0 && (
                    <div>
                      <div style={{ fontWeight: 700, fontSize: '.75rem', textTransform: 'uppercase', letterSpacing: '.07em', color: 'var(--cr-navy)', marginBottom: 8, borderBottom: '2px solid var(--cr-navy)', paddingBottom: 4 }}>
                        Affective Domain
                      </div>
                      {result.affective_rows.map(r => (
                        <div key={r.trait} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '5px 0', borderBottom: '1px solid var(--cr-rule)' }}>
                          <span style={{ fontSize: '.82rem' }}>{r.trait}</span>
                          <RatingPips value={r.rating} />
                        </div>
                      ))}
                    </div>
                  )}
                  {result.psychomotor_rows?.length > 0 && (
                    <div>
                      <div style={{ fontWeight: 700, fontSize: '.75rem', textTransform: 'uppercase', letterSpacing: '.07em', color: 'var(--cr-navy)', marginBottom: 8, borderBottom: '2px solid var(--cr-navy)', paddingBottom: 4 }}>
                        Psychomotor Domain
                      </div>
                      {result.psychomotor_rows.map(r => (
                        <div key={r.skill} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '5px 0', borderBottom: '1px solid var(--cr-rule)' }}>
                          <span style={{ fontSize: '.82rem' }}>{r.skill}</span>
                          <RatingPips value={r.rating} />
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Remarks */}
              {(result.class_teacher_remark || result.principal_remark) && (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 20 }}>
                  {[
                    { label: "Class Teacher's Remark", text: result.class_teacher_remark },
                    { label: "Principal's Remark",     text: result.principal_remark },
                  ].map(({ label, text }) => text ? (
                    <div key={label} style={{
                      padding: '10px 14px', border: '1.5px solid var(--cr-rule)',
                      borderRadius: 7, background: 'var(--cr-navy-pale)',
                    }}>
                      <div style={{ fontSize: '.68rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.06em', color: 'var(--cr-navy)', marginBottom: 5 }}>{label}</div>
                      <div style={{ fontSize: '.9rem', fontStyle: 'italic', color: 'var(--cr-ink)' }}>{text}</div>
                    </div>
                  ) : null)}
                </div>
              )}

              {/* Next term */}
              {result.next_term_date && (
                <div style={{
                  textAlign: 'center', padding: '8px 14px',
                  background: 'var(--cr-navy-pale)', borderRadius: 6,
                  fontSize: '.86rem', fontWeight: 600, color: 'var(--cr-navy)',
                }}>
                  📅 Next Term Begins: {result.next_term_date}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
