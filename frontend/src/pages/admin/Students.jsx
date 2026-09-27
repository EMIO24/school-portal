import {referenceOptions} from '../../services/referenceOptions';
import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../../services/api";
import { classifyRequestFailure } from "../../services/requestState";
import "./Students.css";

export default function Students() {
  const [rows, setRows] = useState([]);
  const [classes, setClasses] = useState([]);
  const [filters, setFilters] = useState({ search: "", class_arm: "", status: "" });
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [next, setNext] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true;
    referenceOptions("/api/class-arms/").then(({ data }) => { if (active) setClasses(data.results ?? data); }).catch(() => {});
    return () => { active = false; };
  }, []);
  useEffect(() => {
    let active = true;
    setLoading(true); setError("");
    const params = new URLSearchParams({ ...filters, page: String(page) });
    api.get("/api/students/?" + params).then(({ data }) => {
      if (!active) return;
      setRows(data.results ?? data);
      setTotal(data.count ?? data.length);
      setNext(Boolean(data.next));
    }).catch(err => { if (active) setError(classifyRequestFailure(err).message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [filters, page, retry]);
  function filter(key, value) { setPage(1); setFilters(prev => ({ ...prev, [key]: value })); }
  return <main className="page-shell">
    <h1>Students</h1>
    <p><Link to="/admin/students/new">Add Student</Link> · <Link to="/admin/students/import">Import Students</Link></p>
    <div className="student-filters">
      <label>Search students <input type="search" value={filters.search} placeholder="Name, email or admission number"
        onChange={e => filter("search", e.target.value)} /></label>
      <label>Class <select value={filters.class_arm} onChange={e => filter("class_arm", e.target.value)}>
        <option value="">All classes</option>{classes.map(c => <option key={c.id} value={c.id}>{c.full_name || c.name}</option>)}
      </select></label>
      <label>Status <select value={filters.status} onChange={e => filter("status", e.target.value)}>
        <option value="">All statuses</option>{["active", "graduated", "withdrawn", "suspended"].map(s => <option key={s}>{s}</option>)}
      </select></label>
    </div>
    {loading ? <p role="status">Loading students...</p> : error ? <div role="alert">{error} <button onClick={() => setRetry(n => n + 1)}>Retry</button></div> :
      <><p>{total} student{total === 1 ? "" : "s"} found</p>
        {rows.length ? <div className="student-directory"><table>
          <thead><tr>{["Name", "Admission number", "Email", "Class", "Status", "Actions"].map(h => <th key={h} style={{ padding: 10 }}>{h}</th>)}</tr></thead>
          <tbody>{rows.map(s => <tr key={s.id}>
            <td data-label="Name"><Link to={"/admin/students/" + s.id}>{s.full_name}</Link></td>
            <td data-label="Admission number">{s.admission_number}</td><td data-label="Email">{s.email}</td><td data-label="Class">{s.current_class_name || "Unassigned"}</td><td data-label="Status">{s.status}</td>
            <td data-label="Actions"><Link to={"/admin/students/" + s.id + "/edit"}>Edit</Link></td>
          </tr>)}</tbody>
        </table></div> : <p>No students match your filters. Add a student or clear the filters.</p>}
        <nav aria-label="Student pages" style={{ display: "flex", gap: 16, marginTop: 20 }}>
          <button disabled={page === 1} onClick={() => setPage(n => n - 1)}>Previous</button>
          <span>Page {page}</span><button disabled={!next} onClick={() => setPage(n => n + 1)}>Next</button>
        </nav>
      </>}
  </main>;
}
