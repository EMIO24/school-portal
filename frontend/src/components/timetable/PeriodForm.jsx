import React, { useEffect, useState } from 'react';
import api from '../../services/api';

export default function PeriodForm({ onSaved, onCancel }) {
  const [form, setForm] = useState({ name: '', start_time: '', end_time: '', order_index: 1, is_break: false });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        let url = '/api/timetable/periods/';
        let maxOrder = 0;
        while (url) {
          const { data } = await api.get(url);
          const rows = Array.isArray(data) ? data : data.results || [];
          maxOrder = Math.max(maxOrder, ...rows.map(period => period.order_index));
          url = Array.isArray(data) ? null : data.next;
        }
        if (active) setForm(prev => ({ ...prev, order_index: maxOrder + 1 }));
      } catch {
        if (active) { setLoadError(true); setError('Could not load existing periods. Close this form and try again.'); }
      } finally { if (active) setLoading(false); }
    }
    load();
    return () => { active = false; };
  }, []);

  async function save(event) {
    event.preventDefault();
    setError('');
    if (!form.name.trim()) { setError('Enter a period name.'); return; }
    if (form.end_time <= form.start_time) { setError('End time must be after start time.'); return; }
    setSaving(true);
    let period;
    try {
      const { data } = await api.post('/api/timetable/periods/', {
        ...form, name: form.name.trim(), order_index: Number(form.order_index),
      });
      period = data;
    } catch (err) {
      const data = err.response?.data;
      setError(data && typeof data === 'object' ?
        Object.entries(data).map(([key, value]) => key + ': ' + (Array.isArray(value) ? value.join(' ') : String(value))).join(' ') :
        'Could not save the period. Please try again.');
      setSaving(false);
      return;
    }
    onSaved(period);
  }

  function input(key, label, type, extra = {}) {
    return <div className="tt-field">
      <label htmlFor={'period-' + key}>{label}</label>
      <input id={'period-' + key} type={type} required value={form[key]}
        onChange={event => setForm(prev => ({ ...prev, [key]: event.target.value }))} {...extra} />
    </div>;
  }

  return <section className="tt-period-form" aria-labelledby="period-form-title">
    <h2 id="period-form-title">Add Period</h2>
    <p>Periods apply to every class and term in this school. Mark lunch or assembly as a break to prevent lesson bookings.</p>
    {error && <p role="alert" className="tt-modal__error">{error}</p>}
    {loading && <p role="status">Loading periods...</p>}
    <form onSubmit={save}>
      <fieldset disabled={loading || saving || loadError}>
        <div className="tt-period-fields">
          {input('name', 'Period name', 'text', { maxLength: 50, autoFocus: true })}
          {input('start_time', 'Start time', 'time')}
          {input('end_time', 'End time', 'time')}
          {input('order_index', 'Display order', 'number', { min: 0, max: 32767, step: 1 })}
        </div>
        <label><input type="checkbox" checked={form.is_break}
          onChange={event => setForm(prev => ({ ...prev, is_break: event.target.checked }))} /> Break (no lessons)</label>
      </fieldset>
      <div className="tt-modal__actions">
        <button type="button" className="tt-btn tt-btn--ghost" disabled={saving} onClick={onCancel}>Cancel</button>
        <button type="submit" className="tt-btn tt-btn--primary" disabled={loading || saving || loadError}>{saving ? 'Saving...' : 'Save Period'}</button>
      </div>
    </form>
  </section>;
}