import React, {useCallback, useEffect, useRef, useState} from 'react';
import {Link, useParams} from 'react-router-dom';
import api from '../../services/api';
import StudentLedger from '../../components/common/StudentLedger';
import './FinanceAccount.css';

const newKey = () => window.crypto?.randomUUID?.() || `finance-${Date.now()}-${Math.random().toString(36).slice(2)}`;
const today = () => new Date().toISOString().slice(0, 10);

export default function FinanceAccount() {
  const {studentId} = useParams();
  const [account, setAccount] = useState(null);
  const [schedules, setSchedules] = useState([]);
  const [refreshKey, setRefreshKey] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [kind, setKind] = useState('opening');
  const [amount, setAmount] = useState('');
  const [reason, setReason] = useState('');
  const [scheduleId, setScheduleId] = useState('');
  const [method, setMethod] = useState('cash');
  const [paymentDate, setPaymentDate] = useState(today());
  const [effectiveDate, setEffectiveDate] = useState(today());
  const [allowCredit, setAllowCredit] = useState(false);
  const [uncertain, setUncertain] = useState(null);
  const key = useRef(newKey());
  const version = useRef(0);

  const load = useCallback(async () => {
    const current = ++version.current;
    setLoading(true);
    try {
      const [accountResponse, scheduleResponse] = await Promise.all([
        api.get(`/api/fees/ledger/student/${studentId}/`),
        api.get(`/api/fees/student/${studentId}/`),
      ]);
      if (current !== version.current) return;
      setAccount(accountResponse.data);
      setSchedules(Array.isArray(scheduleResponse.data) ? scheduleResponse.data : []);
      setError(previous => previous.startsWith('The response is uncertain') ? previous : '');
    } catch { if (current === version.current) setError(previous => previous.startsWith('The response is uncertain')
      ? previous : 'Could not load the student account. Retry.'); }
    finally { if (current === version.current) setLoading(false); }
  }, [studentId]);
  useEffect(() => {setAccount(null); setSchedules([]); setUncertain(null); setError(''); key.current = newKey();
    return () => {version.current += 1;};}, [studentId]);
  useEffect(() => {load(); return () => {version.current += 1;};}, [refreshKey, load]);
  useEffect(() => {if (account?.state === 'active' && kind === 'opening') setKind('payment');}, [account, kind]);

  function resetForm() {
    setAmount(''); setReason(''); setAllowCredit(false); setUncertain(null); key.current = newKey();
  }

  async function submit(event) {
    event.preventDefault();
    if (busy) return;
    const path = uncertain?.path || (kind === 'payment' ? '/api/fees/pay/manual/' : '/api/fees/ledger/changes/');
    const payload = uncertain?.payload || (kind === 'payment'
      ? {student_id: Number(studentId), fee_schedule_id: Number(scheduleId), amount_paid: amount,
         payment_date: paymentDate, method, idempotency_key: key.current, allow_credit: allowCredit}
      : {student_id: Number(studentId), kind, amount, reason,
         ...(kind === 'opening' ? {effective_date: effectiveDate} : {}),
         ...(scheduleId && kind !== 'opening' ? {fee_schedule_id: Number(scheduleId)} : {}),
         idempotency_key: key.current});
    if (!uncertain && !window.confirm(kind === 'payment'
      ? `Record ₦${amount} as a ${method.replace('_', ' ')} payment?`
      : `Record this ${kind} of ₦${amount}? This will remain in financial history.`)) return;
    setBusy(true); setError(''); setNotice('');
    try {
      await api.post(path, payload);
      setNotice(`${kind === 'payment' ? 'Payment' : kind.charAt(0).toUpperCase() + kind.slice(1)} recorded. Review the account history below.`);
      resetForm(); setRefreshKey(value => value + 1);
    } catch (err) {
      if (!err.response || err.response.status >= 500) {
        setUncertain({path, payload});
        setError('The response is uncertain. Check the account history, then retry this exact request. Do not enter it again as a new transaction.');
        setRefreshKey(value => value + 1);
      } else setError(err.response.data?.detail || err.response.data?.error || 'Could not record this change. Review the details.');
    } finally {setBusy(false);}
  }

  const charged = schedules.filter(item => item.charge_state === 'charged');
  const options = kind === 'payment' ? schedules : charged;
  return <main className="finance-account"><Link to="/admin/fee-collection">Back to fee accounts</Link>
    <header><span className="workspace-eyebrow">SCHOOL FINANCE</span><h1>{account?.student_name || 'Student account'}</h1>
      <p>Charges, credits and payments remain in a dated financial history. Existing receipts retain their original numbers.</p></header>
    {loading && <p role="status">Loading account…</p>}
    {error && <p role="alert" className="finance-error">{error} {loading === false && !account && <button onClick={load}>Retry</button>}</p>}
    {notice && <p role="status" className="finance-success">{notice}</p>}
    <StudentLedger studentId={studentId} refreshKey={refreshKey}/>
    {account && <form className="finance-form" onSubmit={submit}>
      <h2>Record a financial change</h2>
      <label>Change type<select disabled={busy || !!uncertain} value={kind} onChange={e => {setKind(e.target.value); setScheduleId(''); resetForm();}}>
        {account.state === 'legacy_review' || account.state === 'uninitialized' ? <option value="opening">Verified opening balance</option> : null}
        <option value="payment">Payment</option>
        {account.state === 'active' && <><option value="discount">Discount</option><option value="scholarship">Scholarship</option><option value="adjustment">Adjustment</option></>}
      </select></label>
      {kind !== 'opening' && <label>Fee item<select disabled={busy || !!uncertain} value={scheduleId} onChange={e => setScheduleId(e.target.value)} required={kind !== 'adjustment'}>
        <option value="">{kind === 'adjustment' ? 'Whole student account' : 'Choose a fee item'}</option>
        {options.map(item => <option key={item.schedule.id} value={item.schedule.id}>{item.schedule.fee_category_name} · {item.schedule.term_name}
          {item.outstanding != null ? ` · ₦${Number(item.outstanding).toLocaleString('en-NG')} remaining` : ' · opening review needed'}</option>)}
      </select></label>}
      <label>Amount (₦)<input type="number" step="0.01" disabled={busy || !!uncertain} value={amount} onChange={e => setAmount(e.target.value)} required /></label>
      {kind === 'opening' && <p>Use a positive amount for debt, a negative amount for credit, or zero when verified. This amount must be the balance at the cutover date; older receipts stay separate.</p>}
      {kind === 'opening' && <label>Balance effective date<input type="date" disabled={busy || !!uncertain} value={effectiveDate} onChange={e => setEffectiveDate(e.target.value)} required /></label>}
      {kind === 'adjustment' && <p>Positive adds debt; negative reduces it. Enter a specific reason.</p>}
      {kind === 'payment' ? <><label>Method<select disabled={busy || !!uncertain} value={method} onChange={e => setMethod(e.target.value)}><option value="cash">Cash</option><option value="bank_transfer">Bank transfer</option></select></label>
        <label>Payment date<input type="date" disabled={busy || !!uncertain} value={paymentDate} onChange={e => setPaymentDate(e.target.value)} required /></label>
        {account.state === 'active' && <label className="finance-check"><input type="checkbox" disabled={busy || !!uncertain} checked={allowCredit} onChange={e => setAllowCredit(e.target.checked)}/>Keep any excess as account credit</label>}</>
        : <label>Reason / verification reference<textarea disabled={busy || !!uncertain} value={reason} onChange={e => setReason(e.target.value)} maxLength={500} required /></label>}
      <button disabled={busy || (kind !== 'opening' && kind !== 'adjustment' && !scheduleId)} type="submit">{busy ? 'Saving…' : uncertain ? 'Retry same request' : 'Record change'}</button>
    </form>}
  </main>;
}
