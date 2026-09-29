import React, {useCallback, useEffect, useRef, useState} from 'react';
import api from '../../services/api';
import {downloadFile} from '../../services/download';
import './StudentLedger.css';

export default function StudentLedger({studentId, refreshKey = 0}) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const requestVersion = useRef(0);
  const load = useCallback(async (url = `/api/fees/ledger/student/${studentId}/`, append = false) => {
    const version = ++requestVersion.current;
    setLoading(true); setError('');
    try {
      const response = await api.get(url);
      if (version === requestVersion.current) setData(old => ({...response.data,
        results: append ? [...(old?.results || []), ...response.data.results] : response.data.results}));
    } catch { if (version === requestVersion.current) setError('Could not load this financial history. Retry.'); }
    finally { if (version === requestVersion.current) setLoading(false); }
  }, [studentId]);
  useEffect(() => {
    requestVersion.current += 1; setData(null);
    if (studentId) load();
    return () => {requestVersion.current += 1;};
  }, [studentId, refreshKey, load]);
  return <section className="student-ledger" aria-label="Student financial account">
    <h2>Student financial account</h2>
    {loading && <p role="status">Loading account…</p>}
    {error && <p role="alert">{error} <button type="button" onClick={() => load()}>Retry</button></p>}
    {data?.state === 'legacy_review' && <p role="status">Opening balance requires school verification. Older receipts remain available, but Paideia cannot infer their original charges from today's fee structure.</p>}
    {data?.state === 'uninitialized' && <p role="status">No student charges or verified opening balance have been recorded yet. A zero balance has not been confirmed.</p>}
    {data?.state === 'active' && <div className="student-ledger-totals"><p>Outstanding <strong>₦{Number(data.outstanding).toLocaleString('en-NG')}</strong></p>
      <p>Account credit <strong>₦{Number(data.credit).toLocaleString('en-NG')}</strong></p></div>}
    {!!data?.results?.length && <div className="student-ledger-rows">{data.results.map(row => <article key={row.id}>
      <div><strong>{row.description}</strong><span>{row.kind.replace('_', ' ')} · Recorded {row.recorded_at?.slice(0, 10) || row.effective_date} · Effective {row.effective_date}</span>
        {row.reason && <small>{row.reason}</small>}</div>
      <div><strong>{Number(row.amount) >= 0 ? '+' : '−'}₦{Math.abs(Number(row.amount)).toLocaleString('en-NG')}</strong>
        <span>Running: ₦{Number(row.running_balance).toLocaleString('en-NG')}</span>
        {row.receipt_id && <button type="button" onClick={() => downloadFile(`/api/fees/receipts/${row.receipt_id}/`, `receipt-${row.receipt_id}.pdf`)}>Receipt</button>}</div>
    </article>)}</div>}
    {data?.next && <button type="button" onClick={() => load(data.next, true)} disabled={loading}>Load more activity</button>}
    {!!data?.legacy_receipts?.length && <div><h3>Older receipts</h3><p>{data.legacy_receipts_note}</p>
      {data.legacy_receipts.map(row => <p key={row.id}>{row.payment_date} · ₦{Number(row.amount_paid).toLocaleString('en-NG')}
        {' '}<button type="button" onClick={() => downloadFile(`/api/fees/receipts/${row.id}/`, `receipt-${row.id}.pdf`)}>Receipt {row.receipt_number}</button></p>)}</div>}
  </section>;
}
