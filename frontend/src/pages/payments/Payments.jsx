import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../../services/api';
import { useAuth } from '../../hooks/useAuth';
import './Payments.css';
const money = value => new Intl.NumberFormat('en-NG', {style:'currency', currency:'NGN'}).format(value);
const message = e => e.response?.data?.error || e.response?.data?.detail || (Array.isArray(e.response?.data) ? e.response.data.join(' ') : 'Unable to complete this request. Please try again.');
function OrderList({orders = [], onVerify, onRetry}) {
  return <div className="payment-orders">{orders.map(o => <article key={o.reference}><strong>{money(o.amount)} - {o.kind}</strong><p>{o.status}{o.school_id ? ' / School ' + o.school_id : ''}</p><code>{o.reference}</code>{onVerify && o.status !== "success" && <p><button onClick={() => onVerify(o.reference)}>Verify with Paystack</button></p>}{onRetry && ["initializing", "pending"].includes(o.status) && <button onClick={() => onRetry(o.reference)}>Reopen existing checkout</button>}{o.note && <p>{o.note}</p>}{o.status !== 'success' && !o.school_id && <p><Link to={'/payments/return?reference=' + encodeURIComponent(o.reference)}>Check payment status</Link></p>}</article>)}</div>;
}
export function PaymentReturn() {
  const {isAuthenticated, isLoading} = useAuth();
  const [result, setResult] = useState(null), [error, setError] = useState(''), [busy, setBusy] = useState(false);
  const reference = new URLSearchParams(window.location.search).get('reference') || '';
  const verify = async () => {setBusy(true); setError(''); try {setResult((await api.get('/api/fees/pay/verify/', {params:{reference}})).data);} catch(e) {setError(message(e));} finally {setBusy(false);}};
  useEffect(() => {if (isAuthenticated && reference) {verify(); sessionStorage.removeItem('payment_return');} /* verification is idempotent */ // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated, reference]);
  if (isLoading) return <main className="payments-page">Restoring your session...</main>;
  return <main className="payments-page"><h1>Payment status</h1><p>Reference: <code>{reference || 'Missing reference'}</code></p>
    {!isAuthenticated ? <><p>Sign in with the account that started this payment to verify it.</p><Link to="/login" onClick={() => sessionStorage.setItem('payment_return', window.location.pathname + window.location.search)}>Sign in</Link></> : <>
    {error && <p role="alert">{error}</p>}{result && <><h2>{result.status === 'success' ? 'Payment verified' : 'Payment ' + result.status}</h2><p>{money(result.amount)} / {result.kind}</p><p>{result.note || (result.status !== 'success' ? 'If you have paid, wait a moment and check again. Do not pay again while verification is pending.' : 'Your account has been updated.')}</p>{result.receipts?.map(r => <button key={r.id} onClick={async () => {try {const response = await api.get('/api/fees/receipts/' + r.id + '/', {responseType:'blob'}); const url=URL.createObjectURL(response.data); const a=document.createElement('a'); a.href=url; a.download=r.receipt_number+'.pdf'; a.click(); setTimeout(() => URL.revokeObjectURL(url), 10000);} catch(e) {setError(message(e));}}}>Download receipt PDF</button>)}</>}
    <button disabled={busy || !reference} onClick={verify}>{busy ? 'Checking...' : 'Check again'}</button><p><Link to="/">Return to dashboard</Link></p></>}
  </main>;
}
export function Subscription() {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get('/api/fees/subscription/').then(r => setData(r.data)).catch(e => setError(message(e)));
  }, []);

  const pay = async plan => {
    setBusy(true);
    setError('');
    try {
      const response = await api.post('/api/fees/subscription/', {plan});
      window.location.assign(response.data.authorization_url);
    } catch (e) {
      setError(message(e) + (e.response?.data?.reference ? ' Reference: ' + e.response.data.reference : ''));
      setBusy(false);
    }
  };

  const schoolStudentCount = data?.school_student_count ?? 0;

  return (
    <main className="payments-page">
      <h1>Portal subscription</h1>
      <p>Pay per student per term. Renewals are manual; your card is not automatically charged. SMS usage is billed separately by arrangement with the platform owner.</p>
      {error && <p role="alert">{error}</p>}
      {data && (
        <>
          <p>Current plan: {data.plan}. Paid through: {data.ends_on || 'No paid period'}.</p>
          <div className="payment-summary">
            <h2>School size summary</h2>
            <p>{data.school_size_summary}</p>
            <p>Active students: <strong>{schoolStudentCount}</strong></p>
            {schoolStudentCount >= 100 ? <p><strong>10% discount is active.</strong></p> : <p>100+ active students unlock a 10% discount.</p>}
          </div>
          <div className="payment-cards">
            {data.offers.map(o => (
              <article key={o.plan}>
                <h2>{o.plan}</h2>
                <ul>{(data.features?.[o.plan] || []).map(f => <li key={f}>{data.feature_labels?.[f] || f}</li>)}</ul>
                {o.discount_applied ? <p><strong>10% off</strong> for schools with 100+ active students.</p> : <p>No discount yet.</p>}
                <p>{money(o.amount)} per student per term</p>
                <p>Term length: {o.months} months</p>
                <p><strong>Total for this school:</strong> {money(o.total_amount ?? (schoolStudentCount * Number(o.amount) * (o.discount_applied ? 0.9 : 1)))}</p>
                <button disabled={busy} onClick={() => pay(o.plan)}>Pay with Paystack</button>
              </article>
            ))}
          </div>
          <h2>Payment history</h2>
          <OrderList orders={data.orders}/>
        </>
      )}
    </main>
  );
}
export function PlatformPayments() {
  const {user}=useAuth(); const [data,setData]=useState(null), [schools,setSchools]=useState([]), [error,setError]=useState(''), [notice,setNotice]=useState(''), [busy,setBusy]=useState(false);
  const load=async () => {try {const p=await api.get('/api/platform/payments/');setData(p.data);setSchools(p.data.schools || []);}catch(e){setError(message(e));}};
  useEffect(() => {if(user?.platformAccess !== "viewer") load();}, [user?.platformAccess]); // eslint-disable-line react-hooks/exhaustive-deps
  const submit=async (e, url, values) => {e.preventDefault();setBusy(true);setError('');setNotice('');try {await api.post(url,values);setNotice('Saved successfully.');await load();}catch(e){setError(message(e));}finally{setBusy(false);}};
  if(user?.platformAccess === 'viewer') return <main className="payments-page"><h1>Payments</h1><p>Only platform owners can manage payment settings.</p></main>;
  return <main className="payments-page"><h1>Payments and subscriptions</h1>{error && <p role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}{data && <><p>Paystack mode: <strong>{data.mode}</strong>. {data.configured ? 'Secret key configured.' : 'Paystack is not configured. Set the backend secret key before testing checkout.'}</p><h2>Subscription prices</h2><p>Changes apply to new checkouts. Existing pending payments keep their original price and period.</p><div className="payment-cards">{data.offers.map(o => <form key={o.plan + o.amount + o.months + o.enabled} onSubmit={e => {const f=new FormData(e.currentTarget);submit(e,'/api/platform/payments/',{plan:o.plan,amount:f.get('amount'),months:Number(f.get('months')),enabled:f.get('enabled')==='on'});}}><h3>{o.plan}</h3><label>Price (NGN)<input name="amount" type="number" min="100" step="0.01" defaultValue={o.amount} required/></label><label>Months per payment<input name="months" type="number" min="1" max="12" defaultValue={o.months} required/></label><label><input name="enabled" type="checkbox" defaultChecked={o.enabled}/> Available to schools</label><button disabled={busy}>Save price</button></form>)}</div>
  <h2>School settlement accounts</h2><p>Create each school's subaccount in your Paystack dashboard. Confirm its bank details there, then connect its ACCT code here. School fee payments go to that school, less Paystack charges; the portal takes no commission. Subscription payments go to your platform account.</p>
  <form onSubmit={e => {const f=new FormData(e.currentTarget);submit(e,'/api/platform/schools/'+f.get('school')+'/payments/',{subaccount_code:f.get('code')});}}><label>School<select name="school" required defaultValue=""><option value="" disabled>Select school</option>{schools.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label><label>Paystack subaccount code<input name="code" placeholder="ACCT_..." required pattern="ACCT_.+"/></label><button disabled={busy}>Verify and connect account</button></form>
  {data.accounts.map(a => <p key={a.school_id}>{schools.find(s => s.id===a.school_id)?.name || a.school_id}: {a.business_name} / {a.bank_name} / ending {a.account_last_four}</p>)}<h2>Recent payments</h2><OrderList orders={data.orders} onRetry={async reference => {try {const r = await api.post("/api/platform/payments/", {reference,action:"retry_checkout"}); setNotice("Existing checkout: " + r.data.authorization_url); await load();} catch(e) {setError(message(e));}}} onVerify={async reference => {try {const r = await api.post("/api/platform/payments/", {reference});setNotice("Payment status: " + r.data.status);await load();} catch(e) {setError(message(e));}}}/></>}</main>;
}
