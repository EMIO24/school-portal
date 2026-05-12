import React, { useState, useEffect } from "react";
import api from "../../services/api";
import "./FeeCollection.css";

function statusOf(paid, total) {
  if (!total || Number(total) === 0) return "na";
  const ratio = Number(paid) / Number(total);
  if (ratio >= 1) return "paid";
  if (ratio > 0)  return "partial";
  return "unpaid";
}

function exportCSV(rows) {
  const header = "Student,Class,Total Fees,Paid,Outstanding\n";
  const body   = rows
    .filter(r => statusOf(r.paid, r.total_fees) !== "paid")
    .map(r => `"${r.student_name}","${r.class}",${r.total_fees},${r.paid},${r.outstanding}`)
    .join("\n");
  const blob = new Blob([header + body], { type: "text/csv" });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement("a"); a.href = url; a.download = "debtors.csv"; a.click();
  URL.revokeObjectURL(url);
}

export default function FeeCollection() {
  const [terms, setTerms]               = useState([]);
  const [classArms, setClassArms]       = useState([]);
  const [selectedTerm, setSelectedTerm] = useState("");
  const [selectedArm, setSelectedArm]   = useState("");
  const [outstanding, setOutstanding]   = useState([]);
  const [loading, setLoading]           = useState(false);
  const [modal, setModal]               = useState(null);
  const [schedules, setSchedules]       = useState([]);
  const [payForm, setPayForm]           = useState({
    fee_schedule_id: "", amount_paid: "", method: "cash",
    payment_date: new Date().toISOString().slice(0, 10),
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get("/api/academics/terms/").then(({ data: d }) => {
      const list = Array.isArray(d) ? d : d.results || [];
      setTerms(list);
      const cur = list.find(t => t.is_current);
      if (cur) setSelectedTerm(String(cur.id));
    }).catch(() => {});

    api.get("/api/enrollment/class-arms/").then(({ data: d }) => {
      setClassArms(Array.isArray(d) ? d : d.results || []);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (selectedTerm) loadOutstanding();
  }, [selectedTerm, selectedArm]);

  function loadOutstanding() {
    setLoading(true);
    let url = `/api/fees/outstanding/?term=${selectedTerm}`;
    if (selectedArm) url += `&class_arm=${selectedArm}`;
    api.get(url)
      .then(({ data: d }) => { setOutstanding(Array.isArray(d) ? d : d.results || []); setLoading(false); })
      .catch(() => setLoading(false));
  }

  async function openPayModal(student) {
    setModal(student);
    setSchedules([]);
    try {
      const { data } = await api.get(`/api/fees/student/${student.student_id}/?term=${selectedTerm}`);
      const list = Array.isArray(data) ? data : [];
      setSchedules(list);
      if (list.length > 0) {
        setPayForm(f => ({ ...f, fee_schedule_id: list[0].schedule.id, amount_paid: list[0].outstanding }));
      }
    } catch {
      alert("Could not load fee schedules for this student.");
      setModal(null);
    }
  }

  async function recordPayment() {
    setSaving(true);
    try {
      await api.post("/api/fees/pay/manual/", {
        student_id: modal.student_id, ...payForm,
      });
      setModal(null);
      loadOutstanding();
    } catch {
      alert("Failed to record payment. Please check the details and try again.");
    } finally {
      setSaving(false);
    }
  }

  const totalExpected    = outstanding.reduce((s, r) => s + Number(r.total_fees), 0);
  const totalCollected   = outstanding.reduce((s, r) => s + Number(r.paid), 0);
  const totalOutstanding = outstanding.reduce((s, r) => s + Number(r.outstanding), 0);

  return (
    <main className="page-shell">
      <h1 className="page-title">Fee Collection</h1>

      {/* Summary cards */}
      <div className="fee-summary-row">
        <div className="summary-card"><span>Expected</span><strong>₦{totalExpected.toLocaleString()}</strong></div>
        <div className="summary-card green"><span>Collected</span><strong>₦{totalCollected.toLocaleString()}</strong></div>
        <div className="summary-card red"><span>Outstanding</span><strong>₦{totalOutstanding.toLocaleString()}</strong></div>
      </div>

      {/* Filters */}
      <div className="filter-row">
        <select className="fee-select" value={selectedTerm} onChange={e => setSelectedTerm(e.target.value)}>
          <option value="">— Term —</option>
          {terms.map(t => <option key={t.id} value={t.id}>{t.name} {t.is_current ? "(current)" : ""}</option>)}
        </select>
        <select className="fee-select" value={selectedArm} onChange={e => setSelectedArm(e.target.value)}>
          <option value="">All Classes</option>
          {classArms.map(c => <option key={c.id} value={c.id}>{c.full_name || c.name}</option>)}
        </select>
        <button className="btn-secondary btn-sm" onClick={() => exportCSV(outstanding)}>Export Debtors CSV</button>
      </div>

      <div className="card table-wrap">
        {loading && <p className="empty-row">Loading…</p>}
        <table>
          <thead>
            <tr>
              <th>Student</th>
              <th>Class</th>
              <th>Total Fees</th>
              <th>Paid</th>
              <th>Outstanding</th>
              <th>Status</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {outstanding.map(row => {
              const st = statusOf(row.paid, row.total_fees);
              return (
                <tr key={row.student_id}>
                  <td>{row.student_name}</td>
                  <td>{row.class}</td>
                  <td>₦{Number(row.total_fees).toLocaleString()}</td>
                  <td>₦{Number(row.paid).toLocaleString()}</td>
                  <td>₦{Number(row.outstanding).toLocaleString()}</td>
                  <td><span className={`status-badge st-${st}`}>{st.charAt(0).toUpperCase() + st.slice(1)}</span></td>
                  <td>
                    {st !== "paid" && (
                      <button className="btn-sm" onClick={() => openPayModal(row)}>Record Payment</button>
                    )}
                  </td>
                </tr>
              );
            })}
            {outstanding.length === 0 && !loading && (
              <tr><td colSpan={7} className="empty-row">No data. Select a term to load.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {modal && (
        <div className="modal-overlay" onClick={() => setModal(null)}>
          <div className="modal-box" onClick={e => e.stopPropagation()}>
            <h2>Record Payment — {modal.student_name}</h2>

            <label>Fee Item</label>
            <select value={payForm.fee_schedule_id} onChange={e => {
              const s = schedules.find(x => String(x.schedule.id) === e.target.value);
              setPayForm(f => ({ ...f, fee_schedule_id: Number(e.target.value), amount_paid: s?.outstanding || "" }));
            }}>
              {schedules.map(s => (
                <option key={s.schedule.id} value={s.schedule.id}>
                  {s.schedule.fee_category_name} — ₦{Number(s.outstanding).toLocaleString()} outstanding
                </option>
              ))}
            </select>

            <label>Amount Paid (₦)</label>
            <input type="number" value={payForm.amount_paid} onChange={e => setPayForm(f => ({ ...f, amount_paid: e.target.value }))} />

            <label>Method</label>
            <select value={payForm.method} onChange={e => setPayForm(f => ({ ...f, method: e.target.value }))}>
              <option value="cash">Cash</option>
              <option value="bank_transfer">Bank Transfer</option>
            </select>

            <label>Payment Date</label>
            <input type="date" value={payForm.payment_date} onChange={e => setPayForm(f => ({ ...f, payment_date: e.target.value }))} />

            <div className="modal-actions">
              <button className="btn-secondary" onClick={() => setModal(null)}>Cancel</button>
              <button className="btn-primary" onClick={recordPayment} disabled={saving}>{saving ? "Saving…" : "Record"}</button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
