/**
 * frontend/src/pages/teacher/MyTimetable.jsx
 *
 * Read-only timetable view for the logged-in teacher.
 *
 * Features:
 *   ✓ Term selector, pre-selects active term
 *   ✓ Highlights the currently ongoing period with a pulsing ring
 *   ✓ Refreshes every 60 s so the highlight stays accurate all day
 *   ✓ Shows only this teacher's lessons — empty cells are not interactive
 */

import React, { useState, useEffect, useCallback } from 'react';
import TimetableGrid from '../../components/timetable/TimetableGrid';
import api from '../../services/api';
import '../../styles/TimetableGrid.css';

export default function MyTimetable() {
  const [terms,        setTerms]        = useState([]);
  const [selectedTerm, setSelectedTerm] = useState('');
  const [periods,      setPeriods]      = useState([]);
  const [entries,      setEntries]      = useState([]);
  const [loading,      setLoading]      = useState(false);

  // Boot: load terms, pre-select active
  useEffect(() => {
    api.get('/academics/terms/').then(({ data }) => {
      const list   = data.results ?? data;
      setTerms(list);
      const active = list.find(t => t.is_active);
      if (active) setSelectedTerm(String(active.id));
    });
  }, []);

  const loadData = useCallback(async () => {
    if (!selectedTerm) return;
    setLoading(true);
    try {
      const [pRes, eRes] = await Promise.all([
        api.get('/timetable/periods/'),
        api.get(`/timetable/entries/my-timetable/?term=${selectedTerm}`),
      ]);
      setPeriods(pRes.data.results ?? pRes.data);
      setEntries(eRes.data.results ?? eRes.data);
    } finally {
      setLoading(false);
    }
  }, [selectedTerm]);

  useEffect(() => { loadData(); }, [loadData]);

  // Refresh every 60 s so the current-period highlight stays live
  useEffect(() => {
    const id = setInterval(loadData, 60_000);
    return () => clearInterval(id);
  }, [loadData]);

  return (
    <div className="tt-page">
      <div className="tt-toolbar">
        <h1 className="tt-toolbar__title">
          My Timetable
          <small>Your assigned lessons for the week</small>
        </h1>

        <div className="tt-selector-group">
          <label>Term</label>
          <select
            className="tt-select"
            value={selectedTerm}
            onChange={e => setSelectedTerm(e.target.value)}
          >
            {terms.map(t => (
              <option key={t.id} value={t.id}>{t.name}</option>
            ))}
          </select>
        </div>
      </div>

      <TimetableGrid
        periods={periods}
        entries={entries}
        editable={false}
        highlightCurrent
        loading={loading}
      />

      <p style={{
        fontSize: '.74rem',
        color: 'var(--ink-muted)',
        marginTop: 14,
        fontFamily: 'var(--font-mono)',
      }}>
        ● Green outline = current period — refreshes automatically every minute
      </p>
    </div>
  );
}