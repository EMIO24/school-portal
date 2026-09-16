/** Student attendance self-view. */
import React, { useState, useEffect, useCallback, useContext, useMemo } from 'react';
import api from '../../services/api';
import { getApiErrorMessage } from '../../services/apiError';
import { AuthContext } from '../../context/AuthContext';
import '../../styles/Attendance.css';

const STATUS_META = {
  present: { label: 'P', title: 'Present' },
  absent: { label: 'A', title: 'Absent' },
  late: { label: 'L', title: 'Late' },
  excused: { label: 'E', title: 'Excused' },
};

function groupByMonth(records) {
  const map = new Map();
  for (const rec of records) {
    const d = new Date(rec.date);
    const key = `${['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][d.getMonth()]} ${d.getFullYear()}`;
    if (!map.has(key)) map.set(key, []);
    map.get(key).push(rec);
  }
  return map;
}

function PctBadge({ pct }) {
  const cls = pct >= 75 ? '' : pct >= 50 ? 'warn' : 'crit';
  return <div className={`att-pct-badge ${cls}`}><span className={`att-pct-badge__num ${cls}`}>{pct.toFixed(0)}%</span><span className="att-pct-badge__label">attendance</span></div>;
}

export default function MyAttendance() {
  const { user } = useContext(AuthContext);
  const [terms, setTerms] = useState([]);
  const [selectedTerm, setSelectedTerm] = useState('');
  const [summary, setSummary] = useState(null);
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    api.get('/api/terms/').then(({ data }) => {
      if (!active) return;
      const list = data.results ?? data;
      setTerms(list);
      const current = list.find(t => t.is_current);
      if (current) setSelectedTerm(String(current.id));
    }).catch(err => active && setError(getApiErrorMessage(err, 'Unable to load school terms.')));
    return () => { active = false; };
  }, []);

  const loadData = useCallback(async () => {
    if (!selectedTerm || !user?.id) return;
    setLoading(true);
    setError('');
    try {
      const [sumRes, recRes] = await Promise.all([
        api.get(`/api/attendance/sessions/report/?student=${user.id}&term=${selectedTerm}`),
        api.get(`/api/attendance/my-records/?term=${selectedTerm}`),
      ]);
      setSummary(sumRes.data);
      setRecords((recRes.data.results ?? recRes.data).sort((a, b) => a.date.localeCompare(b.date)));
    } catch (err) {
      setSummary(null);
      setRecords([]);
      setError(getApiErrorMessage(err, 'Unable to load your attendance.'));
    } finally {
      setLoading(false);
    }
  }, [selectedTerm, user?.id]);

  useEffect(() => { loadData(); }, [loadData]);
  const monthGroups = useMemo(() => groupByMonth(records), [records]);
  const pct = summary?.percentage ?? 0;
  const statusText = pct >= 75 ? 'You are on track.' : pct >= 50 ? 'Your attendance needs improvement.' : 'Your attendance is critically low. Please speak to your form teacher.';
  const alertCls = pct >= 75 ? 'att-alert--info' : pct >= 50 ? 'att-alert--warn' : 'att-alert--error';

  return (
    <div className="att-page">
      <div className="att-header">
        <h1 className="att-header__title">My Attendance<span className="att-header__sub">Track your punctuality and presence this term</span></h1>
        <div className="att-field-group"><label>Term</label><select className="att-select" value={selectedTerm} onChange={e => setSelectedTerm(e.target.value)}>{terms.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}</select></div>
      </div>

      {error && <div className="att-alert att-alert--error" role="alert">⚠ {error}</div>}

      {loading ? <div style={{ display: 'flex', gap: 14, marginBottom: 24 }}>{Array.from({ length: 5 }).map((_, i) => <div key={i} className="att-skeleton" style={{ flex: 1, height: 80 }} />)}</div> : summary && <>
        <div className={`att-alert ${alertCls}`} style={{ marginBottom: 20 }}><span>{pct >= 75 ? 'ℹ' : pct >= 50 ? '⚠' : '🚨'}</span><span>{statusText}</span></div>
        <div style={{ display: 'flex', gap: 20, alignItems: 'center', marginBottom: 24 }}><PctBadge pct={pct} /><div className="att-stats-strip" style={{ flex: 1 }}>{[
          { key: 'present', label: 'Present', cls: '', val: summary.present }, { key: 'absent', label: 'Absent', cls: 'is-absent', val: summary.absent }, { key: 'late', label: 'Late', cls: 'is-late', val: summary.late }, { key: 'excused', label: 'Excused', cls: 'is-excused', val: summary.excused }, { key: 'total', label: 'Total', cls: '', val: summary.total },
        ].map(s => <div key={s.key} className="att-stat-chip"><span className={`att-stat-chip__num ${s.cls}`}>{s.val ?? 0}</span><span className="att-stat-chip__label">{s.label}</span></div>)}</div></div>
      </>}

      <div className="att-card"><div className="att-card__head"><h2 className="att-card__title">📆 Daily Record</h2><div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>{Object.entries(STATUS_META).map(([k,v]) => <span key={k}>{v.label} — {v.title}</span>)}</div></div><div className="att-card__body">
        {!loading && !error && monthGroups.size === 0 ? <div className="att-empty"><strong>No records yet</strong>Attendance data will appear here once your teacher starts marking the register.</div> : Array.from(monthGroups.entries()).map(([month,recs]) => <div key={month} style={{ marginBottom: 20 }}><div style={{ fontWeight: 700, marginBottom: 8 }}>{month}</div><div className="att-mini-cal">{recs.map((rec,i) => <div key={`${rec.session_id}-${i}`} className={`att-mini-dot ${rec.status.charAt(0).toUpperCase()}`} title={`${rec.date} — ${rec.status}${rec.remark ? ': ' + rec.remark : ''}`}>{new Date(rec.date).getDate()}</div>)}</div></div>)}
      </div></div>
    </div>
  );
}
