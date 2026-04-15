/**
 * frontend/src/pages/admin/ScratchCards.jsx
 *
 * Admin scratch card management:
 *   - Generate batch form (quantity, batch name, term, price)
 *   - Batch table: name | total | used | unused | generated date
 *   - Download unused serials CSV per batch
 */

import React, { useState, useEffect, useCallback } from 'react';
import api from '../../services/api';

// ── Styles (inline — minimal, reuses global variables) ────────────────────────
const S = {
  page:    { padding: '28px 32px', maxWidth: 900, margin: '0 auto' },
  title:   { fontSize: '1.35rem', fontWeight: 700, color: 'var(--color-primary)', marginBottom: 4 },
  sub:     { fontSize: '.82rem', color: '#6b7280', marginBottom: 28 },
  card:    { background: '#fff', border: '1px solid #e5e7eb', borderRadius: 10, marginBottom: 24, overflow: 'hidden' },
  cardHead:{ padding: '14px 20px', borderBottom: '1px solid #e5e7eb', display: 'flex', alignItems: 'center', justifyContent: 'space-between' },
  cardTitle:{ fontWeight: 700, fontSize: '1rem', color: 'var(--color-primary)' },
  cardBody:{ padding: 20 },
  grid:    { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 14 },
  field:   { display: 'flex', flexDirection: 'column', gap: 5 },
  label:   { fontSize: '.72rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.06em', color: '#374151' },
  input:   { padding: '9px 12px', border: '1.5px solid #d1d5db', borderRadius: 7, fontSize: '.9rem', color: '#111' },
  btn:     { padding: '10px 20px', border: 'none', borderRadius: 7, fontWeight: 700, fontSize: '.88rem', cursor: 'pointer' },
  table:   { width: '100%', borderCollapse: 'collapse', fontSize: '.86rem' },
  th:      { background: '#0c1c40', color: '#e8eef8', padding: '9px 14px', textAlign: 'left', fontWeight: 600, fontSize: '.76rem', textTransform: 'uppercase', letterSpacing: '.05em' },
  td:      { padding: '10px 14px', borderBottom: '1px solid #f3f4f6' },
  alert:   { padding: '10px 14px', borderRadius: 7, fontSize: '.85rem', marginBottom: 14, fontWeight: 500 },
};

function pct(used, total) {
  if (!total) return '0%';
  return `${Math.round((used / total) * 100)}%`;
}

