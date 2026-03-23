/**
 * frontend/src/pages/admin/AttendanceOverview.jsx
 *
 * Admin attendance overview:
 *   - Class + term selectors
 *   - Calendar heatmap (green → amber → red by daily attendance %)
 *   - Low-attendance panel with badge count + sortable student table
 *   - CSV export button
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import api from '../../services/api';
import '../../styles/Attendance.css';

// ─── Constants ────────────────────────────────────────────────────────────────

const MONTH_NAMES = [
  'January','February','March','April','May','June',
  'July','August','September','October','November','December',
];

const THRESHOLD_DEFAULT = 75;

// ─── Heatmap helpers ──────────────────────────────────────────────────────────

function heatClass(ratio) {
  if (ratio === null) return 'no-data';
  if (ratio >= 0.95)  return 'heat-hi';
  if (ratio >= 0.85)  return 'heat-ok';
  if (ratio >= 0.60)  return 'heat-mid';
  return 'heat-low';
}

/**
 * Group an array of session rows into a nested map:
 *   { year: { month: { day: row } } }
 */
function groupByDate(rows) {
  const map = {};
  for (const row of rows) {
    const d     = new Date(row.date);
    const year  = d.getFullYear();
    const month = d.getMonth();
    const day   = d.getDate();
    if (!map[year])        map[year] = {};
    if (!map[year][month]) map[year][month] = {};
    map[year][month][day]  = row;
  }
  return map;
}

/**
 * Given a year and month (0-based), return all calendar day numbers
 * padded with nulls for Mon-offset (Mon=0 week start).
 */
function calendarDays(year, month) {
  const firstDay = new Date(year, month, 1).getDay(); // 0=Sun
  const offset   = (firstDay + 6) % 7;               // Mon-first offset
  const daysIn   = new Date(year, month + 1, 0).getDate();
  return [...Array(offset).fill(null), ...Array.from({ length: daysIn }, (_, i) => i + 1)];
}

// ─── Percentage bar ───────────────────────────────────────────────────────────

