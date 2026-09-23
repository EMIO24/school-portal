import React, {useEffect, useState} from 'react';
import api from '../../services/api';
import './Platform.css';

export default function DemoRequests() {
  const [requests, setRequests] = useState([]); const [error, setError] = useState('');
  useEffect(() => {api.get('/api/platform/demo-requests/').then(r => setRequests(r.data)).catch(() => setError('Unable to load demo requests.'));}, []);
  return <main className="platform-page"><h1>Demo requests</h1>{error && <p role="alert">{error}</p>}<div className="platform-table-wrap"><table><thead><tr><th>School</th><th>Contact</th><th>Students</th><th>Location</th><th>Requested</th><th>Requirements</th></tr></thead><tbody>{requests.map(item => <tr key={item.id}><td>{item.school_name}</td><td>{item.contact_name}<br/><a href={'mailto:'+item.email}>{item.email}</a><br/>{item.phone}</td><td>{item.student_population}</td><td>{item.location}</td><td>{new Date(item.created_at).toLocaleDateString()}</td><td>{item.message || '—'}</td></tr>)}{!requests.length && <tr><td colSpan="6">No demo requests yet.</td></tr>}</tbody></table></div></main>;
}
