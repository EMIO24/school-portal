import React, { useState } from 'react';
import api from '../../services/api';
import './Platform.css';

export function errorText(error) {
  const data = error.response?.data;
  function flatten(value, prefix = '') {
    if (Array.isArray(value)) return value.map(v => flatten(v, prefix)).join(' ');
    if (value && typeof value === 'object') return Object.entries(value).map(([k,v]) => flatten(v, k.replaceAll('_', ' ') + ': ')).join(' ');
    return prefix + String(value);
  }
  return data ? flatten(data) : 'Could not connect. Please try again.';
}

export function AdministratorFields() {
  return <div className="platform-grid">
    <label>Administrator first name<input name="first_name" required maxLength={150} autoComplete="given-name" /></label>
    <label>Administrator last name<input name="last_name" required maxLength={150} autoComplete="family-name" /></label>
    <label>Administrator email<input name="admin_email" type="email" required autoComplete="email" /></label>
    <label>Administrator password<input name="password" type="password" required minLength={8} maxLength={128} autoComplete="new-password" /></label>
    <label>Confirm password<input name="confirm_password" type="password" required minLength={8} autoComplete="new-password" /></label>
  </div>;
}

export function administratorData(form) {
  if (form.get('password') !== form.get('confirm_password')) throw new Error('Passwords do not match.');
  return { first_name: form.get('first_name'), last_name: form.get('last_name'), email: form.get('admin_email'), password: form.get('password') };
}

export function SchoolCreationForm({ owner = false, onCreated }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function submit(e) {
    e.preventDefault(); setError('');
    const form = e.currentTarget;
    const values = new FormData(form);
    let administrator;
    try { administrator = administratorData(values); } catch (err) { setError(err.message); return; }
    setBusy(true);
    try {
      const { data } = await api.post(owner ? '/api/platform/schools/' : '/api/platform/register/', {
        name: values.get('name'), subdomain: values.get('subdomain'), email: values.get('email'),
        phone: values.get('phone'), address: values.get('address'), administrator,
      });
      form.reset(); onCreated(data);
    } catch (err) { setError(errorText(err)); } finally { setBusy(false); }
  }
  return <form onSubmit={submit} className="platform-form">
    {error && <p role="alert" className="platform-error">{error}</p>}
    <fieldset disabled={busy}><legend>School details</legend><div className="platform-grid">
      <label>School name<input name="name" required maxLength={255} /></label>
      <label>School identifier<input name="subdomain" required maxLength={63} pattern="[a-z0-9]+(-[a-z0-9]+)*" placeholder="greenfield-school" /><small>Lowercase letters, numbers and hyphens. Used for your school login.</small></label>
      <label>School contact email<input name="email" type="email" required /></label>
      <label>School phone<input name="phone" type="tel" maxLength={20} /></label>
      <label>School address<textarea name="address" maxLength={2000} /></label>
    </div></fieldset>
    <fieldset disabled={busy}><legend>First school administrator</legend>
      <AdministratorFields />
      <p>{owner ? 'Share these credentials with the administrator securely. They must change this temporary password on first login.' : 'Choose a strong password. You can sign in after the platform owner approves your school.'}</p>
    </fieldset>
    <button disabled={busy} type="submit">{busy ? 'Saving...' : owner ? 'Create school and administrator' : 'Submit school registration'}</button>
  </form>;
}

export default function SchoolSignup() {
  const [submitted, setSubmitted] = useState(null);
  return <main className="platform-page platform-signup">
    <a href="/login">Back to sign in</a><h1>Register your school</h1>
    <p>Create a separate portal for your school. Your registration will be reviewed before access is enabled.</p>
    {submitted ? <section className="platform-card" role="status"><h2>Registration submitted</h2>
      <p>Your school identifier is <strong>{submitted.subdomain}</strong>. Contact the platform owner for approval; no email has been sent automatically.</p>
      <a href={'/login?school=' + encodeURIComponent(submitted.subdomain)}>School sign in</a>
    </section> : <SchoolCreationForm onCreated={setSubmitted} />}
  </main>;
}
