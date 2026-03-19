/**
 * pages/admin/SubjectAssignment.jsx
 *
 * Three-panel page:
 *   LEFT  — Term selector + teacher list
 *   CENTER— Assignment panel for selected teacher (checkboxes per class arm)
 *   RIGHT — Full assignment grid (class arms × subjects heat-map)
 *
 * Route: /admin/subject-assignments
 */

import React, { useCallback, useEffect, useMemo, useState } from "react";
import api from "../../services/api";
import "./SubjectAssignment.css";

// ── Helpers ────────────────────────────────────────────────────────────────

function initials(name = "") {
  return name.split(" ").map(w => w[0]).join("").slice(0,2).toUpperCase();
}

// ── Term Selector ──────────────────────────────────────────────────────────

function TermSelector({ sessions, selectedTerm, onSelectTerm }) {
  return (
    <div className="sa-term-selector">
      <div className="sa-section-heading">Academic Term</div>
      {sessions.length === 0 && (
        <p className="sa-hint">No sessions found. Create one in Calendar Settings.</p>
      )}
      {sessions.map(session => (
        <div key={session.id} className="sa-session-group">
          <div className="sa-session-label">{session.name}</div>
          {(session.terms || []).map(term => (
            <button
              key={term.id}
              className={`sa-term-btn ${selectedTerm?.id === term.id ? "sa-term-btn--active" : ""}`}
              onClick={() => onSelectTerm(term)}
            >
              {term.name_display || term.name}
              {term.is_current && <span className="sa-current-dot" title="Current term" />}
            </button>
          ))}
        </div>
      ))}
    </div>
  );
}

// ── Teacher List ───────────────────────────────────────────────────────────

