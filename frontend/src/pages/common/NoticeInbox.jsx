import React, {useEffect, useState} from 'react';
import api from '../../services/api';
import '../admin/CommunicationCentre.css';

export default function NoticeInbox() {
  const [inbox, setInbox] = useState({results: [], next: null});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  async function load(url = '/api/communications/inbox/', append = false) {
    setLoading(true); setError('');
    try { const {data} = await api.get(url);
      setInbox(old => ({...data, results: append ? [...old.results, ...data.results] : data.results}));
    } catch { setError('Could not load notices. Check your connection and retry.'); }
    finally { setLoading(false); }
  }
  useEffect(() => { load(); }, []);
  async function open(row) {
    if (row.read_at) return;
    try { const {data} = await api.post(`/api/communications/inbox/${row.id}/read/`);
      setInbox(old => ({...old, results: old.results.map(item => item.id === row.id ? {...item, read_at: data.read_at} : item)}));
    } catch { setError('Could not mark the notice as opened. Retry.'); }
  }
  return <main className="communication-page"><header><span className="workspace-eyebrow">SCHOOL NOTICES</span><h1>Notices</h1>
    <p>Messages sent to your school portal account.</p></header>
    {error && <p role="alert" className="communication-error">{error} <button type="button" onClick={() => load()}>Retry</button></p>}
    {loading && <p role="status">Loading notices…</p>}
    {!loading && !inbox.results.length && <p>No notices for your account yet.</p>}
    <div className="communication-inbox">{inbox.results.map(row => <article className="communication-card" key={row.id}>
      <details onToggle={event => {if (event.currentTarget.open) open(row);}}><summary><strong>{row.title}</strong>
        <span>{row.read_at ? 'Opened' : 'Unread'} · {new Date(row.published_at).toLocaleString()}</span></summary>
        <p>{row.body}</p><small>From {row.sender_name}</small></details>
    </article>)}</div>
    {inbox.next && <button type="button" onClick={() => load(inbox.next, true)} disabled={loading}>Load more notices</button>}
  </main>;
}
