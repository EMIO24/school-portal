import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import AdminDashboard from '../../../pages/admin/AdminDashboard';
import api from '../../../services/api';

jest.mock('../../../components/common/WorkspaceHome', () => () => <div>School shortcuts</div>);
jest.mock('../../../services/api', () => ({ __esModule: true, default: { get: jest.fn() } }));

const snapshot = { term: 1, active_students: 12, active_teachers: 2,
  terms: [{ id: 1, name: 'first', session__name: '2026/27', start_date: '2026-09-01', end_date: '2026-12-18', is_current: true }] };
const sections = {
  attendance: { state: 'no_records', marks: { present: 0, absent: 0, late: 0, excused: 0 },
    classes_with_records: 0, classes_expected: 1, classes_without_records: [{ id: 2, name: 'JSS1 A' }] },
  teaching: { state: 'scheduled', scheduled: 1, counts: { delivered: 0, missed: 0, cancelled: 0, substituted: 0, unresolved: 1 },
    queue: [{ slot_id: 3, class_name: 'JSS1 A', subject_name: 'Math', period_name: 'First' }] },
  curriculum: { state: 'configured', groups: [{ class_arm: 2, class_name: 'JSS1 A', class_level: 4,
    subject: 5, subject_name: 'Math', covered: 1, planned: 3, partial: 1, not_started: 1 }] },
  academic_management: { state: 'configured', applicable_curriculum_scopes: 1,
    standard_counts: { approved: 1 }, lesson_plan_counts: { submitted: 1 }, resource_counts: { reviewed: 1 },
    lesson_plan_review_queue: [{ id: 9 }], resource_review_queue: [{ id: 10 }],
    note: 'Lesson plans and approved resources are planning/review evidence; LessonRecord and TopicCoverage remain delivery evidence.',
    groups: [{ class_arm: 2, class_name: 'JSS1 A', class_level: 4, subject: 5, subject_name: 'Math',
      planned_topics: 3, covered_evidence_rows: 1, partial_evidence_rows: 0, lesson_outcomes: { delivered: 1 },
      assessment_questions_linked: 2, online_assignments_linked: 1 }] },
  academic_history: { state: 'comparable', note: 'Counts describe recorded evidence; they are not teacher-quality or school-quality scores.',
    current: { session_name: '2026/27', term_name: 'first' }, previous: { session_name: '2025/26', term_name: 'first' },
    comparison: [{ class_level: 4, class_level_name: 'JSS1', subject: 5, subject_name: 'Math',
      current: { planned_topics: 3, covered_topics: 1, lesson_outcomes: { delivered: 2 }, approved_resources: 1, result_average: '68.00',
        curriculum: { source: 'Recorded curriculum', version: '2026' }, academic_standard: { title: 'Math standard', revision: 2 } },
      previous: { planned_topics: 2, covered_topics: 1, lesson_outcomes: { delivered: 1 }, approved_resources: 0, result_average: '65.00',
        curriculum: { source: 'Recorded curriculum', version: '2025' }, academic_standard: { title: 'Math standard', revision: 1 } } }] },
  results: { state: 'recorded', counts: { submitted: 1, approved: 0, published: 0 },
    groups: [{ class_arm: 2, class_name: 'JSS1 A', subject: 5, subject_name: 'Math', submitted: 1, approved: 0, published: 0 }] },
  finance: { state: 'unconfigured' },
};

function show() { return render(<MemoryRouter><AdminDashboard /></MemoryRouter>); }
beforeEach(() => {
  jest.resetAllMocks();
  api.get.mockImplementation((url, config) => {
    if (url !== '/api/principal/') throw Error('Unexpected URL');
    const section = config.params.section;
    return Promise.resolve({ data: section === 'snapshot' ? snapshot : sections[section] });
  });
});

test('shows source linked operational facts without analytics refresh', async () => {
  show();
  expect(await screen.findByText('Active students')).toBeVisible();
  expect(await screen.findByText(/Outcome not recorded: 1/)).toBeVisible();
  expect(screen.getByText(/0 of 1 classes/)).toBeVisible();
  expect(screen.getByText(/1\/3 covered/)).toBeVisible();
  expect(screen.getByText(/1 score entries submitted/)).toBeVisible();
  expect(screen.getByText(/Approved standards: 1/)).toBeVisible();
  expect(screen.getByText(/2 linked questions/)).toBeVisible();
  expect(screen.getByText(/2026\/27 compared with 2025\/26/)).toBeVisible();
  expect(screen.getByText(/Current: 1\/3 topics explicitly covered/)).toBeVisible();
  expect(screen.getByText(/No fee schedules configured/)).toBeVisible();
  expect(screen.queryByText(/School Average|Top 5 Students|Refresh Analytics/)).not.toBeInTheDocument();
  expect(screen.getByText('Outcome not recorded: 1').closest('a')).toHaveAttribute('href', expect.stringContaining('outcome=unresolved'));
  expect(api.get).toHaveBeenCalledTimes(8);
});

test('one failed section can be retried while the others remain visible', async () => {
  let fail = true;
  api.get.mockImplementation((url, config) => {
    const section = config.params.section;
    if (section === 'finance' && fail) return Promise.reject(Error('Offline'));
    return Promise.resolve({ data: section === 'snapshot' ? snapshot : sections[section] });
  });
  show();
  expect(await screen.findByText(/Recorded school fees unavailable/)).toBeVisible();
  expect(screen.getByText(/Outcome not recorded: 1/)).toBeVisible();
  fail = false;
  fireEvent.click(screen.getByRole('region', { name: 'Recorded school fees' }).querySelector('button'));
  expect(await screen.findByText(/No fee schedules configured/)).toBeVisible();
});

test('late data from a previous term does not replace the selected term', async () => {
  let resolveOld;
  api.get.mockImplementation((url, config) => {
    const section = config.params.section;
    if (section === 'snapshot') return Promise.resolve({ data: { ...snapshot, terms: [...snapshot.terms,
      { ...snapshot.terms[0], id: 2, name: 'second' }] } });
    if (section === 'teaching' && String(config.params.term) === '1') return new Promise(resolve => { resolveOld = resolve; });
    return Promise.resolve({ data: section === 'teaching' ? { ...sections.teaching, scheduled: 2 } : sections[section] });
  });
  show();
  await screen.findByText('Active students');
  fireEvent.change(screen.getByLabelText('Academic term'), { target: { value: '2' } });
  expect(await screen.findByText('2 dated lessons')).toBeVisible();
  resolveOld({ data: { ...sections.teaching, scheduled: 99 } });
  await waitFor(() => expect(screen.getByText('2 dated lessons')).toBeVisible());
  expect(screen.queryByText('99 dated lessons')).not.toBeInTheDocument();
});
