/**
 * pages/admin/SubjectManager.jsx
 *
 * Manage all subjects for the school:
 *  - List subjects grouped by category (core / elective / vocational)
 *  - Create subject modal (name, code, category, class levels, CA/exam split)
 *  - Edit subject inline
 *  - Delete with confirmation
 *
 * Route: /admin/subjects
 */

import React, { useCallback, useEffect, useState } from "react";
import api from "../../services/api";
import "./SubjectManager.css";

const CATEGORY_COLORS = {
  core:       { bg: "var(--color-primary)",   label: "#fff" },
  elective:   { bg: "var(--color-secondary)", label: "#fff" },
  vocational: { bg: "var(--color-accent)",    label: "#fff" },
};

// ── Modal ──────────────────────────────────────────────────────────────────

function Modal({ title, onClose, children }) {
  useEffect(() => {
    const k = e => e.key === "Escape" && onClose();
    document.addEventListener("keydown", k);
    return () => document.removeEventListener("keydown", k);
  }, [onClose]);

  return (
    <div className="sm-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="sm-modal" role="dialog" aria-modal="true">
        <div className="sm-modal-header">
          <h3 className="sm-modal-title">{title}</h3>
          <button className="sm-modal-close" onClick={onClose}>✕</button>
        </div>
        <div className="sm-modal-body">{children}</div>
      </div>
    </div>
  );
}

// ── Subject Form ───────────────────────────────────────────────────────────

function SubjectForm({ initial, classLevels, onSave, onClose, saving }) {
  const [form, setForm] = useState({
    name:          initial?.name          || "",
    code:          initial?.code          || "",
    category:      initial?.category      || "core",
    max_ca_score:  initial?.max_ca_score  ?? 40,
    max_exam_score:initial?.max_exam_score?? 60,
    class_levels:  initial?.class_levels  || [],
  });
  const [errors, setErrors] = useState({});

  function set(k, v) { setForm(f => ({ ...f, [k]: v })); }

  function toggleLevel(id) {
    setForm(f => ({
      ...f,
      class_levels: f.class_levels.includes(id)
        ? f.class_levels.filter(x => x !== id)
        : [...f.class_levels, id],
    }));
  }

  // Keep CA + exam summing to 100
  function setCA(v) {
    const ca = Math.min(100, Math.max(0, Number(v)));
    setForm(f => ({ ...f, max_ca_score: ca, max_exam_score: 100 - ca }));
  }

  function validate() {
    const e = {};
    if (!form.name.trim()) e.name = "Name is required.";
    if (!form.code.trim()) e.code = "Code is required.";
    if (form.max_ca_score + form.max_exam_score !== 100)
      e.max_ca_score = "CA + Exam scores must total 100.";
    return e;
  }

  function submit(e) {
    e.preventDefault();
    const errs = validate();
    if (Object.keys(errs).length) { setErrors(errs); return; }
    onSave(form);
  }

  return (
    <form className="sm-form" onSubmit={submit} noValidate>
      <div className="sm-form-grid">
        <div className="sm-field sm-field--wide">
          <label>Subject Name <span className="sm-req">*</span></label>
          <input type="text" value={form.name} onChange={e => set("name", e.target.value)}
            className={errors.name ? "input--error" : ""}
            placeholder="e.g. Mathematics" />
          {errors.name && <span className="field-error">{errors.name}</span>}
        </div>

        <div className="sm-field">
          <label>Code <span className="sm-req">*</span></label>
          <input type="text" value={form.code}
            onChange={e => set("code", e.target.value.toUpperCase())}
            className={errors.code ? "input--error" : ""}
            placeholder="MTH" maxLength={10} />
          {errors.code && <span className="field-error">{errors.code}</span>}
        </div>

        <div className="sm-field">
          <label>Category</label>
          <select value={form.category} onChange={e => set("category", e.target.value)}>
            <option value="core">Core</option>
            <option value="elective">Elective</option>
            <option value="vocational">Vocational</option>
          </select>
        </div>
      </div>

      {/* CA / Exam score split */}
      <div className="sm-score-section">
        <div className="sm-score-heading">
          Score Breakdown
          <span className="sm-score-total">
            {form.max_ca_score + form.max_exam_score === 100
              ? "✓ Total: 100" : "⚠ Must total 100"}
          </span>
        </div>
        <div className="sm-score-row">
          <div className="sm-field">
            <label>Continuous Assessment (CA)</label>
            <div className="sm-score-input-wrap">
              <input type="number" min="0" max="100" value={form.max_ca_score}
                onChange={e => setCA(e.target.value)} />
              <span className="sm-score-unit">/ 100</span>
            </div>
            {errors.max_ca_score && <span className="field-error">{errors.max_ca_score}</span>}
          </div>
          <div className="sm-score-divider">+</div>
          <div className="sm-field">
            <label>Examination</label>
            <div className="sm-score-input-wrap">
              <input type="number" min="0" max="100" value={form.max_exam_score}
                readOnly className="sm-readonly" />
              <span className="sm-score-unit">/ 100</span>
            </div>
          </div>
          <div className="sm-score-divider">=</div>
          <div className="sm-total-badge">{form.max_ca_score + form.max_exam_score}</div>
        </div>
        <input type="range" min={0} max={100} value={form.max_ca_score}
          onChange={e => setCA(e.target.value)} className="sm-score-slider"
          aria-label="CA score slider" />
      </div>

      {/* Class levels */}
      <div className="sm-levels-section">
        <label className="sm-levels-heading">
          Offered to Class Levels
          <span className="sm-levels-hint">Leave unchecked = all levels</span>
        </label>
        <div className="sm-levels-grid">
          {classLevels.map(l => (
            <label key={l.id} className={`sm-level-chip ${form.class_levels.includes(l.id) ? "sm-level-chip--on" : ""}`}>
              <input type="checkbox" checked={form.class_levels.includes(l.id)}
                onChange={() => toggleLevel(l.id)} className="sm-hidden-cb" />
              {l.name}
            </label>
          ))}
        </div>
      </div>

      <div className="sm-form-actions">
        <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
        <button type="submit" className="btn btn-primary" disabled={saving}>
          {saving && <span className="sm-btn-spinner" />}
          {saving ? "Saving…" : initial ? "Update Subject" : "Create Subject"}
        </button>
      </div>
    </form>
  );
}

