/**
 * pages/admin/StudentProfile.jsx
 *
 * Full student profile card with:
 *  - Cloudinary photo upload (direct unsigned upload)
 *  - Class assignment panel
 *  - Personal, academic, guardian detail sections
 *
 * Route: /admin/students/:id
 */

import React, { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import api from "../../services/api";
import "./StudentProfile.css";

const STATUS_COLORS = {
  active:    "badge-success",
  graduated: "badge-info",
  withdrawn: "badge-warning",
  suspended: "badge-danger",
};

// ── Cloudinary unsigned upload ─────────────────────────────────────────────
// Set these in your .env:
//   REACT_APP_CLOUDINARY_CLOUD_NAME=your_cloud
//   REACT_APP_CLOUDINARY_UPLOAD_PRESET=your_unsigned_preset

const CLOUD_NAME    = process.env.REACT_APP_CLOUDINARY_CLOUD_NAME || "";
const UPLOAD_PRESET = process.env.REACT_APP_CLOUDINARY_UPLOAD_PRESET || "";

async function uploadToCloudinary(file) {
  if (!CLOUD_NAME || !UPLOAD_PRESET) {
    throw new Error("Cloudinary env vars not configured.");
  }
  const fd = new FormData();
  fd.append("file",         file);
  fd.append("upload_preset", UPLOAD_PRESET);
  fd.append("folder",       "student_photos");

  const res  = await fetch(
    `https://api.cloudinary.com/v1_1/${CLOUD_NAME}/image/upload`,
    { method: "POST", body: fd }
  );
  if (!res.ok) throw new Error("Cloudinary upload failed.");
  const data = await res.json();
  return data.secure_url;
}

// ── Sub-components ─────────────────────────────────────────────────────────

function InfoRow({ label, value }) {
  return (
    <div className="sp-info-row">
      <span className="sp-info-label">{label}</span>
      <span className="sp-info-value">{value || <span className="sp-empty">—</span>}</span>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <section className="sp-section">
      <h3 className="sp-section-title">{title}</h3>
      <div className="sp-section-body">{children}</div>
    </section>
  );
}

// ── Photo Upload ───────────────────────────────────────────────────────────

function PhotoUpload({ currentUrl, name, onUpload }) {
  const inputRef     = useRef();
  const [busy, setBusy] = useState(false);
  const [err,  setErr]  = useState(null);
  const [preview, setPreview] = useState(null);

  const initials = name
    ? name.split(" ").map(w => w[0]).join("").slice(0,2).toUpperCase()
    : "?";

  async function handleChange(e) {
    const file = e.target.files[0];
    if (!file) return;

    // Client preview immediately
    const objUrl = URL.createObjectURL(file);
    setPreview(objUrl);
    setErr(null);
    setBusy(true);

    try {
      const url = await uploadToCloudinary(file);
      // Persist to backend
      await api.patch(`/api/auth/me/`, { profile_photo: url });
      onUpload(url);
      URL.revokeObjectURL(objUrl);
      setPreview(null);
    } catch (e) {
      setErr(e.message || "Upload failed.");
      setPreview(null);
    } finally {
      setBusy(false);
    }
  }

  const displayUrl = preview || currentUrl;

  return (
    <div className="sp-photo-wrap">
      <div className="sp-avatar-wrap" onClick={() => !busy && inputRef.current?.click()}
        title="Click to change photo" style={{ cursor: busy ? "wait" : "pointer" }}>
        {displayUrl
          ? <img className="sp-avatar" src={displayUrl} alt={name} />
          : <div className="sp-avatar sp-avatar--initials">{initials}</div>
        }
        {busy && <div className="sp-avatar-overlay"><div className="sp-upload-spinner" /></div>}
        {!busy && (
          <div className="sp-avatar-edit" aria-hidden="true">📷</div>
        )}
      </div>
      <input ref={inputRef} type="file" accept="image/*"
        className="sp-hidden-input" onChange={handleChange} />
      {err && <p className="sp-photo-err">{err}</p>}
      {!CLOUD_NAME && (
        <p className="sp-photo-warn">Photo upload: set REACT_APP_CLOUDINARY_* env vars.</p>
      )}
    </div>
  );
}

// ── Main Component ─────────────────────────────────────────────────────────

export default function StudentProfilePage() {
  const { id }   = useParams();
  const navigate = useNavigate();

  const [student,   setStudent]   = useState(null);
  const [loading,   setLoading]   = useState(true);
  const [error,     setError]     = useState(null);
  const [classArms, setClassArms] = useState([]);
  const [assigning, setAssigning] = useState(false);
  const [assignVal, setAssignVal] = useState("");
  const [toast,     setToast]     = useState(null);

  function showToast(msg, type = "success") {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  }

  useEffect(() => {
    Promise.all([
      api.get(`/api/students/${id}/`),
      api.get("/api/class-arms/"),
    ]).then(([s, arms]) => {
      setStudent(s.data);
      setAssignVal(s.data.current_class || "");
      setClassArms(arms.data.results || arms.data);
    }).catch(() => setError("Failed to load student."))
      .finally(() => setLoading(false));
  }, [id]);

  async function handleAssignClass() {
    if (!assignVal) return;
    setAssigning(true);
    try {
      const { data } = await api.post(`/api/students/${id}/assign-class/`, {
        class_arm: assignVal,
      });
      setStudent(data);
      showToast("Class assigned successfully.");
    } catch {
      showToast("Failed to assign class.", "error");
    } finally {
      setAssigning(false);
    }
  }

  function handlePhotoUpload(url) {
    setStudent(prev => ({ ...prev, profile_photo: url }));
    showToast("Photo updated.");
  }

  // ── Renders ──────────────────────────────────────────────────────────────

  if (loading) {
    return <div className="sp-loading"><div className="sp-spinner" /></div>;
  }

  if (error || !student) {
    return (
      <div className="sp-root">
        <div className="sp-error">{error || "Student not found."}</div>
      </div>
    );
  }

  const fmt = d => d
    ? new Date(d).toLocaleDateString("en-NG", { day:"numeric", month:"long", year:"numeric" })
    : null;

  return (
    <div className="sp-root">

      {/* ── Toast ── */}
      {toast && (
        <div className={`sp-toast sp-toast--${toast.type}`} role="status">
          {toast.type === "success" ? "✓" : "⚠"} {toast.msg}
        </div>
      )}

      {/* ── Nav ── */}
      <div className="sp-nav">
        <button className="btn btn-ghost btn-sm" onClick={() => navigate(-1)}>
          ← Back to Students
        </button>
        <Link to={`/admin/students/${id}/edit`} className="btn btn-secondary btn-sm">
          Edit Profile
        </Link>
      </div>

      {/* ── Hero card ── */}
      <div className="sp-hero">

        {/* Photo upload */}
        <PhotoUpload
          currentUrl={student.profile_photo}
          name={student.full_name}
          onUpload={handlePhotoUpload}
        />

        <div className="sp-hero-info">
          <h1 className="sp-student-name">{student.full_name}</h1>
          <div className="sp-hero-meta">
            <code className="sp-adm-badge">{student.admission_number}</code>
            <span className={`badge ${STATUS_COLORS[student.status] || ""}`}>
              {student.status}
            </span>
            {student.current_class_name && (
              <span className="sp-class-badge">📚 {student.current_class_name}</span>
            )}
          </div>
          <p className="sp-email">{student.email}</p>
        </div>

        {/* Class assignment */}
        <div className="sp-assign-class">
          <label className="sp-assign-label">Assign to Class</label>
          <div className="sp-assign-row">
            <select className="sp-assign-select" value={assignVal}
              onChange={e => setAssignVal(e.target.value)}>
              <option value="">Not Assigned</option>
              {classArms.map(a => (
                <option key={a.id} value={a.id}>{a.full_name}</option>
              ))}
            </select>
            <button className="btn btn-accent btn-sm"
              onClick={handleAssignClass}
              disabled={assigning || !assignVal}>
              {assigning ? "…" : "Assign"}
            </button>
          </div>
        </div>
      </div>

      {/* ── Detail sections ── */}
      <div className="sp-sections">
        <Section title="Personal Details">
          <InfoRow label="Full Name"       value={student.full_name} />
          <InfoRow label="Email"           value={student.email} />
          <InfoRow label="Date of Birth"   value={fmt(student.dob)} />
          <InfoRow label="Gender"          value={student.gender
            ? student.gender.charAt(0).toUpperCase() + student.gender.slice(1) : null} />
          <InfoRow label="State of Origin" value={student.state_of_origin} />
          <InfoRow label="Religion"        value={student.religion} />
        </Section>

        <Section title="Academic">
          <InfoRow label="Admission No."  value={student.admission_number} />
          <InfoRow label="Admission Date" value={fmt(student.admission_date)} />
          <InfoRow label="Current Class"  value={student.current_class_name} />
          <InfoRow label="Status"         value={
            student.status.charAt(0).toUpperCase() + student.status.slice(1)
          } />
        </Section>

        <Section title="Guardian / Parent">
          <InfoRow label="Name"         value={student.guardian_name} />
          <InfoRow label="Phone"        value={student.guardian_phone} />
          <InfoRow label="Email"        value={student.guardian_email} />
          <InfoRow label="Relationship" value={student.guardian_relationship
            ? student.guardian_relationship.charAt(0).toUpperCase() +
              student.guardian_relationship.slice(1)
            : null} />
        </Section>
      </div>

    </div>
  );
}