function TeacherList({ teachers, selectedTeacher, onSelect, assignmentCounts }) {
  const [q, setQ] = useState("");
  const filtered = teachers.filter(t => {
    const name = `${t.full_name} ${t.specialization || ""}`.toLowerCase();
    return !q || name.includes(q.toLowerCase());
  });

  return (
    <div className="sa-teacher-list">
      <div className="sa-section-heading">
        Teachers
        <span className="sa-count-badge">{teachers.length}</span>
      </div>
      <input
        type="search" className="sa-teacher-search"
        placeholder="Search teacher…"
        value={q} onChange={e => setQ(e.target.value)}
      />
      <div className="sa-teacher-scroll">
        {filtered.length === 0 && (
          <p className="sa-hint">No teachers found.</p>
        )}
        {filtered.map(t => {
          const count = assignmentCounts[t.id] || 0;
          return (
            <button
              key={t.id}
              className={`sa-teacher-btn ${selectedTeacher?.id === t.id ? "sa-teacher-btn--active" : ""}`}
              onClick={() => onSelect(t)}
            >
              <div className="sa-teacher-avatar">{initials(t.full_name)}</div>
              <div className="sa-teacher-info">
                <div className="sa-teacher-name">{t.full_name}</div>
                <div className="sa-teacher-meta">
                  {t.specialization || t.staff_id}
                </div>
              </div>
              {count > 0 && (
                <span className="sa-assign-count">{count}</span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ── Assignment Panel ───────────────────────────────────────────────────────

function AssignmentPanel({ teacher, term, session, subjects, classArms, existing, onSave, saving }) {
  // State: map of "arm_id:subject_id" → boolean
  const [selected, setSelected] = useState(() => {
    const map = {};
    (existing || []).forEach(a => {
      map[`${a.class_arm}:${a.subject}`] = true;
    });
    return map;
  });

  // Re-sync when teacher/term changes
  useEffect(() => {
    const map = {};
    (existing || []).forEach(a => {
      map[`${a.class_arm}:${a.subject}`] = true;
    });
    setSelected(map);
  }, [existing]);

  function toggle(armId, subjectId) {
    const key = `${armId}:${subjectId}`;
    setSelected(prev => ({ ...prev, [key]: !prev[key] }));
  }

  function handleSave() {
    const assignments = Object.entries(selected)
      .filter(([, v]) => v)
      .map(([key]) => {
        const [class_arm_id, subject_id] = key.split(":").map(Number);
        return { class_arm_id, subject_id };
      });
    onSave({ session_id: session.id, term_id: term.id, assignments });
  }

  const totalSelected = Object.values(selected).filter(Boolean).length;

  return (
    <div className="sa-assign-panel">
      <div className="sa-panel-header">
        <div>
          <div className="sa-panel-title">{teacher.full_name}</div>
          <div className="sa-panel-meta">
            {teacher.staff_id} · {teacher.specialization || "No specialization"}
          </div>
        </div>
        <button className="btn btn-primary btn-sm" onClick={handleSave} disabled={saving}>
          {saving ? "Saving…" : `Save ${totalSelected} Assignment${totalSelected !== 1 ? "s" : ""}`}
        </button>
      </div>

      <div className="sa-assign-body">
        {classArms.length === 0 && (
          <p className="sa-hint">No class arms configured.</p>
        )}
        {classArms.map(arm => (
          <div key={arm.id} className="sa-arm-section">
            <div className="sa-arm-heading">{arm.full_name}</div>
            <div className="sa-subject-checks">
              {subjects.map(subj => {
                const key     = `${arm.id}:${subj.id}`;
                const checked = Boolean(selected[key]);
                return (
                  <label key={subj.id}
                    className={`sa-subj-chip ${checked ? "sa-subj-chip--on" : ""}`}>
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggle(arm.id, subj.id)}
                      className="sa-hidden-cb"
                    />
                    <code className="sa-subj-code">{subj.code}</code>
                    {subj.name}
                  </label>
                );
              })}
              {subjects.length === 0 && (
                <span className="sa-hint">No subjects. Create them in Subject Manager.</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Assignment Grid ────────────────────────────────────────────────────────

function AssignmentGrid({ grid, arms, subjects, loading }) {
  const COLORS = [
    "var(--color-primary)",
    "var(--color-secondary)",
    "var(--color-accent)",
    "#16a34a","#7c3aed","#db2777","#0891b2",
  ];

  // Map teacher_id → colour for visual consistency
  const teacherColors = useMemo(() => {
    const seen = {}; let idx = 0;
    Object.values(grid || {}).forEach(row => {
      Object.values(row).forEach(cell => {
        if (cell && !(cell.teacher_id in seen)) {
          seen[cell.teacher_id] = COLORS[idx % COLORS.length];
          idx++;
        }
      });
    });
    return seen;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [grid]);

  if (loading) {
    return <div className="sa-grid-loading"><div className="sa-spinner" /></div>;
  }

  if (!grid || arms.length === 0 || subjects.length === 0) {
    return (
      <div className="sa-grid-empty">
        <div style={{fontSize:"2.5rem"}}>📊</div>
        <p>Select a term to see the assignment grid.</p>
      </div>
    );
  }

  return (
    <div className="sa-grid-wrap">
      <div className="sa-grid-scroll">
        <table className="sa-grid">
          <thead>
            <tr>
              <th className="sa-grid-corner">Class \ Subject</th>
              {subjects.map(s => (
                <th key={s.id} className="sa-grid-subj-header" title={s.name}>
                  <div className="sa-grid-subj-name">{s.code}</div>
                  <div className="sa-grid-subj-full">{s.name}</div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {arms.map(arm => (
              <tr key={arm.id}>
                <td className="sa-grid-arm-cell">{arm.full_name}</td>
                {subjects.map(subj => {
                  const cell = grid[String(arm.id)]?.[String(subj.id)];
                  const bg   = cell ? teacherColors[cell.teacher_id] : null;
                  return (
                    <td key={subj.id}
                      className={`sa-grid-cell ${cell ? "sa-grid-cell--filled" : "sa-grid-cell--empty"}`}
                      title={cell ? `${cell.teacher_name} (${cell.staff_id})` : "Unassigned"}
                      style={cell ? {
                        background: `color-mix(in srgb, ${bg} 15%, transparent)`,
                        borderLeft:  `3px solid ${bg}`,
                      } : {}}>
                      {cell && (
                        <span className="sa-grid-teacher"
                          style={{ color: bg }}>
                          {cell.teacher_name.split(" ").map(w => w[0]).join("")}
                        </span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Legend */}
      <div className="sa-grid-legend">
        {Object.entries(teacherColors).map(([tid, color]) => {
          const name = Object.values(grid)
            .flatMap(r => Object.values(r))
            .find(c => c?.teacher_id === Number(tid))?.teacher_name || `Teacher ${tid}`;
          return (
            <div key={tid} className="sa-legend-item">
              <span className="sa-legend-dot" style={{ background: color }} />
              <span className="sa-legend-name">{name}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Main Component ─────────────────────────────────────────────────────────

export default function SubjectAssignmentPage() {
  const [sessions,     setSessions]     = useState([]);
  const [teachers,     setTeachers]     = useState([]);
  const [subjects,     setSubjects]     = useState([]);
  const [classArms,    setClassArms]    = useState([]);
  const [selectedTerm, setSelectedTerm] = useState(null);
  const [selectedTeacher, setSelectedTeacher] = useState(null);
  const [existing,     setExisting]     = useState([]);  // teacher's current assignments
  const [grid,         setGrid]         = useState(null);
  const [gridArms,     setGridArms]     = useState([]);
  const [gridSubjects, setGridSubjects] = useState([]);
  const [gridLoading,  setGridLoading]  = useState(false);
  const [saving,       setSaving]       = useState(false);
  const [toast,        setToast]        = useState(null);

  // Assignment counts per teacher (for badges in list)
  const [assignmentCounts, setAssignmentCounts] = useState({});

  function showToast(msg, type = "success") {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  }

  // Load reference data once
  useEffect(() => {
    Promise.all([
      api.get("/api/sessions/"),
      api.get("/api/staff/?role=teacher&page_size=200"),
      api.get("/api/subjects/"),
      api.get("/api/class-arms/"),
    ]).then(([sess, teach, sub, arms]) => {
      setSessions(sess.data.results || sess.data);
      setTeachers(teach.data.results || teach.data);
      setSubjects(sub.data.results  || sub.data);
      setClassArms(arms.data.results || arms.data);
    });
  }, []);

  // Load grid when term changes
  const loadGrid = useCallback(async (termId) => {
    setGridLoading(true);
    try {
      const { data } = await api.get(`/api/subject-assignments/grid/?term=${termId}`);
      setGrid(data.grid);
      setGridArms(data.arms);
      setGridSubjects(data.subjects);

      // Compute assignment counts per teacher
      const counts = {};
      Object.values(data.grid).forEach(row => {
        Object.values(row).forEach(cell => {
          if (cell) counts[cell.teacher_id] = (counts[cell.teacher_id] || 0) + 1;
        });
      });
      setAssignmentCounts(counts);
    } catch { setGrid(null); }
    finally { setGridLoading(false); }
  }, []);

  useEffect(() => {
    if (selectedTerm) loadGrid(selectedTerm.id);
    else { setGrid(null); setAssignmentCounts({}); }
  }, [selectedTerm, loadGrid]);

  // Load existing assignments for selected teacher+term
  useEffect(() => {
    if (!selectedTeacher || !selectedTerm) { setExisting([]); return; }
    api.get(`/api/subject-assignments/?teacher=${selectedTeacher.id}&term=${selectedTerm.id}`)
      .then(({ data }) => setExisting(data.results || data))
      .catch(() => setExisting([]));
  }, [selectedTeacher, selectedTerm]);

  async function handleSave(payload) {
    if (!selectedTeacher || !selectedTerm) return;
    setSaving(true);
    try {
      await api.post(`/api/staff/${selectedTeacher.id}/assign-subjects/`, payload);
      showToast("Assignments saved.");
      await loadGrid(selectedTerm.id);
      // Reload this teacher's assignments
      const { data } = await api.get(
        `/api/subject-assignments/?teacher=${selectedTeacher.id}&term=${selectedTerm.id}`
      );
      setExisting(data.results || data);
    } catch (err) {
      showToast(err.response?.data?.error || "Failed to save assignments.", "error");
    } finally { setSaving(false); }
  }

  // Find the session for the selected term
  const selectedSession = useMemo(() => {
    if (!selectedTerm) return null;
    return sessions.find(s => (s.terms || []).some(t => t.id === selectedTerm.id));
  }, [selectedTerm, sessions]);

  return (
    <div className="sa-root">

      {toast && (
        <div className={`sa-toast sa-toast--${toast.type}`}>
          {toast.type === "success" ? "✓" : "⚠"} {toast.msg}
        </div>
      )}

      {/* ── Page header ── */}
      <div className="sa-page-header">
        <h1 className="sa-page-title">Subject Assignments</h1>
        <p className="sa-page-sub">
          Assign teachers to subjects per class arm for each term.
        </p>
      </div>

      <div className="sa-layout">

        {/* ── LEFT: Term + Teacher ── */}
        <div className="sa-left-col">
          <TermSelector
            sessions={sessions}
            selectedTerm={selectedTerm}
            onSelectTerm={t => { setSelectedTerm(t); setSelectedTeacher(null); }}
          />
          {selectedTerm && (
            <TeacherList
              teachers={teachers}
              selectedTeacher={selectedTeacher}
              onSelect={setSelectedTeacher}
              assignmentCounts={assignmentCounts}
            />
          )}
          {!selectedTerm && (
            <p className="sa-hint sa-hint--center">
              ← Select a term to begin.
            </p>
          )}
        </div>

        {/* ── CENTER: Assignment Panel ── */}
        <div className="sa-center-col">
          {!selectedTerm ? (
            <div className="sa-placeholder">
              <div className="sa-placeholder-icon">📅</div>
              <h3>Select a Term</h3>
              <p>Choose an academic term to manage subject assignments.</p>
            </div>
          ) : !selectedTeacher ? (
            <div className="sa-placeholder">
              <div className="sa-placeholder-icon">👩‍🏫</div>
              <h3>Select a Teacher</h3>
              <p>Choose a teacher from the list to assign subjects.</p>
            </div>
          ) : (
            <AssignmentPanel
              teacher={selectedTeacher}
              term={selectedTerm}
              session={selectedSession}
              subjects={subjects}
              classArms={classArms}
              existing={existing}
              onSave={handleSave}
              saving={saving}
            />
          )}
        </div>

        {/* ── RIGHT: Grid ── */}
        <div className="sa-right-col">
          <div className="sa-section-heading">
            Assignment Grid
            {selectedTerm && (
              <span className="sa-grid-term-label">
                {selectedTerm.name_display || selectedTerm.name}
              </span>
            )}
          </div>
          <AssignmentGrid
            grid={grid}
            arms={gridArms}
            subjects={gridSubjects}
            loading={gridLoading}
          />
        </div>

      </div>
    </div>
  );
}