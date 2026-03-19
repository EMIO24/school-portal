/**
 * pages/admin/StaffProfilePage.jsx
 * Route: /admin/staff/:id
 */

import React, { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import api from "../../services/api";
import "./StaffProfilePage.css";

const EMPLOYMENT_COLORS = {
  active:    "badge-success",
  on_leave:  "badge-warning",
  suspended: "badge-danger",
  terminated:"badge-danger",
  resigned:  "badge",
};

const ROLE_COLORS = { teacher: "badge-info", school_admin: "badge-primary" };

function InfoRow({ label, value }) {
  return (
    <div className="spp-info-row">
      <span className="spp-info-label">{label}</span>
      <span className="spp-info-value">{value || <span className="spp-empty">—</span>}</span>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <section className="spp-section">
      <h3 className="spp-section-title">{title}</h3>
      <div className="spp-section-body">{children}</div>
    </section>
  );
}

export default function StaffProfilePage() {
  const { id }   = useParams();
  const navigate = useNavigate();
  const [staff,   setStaff]   = useState(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);

  useEffect(() => {
    api.get(`/api/staff/${id}/`)
      .then(({ data }) => setStaff(data))
      .catch(() => setError("Failed to load staff member."))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <div className="spp-loading"><div className="spp-spinner" /></div>;
  if (error || !staff) return <div className="spp-root"><div className="spp-error">{error || "Not found."}</div></div>;

  const initials = `${staff.first_name?.[0]||""}${staff.last_name?.[0]||""}`.toUpperCase();

  const fmt = dateStr => dateStr
    ? new Date(dateStr).toLocaleDateString("en-NG", { day:"numeric", month:"long", year:"numeric" })
    : null;

  return (
    <div className="spp-root">
      {/* ── Nav ── */}
      <div className="spp-nav">
        <button className="btn btn-ghost btn-sm" onClick={() => navigate(-1)}>← Back to Staff</button>
        <Link to={`/admin/staff/${id}/edit`} className="btn btn-secondary btn-sm">Edit Profile</Link>
      </div>

      {/* ── Hero ── */}
      <div className="spp-hero">
        <div className="spp-avatar-wrap">
          {staff.profile_photo
            ? <img className="spp-avatar" src={staff.profile_photo} alt={staff.full_name} />
            : <div className="spp-avatar spp-avatar--initials">{initials}</div>
          }
        </div>
        <div className="spp-hero-info">
          <h1 className="spp-name">{staff.full_name}</h1>
          <div className="spp-hero-meta">
            <code className="spp-id-badge">{staff.staff_id}</code>
            <span className={`badge ${ROLE_COLORS[staff.role] || ""}`}>
              {staff.role?.replace("_", " ")}
            </span>
            <span className={`badge ${EMPLOYMENT_COLORS[staff.employment_status] || ""}`}>
              {staff.employment_status?.replace("_", " ")}
            </span>
          </div>
          <p className="spp-email">{staff.email}</p>
          {staff.specialization && (
            <p className="spp-specialization">📚 {staff.specialization}</p>
          )}
        </div>
      </div>

      {/* ── Sections ── */}
      <div className="spp-sections">
        <Section title="Personal Details">
          <InfoRow label="Full Name"       value={staff.full_name} />
          <InfoRow label="Email"           value={staff.email} />
          <InfoRow label="Phone"           value={staff.phone} />
          <InfoRow label="Date of Birth"   value={fmt(staff.dob)} />
          <InfoRow label="Gender"          value={staff.gender
            ? staff.gender.charAt(0).toUpperCase() + staff.gender.slice(1) : null} />
          <InfoRow label="State of Origin" value={staff.state_of_origin} />
          <InfoRow label="Religion"        value={staff.religion} />
          <InfoRow label="Address"         value={staff.address} />
        </Section>

        <Section title="Employment">
          <InfoRow label="Staff ID"        value={staff.staff_id} />
          <InfoRow label="Role"            value={staff.role?.replace("_", " ")} />
          <InfoRow label="Qualification"   value={staff.qualification?.toUpperCase()} />
          <InfoRow label="Specialization"  value={staff.specialization} />
          <InfoRow label="Date Employed"   value={fmt(staff.date_employed)} />
          <InfoRow label="Status"          value={staff.employment_status?.replace("_", " ")} />
        </Section>

        {/* ── Teaching assignments ── */}
        {staff.role === "teacher" && (
          <>
            <section className="spp-section spp-section--wide">
              <h3 className="spp-section-title">Subjects Taught</h3>
              <div className="spp-section-body">
                {(staff.subjects_taught_detail || []).length === 0 ? (
                  <p className="spp-no-assign">No subjects assigned yet.</p>
                ) : (
                  <div className="spp-chip-list">
                    {staff.subjects_taught_detail.map(s => (
                      <span key={s.id} className="spp-chip">
                        <code className="spp-chip-code">{s.code}</code> {s.name}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </section>

            <section className="spp-section spp-section--wide">
              <h3 className="spp-section-title">Assigned Classes</h3>
              <div className="spp-section-body">
                {(staff.assigned_classes_detail || []).length === 0 ? (
                  <p className="spp-no-assign">No classes assigned yet.</p>
                ) : (
                  <div className="spp-chip-list">
                    {staff.assigned_classes_detail.map(a => (
                      <span key={a.id} className="spp-chip spp-chip--class">{a.full_name}</span>
                    ))}
                  </div>
                )}
              </div>
            </section>
          </>
        )}
      </div>
    </div>
  );
}