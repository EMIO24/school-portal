import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import api from "../../services/api";
import "./ParentDashboard.css";

const GRADE = (avg) => {
  if (!avg) return "—";
  if (avg >= 70) return "A";
  if (avg >= 60) return "B";
  if (avg >= 50) return "C";
  if (avg >= 45) return "D";
  return "F";
};

const STATUS_DOT = { present: "#1a6b3c", absent: "#c0392b", late: "#e67e22", excused: "#888" };

export default function ParentDashboard() {
  const [children, setChildren]   = useState([]);
  const [activeIdx, setActiveIdx] = useState(0);
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading]     = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    api.get("/api/parent/children/")
      .then(({ data }) => {
        const list = Array.isArray(data) ? data : [];
        setChildren(list);
        if (list.length > 0) loadDashboard(list[0].student_id);
      })
      .catch(() => {});
  }, []);

  function loadDashboard(studentId) {
    setLoading(true);
    api.get(`/api/parent/dashboard/${studentId}/`)
      .then(({ data }) => { setDashboard(data); setLoading(false); })
      .catch(() => setLoading(false));
  }

  function switchChild(idx) {
    setActiveIdx(idx);
    loadDashboard(children[idx].student_id);
  }

  const child = children[activeIdx];
  const d     = dashboard;

  return (
    <div className="parent-app">
      {/* Top bar */}
      <header className="parent-header">
        <span className="parent-header-title">Parent Portal</span>
        <button className="notif-bell" onClick={() => setNotifOpen(o => !o)}>
          🔔
          {d?.recent_notifications?.length > 0 && (
            <span className="notif-badge">{d.recent_notifications.length}</span>
          )}
        </button>
      </header>

      {/* Notification drawer */}
      {notifOpen && (
        <div className="notif-drawer">
          <div className="notif-drawer-header">
            Recent Messages <button onClick={() => setNotifOpen(false)}>✕</button>
          </div>
          {(!d?.recent_notifications?.length) && <p className="empty-msg">No messages yet.</p>}
          {d?.recent_notifications?.map((n, i) => (
            <div key={i} className="notif-item">
              <span className="notif-ch">{n.channel.toUpperCase()}</span>
              <p>{n.message_body}</p>
              <span className="notif-time">{n.sent_at ? new Date(n.sent_at).toLocaleDateString() : ""}</span>
            </div>
          ))}
        </div>
      )}

      <main className="parent-main">
        {/* Ward selector */}
        {children.length > 0 && (
          <div className="ward-selector">
            {children.map((c, i) => (
              <button
                key={c.student_id}
                className={`ward-card ${i === activeIdx ? "active" : ""}`}
                onClick={() => switchChild(i)}
              >
                <div className="ward-avatar">{c.name.charAt(0)}</div>
                <span className="ward-name">{c.name.split(" ")[0]}</span>
                <span className="ward-class">{c.class}</span>
              </button>
            ))}
          </div>
        )}

        {loading && <p className="loading-msg">Loading…</p>}

        {!loading && d && (
          <div className="dashboard-cards">
            {/* Result card */}
            <div className="dash-card">
              <div className="card-label">Results</div>
              {d.result_summary ? (
                <>
                  <div className="result-row">
                    <div className="result-stat">
                      <span>Average</span>
                      <strong>{d.result_summary.average ?? "—"}%</strong>
                    </div>
                    <div className="result-stat">
                      <span>Position</span>
                      <strong>{d.result_summary.position ?? "—"}</strong>
                    </div>
                    <div className={`grade-badge grade-${GRADE(d.result_summary.average)}`}>
                      {GRADE(d.result_summary.average)}
                    </div>
                  </div>
                  <button className="card-link" onClick={() => navigate(`/parent/results/${child?.student_id}`)}>
                    View Full Result →
                  </button>
                </>
              ) : <p className="no-data">No result data available.</p>}
            </div>

            {/* Attendance card */}
            <div className="dash-card">
              <div className="card-label">Attendance</div>
              {d.attendance_summary ? (
                <>
                  {d.attendance_summary.warning && (
                    <div className="attend-warning">⚠ Below 75% attendance</div>
                  )}
                  <div className="attend-pct">{d.attendance_summary.percentage}%</div>
                  <div className="attend-sub">{d.attendance_summary.present} / {d.attendance_summary.total} days present</div>
                  <div className="dot-row">
                    {d.attendance_summary.last_7_days.map((day, i) => (
                      <span
                        key={i}
                        className="attend-dot"
                        style={{ background: STATUS_DOT[day.status] || "#ccc" }}
                        title={`${day.date}: ${day.status}`}
                      />
                    ))}
                  </div>
                </>
              ) : <p className="no-data">No attendance data.</p>}
            </div>

            {/* Fee card */}
            <div className="dash-card">
              <div className="card-label">Fees</div>
              {d.fee_status ? (
                <>
                  <div className="fee-row">
                    <div>
                      <span>Outstanding</span>
                      <strong className={d.fee_status.outstanding > 0 ? "red" : "green"}>
                        ₦{Number(d.fee_status.outstanding).toLocaleString()}
                      </strong>
                    </div>
                    <div>
                      <span>Paid</span>
                      <strong className="green">₦{Number(d.fee_status.paid).toLocaleString()}</strong>
                    </div>
                  </div>
                  {d.fee_status.outstanding > 0 && (
                    <button className="card-btn" onClick={() => navigate(`/parent/fees/${child?.student_id}`)}>
                      Pay Now
                    </button>
                  )}
                </>
              ) : <p className="no-data">No fee data.</p>}
            </div>

            {/* Timetable card */}
            <div className="dash-card">
              <div className="card-label">Today's Timetable</div>
              {d.timetable_today?.length > 0 ? (
                <div className="tt-list">
                  {d.timetable_today.map((p, i) => (
                    <div key={i} className={`tt-row ${p.is_current ? "tt-current" : ""}`}>
                      <span className="tt-time">{p.start_time.slice(0, 5)}</span>
                      <span className="tt-subject">{p.subject}</span>
                      <span className="tt-teacher">{p.teacher}</span>
                    </div>
                  ))}
                </div>
              ) : <p className="no-data">No classes today.</p>}
            </div>
          </div>
        )}

        {children.length === 0 && !loading && (
          <div className="no-children">
            <p>No children linked to your account yet.</p>
            <p>Contact the school admin to link your child's record.</p>
          </div>
        )}
      </main>
    </div>
  );
}
