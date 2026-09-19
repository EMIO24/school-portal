import React from 'react';
import { act, screen, fireEvent } from '@testing-library/react';
import { renderPage } from '../../testSupport/renderPage';
import api from '../../services/api';

jest.mock('../../services/api', () => ({
  __esModule: true,
  default: { get: jest.fn(), post: jest.fn(), patch: jest.fn(), put: jest.fn(), delete: jest.fn() },
  authAPI: { changePassword: jest.fn() },
  tokenStore: { getAccess: jest.fn(), getRefresh: jest.fn(), setTokens: jest.fn() },
}));
jest.mock('axios', () => ({ __esModule: true, default: { post: jest.fn() } }));

// Every page is listed explicitly, including pages not yet wired into App.js.
// Existing dashboard/Login tests cover populated states; these cover boot/empty states.
const cases = [
  ['admin/AdminDashboard', 'Dashboard'],
  ['admin/AttendanceOverview', /Attendance Overview/],
  ['admin/BulkImportPage', 'Bulk Student Import'],
  ['admin/CalendarSettings', 'Academic Calendar'],
  ['admin/ExamManager', 'Exam Manager'],
  ['admin/ExamResults', 'Exam Results'],
  ['admin/FeeCollection', 'Fee Collection'],
  ['admin/FeeSetup', 'Fee Setup'],
  ['admin/Notifications', 'Notifications'],
  ['admin/NotificationTemplates', 'Notification Templates'],
  ['admin/Promotion', 'Promotion Engine'],
  ['admin/QuestionBank', 'Filters'],
  ['admin/ResultManagement', /Result Management/],
  ['admin/ScratchCards', 'Scratch Cards'],
  ['admin/Staff', 'Staff'],
  ['admin/StaffForm', /Add.*Staff|New Staff/i, { path: '/new', route: '/new' }],
  ['admin/StaffProfilePage', 'Ada Okafor'],
  ['admin/StudentForm', 'Add Student', { path: '/new', route: '/new' }],
  ['admin/StudentProfile', 'Ada Okafor'],
  ['admin/Students', 'Students'],
  ['admin/SubjectAssignment', 'Subject Assignments'],
  ['admin/SubjectManager', 'Subjects'],
  ['admin/TimetableBuilder', /Timetable Builder/],
  ['parent/ParentDashboard', null, { text: /No children linked/i }],
  ['parent/ParentLogin', 'Parent Portal'],
  ['public/ChangePassword', 'Set New Password'],
  ['public/CheckResult', 'Result Checker'],
  ['public/Login', 'Sign In', { auth: { isAuthenticated: false } }],
  ['student/ExamList', 'My Exams'],
  ['student/ExamReview', 'Exam Review', { route: '/test/:examId' }],
  ['student/ExamRoom', null, { route: '/test/:examId', text: 'What is 2 + 2?' }],
  ['student/Fees', 'My Fees'],
  ['student/MyAttendance', /My Attendance/],
  ['student/MyPerformance', 'My Performance'],
  ['student/MyResult', null, { text: 'Term' }],
  ['student/StudentDashboard', /^Welcome,/],
  ['student/Timetable', null, { text: 'No class assigned' }],
  ['teacher/AffinityDomain', /Domain Ratings/],
  ['teacher/MyTimetable', /My Timetable/],
  ['teacher/ScoreEntry', /Score Entry/],
  ['teacher/TakeAttendance', /Take Attendance/],
  ['teacher/TeacherDashboard', /^Welcome,/],
];

