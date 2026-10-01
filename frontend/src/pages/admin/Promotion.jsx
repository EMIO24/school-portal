import React, { useState, useEffect } from "react";
import api from "../../services/api";
import "./Promotion.css";

const DECISION_LABELS = { promoted: "Promoted", repeated: "Repeated", graduated: "Graduated", withdrawn: "Withdrawn" };
const DECISION_COLORS = { promoted: "promo-green", repeated: "promo-amber", graduated: "promo-blue", withdrawn: "promo-red" };

export default function Promotion() {
  const [destinationSession, setDestinationSession] = useState('');
  const [sessions, setSessions]       = useState([]);
  const [levels, setLevels]           = useState([]);
  const [classArms, setClassArms]     = useState([]);
  const [destinations, setDestinations] = useState({});
  const [session, setSession]         = useState("");
  const [level, setLevel]             = useState("");
  const [results, setResults]         = useState([]);
  const [overrides, setOverrides]     = useState({});
  const [evaluating, setEvaluating]   = useState(false);
  const [preview, setPreview]         = useState(false);
  const [executing, setExecuting]     = useState(false);
  const [toast, setToast]             = useState(null);

  useEffect(() => {
    api.get("/api/sessions/")
      .then(({ data: d }) => setSessions(Array.isArray(d) ? d : d.results || []))
      .catch(() => {});
    api.get("/api/class-levels/")
      .then(({ data: d }) => setLevels(Array.isArray(d) ? d : d.results || []))
      .catch(() => {});
    api.get("/api/class-arms/")
      .then(({ data: d }) => setClassArms(Array.isArray(d) ? d : d.results || []))
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
      setDestinations({});
    } catch {
      alert("Could not evaluate students. Please try again.");
    } finally {
      setEvaluating(false);
    }
  }

  function setDecision(studentId, decision) {
    setOverrides(o => ({ ...o, [studentId]: decision }));
    if (decision !== "promoted") {
      setDestinations(current => {
        const next = { ...current };
        delete next[studentId];
        return next;
      });
    }
  }

  function eligibleDestinationArms(result) {
    const source = levels.find(l => Number(l.id) === Number(result.class_level_id));
    if (!source) return [];
    const higherLevelIds = new Set(
      levels
        .filter(l => Number(l.order_index) > Number(source.order_index))
        .map(l => Number(l.id))
    );
    return classArms.filter(arm => higherLevelIds.has(Number(arm.class_level)));
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
    const continuing = results.some(r => ["promoted", "repeated"].includes(finalDecision(r)));
    if (continuing && !destinationSession) {
      setToast('Select the destination academic session.');
      return;
    }
    const missingDestination = results.find(
      r => finalDecision(r) === "promoted" && !destinations[r.student_id]
    );
    if (missingDestination) {
      setToast(`Select a destination class for ${missingDestination.student_name}.`);
      return;
    }
    setExecuting(true);
    try {
      const body = results.map(r => {
        const decision = finalDecision(r);
        return {
          student_id: r.student_id,
          session_id: Number(session),
          to_session_id: ["promoted", "repeated"].includes(decision)
            ? Number(destinationSession)
            : undefined,
          to_class_id: decision === "promoted"
            ? Number(destinations[r.student_id])
            : undefined,
          decision,
          criteria_met: r.criteria_met,
        };
      });
      const { data } = await api.post("/api/promotion/execute/", body);
      setPreview(false);
      setResults([]);
      setToast(`Saved — ${data.staged ?? data.executed} year-end decisions staged. Run Academic Rollover from Calendar to apply them.`);
      setTimeout(() => setToast(null), 5000);
    } catch {
      setToast('Could not execute promotions. Check the destination session and class; a previous decision cannot be repeated.');
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
        <label>Destination session<select value={destinationSession} onChange={e => setDestinationSession(e.target.value)}><option value="">Select destination session</option>{sessions.filter(s => String(s.id) !== String(session)).map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
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
                  <th>Destination</th>
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
                    <td>
                      {finalDecision(r) === "promoted" ? (
                        <select
                          aria-label={`Destination class for ${r.student_name}`}
                          value={destinations[r.student_id] || ""}
                          onChange={e => setDestinations(current => ({
                            ...current,
                            [r.student_id]: e.target.value,
                          }))}
                          className="decision-select"
                        >
                          <option value="">Select class</option>
                          {eligibleDestinationArms(r).map(arm => (
                            <option key={arm.id} value={arm.id}>{arm.full_name}</option>
                          ))}
                        </select>
                      ) : finalDecision(r) === "repeated" ? (
                        <span>{r.class} (repeat)</span>
                      ) : (
                        <span>—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="promo-action-row">
            <button className="btn-primary" onClick={() => setPreview(true)}>
              Stage All Decisions ({results.length} students)
            </button>
          </div>
        </>
      )}

      {/* Preview modal */}
      {preview && (
        <div className="modal-overlay" onClick={() => setPreview(false)}>
          <div className="modal-box" onClick={e => e.stopPropagation()}>
            <h2>Confirm Year-End Decisions</h2>
            <p style={{ marginBottom: 16, color: "#555" }}>
              This saves the year-end decisions for review. Student classes, lifecycle status, and next-session enrollments will not change until you execute Academic Rollover from the Calendar page.
            </p>
            <div className="promo-summary">
              <div className="ps-row green"><span>Promoted</span><strong>{summary.promoted}</strong></div>
              <div className="ps-row amber"><span>Repeated</span><strong>{summary.repeated}</strong></div>
              <div className="ps-row blue"><span>Graduated</span><strong>{summary.graduated}</strong></div>
            </div>
            <div className="modal-actions">
              <button className="btn-secondary" onClick={() => setPreview(false)}>Cancel</button>
              <button className="btn-primary" onClick={execute} disabled={executing}>
                {executing ? "Saving…" : "Confirm & Save Decisions"}
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
