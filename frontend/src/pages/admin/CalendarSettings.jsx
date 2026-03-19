/**
 * pages/admin/CalendarSettings.jsx
 *
 * Academic calendar management for school admins.
 * Features:
 *  - List sessions with term breakdown
 *  - Set current session/term
 *  - Create session / create term modals
 *  - Visual timeline bar showing term spans within a session
 */

import React, { useCallback, useEffect, useRef, useState } from "react";
import api from "../../services/api";
import "./CalendarSettings.css";

// ── API helpers ────────────────────────────────────────────────────────────

const calAPI = {
  getSessions:    ()       => api.get("/api/sessions/"),
  createSession:  (data)   => api.post("/api/sessions/", data),
  deleteSession:  (id)     => api.delete(`/api/sessions/${id}/`),
  setCurrentSession: (id)  => api.post(`/api/sessions/${id}/set-current/`),
  createTerm:     (data)   => api.post("/api/terms/", data),
  deleteTerm:     (id)     => api.delete(`/api/terms/${id}/`),
  setCurrentTerm: (id)     => api.post(`/api/terms/${id}/set-current/`),
};

// ── Tiny helpers ───────────────────────────────────────────────────────────

function fmt(dateStr) {
  if (!dateStr) return "—";
  return new Date(dateStr).toLocaleDateString("en-NG", {
    day: "numeric", month: "short", year: "numeric",
  });
}

function weeksApart(a, b) {
  return Math.round((new Date(b) - new Date(a)) / (1000 * 60 * 60 * 24 * 7));
}

// ── Modal ──────────────────────────────────────────────────────────────────

