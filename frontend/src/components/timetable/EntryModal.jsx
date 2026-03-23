/**
 * frontend/src/components/timetable/EntryModal.jsx
 *
 * Modal dialog for creating, editing, or deleting a timetable entry.
 *
 * Props:
 *   isOpen      boolean
 *   onClose     fn()
 *   onSave      fn(payload) → Promise        payload: {subject, teacher, day_of_week, period}
 *   onDelete    fn(entryId) → Promise        only relevant when editing
 *   entry       TimetableEntry | null        null = "add" mode
 *   day         'MON' | ...
 *   period      Period
 *   subjects    Subject[]
 *   teachers    User[]
 *   apiWarning  string | null               non-blocking warning from API response
 */

import React, { useState, useEffect, useRef } from 'react';

const DAY_LABELS = {
  MON: 'Monday', TUE: 'Tuesday', WED: 'Wednesday',
  THU: 'Thursday', FRI: 'Friday',
};

export default function EntryModal({
  isOpen,
  onClose,
  onSave,
  onDelete,
  entry,
  day,
  period,
  subjects = [],
  teachers = [],
  apiWarning = null,
}) {
  const isEdit = Boolean(entry);

  const [subjectId,  setSubjectId]  = useState('');
  const [teacherId,  setTeacherId]  = useState('');
  const [saving,     setSaving]     = useState(false);
  const [deleting,   setDeleting]   = useState(false);
  const [fieldError, setFieldError] = useState(null);  // conflict error from API
  const [warning,    setWarning]    = useState(null);  // overload warning

  const firstInputRef = useRef(null);

  // Reset form when modal opens
  useEffect(() => {
    if (!isOpen) return;
    setSubjectId(entry ? String(entry.subject) : '');
    setTeacherId(entry?.teacher_id ? String(entry.teacher_id) : '');
    setFieldError(null);
    setWarning(apiWarning);

    // Auto-focus first select for keyboard users
    setTimeout(() => firstInputRef.current?.focus(), 80);
  }, [isOpen, entry, apiWarning]);

  if (!isOpen || !period) return null;

  // ── handlers ───────────────────────────────────────────────────────────────

  const handleSave = async () => {
    if (!subjectId) {
      setFieldError('Please select a subject before saving.');
      return;
    }
    setSaving(true);
    setFieldError(null);

    try {
      await onSave({
        subject:     Number(subjectId),
        teacher:     teacherId ? Number(teacherId) : null,
        day_of_week: day,
        period:      period.id,
      });
      // onSave closes the modal on success — parent handles it
    } catch (err) {
      // Surface field-level errors from DRF
      const data = err?.response?.data ?? {};
      setFieldError(
        data.teacher
          ?? data.non_field_errors?.[0]
          ?? data.detail
          ?? 'Failed to save. Please try again.'
      );
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm(`Remove ${entry.subject_name} from this slot?`)) return;
    setDeleting(true);
    try {
      await onDelete(entry.id);
    } catch {
      setFieldError('Failed to remove. Please try again.');
      setDeleting(false);
    }
  };

  const handleBackdropClick = e => {
    if (e.target === e.currentTarget) onClose();
  };

  // ── render ─────────────────────────────────────────────────────────────────

  return (
    <div
      className="tt-modal-backdrop"
      onClick={handleBackdropClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby="tt-modal-title"
    >
      <div className="tt-modal">

        {/* Header */}
        <div className="tt-modal__header">
          <h2 id="tt-modal-title" className="tt-modal__title">
            {isEdit ? 'Edit lesson' : 'Add lesson'}
          </h2>
          <button className="tt-modal__close" onClick={onClose} aria-label="Close">✕</button>
        </div>

        {/* Slot context */}
        <p className="tt-modal__meta">
          {DAY_LABELS[day]}  ·  {period.name}
          &ensp;({period.start_time.slice(0,5)} – {period.end_time.slice(0,5)})
        </p>

        {/* Overload warning (non-blocking) */}
        {warning && (
          <div className="tt-modal__warning">
            <span>⚠</span>
            <span>{warning}</span>
          </div>
        )}

        {/* Conflict / general error */}
        {fieldError && (
          <div className="tt-modal__error">❌ {fieldError}</div>
        )}

        {/* Subject selector */}
        <div className="tt-field">
          <label htmlFor="tt-subject">Subject *</label>
          <select
            id="tt-subject"
            ref={firstInputRef}
            value={subjectId}
            onChange={e => { setSubjectId(e.target.value); setFieldError(null); }}
          >
            <option value="">— Select a subject —</option>
            {subjects.map(s => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </div>

        {/* Teacher selector (optional) */}
        <div className="tt-field">
          <label htmlFor="tt-teacher">Teacher</label>
          <select
            id="tt-teacher"
            value={teacherId}
            onChange={e => setTeacherId(e.target.value)}
          >
            <option value="">— Unassigned —</option>
            {teachers.map(t => (
              <option key={t.id} value={t.id}>
                {t.first_name} {t.last_name}
              </option>
            ))}
          </select>
        </div>

        {/* Actions */}
        <div className="tt-modal__actions">
          {isEdit && (
            <button
              className="tt-btn tt-btn--danger"
              onClick={handleDelete}
              disabled={deleting || saving}
            >
              {deleting ? 'Removing…' : 'Remove'}
            </button>
          )}

          <button
            className="tt-btn tt-btn--ghost"
            onClick={onClose}
            disabled={saving || deleting}
          >
            Cancel
          </button>

          <button
            className="tt-btn tt-btn--primary"
            onClick={handleSave}
            disabled={saving || deleting || !subjectId}
          >
            {saving ? 'Saving…' : isEdit ? 'Update' : 'Add lesson'}
          </button>
        </div>

      </div>
    </div>
  );
}