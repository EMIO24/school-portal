import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useAuth } from '../../hooks/useAuth';
import api from '../../services/api';
import { AdministratorFields, administratorData, errorText, SchoolCreationForm } from './SchoolSignup';
import './Platform.css';

const statusOf = school => school.approval_status !== 'approved' ? school.approval_status : school.is_active ? 'active' : 'suspended';

export default function PlatformDashboard() {
  const { user } = useAuth();
  const canManage = user?.platformAccess !== "viewer";
  const [data, setData] = useState(null);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('');
  const [plan, setPlan] = useState('');
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState(null);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const sequence = useRef(0);
  const panel = useRef(null);
  const invalidate = useCallback(() => { sequence.current++; }, []);
  useEffect(() => { panel.current?.scrollIntoView?.({ behavior: "smooth", block: "start" }); }, [selected?.id, creating]);
  const load = useCallback(async () => {
    const id = ++sequence.current;
    setLoading(true);
    try {
      const response = await api.get('/api/platform/schools/?' + new URLSearchParams({ search, status, plan, page }));
      if (id === sequence.current) { setData(response.data); setError(''); }
    } catch (err) { if (id === sequence.current) setError(errorText(err)); }
    finally { if (id === sequence.current) setLoading(false); }
  }, [search, status, plan, page]);
  useEffect(() => { const timer = setTimeout(load, 200); return () => { clearTimeout(timer); invalidate(); }; }, [load, invalidate]);
  async function open(school) {
    setBusy(true); setError(''); setNotice(''); setSelected(null); setCreating(false);
    try { const response = await api.get('/api/platform/schools/' + school.id + '/'); setSelected(response.data); }
    catch (err) { setError(errorText(err)); } finally { setBusy(false); }
  }
  async function mutate(method, suffix, payload, message) {
    setBusy(true); setError(''); setNotice('');
    try {
      const response = await api[method]('/api/platform/schools/' + selected.id + '/' + suffix, payload);
      setSelected(response.data); setNotice(message); await load(); return true;
    } catch (err) { setError(errorText(err)); return false; } finally { setBusy(false); }
  }
  async function saveDetails(e) {
    e.preventDefault(); const values = Object.fromEntries(new FormData(e.currentTarget));
    values.subscription_ends_on = values.subscription_ends_on || null;
    await mutate('patch', '', values, 'School details saved.');
  }
  async function addAdmin(e) {
    e.preventDefault(); const form = e.currentTarget; let values;
    try { values = administratorData(new FormData(form)); } catch (err) { setError(err.message); return; }
    if (await mutate('post', 'administrators/', values, 'Administrator created. Share the temporary credentials securely.')) form.reset();
  }
  async function changeStatus(action) {
    if (['suspend', 'reject'].includes(action) && !window.confirm(action === 'suspend'
      ? 'Suspend access for everyone in ' + selected.name + '? School records will be kept.'
      : 'Reject the registration for ' + selected.name + '?')) return;
    await mutate('post', '', { action }, 'School access updated.');
  }
  return <main className="platform-page">
    <div className="platform-heading"><div><h1>Manage schools</h1><p>School registrations, administrators, subscriptions and usage.</p></div>
      <button disabled={busy || !canManage} onClick={() => { setCreating(true); setSelected(null); setNotice(''); }}>Create school</button></div>
    <p><a href="/register-school">Public school registration</a></p>
    {data && <div className="platform-summary">{Object.entries(data.summary).map(([label, value]) => <div className="platform-card" key={label}><strong>{value}</strong><span>{label}</span></div>)}</div>}
    {error && <div className="platform-error" role="alert">{error} <button disabled={loading || busy} onClick={load}>Retry school list</button></div>}
    {notice && <p role="status" className="platform-notice">{notice}</p>}
    <div className="platform-filters">
      <label>Search schools<input type="search" value={search} onChange={e => { setSearch(e.target.value); setPage(1); }} /></label>
      <label>Status<select value={status} onChange={e => { setStatus(e.target.value); setPage(1); }}><option value="">All statuses</option>{['pending','active','suspended','rejected'].map(v => <option key={v}>{v}</option>)}</select></label>
      <label>Plan<select value={plan} onChange={e => { setPlan(e.target.value); setPage(1); }}><option value="">All plans</option>{['free','basic','premium','enterprise'].map(v => <option key={v}>{v}</option>)}</select></label>
    </div>
    {loading && <p role="status">Loading schools...</p>}
    {!loading && data?.results.length === 0 && <p>No schools match these filters.</p>}
    <div className="platform-schools" aria-busy={loading}>{data?.results.map(school => <article className="platform-card" key={school.id}>
      <div className="platform-heading"><h2>{school.name}</h2><span className={'platform-status status-' + statusOf(school)}>{statusOf(school)}</span></div>
      <p>{school.subdomain} | {school.subscription_plan}</p>
      <p>{school.usage.student_count} student accounts ? {school.usage.teacher_count} teacher accounts ? {school.usage.admin_count} administrators</p>
      <button disabled={busy} onClick={() => open(school)}>Manage {school.name}</button>
    </article>)}</div>
    {data && <div className="platform-actions"><button disabled={page === 1 || loading} onClick={() => setPage(p => p - 1)}>Previous</button><span>Page {page} | {data.count} schools</span><button disabled={page * 20 >= data.count || loading} onClick={() => setPage(p => p + 1)}>Next</button></div>}
    {creating && <section ref={panel} className="platform-card"><div className="platform-heading"><h2>Create a school</h2><button onClick={() => setCreating(false)}>Close</button></div>
      <SchoolCreationForm owner onCreated={school => { setCreating(false); setSelected(school); setNotice('School and administrator created. Share the temporary credentials securely.'); load(); }} />
    </section>}
    {selected && <section ref={panel} className="platform-card" aria-label="School management"><div className="platform-heading"><h2>{selected.name}</h2><button disabled={busy} onClick={() => setSelected(null)}>Close school details</button></div>
      <p>Status: <strong>{statusOf(selected)}</strong> | <a href={'/login?school=' + encodeURIComponent(selected.subdomain)}>School login link</a></p>
      {selected.setup && <div><h3>Setup readiness</h3><ul>{Object.entries(selected.setup).map(([item,ready])=><li key={item}>{ready?'✓':'○'} {item.replaceAll('_',' ')}</li>)}</ul></div>}
      <div className="platform-actions">{(selected.approval_status === 'pending' ? ['approve','reject'] : selected.approval_status === 'approved' ? [selected.is_active ? 'suspend' : 'activate'] : []).map(action => <button disabled={busy || !canManage} key={action} onClick={() => changeStatus(action)}>{action[0].toUpperCase() + action.slice(1)} school</button>)}</div>
      <form onSubmit={saveDetails} key={selected.id + ':' + selected.activity.length} className="platform-form"><fieldset disabled={busy || !canManage}><legend>School details and subscription</legend><div className="platform-grid">
        <label>School name<input name="name" required defaultValue={selected.name} maxLength={255} /></label>
        <label>Contact email<input name="email" type="email" defaultValue={selected.email} /></label>
        <label>Phone<input name="phone" defaultValue={selected.phone} maxLength={20} /></label>
        <label>Address<textarea name="address" defaultValue={selected.address} /></label>
        <label>Subscription plan<select name="subscription_plan" defaultValue={selected.subscription_plan}>{['free','basic','premium','enterprise'].map(v => <option key={v}>{v}</option>)}</select></label>
        <label>Renewal date<input name="subscription_ends_on" type="date" defaultValue={selected.subscription_ends_on || ''} /></label>
        <label>Owner notes<textarea name="platform_notes" defaultValue={selected.platform_notes} /></label>
      </div><p>The assigned plan activates its included features immediately. This manual change does not collect payment. Renewal dates remain owner-managed; use Payments for Paystack renewals.</p><button type="submit">Save school details</button></fieldset></form>
      <p><a href={"/superadmin/appearance?school="+selected.id}>Customise portal design and plan features</a></p><h3>School administrators</h3><ul className="platform-admins">{selected.administrators.map(admin => <li key={admin.id}><span>{admin.first_name} {admin.last_name} | {admin.email} | {admin.is_active ? 'active' : 'disabled'}</span><button disabled={busy || !canManage} onClick={() => mutate('patch', 'administrators/', { id: admin.id, is_active: !admin.is_active }, 'Administrator access updated.')}>{admin.is_active ? 'Disable' : 'Enable'} {admin.email}</button></li>)}</ul>
      {canManage && <details><summary>Add an administrator</summary><form onSubmit={addAdmin} className="platform-form"><fieldset disabled={busy || !canManage}><legend>New administrator</legend><AdministratorFields /><p>The administrator must change this temporary password on first login.</p><button type="submit">Add administrator</button></fieldset></form></details>}
      <h3>Recent activity</h3><ul>{selected.activity.map((event, i) => <li key={i}>{event.action} | {new Date(event.created_at).toLocaleString()} | {event.actor__email || 'School applicant'}</li>)}</ul>
    </section>}
  </main>;
}