beforeEach(() => {
  jest.clearAllMocks();
  localStorage.clear();
  api.get.mockImplementation(async url => {
    if (/\/api\/(students|staff)\/1\/$/.test(url)) return { data: {
      id: 1, first_name: 'Ada', last_name: 'Okafor', full_name: 'Ada Okafor',
      email: 'ada@example.com', role: 'teacher', status: 'active', subjects_taught_detail: [], assigned_classes_detail: [],
    } };
    if (url.endsWith('/review/')) return { data: { score: 100, questions: [] } };
    if (url.endsWith('/status/')) return { data: { saved_answers: [], tab_switch_count: 0 } };
    if (url.endsWith('/stats/')) return { data: { total: 0, by_difficulty: {}, by_type: {} } };
    if (url.endsWith('/grade-scale/')) return { data: { bands: [] } };
    if (url.endsWith('/settings/')) return { data: { attendance_mode: 'daily' } };
    return { data: [], status: 200 };
  });
  api.post.mockImplementation(async url => {
    if (url.endsWith('/start/')) return { data: {
      questions: [{ id: 1, question_text: 'What is 2 + 2?', question_type: 'mcq', options: [{ id: 'A', text: '4' }] }],
      session_id: 1, time_remaining_seconds: 600, allow_review: true,
    } };
    throw new Error(`Unexpected POST during page boot: ${url}`);
  });
});

test.each(cases)('%s renders its initial content after API requests settle', async (file, heading, options = {}) => {
  const Page = require(`../../pages/${file}`).default;
  await act(async () => { renderPage(<Page />, options); });
  if (heading) expect(screen.getByRole('heading', { name: heading })).toBeVisible();
  else expect(screen.getByText(options.text)).toBeVisible();
  // Loading a page should not create or modify data, except entering an exam.
  if (file !== 'student/ExamRoom') expect(api.post).not.toHaveBeenCalled();
  expect(api.patch).not.toHaveBeenCalled();
  expect(api.delete).not.toHaveBeenCalled();
});

test.each([
  ['admin/CalendarSettings', /No Sessions Yet/],
  ['admin/QuestionBank', /No questions found/],
  ['admin/ResultManagement', /Select a term and class to manage results/],
  ['admin/TimetableBuilder', /Select a term and a class above/],
  ['admin/AttendanceOverview', /Select a term and class/],
  ['teacher/ScoreEntry', /Select a term, session, class, and subject/],
  ['teacher/AffinityDomain', /Select a term and class to enter domain ratings/],
])('%s explains what is needed before work can start', async (file, message) => {
  const Page = require(`../../pages/${file}`).default;
  await act(async () => { renderPage(<Page />); });
  expect(screen.getByText(message)).toBeVisible();
});

test.each([
  ['admin/StaffProfilePage', /Failed to load staff member/],
  ['admin/StudentProfile', /Failed to load student/],
  ['student/ExamReview', /Could not load review/],
])('%s displays a failed detail request', async (file, message) => {
  api.get.mockRejectedValue(new Error('Network unavailable'));
  const Page = require(`../../pages/${file}`).default;
  await act(async () => { renderPage(<Page />, { route: '/test/:examId' }); });
  expect(screen.getByText(message)).toBeVisible();
});

test('ExamRoom shows start failure and offers a route back', async () => {
  api.post.mockRejectedValue(new Error('Offline'));
  const Page = require('../../pages/student/ExamRoom').default;
  await act(async () => { renderPage(<Page />, { route: '/test/:examId' }); });
  expect(screen.getByText(/Could not start exam/)).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: /Back/i }));
  expect(screen.getByText('Navigation destination')).toBeVisible();
});

test.each([
  ['admin/CalendarSettings', /New Session/, 'Create Academic Session'],
  ['admin/SubjectManager', /New Subject/, /Add Subject|New Subject/],
  ['admin/FeeSetup', /^\+ Add$/, 'New Category'],
  ['admin/NotificationTemplates', /New Template/, 'New Template'],
  ['admin/ExamManager', /New Exam/, 'New Exam'],
  ['admin/QuestionBank', /Add Question/, 'New Question'],
])('%s opens and cancels its creation form without saving', async (file, button, heading) => {
  const Page = require(`../../pages/${file}`).default;
  await act(async () => { renderPage(<Page />); });
  fireEvent.click(screen.getAllByRole('button', { name: button })[0]);
  expect(screen.getByRole('heading', { name: heading })).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
  expect(screen.queryByRole('heading', { name: heading })).not.toBeInTheDocument();
  expect(api.post).not.toHaveBeenCalled();
});
