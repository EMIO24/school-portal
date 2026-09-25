import {referenceOptions} from '../../services/referenceOptions';
import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../../services/api";

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
    }).catch(() => { if (active) setError("Could not load students. Check the connection and retry."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [filters, page, retry]);
  function filter(key, value) { setPage(1); setFilters(prev => ({ ...prev, [key]: value })); }
  return <main className="page-shell">
    <h1>Students</h1>
    <p><Link to="/admin/students/new">Add Student</Link> · <Link to="/admin/students/import">Import Students</Link></p>
    <div style={{ display: "flex", flexWrap: "wrap", gap: 16, marginBottom: 20 }}>
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
        {rows.length ? <div style={{ overflowX: "auto" }}><table style={{ width: "100%", textAlign: "left" }}>
          <thead><tr>{["Name", "Admission number", "Email", "Class", "Status", "Actions"].map(h => <th key={h} style={{ padding: 10 }}>{h}</th>)}</tr></thead>
          <tbody>{rows.map(s => <tr key={s.id}>
            <td style={{ padding: 10 }}><Link to={"/admin/students/" + s.id}>{s.full_name}</Link></td>
            <td>{s.admission_number}</td><td>{s.email}</td><td>{s.current_class_name || "Unassigned"}</td><td>{s.status}</td>
            <td><Link to={"/admin/students/" + s.id + "/edit"}>Edit</Link></td>
          </tr>)}</tbody>
        </table></div> : <p>No students match your filters. Add a student or clear the filters.</p>}
        <nav aria-label="Student pages" style={{ display: "flex", gap: 16, marginTop: 20 }}>
          <button disabled={page === 1} onClick={() => setPage(n => n - 1)}>Previous</button>
          <span>Page {page}</span><button disabled={!next} onClick={() => setPage(n => n + 1)}>Next</button>
        </nav>
      </>}
  </main>;
}