function PctBar({ pct }) {
  const cls = pct >= 75 ? 'ok' : pct >= 50 ? 'mid' : '';
  return (
    <div className="att-pct-bar">
      <div className="att-pct-track">
        <div className={`att-pct-fill ${cls}`} style={{ width: `${Math.min(pct,100)}%` }} />
      </div>
      <span className={`att-pct-num`} style={{ color: pct < 75 ? 'var(--att-crimson)' : 'inherit' }}>
        {pct.toFixed(1)}%
      </span>
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function AttendanceOverview() {
  const [terms,     setTerms]     = useState([]);
  const [classArms, setClassArms] = useState([]);

  const [selectedTerm,     setSelectedTerm]     = useState('');
  const [selectedClassArm, setSelectedClassArm] = useState('');
  const [threshold,        setThreshold]        = useState(THRESHOLD_DEFAULT);

  const [heatmapRows,   setHeatmapRows]   = useState([]);
  const [lowStudents,   setLowStudents]   = useState([]);
  const [lowCount,      setLowCount]      = useState(0);
  const [loading,       setLoading]       = useState(false);
  const [lowLoading,    setLowLoading]    = useState(false);

  // Tooltip state for hovered heatmap day
  const [tooltip, setTooltip] = useState(null);

  // ── Boot ──────────────────────────────────────────────────────────────────
  useEffect(() => {
    Promise.all([
      api.get('/academics/terms/'),
      api.get('/academics/class-arms/'),
    ]).then(([t, c]) => {
      const termList = t.data.results ?? t.data;
      setTerms(termList);
      setClassArms(c.data.results ?? c.data);
      const active = termList.find(x => x.is_active);
      if (active) setSelectedTerm(String(active.id));
    });
  }, []);

  // ── Load heatmap data ──────────────────────────────────────────────────────
  const loadHeatmap = useCallback(async () => {
    if (!selectedTerm || !selectedClassArm) return;
    setLoading(true);
    try {
      const { data } = await api.get(
        `/attendance/sessions/class-report/?class_arm=${selectedClassArm}&term=${selectedTerm}`
      );
      setHeatmapRows(data);
    } finally {
      setLoading(false);
    }
  }, [selectedTerm, selectedClassArm]);

  useEffect(() => { loadHeatmap(); }, [loadHeatmap]);

  // ── Load low-attendance panel ──────────────────────────────────────────────
  const loadLowAttendance = useCallback(async () => {
    if (!selectedTerm) return;
    setLowLoading(true);
    try {
      const { data } = await api.get(
        `/attendance/sessions/low-attendance/?term=${selectedTerm}&threshold=${threshold}`
      );
      setLowStudents(data.students);
      setLowCount(data.count);
    } finally {
      setLowLoading(false);
    }
  }, [selectedTerm, threshold]);

  useEffect(() => { loadLowAttendance(); }, [loadLowAttendance]);

  // ── CSV export ─────────────────────────────────────────────────────────────
  const handleExport = () => {
    if (!selectedTerm || !selectedClassArm) return;
    const url = `/attendance/sessions/class-report/?class_arm=${selectedClassArm}&term=${selectedTerm}&format=csv`;
    // Use direct window open for file download from API
    window.open(
      `${process.env.REACT_APP_API_BASE_URL || ''}${url}`, '_blank'
    );
  };

  // ── Heatmap structure ──────────────────────────────────────────────────────
  const dateMap = useMemo(() => groupByDate(heatmapRows), [heatmapRows]);

  // Find all months covered by the data
  const months = useMemo(() => {
    if (!heatmapRows.length) return [];
    const dates = heatmapRows.map(r => new Date(r.date));
    const first = dates.reduce((a, b) => a < b ? a : b);
    const last  = dates.reduce((a, b) => a > b ? a : b);
    const result = [];
    let cur = new Date(first.getFullYear(), first.getMonth(), 1);
    while (cur <= last) {
      result.push({ year: cur.getFullYear(), month: cur.getMonth() });
      cur = new Date(cur.getFullYear(), cur.getMonth() + 1, 1);
    }
    return result;
  }, [heatmapRows]);

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="att-page">
      {/* Header */}
      <div className="att-header">
        <h1 className="att-header__title">
          Attendance Overview
          <span className="att-header__sub">Monitor class attendance patterns &amp; flag at-risk students</span>
        </h1>
      </div>

      {/* Controls */}
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
            <option value="">— All classes —</option>
            {classArms.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>

        <div className="att-field-group">
          <label>Alert threshold (%)</label>
          <input type="number" className="att-input" value={threshold}
            min={0} max={100} style={{ maxWidth: 90 }}
            onChange={e => setThreshold(Number(e.target.value))} />
        </div>

        <div className="att-field-group" style={{ justifyContent: 'flex-end' }}>
          <label>&nbsp;</label>
          <button
            className="att-btn att-btn--ghost"
            onClick={handleExport}
            disabled={!selectedTerm || !selectedClassArm}
          >
            ⬇ Export CSV
          </button>
        </div>
      </div>

      {/* ── Heatmap calendar ─────────────────────────────────────────────── */}
      <div className="att-card" style={{ marginBottom: 24 }}>
        <div className="att-card__head">
          <h2 className="att-card__title">📅 Attendance Calendar</h2>
          <span style={{ fontSize: '.78rem', color: 'var(--att-ink-light)' }}>
            {loading ? 'Loading…' : `${heatmapRows.length} sessions`}
          </span>
        </div>

        {(!selectedTerm || !selectedClassArm) ? (
          <div className="att-empty">
            <strong>Select a term and class</strong>
            to view the attendance calendar.
          </div>
        ) : loading ? (
          <div className="att-heatmap">
            {Array.from({ length: 20 }).map((_, i) => (
              <div key={i} className="att-skeleton" style={{ width: 32, height: 32, display: 'inline-block', margin: '2px' }} />
            ))}
          </div>
        ) : months.length === 0 ? (
          <div className="att-empty">
            <strong>No sessions yet</strong>
            Attendance data will appear here once teachers start taking registers.
          </div>
        ) : (
          <>
            <div className="att-heatmap">
              {months.map(({ year, month }) => {
                const days    = calendarDays(year, month);
                const dayData = dateMap[year]?.[month] ?? {};

                return (
                  <div key={`${year}-${month}`} className="att-heatmap__month">
                    <div className="att-heatmap__month-label">
                      {MONTH_NAMES[month]} {year}
                    </div>
                    <div className="att-heatmap__grid">
                      {['M','T','W','T','F','S','S'].map((d, i) => (
                        <div key={`h-${i}`} style={{
                          width: 32, textAlign: 'center',
                          fontSize: '.65rem', color: 'var(--att-ink-light)',
                          fontFamily: 'var(--font-mono)',
                        }}>{d}</div>
                      ))}
                      {days.map((day, i) => {
                        if (!day) return <div key={`null-${i}`} style={{ width: 32, height: 32 }} />;

                        const d       = new Date(year, month, day);
                        const isWeekend = d.getDay() === 0 || d.getDay() === 6;
                        const row     = dayData[day];

                        if (isWeekend) return (
                          <div key={day} className="att-heatmap__day weekend">{day}</div>
                        );

                        return (
                          <div
                            key={day}
                            className={`att-heatmap__day ${row ? heatClass(row.present_ratio) : 'no-data'}${row?.is_finalized ? ' finalized' : ''}`}
                            onMouseEnter={() => row && setTooltip({ day, month, year, row })}
                            onMouseLeave={() => setTooltip(null)}
                            title={row
                              ? `${row.present_count}/${row.total_students} present (${(row.present_ratio * 100).toFixed(0)}%)`
                              : 'No session'}
                          >
                            {day}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Legend */}
            <div className="att-heatmap__legend">
              {[
                { cls: 'heat-hi',  bg: 'var(--heat-hi)',  label: '≥ 95%' },
                { cls: 'heat-ok',  bg: 'var(--heat-ok)',  label: '85–95%' },
                { cls: 'heat-mid', bg: 'var(--heat-mid)', label: '60–85%' },
                { cls: 'heat-low', bg: 'var(--heat-low)', label: '< 60%' },
                { cls: 'no-data',  bg: 'var(--heat-0)',   label: 'No session' },
              ].map(l => (
                <span key={l.label} className="att-heatmap__legend-item">
                  <span className="att-heatmap__legend-dot" style={{ background: l.bg }} />
                  {l.label}
                </span>
              ))}
            </div>
          </>
        )}
      </div>

      {/* ── Low attendance panel ─────────────────────────────────────────── */}
      <div className="att-card">
        <div className="att-card__head">
          <h2 className="att-card__title">
            ⚠ Low Attendance
            {lowCount > 0 && (
              <span className="att-low-panel__badge">{lowCount} student{lowCount !== 1 ? 's' : ''}</span>
            )}
          </h2>
          <span style={{ fontSize: '.78rem', color: 'var(--att-ink-light)' }}>
            Below {threshold}%
          </span>
        </div>

        <div className="att-card__body" style={{ padding: 0 }}>
          {lowLoading ? (
            <div style={{ padding: 24 }}>
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="att-skeleton" style={{ height: 42, marginBottom: 8 }} />
              ))}
            </div>
          ) : !selectedTerm ? (
            <div className="att-empty"><strong>Select a term to see flagged students.</strong></div>
          ) : lowStudents.length === 0 ? (
            <div className="att-empty">
              <strong>All clear</strong>
              No students below {threshold}% attendance this term.
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table className="att-low-table">
                <thead>
                  <tr>
                    <th>Student</th>
                    <th>Admission No.</th>
                    <th>Class</th>
                    <th>Present</th>
                    <th>Absent</th>
                    <th>Attendance</th>
                  </tr>
                </thead>
                <tbody>
                  {lowStudents.map(s => (
                    <tr key={s.student_id}>
                      <td style={{ fontWeight: 600 }}>{s.student_name}</td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: '.8rem' }}>
                        {s.admission_no || '—'}
                      </td>
                      <td>{s.class_arm || '—'}</td>
                      <td style={{ fontFamily: 'var(--font-mono)' }}>
                        {s.present} / {s.total}
                      </td>
                      <td style={{
                        fontFamily: 'var(--font-mono)',
                        color: 'var(--att-crimson)',
                      }}>
                        {s.absent}
                      </td>
                      <td><PctBar pct={s.percentage} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}