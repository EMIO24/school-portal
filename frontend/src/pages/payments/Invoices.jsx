import React, { useCallback, useEffect, useRef, useState } from 'react';
import api from '../../services/api';
import { downloadFile } from '../../services/download';
import './Invoices.css';

const money = value => new Intl.NumberFormat('en-NG', {style:'currency', currency:'NGN', maximumFractionDigits:2}).format(value);
const day = value => value ? new Date(value).toLocaleDateString('en-GB') : '—';
const labels = {issued:'Unpaid', overdue:'Overdue', paid:'Paid', void:'Void'};
function errorMessage(error) {
  const data = error.response?.data;
  if (typeof data?.error === 'string') return data.error;
  if (typeof data?.detail === 'string') return data.detail;
  if (Array.isArray(data)) return data.join(' ');
  if (Array.isArray(data?.non_field_errors)) return data.non_field_errors.join(' ');
  return 'We could not complete this request. Please try again.';
}

export default function Invoices({owner=false, schools=[]}) {
  const root = owner ? '/api/platform/invoices/' : '/api/fees/subscription/invoices/';
  const [page, setPage] = useState(1), [filters, setFilters] = useState({status:'', plan:'', school:''});
  const [data, setData] = useState(null), [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true), [busy, setBusy] = useState(false), [error, setError] = useState('');
  const [notice, setNotice] = useState(''), [months, setMonths] = useState(3);
  const generation = useRef(0), heading = useRef(null), detailGeneration = useRef(0);
  const load = useCallback(async () => {
    const current = ++generation.current;
    setLoading(true); setError('');
    try {
      const params = Object.fromEntries(Object.entries({...filters, page}).filter(([,value]) => value !== ''));
      const response = await api.get(root, {params});
      if (current === generation.current) setData(response.data);
    } catch (e) { if (current === generation.current) setError(errorMessage(e)); }
    finally { if (current === generation.current) setLoading(false); }
  }, [root, filters, page]);
  useEffect(() => {
    const requests = generation;
    load();
    return () => {requests.current++;};
  }, [load]);
  const show = async id => {
    const current = ++detailGeneration.current;
    setBusy(true); setError('');
    try {
      const response = await api.get(root + id + '/');
      if (current === detailGeneration.current) setDetail(response.data);
    } catch (e) {if (current === detailGeneration.current) setError(errorMessage(e));}
    finally {if (current === detailGeneration.current) setBusy(false);}
  };
  useEffect(() => {if(detail) heading.current?.focus();}, [detail]);
  const pay = async () => {
    setBusy(true); setError('');
    try {
      const response = await api.post('/api/fees/subscription/', {invoice_id:detail.id});
      window.location.assign(response.data.authorization_url);
    } catch (e) {setBusy(false); await show(detail.id); setError(errorMessage(e));}
  };
  const verify = async reference => {
    setBusy(true); setError(''); setNotice('');
    try {
      const response = owner ? await api.post('/api/platform/payments/', {reference})
        : await api.get('/api/fees/pay/verify/', {params:{reference}});
      setNotice(response.data.status === 'success' ? 'Payment verified. Your invoice and receipt are ready.' : 'Payment status: ' + response.data.status + '. ' + (response.data.note || 'You can check again later.'));
      await show(detail.id); await load();
    } catch(e) {setError(errorMessage(e));} finally {setBusy(false);}
  };
  const setDuration = async event => {
    event.preventDefault(); setBusy(true); setError('');
    try {await api.post(root + detail.id + '/', {action:'set_duration', months:Number(months)}); await show(detail.id);}
    catch(e) {setError(errorMessage(e));} finally {setBusy(false);}
  };
  return <section className="invoice-workspace" aria-label="Subscription invoices">
    <header><p className="invoice-eyebrow">PAIDEIA PORTALS</p><h2>{owner ? 'School subscription invoices' : 'Your subscription invoices'}</h2>
      <p>Review your billing period and student pricing before payment. Student tuition and school fees are managed separately.</p></header>
    {error && <div role="alert"><p>{error}</p><button onClick={load} disabled={busy}>Retry invoices</button></div>}
    {notice && <p role="status">{notice}</p>}
    <div className="invoice-filters">
      <label>Invoice status<select value={filters.status} onChange={e => {setFilters({...filters,status:e.target.value});setPage(1);}}><option value="">All statuses</option>{Object.entries(labels).map(([key,label]) => <option key={key} value={key}>{label}</option>)}</select></label>
      <label>Invoice plan<select value={filters.plan} onChange={e => {setFilters({...filters,plan:e.target.value});setPage(1);}}><option value="">All plans</option>{['basic','premium','enterprise'].map(plan => <option key={plan} value={plan}>{plan}</option>)}</select></label>
      {owner && <label>Invoice school<select value={filters.school} onChange={e => {setFilters({...filters,school:e.target.value});setPage(1);}}><option value="">All schools</option>{schools.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>}
    </div>
    {loading ? <p role="status">Loading invoices…</p> : !data?.results?.length ? <div className="invoice-empty"><h3>No invoices to show</h3><p>{owner ? 'No subscription invoices match these filters.' : 'Your invoice will appear here when Paideia issues it. Contact your platform support contact if you are ready to renew.'}</p></div> : <>
      <div className="invoice-cards">{data.results.map(invoice => <article key={invoice.id}>
        <span className={'invoice-badge ' + invoice.status}>{labels[invoice.status]}</span>
        <h3>{invoice.plan} · {invoice.term_name}</h3><p>{invoice.school_name}<br/>{invoice.session_name}</p>
        <p className="invoice-total">{money(invoice.final_amount)}</p><p>Due {day(invoice.due_date)}</p>
        <p className="invoice-number">{invoice.invoice_number}</p>
        <button disabled={busy} onClick={() => {setDetail(null); show(invoice.id);}}>Review invoice {invoice.invoice_number}</button>
      </article>)}</div>
      <nav className="invoice-pages" aria-label="Invoice pages"><button disabled={page===1 || loading} onClick={() => setPage(page-1)}>Previous</button><span>Page {page}</span><button disabled={!data.next || loading} onClick={() => setPage(page+1)}>Next</button></nav>
    </>}
    {detail && <section className="invoice-detail" aria-label="Invoice details">
      <div className="invoice-detail-header"><div><p className="invoice-eyebrow">PAIDEIA PORTALS</p><h2 ref={heading} tabIndex={-1}>Subscription invoice</h2></div><button disabled={busy} onClick={() => {detailGeneration.current++;setDetail(null);}}>Close invoice</button></div>
      <p className="invoice-number">{detail.invoice_number}</p><h3>{detail.school_name}</h3>
      <p>{detail.session_name} · {detail.term_name} · {detail.plan}</p><span className={'invoice-badge ' + detail.status}>{labels[detail.status]}</span>
      <dl className="invoice-breakdown">{[
        ['Billed active students', detail.active_student_count], ['Standard rate per student', money(detail.standard_rate)],
        ['Subtotal', money(detail.subtotal)], ['Discount (' + detail.discount_percentage + '%)', money(detail.discount_amount)],
        ['Effective rate per student', new Intl.NumberFormat('en-NG',{style:'currency',currency:'NGN',maximumFractionDigits:4}).format(detail.effective_rate)],
        ['Total amount', money(detail.final_amount)], ['Issue date', day(detail.issue_date)], ['Due date', day(detail.due_date)],
        ['Subscription duration', detail.subscription_months ? detail.subscription_months + ' months' : 'Awaiting confirmation'],
        ...(detail.paid_at ? [['Paid date',day(detail.paid_at)],['Payment reference',detail.payment_reference]] : [])
      ].map(([label,value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
      {detail.status === 'void' && <p>This invoice has been voided. {detail.void_reason}</p>}
      {!owner && ['issued','overdue'].includes(detail.status) && <div><p>You will continue to Paystack. Payment is confirmed only after server verification. Your card will not be charged automatically for renewals.</p><button disabled={busy || !detail.subscription_months || Number(detail.final_amount)<=0} onClick={pay}>{busy ? 'Checking payment…' : 'Pay ' + money(detail.final_amount)}</button>{!detail.subscription_months && <p>Contact Paideia to confirm the billing duration before paying.</p>}</div>}
      {owner && detail.status !== 'paid' && detail.status !== 'void' && !detail.subscription_months && <form onSubmit={setDuration}><p>Confirm the agreed duration for this existing invoice. Once saved, it cannot be changed.</p><label>Billing duration (months)<input type="number" min="1" max="12" required value={months} onChange={e => setMonths(e.target.value)}/></label><button disabled={busy}>Confirm billing duration</button></form>}
      <div className="invoice-actions"><button onClick={() => downloadFile(root + detail.id + '/invoice.pdf', detail.invoice_number + '.pdf')}>Download invoice PDF</button>
        {detail.status === 'paid' && <button onClick={() => downloadFile(root + detail.id + '/receipt.pdf', detail.receipt_number + '.pdf')}>Download receipt</button>}</div>
      {!!detail.payment_attempts?.length && <section><h3>Payment history</h3>{detail.payment_attempts.map(attempt => <article className="invoice-attempt" key={attempt.reference}><strong>{attempt.status}</strong><p className="invoice-number">{attempt.reference}</p><p>Expected: {money(attempt.amount)}{owner && attempt.received_amount !== null && <> · Provider reported: {attempt.received_currency} {attempt.received_amount}</>}</p>{attempt.note && <p>{attempt.note}</p>}{attempt.status !== 'success' && <button disabled={busy} onClick={() => verify(attempt.reference)}>Check payment</button>}</article>)}</section>}
    </section>}
  </section>;
}