export default function ScratchCards() {
  const [terms,      setTerms]      = useState([]);
  const [batches,    setBatches]    = useState([]);
  const [loading,    setLoading]    = useState(false);
  const [generating, setGenerating] = useState(false);
  const [alert,      setAlert]      = useState(null);

  const [form, setForm] = useState({
    quantity:   50,
    batch_name: '',
    term_id:    '',
    price:      '200',
  });

  // ── Boot ────────────────────────────────────────────────────────────────────
  useEffect(() => {
    api.get('/academics/terms/').then(({ data }) => {
      const list = data.results ?? data;
      setTerms(list);
      const cur = list.find(t => t.is_current);
      if (cur) setForm(f => ({ ...f, term_id: String(cur.id) }));
    });
    loadBatches();
  }, []);

  const loadBatches = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get('/scratch-cards/batch-stats/');
      setBatches(data);
    } catch {
      setAlert({ type: 'error', msg: 'Failed to load batches.' });
    } finally {
      setLoading(false);
    }
  }, []);

  // ── Generate ─────────────────────────────────────────────────────────────────
  const handleGenerate = async e => {
    e.preventDefault();
    if (!form.batch_name.trim()) {
      setAlert({ type: 'error', msg: 'Batch name is required.' });
      return;
    }
    setGenerating(true);
    setAlert(null);

    try {
      const response = await api.post('/scratch-cards/generate/', {
        quantity:   Number(form.quantity),
        batch_name: form.batch_name.trim(),
        term_id:    form.term_id || null,
        price:      form.price,
      }, { responseType: 'blob' });

      // Trigger CSV download
      const url      = window.URL.createObjectURL(new Blob([response.data]));
      const link     = document.createElement('a');
      link.href      = url;
      link.download  = `scratch_cards_${form.batch_name.replace(/\s+/g, '_')}.csv`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);

      setAlert({ type: 'success', msg: `${form.quantity} cards generated. CSV downloaded — keep it safe, PINs cannot be recovered.` });
      setForm(f => ({ ...f, batch_name: '' }));
      await loadBatches();
    } catch (err) {
      setAlert({ type: 'error', msg: err?.response?.data?.detail ?? 'Generation failed.' });
    } finally {
      setGenerating(false);
    }
  };

  // ── Download unused serials ───────────────────────────────────────────────────
  const downloadUnused = async (batchName) => {
    try {
      const response = await api.get(
        `/scratch-cards/unused-csv/?batch=${encodeURIComponent(batchName)}`,
        { responseType: 'blob' }
      );
      const url  = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href  = url;
      link.download = `unused_${batchName.replace(/\s+/g, '_')}.csv`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      setAlert({ type: 'error', msg: 'Failed to download unused serials.' });
    }
  };

  // ── Render ────────────────────────────────────────────────────────────────────
  return (
    <div style={S.page}>
      <h1 style={S.title}>Scratch Cards</h1>
      <p style={S.sub}>Generate PIN batches for result checking · Track usage per batch</p>

      {alert && (
        <div style={{
          ...S.alert,
          background: alert.type === 'success' ? '#dcfce7' : '#fee2e2',
          color:      alert.type === 'success' ? '#166534' : '#991b1b',
          border:     `1px solid ${alert.type === 'success' ? '#86efac' : '#fca5a5'}`,
        }}>
          {alert.type === 'success' ? '✓' : '⚠'} {alert.msg}
        </div>
      )}

      {/* ── Generate form ── */}
      <div style={S.card}>
        <div style={S.cardHead}>
          <span style={S.cardTitle}>Generate New Batch</span>
        </div>
        <div style={S.cardBody}>
          <form onSubmit={handleGenerate}>
            <div style={S.grid}>
              <div style={S.field}>
                <label style={S.label}>Batch Name</label>
                <input
                  style={S.input}
                  placeholder="e.g. 2024/25 First Term"
                  value={form.batch_name}
                  onChange={e => setForm(f => ({ ...f, batch_name: e.target.value }))}
                  required
                />
              </div>

              <div style={S.field}>
                <label style={S.label}>Quantity</label>
                <input
                  style={S.input}
                  type="number"
                  min={1}
                  max={500}
                  value={form.quantity}
                  onChange={e => setForm(f => ({ ...f, quantity: e.target.value }))}
                />
              </div>

              <div style={S.field}>
                <label style={S.label}>Term (optional)</label>
                <select
                  style={S.input}
                  value={form.term_id}
                  onChange={e => setForm(f => ({ ...f, term_id: e.target.value }))}
                >
                  <option value="">— Any term —</option>
                  {terms.map(t => (
                    <option key={t.id} value={t.id}>{t.name}</option>
                  ))}
                </select>
              </div>

              <div style={S.field}>
                <label style={S.label}>Price (₦)</label>
                <input
                  style={S.input}
                  type="number"
                  min={0}
                  value={form.price}
                  onChange={e => setForm(f => ({ ...f, price: e.target.value }))}
                />
              </div>
            </div>

            <div style={{ marginTop: 18, display: 'flex', gap: 10 }}>
              <button
                type="submit"
                style={{ ...S.btn, background: '#0c1c40', color: '#fff' }}
                disabled={generating}
              >
                {generating ? '⏳ Generating…' : '🪙 Generate & Download CSV'}
              </button>
            </div>

            <p style={{ fontSize: '.76rem', color: '#6b7280', marginTop: 10 }}>
              ⚠ The CSV with plain PINs downloads immediately. Store it securely — PINs are hashed in the database and cannot be recovered.
            </p>
          </form>
        </div>
      </div>

      {/* ── Batch table ── */}
      <div style={S.card}>
        <div style={S.cardHead}>
          <span style={S.cardTitle}>Batches</span>
          <button
            style={{ ...S.btn, background: '#f3f4f6', color: '#374151', padding: '7px 14px' }}
            onClick={loadBatches}
          >
            ↻ Refresh
          </button>
        </div>
        <div style={{ overflowX: 'auto' }}>
          {loading ? (
            <div style={{ padding: 24, color: '#6b7280', textAlign: 'center' }}>Loading…</div>
          ) : batches.length === 0 ? (
            <div style={{ padding: 24, color: '#6b7280', textAlign: 'center' }}>
              No batches yet. Generate your first batch above.
            </div>
          ) : (
            <table style={S.table}>
              <thead>
                <tr>
                  {['Batch Name', 'Total', 'Used', 'Unused', 'Usage %', 'Generated', 'Actions'].map(h => (
                    <th key={h} style={S.th}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {batches.map((b, i) => (
                  <tr key={b.batch_name} style={{ background: i % 2 === 0 ? '#fff' : '#f9fafb' }}>
                    <td style={{ ...S.td, fontWeight: 600, color: '#0c1c40' }}>{b.batch_name}</td>
                    <td style={S.td}>{b.total}</td>
                    <td style={{ ...S.td, color: '#991b1b' }}>{b.used}</td>
                    <td style={{ ...S.td, color: '#166534' }}>{b.unused}</td>
                    <td style={S.td}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <div style={{ flex: 1, height: 6, background: '#e5e7eb', borderRadius: 3, overflow: 'hidden' }}>
                          <div style={{ width: pct(b.used, b.total), height: '100%', background: '#0c1c40', borderRadius: 3 }} />
                        </div>
                        <span style={{ fontSize: '.78rem', color: '#6b7280', whiteSpace: 'nowrap' }}>
                          {pct(b.used, b.total)}
                        </span>
                      </div>
                    </td>
                    <td style={{ ...S.td, fontSize: '.78rem', color: '#6b7280' }}>
                      {b.created_at ? new Date(b.created_at).toLocaleDateString() : '—'}
                    </td>
                    <td style={S.td}>
                      <button
                        style={{ ...S.btn, background: '#f3f4f6', color: '#374151', padding: '5px 12px', fontSize: '.78rem' }}
                        onClick={() => downloadUnused(b.batch_name)}
                        disabled={b.unused === 0}
                        title={b.unused === 0 ? 'No unused cards in this batch' : 'Download unused serial numbers'}
                      >
                        📥 Unused CSV
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
