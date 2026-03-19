/**
 * pages/admin/Staff.jsx
 *
 * Staff roster — teachers and school admins.
 * Filter by role, employment status, search by name/email/specialization.
 */

import React, { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../../services/api";
import "./Staff.css";

const STATUS_COLORS = {
  active:     "badge-success",
  on_leave:   "badge-warning",
  suspended:  "badge-danger",
  terminated: "badge-danger",
  resigned:   "badge",
};

const ROLE_LABELS = { teacher: "Teacher", school_admin: "Admin" };
const ROLE_COLORS = { teacher: "badge-info", school_admin: "badge-primary" };

function Avatar({ photo, name }) {
  const initials = name
    ? name.split(" ").map(w => w[0]).join("").slice(0,2).toUpperCase()
    : "?";
  return photo
    ? <img className="staff-avatar" src={photo} alt={name} />
    : <div className="staff-avatar staff-avatar--initials">{initials}</div>;
}

export default function Staff() {
  const [staff,        setStaff]        = useState([]);
  const [loading,      setLoading]      = useState(true);
  const [error,        setError]        = useState(null);
  const [totalCount,   setTotalCount]   = useState(0);
  const [search,       setSearch]       = useState("");
  const [roleFilter,   setRoleFilter]   = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [page,         setPage]         = useState(1);
  const PAGE_SIZE = 20;

  const loadStaff = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        page, page_size: PAGE_SIZE,
        ...(search       && { search }),
        ...(roleFilter   && { role:   roleFilter }),
        ...(statusFilter && { status: statusFilter }),
      });
      const { data } = await api.get(`/api/staff/?${params}`);
      setStaff(data.results || data);
      setTotalCount(data.count || data.length);
    } catch {
      setError("Failed to load staff.");
    } finally {
      setLoading(false);
    }
  }, [search, roleFilter, statusFilter, page]);

  useEffect(() => {
    const t = setTimeout(loadStaff, search ? 350 : 0);
    return () => clearTimeout(t);
  }, [loadStaff, search]);

  useEffect(() => { setPage(1); }, [search, roleFilter, statusFilter]);

  const totalPages = Math.ceil(totalCount / PAGE_SIZE);

  return (
    <div className="staff-root">
      {/* ── Header ── */}
      <div className="staff-page-header">
        <div>
          <h1 className="staff-page-title">Staff</h1>
          <p className="staff-page-sub">
            {totalCount > 0 ? `${totalCount} staff member${totalCount !== 1 ? "s" : ""}` : "No staff found"}
          </p>
        </div>
        <div className="staff-header-actions">
          <Link to="/admin/staff/import" className="btn btn-secondary">
            ↑ Bulk Import
          </Link>
          <Link to="/admin/staff/new" className="btn btn-primary">
            + Add Staff
          </Link>
        </div>
      </div>

      {/* ── Filters ── */}
      <div className="staff-filters">
        <div className="staff-search-wrap">
          <span className="staff-search-icon">🔍</span>
          <input
            type="search"
            className="staff-search"
            placeholder="Search name, email, specialization…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>

        <select className="staff-filter-select" value={roleFilter}
          onChange={e => setRoleFilter(e.target.value)}>
          <option value="">All Roles</option>
          <option value="teacher">Teachers</option>
          <option value="school_admin">Admins</option>
        </select>

        <select className="staff-filter-select" value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}>
          <option value="">All Statuses</option>
          <option value="active">Active</option>
          <option value="on_leave">On Leave</option>
          <option value="suspended">Suspended</option>
          <option value="terminated">Terminated</option>
          <option value="resigned">Resigned</option>
        </select>

        {(search || roleFilter || statusFilter) && (
          <button className="btn btn-ghost btn-sm"
            onClick={() => { setSearch(""); setRoleFilter(""); setStatusFilter(""); }}>
            Clear ✕
          </button>
        )}
      </div>

      {/* ── Table ── */}
      {error ? (
        <div className="staff-error">{error}</div>
      ) : loading ? (
        <div className="staff-loading"><div className="staff-spinner" /></div>
      ) : staff.length === 0 ? (
        <div className="staff-empty">
          <div className="staff-empty-icon">👩‍🏫</div>
          <h3>No staff found</h3>
          <p>Try adjusting your search or filters.</p>
        </div>
      ) : (
        <>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Staff Member</th>
                  <th>Staff ID</th>
                  <th>Role</th>
                  <th>Specialization</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {staff.map(s => (
                  <tr key={s.id}>
                    <td>
                      <div className="staff-name-cell">
                        <Avatar photo={s.profile_photo} name={s.full_name} />
                        <div>
                          <div className="staff-name">{s.full_name}</div>
                          <div className="staff-email">{s.email}</div>
                        </div>
                      </div>
                    </td>
                    <td><code className="staff-id-badge">{s.staff_id}</code></td>
                    <td>
                      <span className={`badge ${ROLE_COLORS[s.role] || ""}`}>
                        {ROLE_LABELS[s.role] || s.role}
                      </span>
                    </td>
                    <td className="text-muted">{s.specialization || "—"}</td>
                    <td>
                      <span className={`badge ${STATUS_COLORS[s.employment_status] || ""}`}>
                        {s.employment_status?.replace("_", " ")}
                      </span>
                    </td>
                    <td>
                      <div className="staff-row-actions">
                        <Link to={`/admin/staff/${s.id}`} className="btn btn-sm btn-ghost">View</Link>
                        <Link to={`/admin/staff/${s.id}/edit`} className="btn btn-sm btn-secondary">Edit</Link>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div className="staff-pagination">
              <button className="btn btn-sm btn-ghost"
                disabled={page <= 1} onClick={() => setPage(p => p - 1)}>
                ← Prev
              </button>
              <span className="staff-page-info">Page {page} of {totalPages}</span>
              <button className="btn btn-sm btn-ghost"
                disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>
                Next →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}