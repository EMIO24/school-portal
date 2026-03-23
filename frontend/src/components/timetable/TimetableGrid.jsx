/**
 * frontend/src/components/timetable/TimetableGrid.jsx
 *
 * The pure presentational grid shared across all three role views.
 *
 * Props:
 *   periods              Period[]         ordered list of time slots
 *   entries              TimetableEntry[] entries for the selected class+term
 *   editable             boolean          if true, cells are clickable → onCellClick
 *   highlightCurrent     boolean          if true, current period pulses (teacher view)
 *   loading              boolean          shows skeleton loader
 *   onCellClick          fn(day, period, existingEntry | null)
 */

import React, { useMemo } from 'react';

// ─── Constants ───────────────────────────────────────────────────────────────

export const DAYS = [
  { key: 'MON', label: 'Monday',    short: 'Mon' },
  { key: 'TUE', label: 'Tuesday',   short: 'Tue' },
  { key: 'WED', label: 'Wednesday', short: 'Wed' },
  { key: 'THU', label: 'Thursday',  short: 'Thu' },
  { key: 'FRI', label: 'Friday',    short: 'Fri' },
];

const DAY_INDEX_MAP = { SUN:0, MON:1, TUE:2, WED:3, THU:4, FRI:5, SAT:6 };

/** Current day key (MON–FRI) or null on weekends */
function todayKey() {
  const keys = ['SUN','MON','TUE','WED','THU','FRI','SAT'];
  return keys[new Date().getDay()] ?? null;
}

