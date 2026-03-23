/**
 * frontend/src/pages/student/MyAttendance.jsx
 *
 * Student attendance self-view:
 *   - Circular percentage badge (green / amber / red by threshold)
 *   - Summary chip strip (present / absent / late / excused counts)
 *   - Mini calendar dot view: one dot per school day, colour-coded by status
 *   - Term selector
 */

import React, { useState, useEffect, useCallback, useContext, useMemo } from 'react';
import api from '../../services/api';
import { AuthContext } from '../../context/AuthContext';
import '../../styles/Attendance.css';

// ─── Status dot helpers ───────────────────────────────────────────────────────

const STATUS_META = {
  present: { label: 'P', title: 'Present' },
  absent:  { label: 'A', title: 'Absent'  },
  late:    { label: 'L', title: 'Late'    },
  excused: { label: 'E', title: 'Excused' },
};

/** Group records by month label "Jan 2025" */
function groupByMonth(records) {
  const map = new Map();
  for (const rec of records) {
    const d     = new Date(rec.date);
    const key   = `${['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][d.getMonth()]} ${d.getFullYear()}`;
    if (!map.has(key)) map.set(key, []);
    map.get(key).push(rec);
  }
  return map;
}

// ─── Pct badge ────────────────────────────────────────────────────────────────

