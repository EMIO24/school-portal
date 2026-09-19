import React, { useCallback, useEffect, useState } from 'react';
import api from '../../services/api';
import { useAuth } from '../../hooks/useAuth';
import { AdministratorFields, administratorData, errorText } from './SchoolSignup';
import './Platform.css';

export default function PlatformTeam() {
  const { user } = useAuth();
  const [accounts, setAccounts] = useState([]);
  const [events, setEvents] = useState({ count: 0, results: [] });
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const owner = user?.platformAccess !== 'viewer';
  const load = useCallback(async () => {
    try { const [a, e] = await Promise.all([api.get('/api/platform/accounts/'), api.get('/api/platform/audit/?' + new URLSearchParams({ page, search }))]); setAccounts(a.data); setEvents(e.data); setError(''); }
    catch (err) { setError(errorText(err)); }
  }, [page, search]);
  useEffect(() => { if (owner) load(); }, [load, owner]);
  async function create(e) {
    e.preventDefault(); const form=e.currentTarget; const data=new FormData(form); let values;
    try { values = administratorData(data); } catch(err) { setError(err.message); return; }
    setBusy(true); setNotice('');
    try { await api.post('/api/platform/accounts/', { ...values, access_level: data.get('access_level') }); form.reset(); setNotice('Account created. Share the temporary password securely; the user must set up their own authenticator.'); await load(); }
    catch(err) { setError(errorText(err)); } finally { setBusy(false); }
  }
  async function toggle(account) {
    if (!window.confirm((account.is_active ? 'Disable ' : 'Enable ') + account.email + '? Previous sessions will be revoked.')) return;
    setBusy(true);
    try { await api.patch('/api/platform/accounts/', { id: account.id, is_active: !account.is_active }); await load(); }
    catch(err) { setError(errorText(err)); } finally { setBusy(false); }
  }
  if (!owner) return <main className="platform-page"><h1>Owner access required</h1><p>Your account can view school information. Only owners can manage platform accounts and audit records.</p></main>;
  return <main className="platform-page"><h1>Platform staff and activity</h1><p>Give each person their own login. Owner accounts can change schools; read-only accounts can inspect school information.</p>
    {error && <p role="alert" className="platform-error">{error} <button onClick={load}>Retry</button></p>}{notice && <p role="status">{notice}</p>}
    <section className="platform-card"><h2>Platform accounts</h2><ul className="platform-admins">{accounts.map(a => <li key={a.id}><span>{a.email} | {a.access_level} | {a.is_active ? 'active' : 'disabled'} | {a.mfa_enabled ? '2FA enabled' : '2FA setup required'}</span><button disabled={busy || a.id === user.id} onClick={() => toggle(a)}>{a.is_active ? 'Disable' : 'Enable'} {a.email}</button></li>)}</ul>
      <details><summary>Create a platform account</summary><form onSubmit={create} className="platform-form"><fieldset disabled={busy}><legend>New platform account</legend><AdministratorFields /><label>Access level<select name="access_level" defaultValue="viewer"><option value="viewer">Read only - view schools</option><option value="owner">Owner - manage schools and platform staff</option></select></label><p>This account has no school. Two-factor authentication is required before access is granted.</p><button>Create platform account</button></fieldset></form></details></section>
    <section className="platform-card"><h2>Activity records</h2><label>Search activity<input type="search" value={search} onChange={e => { setSearch(e.target.value); setPage(1); }} /></label>
      {events.results.length === 0 && <p>No matching activity.</p>}
      {events.results.map(event => <article className="platform-card" key={event.id}><strong>{event.action}</strong><p>{event.actor_email || 'Public applicant'} | {new Date(event.created_at).toLocaleString()} | Target: {event.target || '-'} | IP: {event.ip_address || '-'}</p><dl>{Object.entries(event.details).map(([key,value]) => <React.Fragment key={key}><dt>{key.replaceAll('_',' ')}</dt><dd>{typeof value === 'object' ? 'Before: ' + value.before + ' / After: ' + value.after : String(value)}</dd></React.Fragment>)}</dl></article>)}
      <div className="platform-actions"><button disabled={page===1} onClick={() => setPage(p=>p-1)}>Previous</button><span>Page {page} | {events.count} events</span><button disabled={page*30>=events.count} onClick={() => setPage(p=>p+1)}>Next</button></div></section></main>;
}
