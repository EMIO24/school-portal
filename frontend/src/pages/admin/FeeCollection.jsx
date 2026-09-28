import React, { useState, useEffect, useCallback, useRef } from "react";
import { Link } from "react-router-dom";
import { downloadReport } from "../../services/pdf";
import api from "../../services/api";
import { classifyRequestFailure } from "../../services/requestState";
import "./FeeCollection.css";

function paymentRetryKey() {
  if (window.crypto?.randomUUID) return window.crypto.randomUUID();
  return `manual-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function statusOf(paid, state, balance) {
  if (state !== 'active') return state === 'legacy_review' ? 'review' : 'uninitialized';
  if (Number(balance) < 0) return 'credit';
  if (Number(balance) === 0) return 'paid';
  if (Number(paid) > 0) return 'partial';
  return "unpaid";
}

function exportPDF(rows) {
  const debtors = rows.filter(row => Number(row.outstanding) > 0);
  const lines = debtors.length ? debtors.flatMap(row => [
    row.student_name + ' | Class: ' + row.class,
    'Verified account outstanding: NGN ' + row.outstanding,
    '',
  ]) : ['No outstanding balances in the selected term/class.'];
  downloadReport('Outstanding school fees', lines, 'debtors.pdf');
}

export default function FeeCollection() {
  const [terms, setTerms]               = useState([]);
  const [classArms, setClassArms]       = useState([]);
  const [selectedTerm, setSelectedTerm] = useState("");
  const [termsLoaded, setTermsLoaded] = useState(false);
  const [selectedArm, setSelectedArm]   = useState("");
  const [search, setSearch] = useState("");
  const [generating, setGenerating] = useState(false);
  const [chargeNotice, setChargeNotice] = useState('');
  const [outstanding, setOutstanding]   = useState([]);
  const [summary, setSummary]           = useState(null);
  const [page, setPage]                 = useState(1);
  const [pageInfo, setPageInfo]         = useState({ next: null, previous: null });
  const [loading, setLoading]           = useState(false);
  const [loadError, setLoadError]         = useState("");
  const balanceRequest = useRef(0);
  const [modal, setModal]               = useState(null);
  const [schedules, setSchedules]       = useState([]);
  const [payForm, setPayForm]           = useState({
    fee_schedule_id: "", amount_paid: "", method: "cash",
    payment_date: new Date().toISOString().slice(0, 10),
    idempotency_key: paymentRetryKey(),
  });
  const [saving, setSaving] = useState(false);
  const [paymentError, setPaymentError] = useState("");
  const [uncertainPayment, setUncertainPayment] = useState(null);
  const paymentInFlight = useRef(false);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    api.get("/api/terms/").then(({ data: d }) => {
      const list = Array.isArray(d) ? d : d.results || [];
      setTerms(list);
      const cur = list.find(t => t.is_current);
      if (cur) setSelectedTerm(String(cur.id));
      setTermsLoaded(true);
    }).catch(() => setTermsLoaded(true));

    api.get("/api/class-arms/").then(({ data: d }) => {
      setClassArms(Array.isArray(d) ? d : d.results || []);
    }).catch(() => {});
  }, []);


  const loadOutstanding = useCallback(() => {
    const request = ++balanceRequest.current;
    setLoading(true);
    setLoadError("");
    let url = `/api/fees/ledger/accounts/?page=${page}`;
    if (selectedTerm) url += `&term=${selectedTerm}`;
    if (selectedArm) url += `&class_arm=${selectedArm}`;
    if (search.trim()) url += `&search=${encodeURIComponent(search.trim())}`;
    api.get(url)
      .then(({ data: d }) => {
        if (request !== balanceRequest.current) return;
        setOutstanding(Array.isArray(d) ? d : d.results || []);
        setSummary(Array.isArray(d) ? null : d.summary || null);
        setPageInfo(Array.isArray(d) ? { next: null, previous: null } : { next: d.next, previous: d.previous });
      })
      .catch(err => { if (request === balanceRequest.current) setLoadError(classifyRequestFailure(err).message); })
      .finally(() => { if (request === balanceRequest.current) setLoading(false); });
  }, [selectedTerm, selectedArm, search, page]);

  useEffect(() => {
    if (termsLoaded) loadOutstanding();
  }, [loadOutstanding, termsLoaded]);

  async function generateCharges() {
    if (!selectedTerm || generating || !window.confirm('Generate this term’s fee charges for active students? Existing charges will be kept.')) return;
    setGenerating(true); setChargeNotice('');
    try {
      const {data} = await api.post('/api/fees/ledger/charges/', {term_id: Number(selectedTerm),
        ...(selectedArm ? {class_arm_id: Number(selectedArm)} : {})});
      setChargeNotice(`${data.created} charges created; ${data.existing} already existed; ${data.legacy_skipped} legacy items need review.`);
      loadOutstanding();
    } catch {setChargeNotice('Could not confirm charge generation. Reload the accounts; retrying keeps existing charges.');}
    finally {setGenerating(false);}
  }


  async function openPayModal(student) {
    setModal(student);
    setPaymentError("");
    setUncertainPayment(null);
    setSchedules([]);
    try {
      const { data } = await api.get(`/api/fees/student/${student.student_id}/?term=${selectedTerm}`);
      const list = Array.isArray(data) ? data : [];
      const payable = list.filter(item => item.outstanding != null && Number(item.outstanding) > 0);
      if (!payable.length) {
        setModal(null);
        setChargeNotice('This account has no generated fee item to pay here. Open the student account to review its balance.');
        return;
      }
      setSchedules(payable);
      setPayForm(f => ({ ...f, fee_schedule_id: payable[0].schedule.id,
        amount_paid: payable[0].outstanding, idempotency_key: paymentRetryKey() }));
    } catch {
      alert("Could not load fee schedules for this student.");
      setModal(null);
    }
  }

  async function recordPayment() {
    if (paymentInFlight.current) return;
    paymentInFlight.current = true;
    setSaving(true);
    setPaymentError("");
    const payload = uncertainPayment || { student_id: modal.student_id, ...payForm };
    try {
      await api.post("/api/fees/pay/manual/", payload);
      setModal(null);
      setUncertainPayment(null);
      loadOutstanding();
    } catch (error) {
      if (!error?.response || error.response.status >= 500) {
        setUncertainPayment(payload);
        setPaymentError("Could not confirm whether this payment was recorded. Keep these details and retry the same payment; do not enter it again as a new payment.");
      } else {
        setPaymentError(error.response.data?.error || error.response.data?.detail || "Could not record this payment. Review the details and try again.");
      }
    } finally {
      paymentInFlight.current = false;
      setSaving(false);
    }
  }

  async function downloadDebtors() {
    setExporting(true);
    try {
      const rows = [];
      for (let pageNumber = 1; pageNumber <= 200; pageNumber += 1) {
        let url = `/api/fees/ledger/debtors/?page=${pageNumber}`;
        if (selectedTerm) url += `&term=${selectedTerm}`;
        if (selectedArm) url += `&class_arm=${selectedArm}`;
        if (search.trim()) url += `&search=${encodeURIComponent(search.trim())}`;
        const {data} = await api.get(url);
        rows.push(...(Array.isArray(data) ? data : data.results || []));
        if (pageNumber === 200 && !Array.isArray(data) && data.next) throw new Error('Report exceeds supported export size. Narrow the filters.');
        if (Array.isArray(data) || !data.next) break;
      }
      exportPDF(rows);
    } catch {
      alert("Could not prepare the debtor report. Please try again.");
    } finally {
      setExporting(false);
    }
  }

  const totalExpected    = Number(summary?.total_expected ?? 0);
  const totalCollected   = Number(summary?.total_collected ?? 0);
  const totalOutstanding = Number(summary?.total_outstanding ?? 0);

  return (
    <main className="page-shell">
      <h1 className="page-title">Fee Collection</h1>

      {/* Summary cards */}
      {!loading && !loadError && <div className="fee-summary-row">
        <div className="summary-card"><span>Unknown accounts</span><strong>{summary?.unknown_accounts ?? '—'}</strong></div>
        <div className="summary-card"><span>Recorded debits</span><strong>₦{totalExpected.toLocaleString()}</strong></div>
        <div className="summary-card green"><span>Collected</span><strong>₦{totalCollected.toLocaleString()}</strong></div>
        <div className="summary-card red"><span>Known outstanding</span><strong>₦{totalOutstanding.toLocaleString()}</strong></div>
      </div>}
      <p>Balances cover each full student account. Generate charges for a selected term; older receipts require opening balance review.</p>

      {/* Filters */}
      <div className="filter-row">
        <select className="fee-select" value={selectedTerm} onChange={e => { setSelectedTerm(e.target.value); setPage(1); }}>
          <option value="">— Term —</option>
          {terms.map(t => <option key={t.id} value={t.id}>{t.name} {t.is_current ? "(current)" : ""}</option>)}
        </select>
        <select className="fee-select" value={selectedArm} onChange={e => { setSelectedArm(e.target.value); setPage(1); }}>
          <option value="">All Classes</option>
          {classArms.map(c => <option key={c.id} value={c.id}>{c.full_name || c.name}</option>)}
        </select>
        <input aria-label="Search students" placeholder="Search student or admission number" value={search} onChange={e => {setSearch(e.target.value); setPage(1);}} />
        <button className="btn-secondary btn-sm" disabled={generating || !selectedTerm} onClick={generateCharges}>{generating ? 'Generating…' : 'Generate charges'}</button>
        <button className="btn-secondary btn-sm" disabled={exporting} onClick={downloadDebtors}>
          {exporting ? "Preparing…" : "Download Debtors PDF"}
        </button>
      </div>
      {chargeNotice && <p role="status">{chargeNotice}</p>}

      <div className="card table-wrap">
        {loading && <p className="empty-row" role="status">Loading balances…</p>}
        {loadError && <p className="empty-row" role="alert">{loadError} <button type="button" onClick={loadOutstanding}>Retry</button></p>}
        {!loadError && !loading && <table className="fee-directory">
          <thead>
            <tr>
              <th>Student</th>
              <th>Class</th>
              <th>Recorded debits</th>
              <th>Payments</th>
              <th>Outstanding</th>
              <th>Status</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {outstanding.map(row => {
              const st = statusOf(row.paid, row.state, Number(row.outstanding || 0) - Number(row.credit || 0));
              return (
                <tr key={row.student_id}>
                  <td data-label="Student">{row.student_name}</td>
                  <td data-label="Class">{row.class}</td>
                  <td data-label="Total">{row.total_fees == null ? 'Not verified' : `₦${Number(row.total_fees).toLocaleString()}`}</td>
                  <td data-label="Paid">{row.paid == null ? 'Not verified' : `₦${Number(row.paid).toLocaleString()}`}</td>
                  <td data-label="Balance">{row.outstanding == null ? 'Unknown' : Number(row.credit) > 0 ? `₦${Number(row.credit).toLocaleString()} credit` : `₦${Number(row.outstanding).toLocaleString()}`}</td>
                  <td data-label="Status"><span className={`status-badge st-${st}`}>{st.charAt(0).toUpperCase() + st.slice(1)}</span></td>
                  <td data-label="Action">
                    <Link to={`/admin/finance/${row.student_id}`}>View account</Link>{' '}
                    {row.state === 'active' && Number(row.outstanding) > 0 && (
                      <button className="btn-sm" onClick={() => openPayModal(row)}>Record Payment</button>
                    )}
                  </td>
                </tr>
              );
            })}
            {outstanding.length === 0 && !loading && (
              <tr><td colSpan={7} className="empty-row">No student accounts found for these filters.</td></tr>
            )}
          </tbody>
        </table>}
      </div>
      <nav aria-label="Debtor pages" className="filter-row">
        <button disabled={!pageInfo.previous || loading} onClick={() => setPage(value => value - 1)}>Previous</button>
        <span>Page {page}</span>
        <button disabled={!pageInfo.next || loading} onClick={() => setPage(value => value + 1)}>Next</button>
      </nav>

      {modal && (
        <div className="modal-overlay" onClick={() => {if (!saving) setModal(null);}}>
          <div className="modal-box" onClick={e => e.stopPropagation()}>
            <h2>Record Payment — {modal.student_name}</h2>

            <label>Fee Item</label>
            <select disabled={saving || !!uncertainPayment} value={payForm.fee_schedule_id} onChange={e => {
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
            <input disabled={saving || !!uncertainPayment} type="number" value={payForm.amount_paid} onChange={e => setPayForm(f => ({ ...f, amount_paid: e.target.value }))} />

            <label>Method</label>
            <select disabled={saving || !!uncertainPayment} value={payForm.method} onChange={e => setPayForm(f => ({ ...f, method: e.target.value }))}>
              <option value="cash">Cash</option>
              <option value="bank_transfer">Bank Transfer</option>
            </select>

            <label>Payment Date</label>
            <input disabled={saving || !!uncertainPayment} type="date" value={payForm.payment_date} onChange={e => setPayForm(f => ({ ...f, payment_date: e.target.value }))} />

            {paymentError && <p role="alert">{paymentError}</p>}

            <div className="modal-actions">
              <button className="btn-secondary" disabled={saving} onClick={() => setModal(null)}>Cancel</button>
              <button className="btn-primary" onClick={recordPayment} disabled={saving}>{saving ? "Saving…" : uncertainPayment ? "Retry same payment" : "Record"}</button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
