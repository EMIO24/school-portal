import WorkspaceHome from "../../components/common/WorkspaceHome";
import { useTheme } from "../../context/ThemeContext";
import { hasFeature } from "../../services/features";
import React, { useState, useEffect } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell,
} from "recharts";
import api from "../../services/api";
import "./AdminDashboard.css";

const COLORS = ["#1a6b3c", "#2ecc71", "#f39c12", "#e74c3c", "#3498db", "#9b59b6"];

function KPICard({ label, value, sub, color }) {
  return (
    <div className="kpi-card" style={{ borderTopColor: color || "var(--primary)" }}>
      <span className="kpi-label">{label}</span>
      <strong className="kpi-value">{value ?? "—"}</strong>
      {sub && <span className="kpi-sub">{sub}</span>}
    </div>
  );
}

export default function AdminDashboard() {
  const {school}=useTheme();
  const analyticsEnabled=hasFeature(school,"analytics");
  const [snap, setSnap]       = useState(null);
  const [loading, setLoading] = useState(true);
  const [terms, setTerms]     = useState([]);
  const [term, setTerm]       = useState("");
  const [error, setError] = useState("");
  const [summary, setSummary] = useState(null);
  const [summaryError, setSummaryError] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let active = true;
    Promise.all(["students", "staff", "class-arms", "subjects"].map(resource =>
      api.get("/api/" + resource + "/?page_size=1").then(({ data }) =>
        Array.isArray(data) ? data.length : data.count ?? data.results?.length ?? 0)
    )).then(counts => { if (active) setSummary(counts); })
      .catch(() => { if (active) setSummaryError("Could not load school counts. Reload to retry."); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    api.get("/api/terms/").then(({ data: d }) => {
      const list = Array.isArray(d) ? d : d.results || [];
      setTerms(list);
      const cur = list.find(t => t.is_current);
      if (cur || list[0]) setTerm(String((cur || list[0]).id));
      else setLoading(false);
    }).catch(() => { setError("Could not load terms. Reload this page to retry."); setLoading(false); });
  }, []);

  useEffect(() => {
    if (!term || !analyticsEnabled) {setLoading(false);return;}
    let active = true;
    setLoading(true); setSnap(null); setError(""); setNotice("");
    api.get("/api/analytics/overview/?term=" + term)
      .then(({ data, status }) => { if (active) setSnap(status === 204 ? null : data); })
      .catch(() => { if (active) setError("Could not load analytics. Try Refresh Analytics or reload the page."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [term, analyticsEnabled]);

  async function refresh() {
    setRefreshing(true); setError(""); setNotice("");
    try {
      await api.post("/api/analytics/refresh/?term=" + term);
      const { data, status } = await api.get("/api/analytics/overview/?term=" + term);
      setSnap(status === 204 ? null : data);
      setNotice("Refresh requested. Background processing may take a moment; refresh again to check for updated figures.");
    } catch {
      setError("Could not refresh analytics. Please try again.");
    } finally {
      setRefreshing(false);
    }
  }

  const gradeData   = snap ? Object.entries(snap.grade_distribution || {}).map(([g, n]) => ({ grade: g, count: n })) : [];
  const subjectData = (snap?.subject_averages || []).slice(-8);
  const classData   = snap?.class_averages || [];

  return (
    <main className="page-shell admin-dash">
      <WorkspaceHome compact/>
      <div className="dash-header-row">
        <h1 className="page-title">Dashboard</h1>
        {analyticsEnabled && <div className="dash-controls">
          <select aria-label="Academic term" disabled={refreshing} value={term} onChange={e => setTerm(e.target.value)} className="dash-select">
            <option value="" disabled>Select a term</option>
            {terms.map(t => <option key={t.id} value={t.id}>{t.name} {t.is_current ? "(current)" : ""}</option>)}
          </select>
          <button className="btn-secondary btn-sm" onClick={refresh} disabled={!term || refreshing}>↻ Refresh Analytics</button>
        </div>}
      </div>

      {summaryError && <p role="alert">{summaryError}</p>}
      {summary && <div className="kpi-row">
        {["Enrolled Students", "Staff Members", "Classes", "Subjects"].map((label, index) =>
          <KPICard key={label} label={label} value={summary[index]} />)}
      </div>}
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      {!loading && !term && !error && <p>No academic terms found. Add a session and term in Academic Calendar.</p>}
      {loading && <p className="loading-msg">Loading analytics…</p>}
      {analyticsEnabled && !loading && term && !snap && !error && (
        <div className="no-snap">
          Your term overview is ready to prepare. Select <strong>↻ Refresh Analytics</strong> to summarise results, attendance and fee collection for this term.
        </div>
      )}

      {snap && (
        <>
          {/* Row 1 — KPI cards */}
          <div className="kpi-row">
            <KPICard label="Total Students"  value={snap.total_students}                       color="var(--primary)" />
            <KPICard label="School Average"  value={`${snap.school_average}%`}                color="var(--secondary)" />
            <KPICard label="Pass Rate"       value={`${snap.overall_pass_rate}%`}             color="var(--accent)" />
            <KPICard label="Fee Collection"  value={`${snap.fee_collection_rate}%`} sub="of expected" color="#9b59b6" />
          </div>

          {/* Row 2 — Subject performance + Grade distribution */}
          <div className="chart-row">
            <div className="chart-card">
              <h3>Subject Performance (Average %)</h3>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={subjectData} layout="vertical" margin={{ left: 20 }}>
                  <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11 }} />
                  <YAxis type="category" dataKey="subject" width={90} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="avg" fill="var(--primary, #1a6b3c)" radius={[0, 3, 3, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="chart-card">
              <h3>Grade Distribution</h3>
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie data={gradeData} dataKey="count" nameKey="grade" cx="50%" cy="50%" outerRadius={80} label={({ grade }) => grade}>
                    {gradeData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Row 3 — Class comparison */}
          {classData.length > 0 && (
            <div className="chart-card full-width">
              <h3>Class Average Comparison</h3>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={classData}>
                  <XAxis dataKey="class_arm" tick={{ fontSize: 11 }} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="avg" fill="var(--secondary)" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Row 4 — Top students + Attendance */}
          <div className="chart-row">
            <div className="chart-card">
              <h3>Top 5 Students</h3>
              <table className="leaderboard">
                <thead><tr><th>#</th><th>Name</th><th>Class</th><th>Avg</th></tr></thead>
                <tbody>
                  {(snap.top_students || []).slice(0, 5).map((s, i) => (
                    <tr key={i}>
                      <td className={`rank rank-${i + 1}`}>{i + 1}</td>
                      <td>{s.name}</td>
                      <td>{s.class}</td>
                      <td><strong>{s.average}%</strong></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="chart-card">
              <h3>School Attendance</h3>
              <div className="attend-big">{snap.attendance_school_avg}%</div>
              <p className="attend-label">School-wide attendance average this term</p>
              {snap.attendance_school_avg < 75 && (
                <div className="attend-alert">⚠ Below 75% — action recommended</div>
              )}
            </div>
          </div>
        </>
      )}
    </main>
  );
}