/** HH:MM string for right now */
function nowHHMM() {
  const d = new Date();
  return `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
}

function isCurrentPeriod(period) {
  const now   = nowHHMM();
  const start = period.start_time.slice(0, 5);
  const end   = period.end_time.slice(0, 5);
  return now >= start && now < end;
}

/**
 * Build a lookup map so each cell can find its entry in O(1).
 * Key format: `${dayKey}_${periodId}`
 */
function buildEntryMap(entries) {
  const map = {};
  for (const e of entries) {
    map[`${e.day_of_week}_${e.period}`] = e;
  }
  return map;
}

// ─────────────────────────────────────────────────────────────────────────────

export default function TimetableGrid({
  periods = [],
  entries = [],
  editable = false,
  highlightCurrent = false,
  loading = false,
  onCellClick,
}) {
  const today    = todayKey();
  const entryMap = useMemo(() => buildEntryMap(entries), [entries]);

  // ── Loading skeleton ──────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="tt-grid-wrap">
        <div className="tt-grid">
          {/* Header */}
          <div className="tt-day-header">Period</div>
          {DAYS.map(d => (
            <div key={d.key} className="tt-day-header">{d.label}</div>
          ))}
          {/* 8 skeleton rows */}
          {Array.from({ length: 8 }).map((_, r) => (
            <React.Fragment key={r}>
              <div className="tt-period-label">
                <div className="tt-skeleton" style={{ height: 14, width: '75%', marginBottom: 5 }} />
                <div className="tt-skeleton" style={{ height: 11, width: '55%' }} />
              </div>
              {DAYS.map(d => (
                <div key={d.key} className="tt-cell">
                  {r % 3 !== 2 && r % 4 !== 1 && (
                    <div className="tt-skeleton" style={{ height: 54 }} />
                  )}
                </div>
              ))}
            </React.Fragment>
          ))}
        </div>
      </div>
    );
  }

  // ── Empty — no periods configured ────────────────────────────────────────
  if (!periods.length) {
    return (
      <div className="tt-grid-wrap">
        <div className="tt-empty-state">
          <strong>No periods configured</strong>
          Ask a school administrator to set up the daily time slots first.
        </div>
      </div>
    );
  }

  // ── Main grid ─────────────────────────────────────────────────────────────
  return (
    <div className="tt-grid-wrap">
      <div className="tt-grid">

        {/* Header row */}
        <div className="tt-day-header">Period</div>
        {DAYS.map(day => (
          <div
            key={day.key}
            className={`tt-day-header${day.key === today ? ' is-today' : ''}`}
          >
            {day.label}
            <span className="day-abbr">{day.short}</span>
          </div>
        ))}

        {/* Data rows — one per period */}
        {periods.map(period => {
          const isCurrent = highlightCurrent && isCurrentPeriod(period);

          return (
            <React.Fragment key={period.id}>
              {/* Period label */}
              <div className={`tt-period-label${period.is_break ? ' is-break' : ''}`}>
                <span className="p-name">{period.name}</span>
                <span className="p-time">
                  {period.start_time.slice(0,5)}–{period.end_time.slice(0,5)}
                </span>
              </div>

              {/* Day cells */}
              {DAYS.map(day => {
                const key   = `${day.key}_${period.id}`;
                const entry = entryMap[key] ?? null;
                const isToday = day.key === today;

                const cellClass = [
                  'tt-cell',
                  period.is_break   && 'is-break',
                  !entry && !period.is_break && 'is-empty',
                  isToday           && 'is-today-col',
                  isCurrent         && 'is-current-period',
                ].filter(Boolean).join(' ');

                const handleClick = () => {
                  if (!editable || period.is_break) return;
                  onCellClick?.(day.key, period, entry);
                };

                return (
                  <div
                    key={day.key}
                    className={cellClass}
                    onClick={handleClick}
                    role={editable && !period.is_break ? 'button' : undefined}
                    tabIndex={editable && !period.is_break ? 0 : undefined}
                    onKeyDown={e => {
                      if (e.key === 'Enter' || e.key === ' ') handleClick();
                    }}
                    aria-label={
                      entry
                        ? `${day.label} ${period.name}: ${entry.subject_name}`
                        : `${day.label} ${period.name}: empty`
                    }
                  >
                    {/* Hover plus hint for empty cells */}
                    {!entry && !period.is_break && (
                      <span className="tt-add-hint" aria-hidden>+</span>
                    )}

                    {/* Lesson card */}
                    {entry && <LessonCard entry={entry} />}
                  </div>
                );
              })}
            </React.Fragment>
          );
        })}

      </div>
    </div>
  );
}

// ─── LessonCard ───────────────────────────────────────────────────────────────

function LessonCard({ entry }) {
  const category = entry.subject_category || '';
  return (
    <div
      className="tt-lesson-card"
      data-cat={category}
    >
      <span className="lc-subject">{entry.subject_name}</span>
      {entry.teacher_name && (
        <span className="lc-teacher">{entry.teacher_name}</span>
      )}
    </div>
  );
}

// ─── TimetableLegend ─────────────────────────────────────────────────────────

const DEFAULT_LEGEND = [
  { name: 'Sciences',    bg: 'var(--cat-sciences-bg)',   fg: 'var(--cat-sciences-fg)' },
  { name: 'Arts',        bg: 'var(--cat-arts-bg)',       fg: 'var(--cat-arts-fg)' },
  { name: 'Languages',   bg: 'var(--cat-languages-bg)',  fg: 'var(--cat-languages-fg)' },
  { name: 'Social',      bg: 'var(--cat-social-bg)',     fg: 'var(--cat-social-fg)' },
  { name: 'Technology',  bg: 'var(--cat-tech-bg)',       fg: 'var(--cat-tech-fg)' },
  { name: 'Mathematics', bg: 'var(--cat-math-bg)',       fg: 'var(--cat-math-fg)' },
  { name: 'PE',          bg: 'var(--cat-pe-bg)',         fg: 'var(--cat-pe-fg)' },
];

export function TimetableLegend({ categories }) {
  const items = categories?.length ? categories : DEFAULT_LEGEND;
  return (
    <div className="tt-legend" aria-label="Subject categories">
      {items.map(cat => (
        <span key={cat.name} className="tt-legend-item">
          <span
            className="tt-legend-pip"
            style={{ background: cat.bg }}
            aria-hidden
          />
          {cat.name}
        </span>
      ))}
    </div>
  );
}