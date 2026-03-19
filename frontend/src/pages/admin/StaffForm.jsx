/**
 * pages/admin/StaffForm.jsx
 *
 * Create or edit a staff member (teacher or school_admin).
 * Includes multi-select pickers for subjects taught and assigned classes.
 * Route: /admin/staff/new | /admin/staff/:id/edit
 */

import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import api from "../../services/api";
import "./StaffForm.css";

const QUALIFICATIONS = [
  { value: "ssce", label: "SSCE / WAEC" },
  { value: "nd",   label: "ND / NCE" },
  { value: "hnd",  label: "HND" },
  { value: "bsc",  label: "B.Sc / B.Ed / BA" },
  { value: "pgd",  label: "PGD" },
  { value: "msc",  label: "M.Sc / M.Ed / MA" },
  { value: "phd",  label: "Ph.D" },
  { value: "other",label: "Other" },
];

function Field({ label, error, children, hint }) {
  return (
    <div className="stf-field">
      <label>{label}{hint && <span className="stf-hint"> — {hint}</span>}</label>
      {children}
      {error && <span className="field-error">{error}</span>}
    </div>
  );
}

/** Checkbox multi-picker for subjects or class arms */
function MultiPicker({ items, selected, onToggle, labelKey = "name", badgeKey }) {
  return (
    <div className="stf-multi-picker">
      {items.length === 0 && (
        <p className="stf-picker-empty">No items found. Create them first.</p>
      )}
      {items.map(item => {
        const isSelected = selected.includes(item.id);
        return (
          <label key={item.id} className={`stf-picker-item ${isSelected ? "stf-picker-item--on" : ""}`}>
            <input
              type="checkbox"
              checked={isSelected}
              onChange={() => onToggle(item.id)}
              className="stf-picker-checkbox"
            />
            <span className="stf-picker-label">
              {badgeKey && <code className="stf-picker-badge">{item[badgeKey]}</code>}
              {item[labelKey]}
            </span>
          </label>
        );
      })}
    </div>
  );
}

