/**
 * frontend/src/components/teacher/GradeCell.jsx
 *
 * Reusable components for the gradebook spreadsheet:
 *
 *   GradeBadge   — coloured WAEC grade chip (A1–F9)
 *   GradeCell    — editable score input with max-score hint + validation
 *   ComputedCell — read-only display of auto-calculated values (CA total, total)
 *
 * All components are pure/presentational — no API calls.
 */

import React, { useRef, useEffect } from 'react';

// ─── Grade badge colours match CSS .gb-grade-badge.XX ────────────────────────

const GRADE_PASS_BANDS   = new Set(['A1','B2','B3','C4','C5','C6']);
const GRADE_WARN_BANDS   = new Set(['D7','E8']);

/** Return the CSS row-tint class based on grade string */
export function rowClass(grade) {
  if (!grade) return '';
  if (GRADE_PASS_BANDS.has(grade)) return 'row-pass';
  if (GRADE_WARN_BANDS.has(grade)) return 'row-warn';
  return 'row-fail';
}

// ─── GradeBadge ───────────────────────────────────────────────────────────────

export function GradeBadge({ grade }) {
  if (!grade) return <span className="gb-grade-badge">—</span>;
  return <span className={`gb-grade-badge ${grade}`}>{grade}</span>;
}

// ─── ComputedCell ─────────────────────────────────────────────────────────────

export function ComputedCell({ value }) {
  const display = value !== undefined && value !== null && value !== ''
    ? Number(value).toFixed(1).replace('.0', '')
    : '—';
  return <span className="gb-computed-val">{display}</span>;
}

// ─── GradeCell (editable input) ───────────────────────────────────────────────

/**
 * Props:
 *   value        number | ''
 *   max          number            — maximum allowed score (shown as hint)
 *   onChange     fn(newVal)        — called with parsed float or ''
 *   onTab        fn(e)             — called on Tab/Shift-Tab for cell navigation
 *   inputRef     fn(el)            — callback ref attached directly to <input>
 *   autoFocus    bool
 *   disabled     bool
 *   hasError     bool
 *   fieldName    string            — e.g. 'first_test', used for aria-label
 */
export default function GradeCell({
  value,
  max,
  onChange,
  onTab,
  inputRef,
  autoFocus = false,
  disabled  = false,
  hasError  = false,
  fieldName = 'score',
}) {
  const ownRef = useRef(null);

  // Merge inputRef callback with our own ref
  const setRef = (el) => {
    ownRef.current = el;
    if (typeof inputRef === 'function') inputRef(el);
  };

  useEffect(() => {
    if (autoFocus) ownRef.current?.focus();
  }, [autoFocus]);

  const handleChange = (e) => {
    const raw = e.target.value;
    if (raw === '' || raw === '-') {
      onChange('');
      return;
    }
    const num = parseFloat(raw);
    if (!isNaN(num)) onChange(num);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Tab') {
      onTab?.(e);
    }
    // Allow only digits, dot, backspace, delete, arrows, tab
    if (
      !/[\d.]/.test(e.key) &&
      !['Backspace','Delete','ArrowLeft','ArrowRight','Tab'].includes(e.key)
    ) {
      e.preventDefault();
    }
  };

  const displayVal = value === '' || value === null || value === undefined ? '' : value;

  return (
    <td className="gb-score-cell">
      {max !== undefined && (
        <span className="gb-score-max">/{max}</span>
      )}
      <input
        ref={setRef}
        type="number"
        className={`gb-score-input${hasError ? ' has-error' : ''}`}
        value={displayVal}
        min={0}
        max={max}
        step="0.5"
        disabled={disabled}
        aria-label={fieldName}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        onFocus={e => e.target.select()}
      />
    </td>
  );
}