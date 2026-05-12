import React, { useState, useEffect, useContext } from "react";
import { AuthContext } from "../../context/AuthContext";
import api from "../../services/api";
import "./Fees.css";

export default function Fees() {
  const { user } = useContext(AuthContext);
  const studentId = user?.student_id || user?.id;

  const [terms, setTerms]       = useState([]);
  const [selectedTerm, setSelectedTerm] = useState("");
  const [feeData, setFeeData]   = useState([]);
  const [loading, setLoading]   = useState(false);
  const [paying, setPaying]     = useState(false);
  const [selected, setSelected] = useState({});

  useEffect(() => {
    api.get("/api/academics/terms/").then(({ data }) => {
      const list = Array.isArray(data) ? data : data.results || [];
      setTerms(list);
      const cur = list.find(t => t.is_current);
      if (cur) setSelectedTerm(String(cur.id));
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (selectedTerm && studentId) loadFees();
  }, [selectedTerm, studentId]);

  function loadFees() {
    setLoading(true);
    api.get(`/api/fees/student/${studentId}/?term=${selectedTerm}`)
      .then(({ data }) => { setFeeData(Array.isArray(data) ? data : []); setLoading(false); })
      .catch(() => setLoading(false));
  }

  function toggleSelect(scheduleId) {
    setSelected(s => ({ ...s, [scheduleId]: !s[scheduleId] }));
  }

  async function payOnline() {
    const ids = feeData
      .filter(f => selected[f.schedule.id] && Number(f.outstanding) > 0)
      .map(f => f.schedule.id);
    if (ids.length === 0) return;
    setPaying(true);
    try {
      const { data } = await api.post("/api/fees/pay/initiate/", {
        student_id: studentId, fee_schedule_ids: ids,
      });
      if (data.authorization_url) {
        window.location.href = data.authorization_url;
      }
    } catch {
      alert("Payment initiation failed. Please try again.");
    } finally {
      setPaying(false);
    }
  }

  const anySelected = feeData.some(f => selected[f.schedule.id] && Number(f.outstanding) > 0);

  return (
    <main className="page-shell fees-page">
      <h1 className="page-title">My Fees</h1>

      <div className="fees-filter-row">
        <select className="fees-select" value={selectedTerm} onChange={e => setSelectedTerm(e.target.value)}>
          <option value="">— Select term —</option>
          {terms.map(t => <option key={t.id} value={t.id}>{t.name} {t.is_current ? "(current)" : ""}</option>)}
        </select>
      </div>

      {loading && <p className="empty-row">Loading fees…</p>}

      <div className="fee-cards">
        {feeData.map(f => {
          const pct = f.amount > 0 ? Math.min(100, Math.round((Number(f.paid) / Number(f.amount)) * 100)) : 0;
          const outstanding = Number(f.outstanding);
          return (
            <div key={f.schedule.id} className={`fee-card ${outstanding === 0 ? "fee-paid" : ""}`}>
              <div className="fee-card-header">
                <span className="fee-name">{f.schedule.fee_category_name}</span>
                {outstanding > 0 && (
                  <label className="fee-checkbox">
                    <input type="checkbox" checked={!!selected[f.schedule.id]} onChange={() => toggleSelect(f.schedule.id)} />
                    Select
                  </label>
                )}
              </div>
              <div className="fee-amounts">
                <div><span>Total</span><strong>₦{Number(f.amount).toLocaleString()}</strong></div>
                <div><span>Paid</span><strong className="green">₦{Number(f.paid).toLocaleString()}</strong></div>
                <div><span>Outstanding</span><strong className={outstanding > 0 ? "red" : "green"}>₦{outstanding.toLocaleString()}</strong></div>
              </div>
              <div className="fee-progress-bar">
                <div className="fee-progress-fill" style={{ width: `${pct}%` }} />
              </div>
              {f.schedule.due_date && <p className="due-date">Due: {f.schedule.due_date}</p>}

              {f.payments.length > 0 && (
                <div className="fee-history">
                  <p className="history-title">Payment History</p>
                  {f.payments.map(p => (
                    <div key={p.id} className="payment-row">
                      <span>{p.payment_date}</span>
                      <span>{p.method}</span>
                      <span>₦{Number(p.amount_paid).toLocaleString()}</span>
                      <a
                        href={`/api/fees/receipts/${p.id}/`}
                        target="_blank"
                        rel="noreferrer"
                        className="receipt-link"
                      >
                        Receipt
                      </a>
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
          <button className="btn-primary pay-btn" onClick={payOnline} disabled={paying}>
            {paying ? "Redirecting…" : "Pay Online via Paystack"}
          </button>
        </div>
      )}
    </main>
  );
}