export default function StaffForm() {
  const { id }   = useParams();
  const navigate = useNavigate();
  const isEdit   = Boolean(id);

  const [subjects,    setSubjects]    = useState([]);
  const [classArms,   setClassArms]   = useState([]);
  const [loading,     setLoading]     = useState(isEdit);
  const [saving,      setSaving]      = useState(false);
  const [errors,      setErrors]      = useState({});
  const [apiError,    setApiError]    = useState(null);
  const [toast,       setToast]       = useState(null);

  const [form, setForm] = useState({
    new_email:        "",
    new_first_name:   "",
    new_last_name:    "",
    new_role:         "teacher",
    dob:              "",
    gender:           "",
    phone:            "",
    address:          "",
    state_of_origin:  "",
    religion:         "",
    qualification:    "",
    specialization:   "",
    date_employed:    "",
    employment_status:"active",
    subjects_taught:  [],   // array of IDs
    assigned_classes: [],   // array of IDs
  });

  function set(k, v) { setForm(f => ({ ...f, [k]: v })); }

  function toggleSelection(key, id) {
    setForm(f => {
      const current = f[key];
      return {
        ...f,
        [key]: current.includes(id)
          ? current.filter(x => x !== id)
          : [...current, id],
      };
    });
  }

  function showToast(msg, type = "success") {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  }

  // Load reference data
  useEffect(() => {
    Promise.all([
      api.get("/api/subjects/"),
      api.get("/api/class-arms/"),
    ]).then(([sub, arms]) => {
      setSubjects(sub.data.results   || sub.data);
      setClassArms(arms.data.results || arms.data);
    });
  }, []);

  // Load staff for edit
  useEffect(() => {
    if (!isEdit) return;
    api.get(`/api/staff/${id}/`).then(({ data }) => {
      setForm({
        new_email:        data.email         || "",
        new_first_name:   data.first_name    || "",
        new_last_name:    data.last_name     || "",
        new_role:         data.role          || "teacher",
        dob:              data.dob           || "",
        gender:           data.gender        || "",
        phone:            data.phone         || "",
        address:          data.address       || "",
        state_of_origin:  data.state_of_origin || "",
        religion:         data.religion      || "",
        qualification:    data.qualification || "",
        specialization:   data.specialization || "",
        date_employed:    data.date_employed || "",
        employment_status:data.employment_status || "active",
        subjects_taught:  (data.subjects_taught  || []).map(s => s.id || s),
        assigned_classes: (data.assigned_classes || []).map(a => a.id || a),
      });
    }).catch(() => setApiError("Failed to load staff member."))
      .finally(() => setLoading(false));
  }, [id, isEdit]);

  function validate() {
    const e = {};
    if (!isEdit) {
      if (!form.new_email.trim())      e.new_email      = "Email is required.";
      if (!form.new_first_name.trim()) e.new_first_name = "First name is required.";
      if (!form.new_last_name.trim())  e.new_last_name  = "Last name is required.";
    }
    return e;
  }

  async function handleSubmit(e) {
    e.preventDefault();
    const errs = validate();
    if (Object.keys(errs).length) { setErrors(errs); return; }
    setErrors({});
    setApiError(null);
    setSaving(true);

    try {
      let staffId = id;
      if (isEdit) {
        await api.patch(`/api/staff/${id}/`, form);
        // Sync M2M assignments via dedicated endpoints
        await api.post(`/api/staff/${id}/assign-subjects/`, { subjects: form.subjects_taught });
        await api.post(`/api/staff/${id}/assign-classes/`, { classes: form.assigned_classes });
        showToast("Staff member updated.");
        setTimeout(() => navigate(`/admin/staff/${id}`), 1200);
      } else {
        const { data } = await api.post("/api/staff/", form);
        staffId = data.id;
        navigate(`/admin/staff/${staffId}`, { replace: true });
      }
    } catch (err) {
      const data = err.response?.data;
      if (data && typeof data === "object") {
        setErrors(data);
        setApiError("Please fix the errors below.");
      } else {
        setApiError("Failed to save staff member.");
      }
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div className="stf-loading"><div className="stf-spinner" /></div>;

  return (
    <div className="stf-root">
      {toast && (
        <div className={`stf-toast stf-toast--${toast.type}`}>{toast.msg}</div>
      )}

      <div className="stf-page-header">
        <button className="btn btn-ghost btn-sm" onClick={() => navigate(-1)}>← Back</button>
        <h1 className="stf-page-title">
          {isEdit ? "Edit Staff Member" : "Add Staff Member"}
        </h1>
      </div>

      {apiError && <div className="stf-api-error" role="alert">{apiError}</div>}

      <form className="stf-form" onSubmit={handleSubmit} noValidate>

        {/* ── Account Details ── */}
        {!isEdit && (
          <section className="stf-section">
            <h2 className="stf-section-title">Account Details</h2>
            <p className="stf-section-sub">Default password will be set to the staff ID.</p>
            <div className="stf-grid stf-grid--3">
              <Field label="First Name" error={errors.new_first_name}>
                <input type="text" value={form.new_first_name}
                  onChange={e => set("new_first_name", e.target.value)}
                  className={errors.new_first_name ? "input--error" : ""}
                  placeholder="Ngozi" />
              </Field>
              <Field label="Last Name" error={errors.new_last_name}>
                <input type="text" value={form.new_last_name}
                  onChange={e => set("new_last_name", e.target.value)}
                  className={errors.new_last_name ? "input--error" : ""}
                  placeholder="Adeyemi" />
              </Field>
              <Field label="Email" error={errors.new_email}>
                <input type="email" value={form.new_email}
                  onChange={e => set("new_email", e.target.value)}
                  className={errors.new_email ? "input--error" : ""}
                  placeholder="ngozi@school.edu.ng" />
              </Field>
              <Field label="Role" error={errors.new_role}>
                <select value={form.new_role} onChange={e => set("new_role", e.target.value)}>
                  <option value="teacher">Teacher</option>
                  <option value="school_admin">School Admin</option>
                </select>
              </Field>
            </div>
          </section>
        )}

        {/* ── Personal Information ── */}
        <section className="stf-section">
          <h2 className="stf-section-title">Personal Information</h2>
          <div className="stf-grid stf-grid--3">
            <Field label="Date of Birth"><input type="date" value={form.dob} onChange={e => set("dob", e.target.value)} /></Field>
            <Field label="Gender">
              <select value={form.gender} onChange={e => set("gender", e.target.value)}>
                <option value="">Select…</option>
                <option value="male">Male</option>
                <option value="female">Female</option>
              </select>
            </Field>
            <Field label="Phone"><input type="tel" value={form.phone} onChange={e => set("phone", e.target.value)} placeholder="08012345678" /></Field>
            <Field label="State of Origin"><input type="text" value={form.state_of_origin} onChange={e => set("state_of_origin", e.target.value)} /></Field>
            <Field label="Religion"><input type="text" value={form.religion} onChange={e => set("religion", e.target.value)} /></Field>
          </div>
          <div className="stf-grid stf-grid--1" style={{marginTop:"var(--space-3)"}}>
            <Field label="Address"><textarea value={form.address} onChange={e => set("address", e.target.value)} rows={2} placeholder="Home address" /></Field>
          </div>
        </section>

        {/* ── Professional Details ── */}
        <section className="stf-section">
          <h2 className="stf-section-title">Professional Details</h2>
          <div className="stf-grid stf-grid--3">
            <Field label="Qualification">
              <select value={form.qualification} onChange={e => set("qualification", e.target.value)}>
                <option value="">Select…</option>
                {QUALIFICATIONS.map(q => <option key={q.value} value={q.value}>{q.label}</option>)}
              </select>
            </Field>
            <Field label="Specialization" hint="Subject area / department">
              <input type="text" value={form.specialization} onChange={e => set("specialization", e.target.value)} placeholder="e.g. Mathematics" />
            </Field>
            <Field label="Date Employed"><input type="date" value={form.date_employed} onChange={e => set("date_employed", e.target.value)} /></Field>
            {isEdit && (
              <Field label="Employment Status">
                <select value={form.employment_status} onChange={e => set("employment_status", e.target.value)}>
                  <option value="active">Active</option>
                  <option value="on_leave">On Leave</option>
                  <option value="suspended">Suspended</option>
                  <option value="terminated">Terminated</option>
                  <option value="resigned">Resigned</option>
                </select>
              </Field>
            )}
          </div>
        </section>

        {/* ── Teaching Assignments (teachers only) ── */}
        {(form.new_role === "teacher" || isEdit) && (
          <section className="stf-section">
            <h2 className="stf-section-title">Teaching Assignments</h2>
            <p className="stf-section-sub">Select the subjects and classes this teacher is responsible for.</p>
            <div className="stf-assignments-grid">
              <div>
                <h4 className="stf-picker-heading">Subjects</h4>
                <MultiPicker
                  items={subjects}
                  selected={form.subjects_taught}
                  onToggle={id => toggleSelection("subjects_taught", id)}
                  labelKey="name"
                  badgeKey="code"
                />
              </div>
              <div>
                <h4 className="stf-picker-heading">Classes</h4>
                <MultiPicker
                  items={classArms}
                  selected={form.assigned_classes}
                  onToggle={id => toggleSelection("assigned_classes", id)}
                  labelKey="full_name"
                />
              </div>
            </div>
          </section>
        )}

        <div className="stf-form-actions">
          <button type="button" className="btn btn-ghost" onClick={() => navigate(-1)}>Cancel</button>
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving && <span className="stf-btn-spinner" />}
            {saving ? "Saving…" : isEdit ? "Save Changes" : "Add Staff Member"}
          </button>
        </div>
      </form>
    </div>
  );
}