// ── Subject Row ────────────────────────────────────────────────────────────

function SubjectRow({ subject, onEdit, onDelete }) {
  const cat = CATEGORY_COLORS[subject.category] || CATEGORY_COLORS.core;
  return (
    <tr>
      <td>
        <div className="sm-subject-name-cell">
          <span className="sm-category-dot" style={{ background: cat.bg }} />
          <div>
            <div className="sm-subject-name">{subject.name}</div>
            <code className="sm-subject-code">{subject.code}</code>
          </div>
        </div>
      </td>
      <td>
        <span className="sm-category-badge"
          style={{ background: cat.bg, color: cat.label }}>
          {subject.category}
        </span>
      </td>
      <td>
        <div className="sm-score-display">
          <span className="sm-score-ca">{subject.max_ca_score} CA</span>
          <span className="sm-score-sep">+</span>
          <span className="sm-score-exam">{subject.max_exam_score} Exam</span>
          <span className="sm-score-eq">= 100</span>
        </div>
      </td>
      <td>
        {subject.class_levels?.length > 0
          ? <div className="sm-levels-chips">
              {/* class_levels may be IDs or objects from API */}
              {subject.class_levels.slice(0,4).map((l, i) => (
                <span key={i} className="sm-small-chip">
                  {typeof l === "object" ? l.name : l}
                </span>
              ))}
              {subject.class_levels.length > 4 &&
                <span className="sm-small-chip sm-small-chip--more">
                  +{subject.class_levels.length - 4}
                </span>
              }
            </div>
          : <span className="text-muted" style={{fontSize:"0.8rem"}}>All levels</span>
        }
      </td>
      <td>
        <div className="sm-row-actions">
          <button className="btn btn-sm btn-ghost" onClick={() => onEdit(subject)}>Edit</button>
          <button className="btn btn-sm btn-ghost sm-delete-btn"
            onClick={() => onDelete(subject)}>✕</button>
        </div>
      </td>
    </tr>
  );
}

// ── Main Component ─────────────────────────────────────────────────────────