function Modal({ title, onClose, children }) {
  const ref = useRef();

  useEffect(() => {
    function onKey(e) { if (e.key === "Escape") onClose(); }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="cs-modal-overlay" onClick={e => e.target === ref.current && onClose()} ref={ref}>
      <div className="cs-modal" role="dialog" aria-modal="true" aria-label={title}>
        <div className="cs-modal-header">
          <h3 className="cs-modal-title">{title}</h3>
          <button className="cs-modal-close" onClick={onClose} aria-label="Close">✕</button>
        </div>
        <div className="cs-modal-body">{children}</div>
      </div>
    </div>
  );
}

// ── Term Timeline ──────────────────────────────────────────────────────────

function TermTimeline({ session }) {
  if (!session.start_date || !session.end_date) return null;
  const totalDays = (new Date(session.end_date) - new Date(session.start_date)) / 86400000;
  if (totalDays <= 0) return null;

  const TERM_COLORS = {
    first:  { bg: "var(--color-primary)",   label: "#fff" },
    second: { bg: "var(--color-secondary)", label: "#fff" },
    third:  { bg: "var(--color-accent)",    label: "#fff" },
  };

  const sessionStart = new Date(session.start_date);

  return (
    <div className="cs-timeline-wrap">
      <div className="cs-timeline-label-row">
        <span>{fmt(session.start_date)}</span>
        <span>{fmt(session.end_date)}</span>
      </div>
      <div className="cs-timeline-bar">
        {(session.terms || []).map(term => {
          const tStart = new Date(term.start_date);
          const tEnd   = new Date(term.end_date);
          const left   = ((tStart - sessionStart) / 86400000 / totalDays) * 100;
          const width  = ((tEnd  - tStart)         / 86400000 / totalDays) * 100;
          const colors = TERM_COLORS[term.name] || TERM_COLORS.first;
          const weeks  = weeksApart(term.start_date, term.end_date);

          return (
            <div
              key={term.id}
              className={`cs-timeline-segment ${term.is_current ? "is-current" : ""}`}
              style={{
                left:       `${Math.max(0, left)}%`,
                width:      `${Math.min(width, 100 - left)}%`,
                background: colors.bg,
                color:      colors.label,
              }}
              title={`${term.get_name_display || term.name}: ${fmt(term.start_date)} – ${fmt(term.end_date)}`}
            >
              <span className="cs-tl-name">
                {term.name_display_short || term.name}
                {term.is_current && " ✓"}
              </span>
              <span className="cs-tl-weeks">{weeks}w</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Create Session Form ────────────────────────────────────────────────────

function CreateSessionForm({ onSave, onClose, loading }) {
  const [form, setForm] = useState({ name: "", start_date: "", end_date: "" });
  const [err,  setErr]  = useState({});

  function set(k, v) { setForm(f => ({ ...f, [k]: v })); }

  function validate() {
    const e = {};
    if (!form.name.trim())   e.name       = "Required";
    if (!form.start_date)    e.start_date = "Required";
    if (!form.end_date)      e.end_date   = "Required";
    if (form.start_date && form.end_date && form.start_date >= form.end_date)
      e.end_date = "Must be after start date";
    return e;
  }

  function submit(e) {
    e.preventDefault();
    const errs = validate();
    if (Object.keys(errs).length) { setErr(errs); return; }
    onSave(form);
  }

  return (
    <form className="cs-form" onSubmit={submit} noValidate>
      <div className="cs-form-row">
        <div className="cs-form-field">
          <label>Session Name</label>
          <input
            type="text" placeholder="e.g. 2024/2025"
            value={form.name} onChange={e => set("name", e.target.value)}
          />
          {err.name && <span className="field-error">{err.name}</span>}
        </div>
      </div>
      <div className="cs-form-row cs-form-row--2col">
        <div className="cs-form-field">
          <label>Start Date</label>
          <input type="date" value={form.start_date} onChange={e => set("start_date", e.target.value)} />
          {err.start_date && <span className="field-error">{err.start_date}</span>}
        </div>
        <div className="cs-form-field">
          <label>End Date</label>
          <input type="date" value={form.end_date} onChange={e => set("end_date", e.target.value)} />
          {err.end_date && <span className="field-error">{err.end_date}</span>}
        </div>
      </div>
      <div className="cs-form-actions">
        <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
        <button type="submit" className="btn btn-primary" disabled={loading}>
          {loading ? "Saving…" : "Create Session"}
        </button>
      </div>
    </form>
  );
}

// ── Create Term Form ───────────────────────────────────────────────────────

function CreateTermForm({ session, onSave, onClose, loading }) {
  const [form, setForm] = useState({
    session: session.id,
    name: "", start_date: "", end_date: "", next_term_begins: "",
  });
  const [err, setErr] = useState({});

  const existingNames = (session.terms || []).map(t => t.name);
  const available = ["first","second","third"].filter(n => !existingNames.includes(n));

  function set(k, v) { setForm(f => ({ ...f, [k]: v })); }

  function validate() {
    const e = {};
    if (!form.name)       e.name       = "Required";
    if (!form.start_date) e.start_date = "Required";
    if (!form.end_date)   e.end_date   = "Required";
    if (form.start_date && form.end_date && form.start_date >= form.end_date)
      e.end_date = "Must be after start date";
    return e;
  }

  function submit(e) {
    e.preventDefault();
    const errs = validate();
    if (Object.keys(errs).length) { setErr(errs); return; }
    onSave(form);
  }

  if (available.length === 0) {
    return (
      <div className="cs-empty-msg">
        All three terms have been created for this session.
        <div className="cs-form-actions">
          <button className="btn btn-ghost" onClick={onClose}>Close</button>
        </div>
      </div>
    );
  }

  return (
    <form className="cs-form" onSubmit={submit} noValidate>
      <p className="cs-form-hint">Adding term to: <strong>{session.name}</strong></p>
      <div className="cs-form-row">
        <div className="cs-form-field">
          <label>Term</label>
          <select value={form.name} onChange={e => set("name", e.target.value)}>
            <option value="">Select term…</option>
            {available.map(n => (
              <option key={n} value={n}>
                {n.charAt(0).toUpperCase() + n.slice(1)} Term
              </option>
            ))}
          </select>
          {err.name && <span className="field-error">{err.name}</span>}
        </div>
      </div>
      <div className="cs-form-row cs-form-row--2col">
        <div className="cs-form-field">
          <label>Start Date</label>
          <input type="date" value={form.start_date} onChange={e => set("start_date", e.target.value)} />
          {err.start_date && <span className="field-error">{err.start_date}</span>}
        </div>
        <div className="cs-form-field">
          <label>End Date</label>
          <input type="date" value={form.end_date} onChange={e => set("end_date", e.target.value)} />
          {err.end_date && <span className="field-error">{err.end_date}</span>}
        </div>
      </div>
      <div className="cs-form-row">
        <div className="cs-form-field">
          <label>Next Term Begins <span className="cs-optional">(optional)</span></label>
          <input type="date" value={form.next_term_begins} onChange={e => set("next_term_begins", e.target.value)} />
        </div>
      </div>
      <div className="cs-form-actions">
        <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
        <button type="submit" className="btn btn-primary" disabled={loading}>
          {loading ? "Saving…" : "Add Term"}
        </button>
      </div>
    </form>
  );
}

// ── Term Row ───────────────────────────────────────────────────────────────

function TermRow({ term, onSetCurrent, onDelete, busy }) {
  const TERM_DOTS = { first: "cs-dot--1", second: "cs-dot--2", third: "cs-dot--3" };
  const weeks = weeksApart(term.start_date, term.end_date);

  return (
    <div className={`cs-term-row ${term.is_current ? "cs-term-row--current" : ""}`}>
      <div className="cs-term-left">
        <span className={`cs-dot ${TERM_DOTS[term.name] || ""}`} />
        <div>
          <span className="cs-term-name">
            {term.name_display || `${term.name} Term`}
            {term.is_current && <span className="cs-badge-current">Current</span>}
          </span>
          <span className="cs-term-dates">
            {fmt(term.start_date)} → {fmt(term.end_date)}
            <span className="cs-term-weeks">{weeks} weeks</span>
          </span>
        </div>
      </div>
      <div className="cs-term-actions">
        {!term.is_current && (
          <button
            className="btn btn-sm btn-secondary"
            onClick={() => onSetCurrent(term.id)}
            disabled={busy}
          >
            Set Current
          </button>
        )}
        <button
          className="btn btn-sm btn-ghost cs-delete-btn"
          onClick={() => onDelete(term.id)}
          disabled={busy}
          aria-label="Delete term"
        >
          ✕
        </button>
      </div>
    </div>
  );
}

// ── Session Card ───────────────────────────────────────────────────────────

function SessionCard({ session, onSetCurrent, onSetCurrentTerm, onDeleteTerm, onAddTerm, busy }) {
  const [expanded, setExpanded] = useState(session.is_current);

  return (
    <div className={`cs-session-card ${session.is_current ? "cs-session-card--current" : ""}`}>
      {/* Header */}
      <div className="cs-session-header" onClick={() => setExpanded(e => !e)} role="button" tabIndex={0}
        onKeyDown={e => e.key === "Enter" && setExpanded(ex => !ex)}>
        <div className="cs-session-left">
          <span className={`cs-session-chevron ${expanded ? "cs-session-chevron--open" : ""}`}>›</span>
          <div>
            <h3 className="cs-session-name">
              {session.name}
              {session.is_current && <span className="cs-badge-current cs-badge-current--session">Active</span>}
            </h3>
            <span className="cs-session-dates">
              {fmt(session.start_date)} → {fmt(session.end_date)}
              <span className="cs-session-terms-count">
                {(session.terms || []).length} / 3 terms
              </span>
            </span>
          </div>
        </div>
        <div className="cs-session-header-actions" onClick={e => e.stopPropagation()}>
          {!session.is_current && (
            <button
              className="btn btn-sm btn-primary"
              onClick={() => onSetCurrent(session.id)}
              disabled={busy}
            >
              Set Active
            </button>
          )}
          <button
            className="btn btn-sm btn-accent"
            onClick={() => onAddTerm(session)}
            disabled={busy}
          >
            + Add Term
          </button>
        </div>
      </div>

      {/* Expanded body */}
      {expanded && (
        <div className="cs-session-body">
          <TermTimeline session={session} />

          {(session.terms || []).length === 0 ? (
            <p className="cs-empty-msg">No terms yet. Add the first term above.</p>
          ) : (
            <div className="cs-terms-list">
              {[...session.terms].sort((a,b) => {
                const order = { first: 0, second: 1, third: 2 };
                return order[a.name] - order[b.name];
              }).map(term => (
                <TermRow
                  key={term.id}
                  term={term}
                  onSetCurrent={onSetCurrentTerm}
                  onDelete={onDeleteTerm}
                  busy={busy}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main Component ─────────────────────────────────────────────────────────

export default function CalendarSettings() {
  const [sessions,       setSessions]       = useState([]);
  const [loading,        setLoading]        = useState(true);
  const [busy,           setBusy]           = useState(false);
  const [error,          setError]          = useState(null);
  const [toast,          setToast]          = useState(null);
  const [showNewSession, setShowNewSession] = useState(false);
  const [addTermTarget,  setAddTermTarget]  = useState(null);  // session obj

  function showToast(msg, type = "success") {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3200);
  }

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await calAPI.getSessions();
      setSessions(data.results || data);
    } catch {
      setError("Failed to load sessions.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // ── Handlers ──────────────────────────────────────────────────────────────

  async function handleCreateSession(formData) {
    setBusy(true);
    try {
      await calAPI.createSession(formData);
      await load();
      setShowNewSession(false);
      showToast("Session created successfully.");
    } catch (err) {
      showToast(err.response?.data?.name?.[0] || "Failed to create session.", "error");
    } finally {
      setBusy(false);
    }
  }

  async function handleSetCurrentSession(id) {
    setBusy(true);
    try {
      await calAPI.setCurrentSession(id);
      await load();
      showToast("Active session updated.");
    } catch {
      showToast("Failed to update active session.", "error");
    } finally {
      setBusy(false);
    }
  }

  async function handleCreateTerm(formData) {
    setBusy(true);
    try {
      await calAPI.createTerm(formData);
      await load();
      setAddTermTarget(null);
      showToast("Term added successfully.");
    } catch (err) {
      const msg = err.response?.data?.non_field_errors?.[0] ||
                  err.response?.data?.name?.[0] ||
                  "Failed to create term.";
      showToast(msg, "error");
    } finally {
      setBusy(false);
    }
  }

  async function handleSetCurrentTerm(id) {
    setBusy(true);
    try {
      await calAPI.setCurrentTerm(id);
      await load();
      showToast("Active term updated.");
    } catch {
      showToast("Failed to update active term.", "error");
    } finally {
      setBusy(false);
    }
  }

  async function handleDeleteTerm(id) {
    if (!window.confirm("Delete this term? This cannot be undone.")) return;
    setBusy(true);
    try {
      await calAPI.deleteTerm(id);
      await load();
      showToast("Term deleted.");
    } catch {
      showToast("Failed to delete term.", "error");
    } finally {
      setBusy(false);
    }
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="cs-root">
        <div className="cs-loading">
          <div className="cs-spinner" />
          <span>Loading calendar…</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="cs-root">
        <div className="cs-error-banner">{error}</div>
      </div>
    );
  }

  const currentSession = sessions.find(s => s.is_current);
  const currentTerm    = sessions.flatMap(s => s.terms || []).find(t => t.is_current);

  return (
    <div className="cs-root">

      {/* ── Toast ── */}
      {toast && (
        <div className={`cs-toast cs-toast--${toast.type}`} role="status">
          {toast.type === "success" ? "✓" : "⚠"} {toast.msg}
        </div>
      )}

      {/* ── Page header ── */}
      <div className="cs-page-header">
        <div>
          <h1 className="cs-page-title">Academic Calendar</h1>
          <p className="cs-page-sub">
            Manage sessions and terms. One session and one term can be active at a time.
          </p>
        </div>
        <button
          className="btn btn-primary"
          onClick={() => setShowNewSession(true)}
          disabled={busy}
        >
          + New Session
        </button>
      </div>

      {/* ── Current status banner ── */}
      {(currentSession || currentTerm) && (
        <div className="cs-status-banner">
          <div className="cs-status-item">
            <span className="cs-status-dot" />
            <span className="cs-status-label">Active Session:</span>
            <strong>{currentSession?.name || "—"}</strong>
          </div>
          <div className="cs-status-divider" />
          <div className="cs-status-item">
            <span className="cs-status-dot cs-status-dot--term" />
            <span className="cs-status-label">Active Term:</span>
            <strong>
              {currentTerm
                ? `${currentTerm.name_display || currentTerm.name} (${currentSession?.name})`
                : "—"}
            </strong>
          </div>
        </div>
      )}

      {/* ── Sessions list ── */}
      {sessions.length === 0 ? (
        <div className="cs-empty-state">
          <div className="cs-empty-icon">📅</div>
          <h2>No Sessions Yet</h2>
          <p>Create your first academic session to get started.</p>
          <button className="btn btn-primary" onClick={() => setShowNewSession(true)}>
            Create Session
          </button>
        </div>
      ) : (
        <div className="cs-sessions-list">
          {sessions.map(session => (
            <SessionCard
              key={session.id}
              session={session}
              onSetCurrent={handleSetCurrentSession}
              onSetCurrentTerm={handleSetCurrentTerm}
              onDeleteTerm={handleDeleteTerm}
              onAddTerm={setAddTermTarget}
              busy={busy}
            />
          ))}
        </div>
      )}

      {/* ── Modals ── */}
      {showNewSession && (
        <Modal title="Create Academic Session" onClose={() => setShowNewSession(false)}>
          <CreateSessionForm
            onSave={handleCreateSession}
            onClose={() => setShowNewSession(false)}
            loading={busy}
          />
        </Modal>
      )}

      {addTermTarget && (
        <Modal title="Add Term" onClose={() => setAddTermTarget(null)}>
          <CreateTermForm
            session={addTermTarget}
            onSave={handleCreateTerm}
            onClose={() => setAddTermTarget(null)}
            loading={busy}
          />
        </Modal>
      )}

    </div>
  );
}