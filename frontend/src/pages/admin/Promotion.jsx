import React, { useState, useEffect } from "react";
import api from "../../services/api";
import "./Promotion.css";

const DECISION_LABELS = { promoted: "Promoted", repeated: "Repeated", graduated: "Graduated", withdrawn: "Withdrawn" };
const DECISION_COLORS = { promoted: "promo-green", repeated: "promo-amber", graduated: "promo-blue", withdrawn: "promo-red" };

export default function Promotion() {
  const [sessions, setSessions]       = useState([]);
  const [levels, setLevels]           = useState([]);
  const [session, setSession]         = useState("");
  const [level, setLevel]             = useState("");
  const [results, setResults]         = useState([]);
  const [overrides, setOverrides]     = useState({});
  const [evaluating, setEvaluating]   = useState(false);
  const [preview, setPreview]         = useState(false);
  const [executing, setExecuting]     = useState(false);
  const [toast, setToast]             = useState(null);

  useEffect(() => {
    api.get("/api/academics/sessions/")
      .then(({ data: d }) => setSessions(Array.isArray(d) ? d : d.results || []))
      .catch(() => {});
    api.get("/api/enrollment/class-levels/")
      .then(({ data: d }) => setLevels(Array.isArray(d) ? d : d.results || []))
      .catch(() => {});
  }, []);

  async function evaluate() {
    if (!session) return;
    setEvaluating(true);
    try {
      let url = `/api/promotion/evaluate/?session=${session}`;
      if (level) url += `&class_level=${level}`;
      const { data } = await api.post(url);
      setResults(Array.isArray(data) ? data : []);
      setOverrides({});
    } catch {
      alert("Could not evaluate students. Please try again.");
    } finally {
      setEvaluating(false);
    }
  }

  function setDecision(studentId, decision) {
    setOverrides(o => ({ ...o, [studentId]: decision }));
  }

  function finalDecision(r) {
    return overrides[r.student_id] || r.recommended;
  }

  const summary = {
    promoted:  results.filter(r => finalDecision(r) === "promoted").length,
    repeated:  results.filter(r => finalDecision(r) === "repeated").length,
    graduated: results.filter(r => finalDecision(r) === "graduated").length,
  };

  async function execute() {
    setExecuting(true);
    try {
      const body = results.map(r => ({
        student_id:   r.student_id,
        session_id:   Number(session),
        decision:     finalDecision(r),
        criteria_met: r.criteria_met,
      }));
      const { data } = await api.post("/api/promotion/execute/", body);
      setPreview(false);
      setResults([]);
      setToast(`Done — ${data.executed} processed, ${data.graduated} graduated.`);
      setTimeout(() => setToast(null), 5000);
    } catch {
      alert("Could not execute promotions. Please try again.");
    } finally {
      setExecuting(false);
    }
  }

  return (
    <main className="page-shell">
      <h1 className="page-title">Promotion Engine</h1>
      {toast && <div className="promo-toast">{toast}</div>}

      {/* Controls */}
      <div className="promo-controls card">
        <select value={session} onChange={e => setSession(e.target.value)} className="promo-select">
          <option value="">— Select session —</option>
          {sessions.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
        <select value={level} onChange={e => setLevel(e.target.value)} className="promo-select">
          <option value="">All class levels</option>
          {levels.map(l => <option key={l.id} value={l.id}>{l.name}</option>)}
        </select>
        <button className="btn-primary" onClick={evaluate} disabled={evaluating || !session}>
          {evaluating ? "Evaluating…" : "Evaluate Students"}
        </button>
      </div>

      {/* Results table */}
      {results.length > 0 && (
        <>
          <div className="card table-wrap" style={{ marginTop: 16 }}>
            <table>
              <thead>
                <tr>
                  <th>Student</th>
                  <th>Class</th>
                  <th>Avg</th>
                  <th>Subj Passed</th>
                  <th>Attendance</th>
                  <th>Criteria</th>
                  <th>Recommended</th>
                  <th>Decision</th>
                </tr>
              </thead>
              <tbody>
                {results.map(r => (
                  <tr key={r.student_id}>
                    <td>{r.student_name}</td>
                    <td>{r.class}</td>
                    <td>{r.session_avg}%</td>
                    <td>{r.subjects_passed}</td>
                    <td>{r.attendance_pct}%</td>
                    <td>
                      <span className={`criteria-badge ${r.criteria_met ? "met" : "not-met"}`}>
                        {r.criteria_met ? "Met" : "Not met"}
                      </span>
                    </td>
                    <td>
                      <span className={`decision-badge ${DECISION_COLORS[r.recommended]}`}>
                        {DECISION_LABELS[r.recommended]}
                      </span>
                    </td>
                    <td>
                      <select
                        value={finalDecision(r)}
                        onChange={e => setDecision(r.student_id, e.target.value)}
                        className="decision-select"
                      >
                        {Object.entries(DECISION_LABELS).map(([v, l]) => (
                          <option key={v} value={v}>{l}</option>
                        ))}
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="promo-action-row">
            <button className="btn-primary" onClick={() => setPreview(true)}>
              Apply All Decisions ({results.length} students)
            </button>
          </div>
        </>
      )}

      {/* Preview modal */}
      {preview && (
        <div className="modal-overlay" onClick={() => setPreview(false)}>
          <div className="modal-box" onClick={e => e.stopPropagation()}>
            <h2>Confirm Promotion Execution</h2>
            <p style={{ marginBottom: 16, color: "#555" }}>
              This will update all student class placements. This action cannot be undone.
            </p>
            <div className="promo-summary">
              <div className="ps-row green"><span>Promoted</span><strong>{summary.promoted}</strong></div>
              <div className="ps-row amber"><span>Repeated</span><strong>{summary.repeated}</strong></div>
              <div className="ps-row blue"><span>Graduated</span><strong>{summary.graduated}</strong></div>
            </div>
            <div className="modal-actions">
              <button className="btn-secondary" onClick={() => setPreview(false)}>Cancel</button>
              <button className="btn-primary" onClick={execute} disabled={executing}>
                {executing ? "Executing…" : "Confirm & Execute"}
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