export default function SubjectManager() {
  const [subjects,     setSubjects]     = useState([]);
  const [classLevels,  setClassLevels]  = useState([]);
  const [loading,      setLoading]      = useState(true);
  const [error,        setError]        = useState(null);
  const [saving,       setSaving]       = useState(false);
  const [toast,        setToast]        = useState(null);
  const [modal,        setModal]        = useState(null); // "create" | subject-obj (edit)
  const [search,       setSearch]       = useState("");
  const [catFilter,    setCatFilter]    = useState("");

  function showToast(msg, type = "success") {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  }

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [sub, lvl] = await Promise.all([
        api.get("/api/subjects/"),
        api.get("/api/class-levels/"),
      ]);
      setSubjects(sub.data.results || sub.data);
      setClassLevels(lvl.data.results || lvl.data);
    } catch { setError("Failed to load subjects."); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function handleSave(form) {
    setSaving(true);
    try {
      if (modal === "create") {
        await api.post("/api/subjects/", form);
        showToast("Subject created.");
      } else {
        await api.patch(`/api/subjects/${modal.id}/`, form);
        showToast("Subject updated.");
      }
      setModal(null);
      await load();
    } catch (err) {
      showToast(err.response?.data?.code?.[0] || "Failed to save.", "error");
    } finally { setSaving(false); }
  }

  async function handleDelete(subject) {
    if (!window.confirm(`Delete "${subject.name}" (${subject.code})? This cannot be undone.`)) return;
    try {
      await api.delete(`/api/subjects/${subject.id}/`);
      showToast("Subject deleted.");
      await load();
    } catch { showToast("Failed to delete subject.", "error"); }
  }

  const filtered = subjects.filter(s => {
    const q = search.toLowerCase();
    const matchSearch = !q || s.name.toLowerCase().includes(q) || s.code.toLowerCase().includes(q);
    const matchCat    = !catFilter || s.category === catFilter;
    return matchSearch && matchCat;
  });

  const grouped = {
    core:       filtered.filter(s => s.category === "core"),
    elective:   filtered.filter(s => s.category === "elective"),
    vocational: filtered.filter(s => s.category === "vocational"),
  };

  return (
    <div className="sm-root">

      {toast && (
        <div className={`sm-toast sm-toast--${toast.type}`}>
          {toast.type === "success" ? "✓" : "⚠"} {toast.msg}
        </div>
      )}

      {/* ── Header ── */}
      <div className="sm-page-header">
        <div>
          <h1 className="sm-page-title">Subjects</h1>
          <p className="sm-page-sub">
            {subjects.length} subject{subjects.length !== 1 ? "s" : ""} configured
          </p>
        </div>
        <button className="btn btn-primary" onClick={() => setModal("create")}>
          + New Subject
        </button>
      </div>

      {/* ── Filters ── */}
      <div className="sm-filters">
        <div className="sm-search-wrap">
          <span className="sm-search-icon">🔍</span>
          <input type="search" className="sm-search" placeholder="Search name or code…"
            value={search} onChange={e => setSearch(e.target.value)} />
        </div>
        <select className="sm-filter-select" value={catFilter}
          onChange={e => setCatFilter(e.target.value)}>
          <option value="">All Categories</option>
          <option value="core">Core</option>
          <option value="elective">Elective</option>
          <option value="vocational">Vocational</option>
        </select>
        {(search || catFilter) && (
          <button className="btn btn-ghost btn-sm"
            onClick={() => { setSearch(""); setCatFilter(""); }}>Clear ✕</button>
        )}
      </div>

      {/* ── Table ── */}
      {loading ? (
        <div className="sm-loading"><div className="sm-spinner" /></div>
      ) : error ? (
        <div className="sm-error">{error}</div>
      ) : filtered.length === 0 ? (
        <div className="sm-empty">
          <div style={{fontSize:"3rem"}}>📚</div>
          <h3>No subjects found</h3>
          <p>Create your first subject or adjust your filters.</p>
          <button className="btn btn-primary" onClick={() => setModal("create")}>
            + New Subject
          </button>
        </div>
      ) : (
        Object.entries(grouped).map(([cat, items]) => items.length === 0 ? null : (
          <div key={cat} className="sm-category-group">
            <div className="sm-category-group-header">
              <span className="sm-category-dot-lg"
                style={{ background: CATEGORY_COLORS[cat]?.bg }} />
              {cat.charAt(0).toUpperCase() + cat.slice(1)}
              <span className="sm-category-count">{items.length}</span>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Subject</th>
                    <th>Category</th>
                    <th>Score Split</th>
                    <th>Class Levels</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map(s => (
                    <SubjectRow key={s.id} subject={s}
                      onEdit={setModal} onDelete={handleDelete} />
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))
      )}

      {/* ── Modals ── */}
      {modal && (
        <Modal
          title={modal === "create" ? "New Subject" : `Edit: ${modal.name}`}
          onClose={() => setModal(null)}
        >
          <SubjectForm
            initial={modal !== "create" ? modal : null}
            classLevels={classLevels}
            onSave={handleSave}
            onClose={() => setModal(null)}
            saving={saving}
          />
        </Modal>
      )}
    </div>
  );
}