import React, { useState, useEffect, useContext, useCallback, useRef } from "react";
import { AuthContext } from "../../context/AuthContext";
import api from "../../services/api";
import { downloadFile } from "../../services/download";
import StudentLedger from "../../components/common/StudentLedger";
import "./Fees.css";

export default function Fees({ studentId: requestedStudentId }) {
  const { user } = useContext(AuthContext);
  const studentId = requestedStudentId ?? user?.student_id;

  const [terms, setTerms]       = useState([]);
  const [selectedTerm, setSelectedTerm] = useState("");
  const [feeData, setFeeData]   = useState([]);
  const [loading, setLoading]   = useState(false);
  const [paying, setPaying]     = useState(false);
  const [selected, setSelected] = useState({});
  const [amounts, setAmounts] = useState({});
  const [feeError, setFeeError] = useState('');
  const loadVersion = useRef(0);

  useEffect(() => {
    api.get("/api/terms/").then(({ data }) => {
      const list = Array.isArray(data) ? data : data.results || [];
      setTerms(list);
      const cur = list.find(t => t.is_current);
      if (cur) setSelectedTerm(String(cur.id));
    }).catch(() => {});
  }, []);


  const loadFees = useCallback(() => {
    const version = ++loadVersion.current;
    setLoading(true); setFeeError(''); setFeeData([]); setSelected({}); setAmounts({});
    api.get(`/api/fees/student/${studentId}/?term=${selectedTerm}`)
      .then(({ data }) => { if (version === loadVersion.current) setFeeData(Array.isArray(data) ? data : []); })
      .catch(() => { if (version === loadVersion.current) setFeeError('Could not load term fees. Retry.'); })
      .finally(() => { if (version === loadVersion.current) setLoading(false); });
  }, [selectedTerm, studentId]);

  useEffect(() => {
    if (selectedTerm && studentId) loadFees();
    return () => {loadVersion.current += 1;};
  }, [loadFees, selectedTerm, studentId]);


  function toggleSelect(fee) {
    const scheduleId = fee.schedule.id;
    const nextSelected = !selected[scheduleId];
    setSelected(s => ({ ...s, [scheduleId]: nextSelected }));
    if (nextSelected) {
      setAmounts(current => ({
        ...current,
        [scheduleId]: current[scheduleId] || String(fee.outstanding),
      }));
    }
  }

  async function payOnline() {
    const allocations = feeData
      .filter(f => selected[f.schedule.id] && f.outstanding != null && Number(f.outstanding) > 0)
      .map(f => ({
        schedule_id: f.schedule.id,
        amount: amounts[f.schedule.id],
        outstanding: Number(f.outstanding),
      }));
    if (allocations.length === 0) return;
    const invalid = allocations.find(item => {
      const amount = Number(item.amount);
      return !Number.isFinite(amount) || amount <= 0 || amount > item.outstanding ||
        !/^\d+(?:\.\d{1,2})?$/.test(String(item.amount).trim());
    });
    if (invalid) {
      alert("Enter a valid amount up to the outstanding balance for each selected fee.");
      return;
    }
    setPaying(true);
    try {
      const { data } = await api.post("/api/fees/pay/initiate/", {
        student_id: studentId,
        allocations: allocations.map(({schedule_id, amount}) => ({schedule_id, amount})),
      });
      if (data.authorization_url) {
        window.location.href = data.authorization_url;
      }
    } catch (error) {
      const reference = error.response?.data?.reference;
      alert((error.response?.data?.error || "Payment initiation failed. Please try again.") + (reference ? " Reference: " + reference : ""));
      if (reference) window.location.assign("/payments/return?reference=" + encodeURIComponent(reference));
    } finally {
      setPaying(false);
    }
  }

  const anySelected = feeData.some(f => selected[f.schedule.id] && f.outstanding != null && Number(f.outstanding) > 0);
  const selectedTotal = feeData.reduce((total, f) => selected[f.schedule.id]
    ? total + (Number(amounts[f.schedule.id]) || 0) : total, 0);

  return (
    <main className="page-shell fees-page">
      <h1 className="page-title">My Fees</h1>
      {studentId && <StudentLedger studentId={studentId} />}

      <div className="fees-filter-row">
        <select className="fees-select" value={selectedTerm} onChange={e => setSelectedTerm(e.target.value)}>
          <option value="">— Select term —</option>
          {terms.map(t => <option key={t.id} value={t.id}>{t.name} {t.is_current ? "(current)" : ""}</option>)}
        </select>
      </div>

      {loading && <p className="empty-row">Loading fees…</p>}
      {feeError && <p role="alert">{feeError} <button type="button" onClick={loadFees}>Retry</button></p>}

      <div className="fee-cards">
        {feeData.map(f => {
          const outstanding = f.outstanding == null ? null : Number(f.outstanding);
          const pct = outstanding != null && Number(f.amount) > 0
            ? Math.min(100, Math.round(((Number(f.amount) - outstanding) / Number(f.amount)) * 100)) : 0;
          return (
            <div key={f.schedule.id} className={`fee-card ${outstanding === 0 ? "fee-paid" : ""}`}>
              <div className="fee-card-header">
                <span className="fee-name">{f.schedule.fee_category_name}</span>
                {outstanding > 0 && (
                  <label className="fee-checkbox">
                    <input type="checkbox" checked={!!selected[f.schedule.id]} onChange={() => toggleSelect(f)} />
                    Select
                  </label>
                )}
              </div>
              <div className="fee-amounts">
                <div><span>Total</span><strong>₦{Number(f.amount).toLocaleString()}</strong></div>
                <div><span>Paid</span><strong className="green">₦{Number(f.paid).toLocaleString()}</strong></div>
                {Number(f.credits) > 0 && <div><span>Discounts / credits</span><strong className="green">₦{Number(f.credits).toLocaleString()}</strong></div>}
                <div><span>Outstanding</span><strong className={outstanding > 0 ? "red" : "green"}>{outstanding == null ? 'Awaiting charge or balance verification' : `₦${outstanding.toLocaleString()}`}</strong></div>
              </div>
              <div className="fee-progress-bar">
                <div className="fee-progress-fill" style={{ width: `${pct}%` }} />
              </div>
              {f.schedule.due_date && <p className="due-date">Due: {f.schedule.due_date}</p>}
              {selected[f.schedule.id] && outstanding > 0 && (
                <label className="fee-payment-amount">
                  Amount to pay (₦)
                  <input
                    aria-label={`Amount to pay for ${f.schedule.fee_category_name}`}
                    type="number"
                    min="0.01"
                    step="0.01"
                    max={outstanding}
                    value={amounts[f.schedule.id] ?? ''}
                    onChange={event => setAmounts(current => ({
                      ...current,
                      [f.schedule.id]: event.target.value,
                    }))}
                  />
                  <small>Maximum ₦{outstanding.toLocaleString()}</small>
                </label>
              )}

              {f.payments.length > 0 && (
                <div className="fee-history">
                  <p className="history-title">Payment History</p>
                  {f.payments.map(p => (
                    <div key={p.id} className="payment-row">
                      <span>{p.payment_date}</span>
                      <span>{p.method}</span>
                      <span>₦{Number(p.amount_paid).toLocaleString()}</span>
                      <button
                        type="button"
                        onClick={() => downloadFile(`/api/fees/receipts/${p.id}/`, `receipt-${p.id}.pdf`)}
                        className="receipt-link"
                      >
                        Receipt
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
        {feeData.length === 0 && !loading && selectedTerm && (
          <p className="empty-row">No fee schedules found for this term.</p>
        )}
      </div>

      {anySelected && (
        <div className="pay-bar">
          <span>Selected payment: <strong>₦{selectedTotal.toLocaleString()}</strong></span>
          <button className="btn-primary pay-btn" onClick={payOnline} disabled={paying}>
            {paying ? "Redirecting…" : "Pay Online via Paystack"}
          </button>
        </div>
      )}
    </main>
  );
}
