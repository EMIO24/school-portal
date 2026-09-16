import React, { useState } from 'react';
import api from '../../services/api';
import { useAuth } from '../../hooks/useAuth';
import { errorText } from './SchoolSignup';
import './Platform.css';

export default function PlatformMFA({ challenge, onCancel }) {
  const { finishLogin } = useAuth();
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  async function verify(e) {
    e.preventDefault(); setBusy(true); setError('');
    try {
      const { data } = await api.post('/api/platform/auth/verify/', { challenge: challenge.challenge, code: code.trim() });
      if (data.recovery_codes?.length) setResult(data); else finishLogin(data);
    } catch (err) { setError(errorText(err)); } finally { setBusy(false); }
  }
  if (result) return <main className="platform-page platform-signup"><h1>Save your recovery codes</h1>
    <p>Keep these in a password manager or another private place. Each code works once if you lose access to your authenticator. They will not be shown again.</p>
    <div className="platform-card"><ul>{result.recovery_codes.map(value => <li key={value}><code>{value}</code></li>)}</ul></div>
    <button onClick={() => finishLogin(result)}>I saved my codes - continue</button></main>;
  return <main className="platform-page platform-signup"><h1>{challenge.mfa_setup_required ? 'Set up two-factor authentication' : 'Verify your sign-in'}</h1>
    {challenge.mfa_setup_required ? <><ol><li>Open your authenticator app and add a time-based account.</li><li>Scan this QR code, or enter the setup key below into the authenticator app.</li><li>Enter the six-digit code from the app in the verification box below. Do not enter the long setup key there.</li></ol><p>If you already added this account but its codes are rejected, replace that authenticator entry by scanning the QR code shown here.</p>
      <img src={challenge.qr_code} alt="Authenticator setup QR code" style={{ width: 240, maxWidth: '100%' }} />
      <p>Setup key: <code>{challenge.secret}</code></p></> : <p>Enter the current six-digit authenticator code, or one unused recovery code.</p>}
    {error && <p role="alert" className="platform-error">{error}</p>}
    <p>Keep your phone's date and time set to automatic. If a code is about to expire, wait for the next one. Complete verification within five minutes; if sign-in expires, go back and sign in again.</p>
    <form onSubmit={verify} className="platform-form"><label>Verification code<input autoComplete="one-time-code" value={code} onChange={e => setCode(e.target.value)} required maxLength={32} inputMode={challenge.mfa_setup_required ? "numeric" : "text"} placeholder={challenge.mfa_setup_required ? "Six-digit code from your app" : "Authenticator or recovery code"} autoFocus /></label>
      <div className="platform-actions"><button disabled={busy}>Verify code</button><button type="button" disabled={busy} onClick={onCancel}>Back to sign in</button></div></form>
  </main>;
}
