import React, { useState, useEffect, useContext } from "react";
import { AuthContext } from "../../context/AuthContext";
import api from "../../services/api";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Legend,
} from "recharts";
import "./MyPerformance.css";

const COLORS = ["#1a6b3c", "#3498db", "#e67e22", "#9b59b6", "#e74c3c", "#2ecc71"];

export default function MyPerformance() {
  const { user } = useContext(AuthContext);
  const studentId = user?.student_id || user?.id;

  const [trends, setTrends]   = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!studentId) return;
    api.get(`/api/analytics/student/${studentId}/trends/?terms=4`)
      .then(({ data }) => { setTrends(Array.isArray(data) ? data : []); setLoading(false); })
      .catch(() => setLoading(false));
  }, [studentId]);

  // Build multi-line data: one point per term, one line per subject
  const allSubjects = [...new Set(trends.flatMap(t => t.subjects.map(s => s.subject)))];
  const lineData    = trends.map(t => {
    const row = { term: t.term_name.replace(' Term', '').replace(' 20', " '") };
    t.subjects.forEach(s => { row[s.subject] = s.score; });
    return row;
  });

  // Radar data from most recent term
  const latest      = trends[trends.length - 1];
  const radarData   = latest?.subjects.map(s => ({ subject: s.subject.length > 10 ? s.subject.slice(0, 10) + '…' : s.subject, score: s.score })) || [];

  // Best and most improved
  const avgBySubject = allSubjects.map(sub => {
    const vals = trends.map(t => t.subjects.find(s => s.subject === sub)?.score).filter(Boolean);
    return { subject: sub, avg: vals.reduce((a, b) => a + b, 0) / (vals.length || 1) };
  });
  const bestSubject = [...avgBySubject].sort((a, b) => b.avg - a.avg)[0];
  const mostImproved = allSubjects.map(sub => {
    const vals = trends.map(t => t.subjects.find(s => s.subject === sub)?.score || null).filter(Boolean);
    const improvement = vals.length >= 2 ? vals[vals.length - 1] - vals[0] : 0;
    return { subject: sub, improvement };
  }).sort((a, b) => b.improvement - a.improvement)[0];

  return (
    <main className="page-shell performance-page">
      <h1 className="page-title">My Performance</h1>

      {loading && <p className="loading-msg">Loading trends…</p>}

      {!loading && trends.length === 0 && (
        <p className="empty-row">No performance data available yet.</p>
      )}

      {!loading && trends.length > 0 && (
        <>
          {/* Badges */}
          <div className="perf-badges">
            {bestSubject && (
              <div className="perf-badge gold">
                <span className="badge-icon">⭐</span>
                <div>
                  <span className="badge-label">Best Subject</span>
                  <strong>{bestSubject.subject}</strong>
                  <span className="badge-sub">{bestSubject.avg.toFixed(1)}% average</span>
                </div>
              </div>
            )}
            {mostImproved?.improvement > 0 && (
              <div className="perf-badge green">
                <span className="badge-icon">📈</span>
                <div>
                  <span className="badge-label">Most Improved</span>
                  <strong>{mostImproved.subject}</strong>
                  <span className="badge-sub">+{mostImproved.improvement.toFixed(1)} pts over {trends.length} terms</span>
                </div>
              </div>
            )}
          </div>

          {/* Line chart — all subjects over terms */}
          <div className="chart-card">
            <h3>Score Trends — All Subjects</h3>
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={lineData} margin={{ right: 10 }}>
                <XAxis dataKey="term" tick={{ fontSize: 11 }} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                {allSubjects.slice(0, 8).map((sub, i) => (
                  <Line key={sub} type="monotone" dataKey={sub} stroke={COLORS[i % COLORS.length]} dot strokeWidth={2} />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Radar — current term */}
          {radarData.length > 0 && (
            <div className="chart-card">
              <h3>Subject Breakdown — {latest?.term_name}</h3>
              <ResponsiveContainer width="100%" height={260}>
                <RadarChart data={radarData}>
                  <PolarGrid />
                  <PolarAngleAxis dataKey="subject" tick={{ fontSize: 10 }} />
                  <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fontSize: 9 }} />
                  <Radar dataKey="score" stroke="var(--primary,#1a6b3c)" fill="var(--primary,#1a6b3c)" fillOpacity={0.35} />
                  <Tooltip />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Term summary table */}
          <div className="card table-wrap">
            <table>
              <thead>
                <tr><th>Term</th><th>Average</th><th>Position</th><th>Attendance</th></tr>
              </thead>
              <tbody>
                {trends.map((t, i) => {
                  const prev = trends[i - 1];
                  const arrow = prev && t.average && prev.average
                    ? t.average > prev.average ? "↑" : t.average < prev.average ? "↓" : "→"
                    : "";
                  const arrowClass = arrow === "↑" ? "up" : arrow === "↓" ? "down" : "";
                  return (
                    <tr key={i}>
                      <td>{t.term_name}</td>
                      <td><strong>{t.average ?? "—"}%</strong> <span className={`trend-arrow ${arrowClass}`}>{arrow}</span></td>
                      <td>{t.position ? `#${t.position}` : "—"}</td>
                      <td>{t.attendance_pct != null ? `${t.attendance_pct}%` : "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </main>
  );
}
