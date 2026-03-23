/**
 * frontend/src/pages/admin/TimetableBuilder.jsx
 *
 * Full editable timetable builder for school_admin role.
 *
 * Features:
 *   ✓ Term + class-arm selectors
 *   ✓ Interactive Day×Period grid
 *   ✓ Click empty cell → create modal
 *   ✓ Click filled cell → edit / delete modal
 *   ✓ API conflict errors surfaced in modal
 *   ✓ Non-blocking teacher overload warnings
 *   ✓ Subject category colour legend
 */

import React, { useState, useEffect, useCallback } from 'react';
import TimetableGrid, { TimetableLegend } from '../../components/timetable/TimetableGrid';
import EntryModal from '../../components/timetable/EntryModal';
import api from '../../services/api';              // project Axios instance
import '../../styles/TimetableGrid.css';

export default function TimetableBuilder() {

  // ── Reference data ────────────────────────────────────────────────────────
  const [terms,     setTerms]     = useState([]);
  const [classArms, setClassArms] = useState([]);
  const [subjects,  setSubjects]  = useState([]);
  const [teachers,  setTeachers]  = useState([]);

  // ── Selector values ───────────────────────────────────────────────────────
  const [selectedTerm,     setSelectedTerm]     = useState('');
  const [selectedClassArm, setSelectedClassArm] = useState('');

  // ── Grid data ─────────────────────────────────────────────────────────────
  const [periods,  setPeriods]  = useState([]);
  const [entries,  setEntries]  = useState([]);
  const [loading,  setLoading]  = useState(false);

  // ── Modal state ───────────────────────────────────────────────────────────
  const [modal, setModal] = useState({
    open:       false,
    day:        null,
    period:     null,
    entry:      null,    // null → create mode
    apiWarning: null,
  });

  // ── Boot: load dropdown data ───────────────────────────────────────────────
  useEffect(() => {
    Promise.all([
      api.get('/academics/terms/'),
      api.get('/academics/class-arms/'),
      api.get('/academics/subjects/'),
      api.get('/accounts/users/?role=teacher&page_size=300'),
    ]).then(([t, c, s, u]) => {
      setTerms(    t.data.results ?? t.data);
      setClassArms(c.data.results ?? c.data);
      setSubjects( s.data.results ?? s.data);
      setTeachers( u.data.results ?? u.data);

      // Pre-select the active term if available
      const active = (t.data.results ?? t.data).find(x => x.is_active);
      if (active) setSelectedTerm(String(active.id));
    });
  }, []);

  // ── Load grid whenever selectors change ───────────────────────────────────
  const loadGrid = useCallback(async () => {
    if (!selectedTerm || !selectedClassArm) return;
    setLoading(true);
    try {
      const { data } = await api.get(
        `/timetable/entries/grid/?class_arm=${selectedClassArm}&term=${selectedTerm}`
      );
      setPeriods(data.periods);
      setEntries(data.entries);
    } catch (err) {
      console.error('Grid load failed', err);
    } finally {
      setLoading(false);
    }
  }, [selectedTerm, selectedClassArm]);

  useEffect(() => { loadGrid(); }, [loadGrid]);

  // ── Cell click → open modal ───────────────────────────────────────────────
  const handleCellClick = (day, period, entry) => {
    setModal({ open: true, day, period, entry, apiWarning: null });
  };

  // ── Save (create or update) ────────────────────────────────────────────────
  const handleSave = async (payload) => {
    const isEdit = Boolean(modal.entry);
    const body   = {
      ...payload,
      term:      Number(selectedTerm),
      class_arm: Number(selectedClassArm),
    };

    let response;
    if (isEdit) {
      response = await api.patch(`/timetable/entries/${modal.entry.id}/`, body);
    } else {
      response = await api.post('/timetable/entries/', body);
    }

    // Handle non-blocking warning from API
    if (response.data.warning) {
      // Show warning in modal but keep it open momentarily
      setModal(prev => ({ ...prev, apiWarning: response.data.warning }));
    }

    // Reload grid with fresh data
    await loadGrid();

    // Close modal (slight delay if there was a warning so user sees it)
    if (response.data.warning) {
      setTimeout(() => setModal(prev => ({ ...prev, open: false })), 1800);
    } else {
      setModal(prev => ({ ...prev, open: false }));
    }
  };

  // ── Delete ────────────────────────────────────────────────────────────────
  const handleDelete = async (entryId) => {
    await api.delete(`/timetable/entries/${entryId}/`);
    await loadGrid();
    setModal(prev => ({ ...prev, open: false }));
  };

  const canRender = selectedTerm && selectedClassArm;

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="tt-page">

      {/* Toolbar */}
      <div className="tt-toolbar">
        <h1 className="tt-toolbar__title">
          Timetable Builder
          <small>Drag subjects into empty slots to build the weekly schedule</small>
        </h1>

        <div className="tt-selector-group">
          <label>Term</label>
          <select
            className="tt-select"
            value={selectedTerm}
            onChange={e => setSelectedTerm(e.target.value)}
          >
            <option value="">— Select term —</option>
            {terms.map(t => (
              <option key={t.id} value={t.id}>{t.name}</option>
            ))}
          </select>
        </div>

        <div className="tt-selector-group">
          <label>Class</label>
          <select
            className="tt-select"
            value={selectedClassArm}
            onChange={e => setSelectedClassArm(e.target.value)}
          >
            <option value="">— Select class —</option>
            {classArms.map(c => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Grid */}
      {canRender ? (
        <>
          <TimetableGrid
            periods={periods}
            entries={entries}
            editable
            loading={loading}
            onCellClick={handleCellClick}
          />
          <TimetableLegend />
        </>
      ) : (
        <div className="tt-grid-wrap">
          <div className="tt-empty-state">
            <strong>Nothing to display yet</strong>
            Select a term and a class above to start building the timetable.
          </div>
        </div>
      )}

      {/* Entry modal */}
      <EntryModal
        isOpen={modal.open}
        onClose={() => setModal(prev => ({ ...prev, open: false }))}
        onSave={handleSave}
        onDelete={handleDelete}
        entry={modal.entry}
        day={modal.day}
        period={modal.period}
        subjects={subjects}
        teachers={teachers}
        apiWarning={modal.apiWarning}
      />
    </div>
  );
}