function PctBadge({ pct }) {
  const cls = pct >= 75 ? '' : pct >= 50 ? 'warn' : 'crit';
  return (
    <div className={`att-pct-badge ${cls}`}>
      <span className={`att-pct-badge__num ${cls}`}>{pct.toFixed(0)}%</span>
      <span className="att-pct-badge__label">attendance</span>
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function MyAttendance() {
  const { user } = useContext(AuthContext);

  const [terms,        setTerms]        = useState([]);
  const [selectedTerm, setSelectedTerm] = useState('');
  const [summary,      setSummary]      = useState(null);
  const [records,      setRecords]      = useState([]);  // flat per-session records
  const [loading,      setLoading]      = useState(false);

  // ── Boot ───────────────────────────────────────────────────────────────────
  useEffect(() => {
    api.get('/academics/terms/').then(({ data }) => {
      const list   = data.results ?? data;
      setTerms(list);
      const active = list.find(t => t.is_active);
      if (active) setSelectedTerm(String(active.id));
    });
  }, []);

  // ── Load data ──────────────────────────────────────────────────────────────
  const loadData = useCallback(async () => {
    if (!selectedTerm || !user?.id) return;
    setLoading(true);
    try {
      // Summary figures
      const sumRes = await api.get(
        `/attendance/sessions/report/?student=${user.id}&term=${selectedTerm}`
      );
      setSummary(sumRes.data);

      // Raw records for dot calendar — GET all sessions with this student's mark
      // The backend returns flat records keyed by session date
      const recRes = await api.get(
        `/attendance/sessions/?term=${selectedTerm}&student=${user.id}`
      );
      const sessions = recRes.data.results ?? recRes.data;
      // Flatten to {date, status, remark} per session
      const flat = sessions.flatMap(session =>
        session.records
          .filter(r => r.student === user.id)
          .map(r => ({
            date:   session.date,
            status: r.status,
            remark: r.remark,
            session_id: session.id,
          }))
      );
      setRecords(flat.sort((a, b) => a.date.localeCompare(b.date)));
    } catch (err) {
      console.error('MyAttendance load error', err);
    } finally {
      setLoading(false);
    }
  }, [selectedTerm, user?.id]);

  useEffect(() => { loadData(); }, [loadData]);

  // ── Group dots by month ────────────────────────────────────────────────────
  const monthGroups = useMemo(() => groupByMonth(records), [records]);

  // ── Determine overall status text ─────────────────────────────────────────
  const pct        = summary?.percentage ?? 0;
  const statusText = pct >= 75
    ? 'You are on track.'
    : pct >= 50
    ? 'Your attendance needs improvement.'
    : 'Your attendance is critically low. Please speak to your form teacher.';
  const alertCls   = pct >= 75 ? 'att-alert--info' : pct >= 50 ? 'att-alert--warn' : 'att-alert--error';

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="att-page">
      {/* Header */}
      <div className="att-header">
        <h1 className="att-header__title">
          My Attendance
          <span className="att-header__sub">Track your punctuality and presence this term</span>
        </h1>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div className="att-field-group">
            <label>Term</label>
            <select className="att-select" value={selectedTerm}
              onChange={e => setSelectedTerm(e.target.value)}>
              {terms.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </div>
        </div>
      </div>

      {/* Summary row */}
      {loading ? (
        <div style={{ display: 'flex', gap: 14, marginBottom: 24 }}>
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="att-skeleton" style={{ flex: 1, height: 80 }} />
          ))}
        </div>
      ) : summary && (
        <>
          {/* Alert banner */}
          <div className={`att-alert ${alertCls}`} style={{ marginBottom: 20 }}>
            <span>{pct >= 75 ? 'ℹ' : pct >= 50 ? '⚠' : '🚨'}</span>
            <span>{statusText}</span>
          </div>

          {/* Pct badge + stats strip */}
          <div style={{ display: 'flex', gap: 20, alignItems: 'center', marginBottom: 24 }}>
            <PctBadge pct={pct} />
            <div className="att-stats-strip" style={{ flex: 1 }}>
              {[
                { key: 'present', label: 'Present',  cls: '',           val: summary.present },
                { key: 'absent',  label: 'Absent',   cls: 'is-absent',  val: summary.absent  },
                { key: 'late',    label: 'Late',      cls: 'is-late',    val: summary.late    },
                { key: 'excused', label: 'Excused',   cls: 'is-excused', val: summary.excused },
                { key: 'total',   label: 'Total',     cls: '',           val: summary.total   },
              ].map(s => (
                <div key={s.key} className="att-stat-chip">
                  <span className={`att-stat-chip__num ${s.cls}`}>{s.val ?? 0}</span>
                  <span className="att-stat-chip__label">{s.label}</span>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {/* Dot calendar */}
      <div className="att-card">
        <div className="att-card__head">
          <h2 className="att-card__title">📆 Daily Record</h2>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
            {Object.entries(STATUS_META).map(([k, v]) => (
              <span key={k} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: '.73rem', color: 'var(--att-ink-mid)' }}>
                <span className={`att-mini-dot ${k.charAt(0).toUpperCase()}`}
                  style={{ width: 14, height: 14, fontSize: '.55rem' }}>
                  {v.label}
                </span>
                {v.title}
              </span>
            ))}
          </div>
        </div>

        <div className="att-card__body">
          {loading ? (
            <div className="att-mini-cal">
              {Array.from({ length: 40 }).map((_, i) => (
                <div key={i} className="att-skeleton att-mini-dot" style={{ background: undefined }} />
              ))}
            </div>
          ) : monthGroups.size === 0 ? (
            <div className="att-empty">
              <strong>No records yet</strong>
              Attendance data will appear here once your teacher starts marking the register.
            </div>
          ) : (
            Array.from(monthGroups.entries()).map(([month, recs]) => (
              <div key={month} style={{ marginBottom: 20 }}>
                <div style={{
                  fontSize: '.73rem', fontWeight: 700, textTransform: 'uppercase',
                  letterSpacing: '.08em', color: 'var(--att-ink-mid)', marginBottom: 8,
                }}>
                  {month}
                </div>
                <div className="att-mini-cal">
                  {recs.map((rec, i) => {
                    const statusChar = rec.status.charAt(0).toUpperCase();
                    const d          = new Date(rec.date);
                    const dayNum     = d.getDate();
                    return (
                      <div
                        key={i}
                        className={`att-mini-dot ${statusChar}`}
                        title={`${rec.date} — ${rec.status}${rec.remark ? ': ' + rec.remark : ''}`}
                      >
                        {dayNum}
                      </div>
                    );
                  })}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}