import React, { useState } from 'react';
import api from '../../services/api';

const base = '/api/platform/payment-exceptions/';
const kinds = ['refund', 'duplicate', 'incorrect', 'provider', 'manual'];
const states = ['requested', 'under_review', 'approved', 'rejected', 'provider_pending', 'provider_failed', 'resolved'];
const label = value => value.replaceAll('_', ' ');

export default function PaymentExceptions() {
  const [opened, setOpened] = useState(false), [rows, setRows] = useState([]), [next, setNext] = useState(null);
  const [selected, setSelected] = useState(null), [filters, setFilters] = useState({ status: '', kind: '', reference: '' });
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  async function perform(action) {
    setBusy(true); setError('');
    try { await action(); } catch (e) {
      const data = e.response?.data;
      setError(data?.detail || (Array.isArray(data) ? data.join(' ') : 'Unable to save or load the case. Reload and check the fields.'));
    } finally { setBusy(false); }
  }
  async function load(before) {
    const { data } = await api.get(base, { params: { ...filters, ...(before ? { before } : {}) } });
    setRows(data.results); setNext(data.next_before);
  }
  const transitions = selected?.kind === 'refund'
    ? { requested: ['under_review'], under_review: ['approved', 'rejected'], approved: ['provider_pending'], provider_pending: ['provider_failed', 'resolved'], provider_failed: ['provider_pending'] }
    : { requested: ['under_review'], under_review: ['resolved'] };
  const terminal = selected && ['resolved', 'rejected'].includes(selected.status);
  return <section><h2>Payment exceptions and refund requests</h2>
    <p>Recording or approving a case does not send money or change fee balances or subscriptions. Do not enter card details, passwords or secrets.</p>
    <button disabled={busy} onClick={() => perform(async () => { setOpened(true); await load(); })}>Open exception operations</button>
    {error && <p role="alert">{error}</p>}
    {opened && <>
      <form onSubmit={e => { e.preventDefault(); perform(() => load()); }}>
        <label>Case status<select value={filters.status} onChange={e => setFilters({ ...filters, status: e.target.value })}><option value="">All</option>{states.map(s => <option key={s}>{s}</option>)}</select></label>
        <label>Case type<select value={filters.kind} onChange={e => setFilters({ ...filters, kind: e.target.value })}><option value="">All</option>{kinds.map(s => <option key={s}>{s}</option>)}</select></label>
        <label>Payment reference filter<input value={filters.reference} onChange={e => setFilters({ ...filters, reference: e.target.value })}/></label><button disabled={busy}>Filter cases</button>
      </form>
      <form onSubmit={e => { e.preventDefault(); const f = new FormData(e.currentTarget); perform(async () => { const { data } = await api.post(base, { reference: f.get('reference'), kind: f.get('kind'), reason: f.get('reason') }); setSelected(null); await load(); setSelected((await api.get(base + data.id + '/')).data); }); }}>
        <h3>Report a payment exception</h3><label>Payment reference<input name="reference" maxLength="100" required/></label>
        <label>Report type<select name="kind">{kinds.map(s => <option key={s}>{s}</option>)}</select></label>
        <label>Reason<textarea name="reason" maxLength="2000" required/></label><button disabled={busy}>Create case</button>
      </form>
      {rows.map(row => <p key={row.id}>#{row.id} / School {row.school_id} / {row.reference} / {row.kind} / {label(row.status)} <button disabled={busy} onClick={() => perform(async () => setSelected((await api.get(base + row.id + '/')).data))}>Inspect case {row.id}</button></p>)}
      {next && <button disabled={busy} onClick={() => perform(() => load(next))}>Older cases</button>}
      {selected && <article><h3>Case {selected.id}: {label(selected.status)}</h3><p>{selected.reason}</p>
        <p>Payment {selected.reference}: {selected.payment.amount} {selected.payment.currency}; {selected.payment.kind}; local status {selected.payment.status}; {selected.payment.mode} mode.</p>
        <p>Payer #{selected.payment.payer_id}; student #{selected.payment.student_id || '-'}; provider transaction {selected.payment.provider_id || 'Not recorded'}; created {selected.payment.created_at}; paid {selected.payment.paid_at || 'Not recorded'}.</p>
        <p>Plan: {selected.payment.plan || '-'}; fee allocations: {selected.payment.allocations.map(a => a.schedule_id).join(', ') || '-'}</p>
        <p>Latest internal note: {selected.admin_notes || 'None'}</p>
        {!terminal && <form key={selected.id + selected.updated_at} onSubmit={e => { e.preventDefault(); const f = new FormData(e.currentTarget); perform(async () => { const { data } = await api.patch(base + selected.id + '/', { expected_status: selected.status, status: f.get('status'), admin_notes: f.get('admin_notes'), provider_ref: f.get('provider_ref') }); setSelected(data); await load(); }); }}>
          <label>Next case state<select name="status"><option value={selected.status}>Save investigation note</option>{(transitions[selected.status] || []).map(s => <option key={s} value={s}>{label(s)}</option>)}</select></label>
          <label>Internal investigation note<textarea name="admin_notes" maxLength="2000" required/></label>
          <label>Confirmed provider refund reference<input name="provider_ref" maxLength="100"/></label>
          <p>Only use this reference when resolving a refund after independently confirming manual provider completion. For discrepancies, use the existing payment reconciliation controls; unavailable verification does not prove a refund.</p>
          <button disabled={busy}>Record case update</button>
        </form>}
        <h4>Case history</h4>{selected.history?.map((event, i) => <p key={i}>{event.created_at} / Actor #{event.actor_id}: {event.details.previous_status || 'new'} → {event.details.status}. {event.details.admin_notes} {event.details.provider_ref}</p>)}
      </article>}
    </>}
  </section>;
}
