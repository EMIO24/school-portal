/**
 * frontend/src/pages/student/Timetable.jsx
 *
 * Read-only timetable view for a student.
 *
 * The student's class_arm_id is derived from the auth context
 * (set on login, stored in the decoded JWT / user profile).
 *
 * Features:
 *   ✓ Auto-selects the active term
 *   ✓ Shows all lessons for the student's class arm
 *   ✓ Subject category legend
 *   ✓ Graceful "no class assigned" state
 */

import React, { useState, useEffect, useCallback, useContext } from 'react';
import TimetableGrid, { TimetableLegend } from '../../components/timetable/TimetableGrid';
import api from '../../services/api';
import { AuthContext } from '../../context/AuthContext';  // project-wide auth context
import '../../styles/TimetableGrid.css';

export default function StudentTimetable() {
  const { user } = useContext(AuthContext);
  const classArmId = user?.class_arm_id ?? null;

  const [terms,        setTerms]        = useState([]);
  const [selectedTerm, setSelectedTerm] = useState('');
  const [periods,      setPeriods]      = useState([]);
  const [entries,      setEntries]      = useState([]);
  const [loading,      setLoading]      = useState(false);

  // Boot
  useEffect(() => {
    api.get('/academics/terms/').then(({ data }) => {
      const list   = data.results ?? data;
      setTerms(list);
      const active = list.find(t => t.is_active);
      if (active) setSelectedTerm(String(active.id));
    });
  }, []);

  const loadData = useCallback(async () => {
    if (!selectedTerm || !classArmId) return;
    setLoading(true);
    try {
      const [pRes, eRes] = await Promise.all([
        api.get('/timetable/periods/'),
        api.get(`/timetable/entries/by-class/${classArmId}/?term=${selectedTerm}`),
      ]);
      setPeriods(pRes.data.results ?? pRes.data);
      setEntries(eRes.data);
    } finally {
      setLoading(false);
    }
  }, [selectedTerm, classArmId]);

  useEffect(() => { loadData(); }, [loadData]);

  // Guard — student not yet assigned to a class
  if (!classArmId) {
    return (
      <div className="tt-page">
        <div className="tt-grid-wrap">
          <div className="tt-empty-state">
            <strong>No class assigned</strong>
            Your class placement hasn't been recorded yet.
            Please contact your school administrator.
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="tt-page">
      <div className="tt-toolbar">
        <h1 className="tt-toolbar__title">
          Class Timetable
          <small>Your weekly lesson schedule</small>
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
        highlightCurrent={false}
        loading={loading}
      />

      <TimetableLegend />
    </div>
  );
}