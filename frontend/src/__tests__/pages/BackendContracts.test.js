import React from 'react';
import { act, screen, fireEvent, waitFor } from '@testing-library/react';
import { renderPage } from '../../testSupport/renderPage';
import TimetableBuilder from '../../pages/admin/TimetableBuilder';
import StaffForm from '../../pages/admin/StaffForm';
import ExamResults from '../../pages/admin/ExamResults';
import StudentTimetable from '../../pages/student/Timetable';
import MyAttendance from '../../pages/student/MyAttendance';
import MyResult from '../../pages/student/MyResult';
import NotificationTemplates from '../../pages/admin/NotificationTemplates';
import FeeSetup from '../../pages/admin/FeeSetup';
import api from '../../services/api';
import ScoreEntry from '../../pages/teacher/ScoreEntry';
import TakeAttendance from '../../pages/teacher/TakeAttendance';
import ChildDetails from '../../pages/parent/ChildDetails';
jest.mock('../../services/api', () => ({ __esModule: true, default: {
  get: jest.fn(), post: jest.fn(), patch: jest.fn(), put: jest.fn(), delete: jest.fn(),
} }));
const term = { id: 2, name: 'First Term', is_current: true };
const period = { id: 5, name: 'Period 1', start_time: '08:00:00', end_time: '09:00:00' };
beforeEach(() => {
  jest.clearAllMocks();
  api.get.mockResolvedValue({ data: [] });
  for (const method of ['post', 'patch', 'put', 'delete']) api[method].mockResolvedValue({ data: {} });
  jest.spyOn(window, 'confirm').mockReturnValue(true);
  jest.spyOn(window, 'alert').mockImplementation(() => {});
});
afterEach(() => jest.restoreAllMocks());

test('timetable creation submits the teacher user ID and current term', async () => {
  api.get.mockImplementation(async url => ({ data:
    url === '/api/terms/' ? [term] : url === '/api/class-arms/' ? [{ id: 3, name: 'JSS1 A' }] :
    url === '/api/subjects/' ? [{ id: 4, name: 'Mathematics' }] :
    url.includes('/staff/') ? [{ id: 7, user: 41, full_name: 'Ada Teacher' }] :
    { periods: [period], entries: [] },
  }));
  await act(async () => renderPage(<TimetableBuilder />));
  expect(screen.getAllByRole('combobox')[0]).toHaveValue('2');
  fireEvent.change(screen.getAllByRole('combobox')[1], { target: { value: '3' } });
  fireEvent.click(await screen.findByRole('button', { name: 'Monday Period 1: empty' }));
  fireEvent.change(screen.getByLabelText('Subject *'), { target: { value: '4' } });
  expect(screen.getByRole('option', { name: 'Ada Teacher' })).toHaveValue('41');
  fireEvent.change(screen.getByLabelText('Teacher'), { target: { value: '41' } });
  fireEvent.click(screen.getByRole('button', { name: 'Add lesson' }));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/timetable/entries/', {
    subject: 4, teacher: 41, period: 5, day_of_week: 'MON', term: 2, class_arm: 3,
  }));
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
});
test('staff editing uses the profile PATCH and does not send an incompatible assignment request', async () => {
  api.get.mockImplementation(async url => ({ data: url === '/api/staff/1/' ? {
    id: 1, email: 'teacher@example.com', first_name: 'Ada', last_name: 'Teacher', role: 'teacher',
    subjects_taught: [4], assigned_classes: [3],
  } : [] }));
  let page;
  await act(async () => { page = renderPage(<StaffForm />); });
  fireEvent.submit(page.container.querySelector('form'));
  await waitFor(() => expect(api.patch).toHaveBeenCalledWith('/api/staff/1/', expect.objectContaining({
    dob: null, date_employed: null, subjects_taught: [4], assigned_classes: [3],
  })));
  expect(api.patch.mock.calls[0][1]).not.toHaveProperty('new_email');
  expect(api.post).not.toHaveBeenCalled();
});
test('student timetable loads the profile class and selects the backend current term', async () => {
  api.get.mockImplementation(async url => ({ data: url === '/api/terms/' ? [term] : url.includes('/periods/') ? [period] : [] }));
  await act(async () => renderPage(<StudentTimetable />, { auth: { user: { id: 41, student_id: 7, class_arm_id: 12 } } }));
  expect(api.get).toHaveBeenCalledWith('/api/timetable/entries/by-class/12/?term=2');
  expect(screen.getByRole('heading', { name: /Class Timetable/ })).toBeVisible();
});
test('student result requests use the account ID required by the result backend', async () => {
  api.get.mockImplementation(url => url === '/api/terms/' ? Promise.resolve({ data: [term] }) : Promise.reject({ response: { status: 404 } }));
  await act(async () => renderPage(<MyResult />, { auth: { user: { id: 41, student_id: 7 } } }));
  expect(api.get).toHaveBeenCalledWith('/api/results/slip-data/41/?term=2');
  expect(screen.getByText(/Results are not available/)).toBeVisible();
});
test('student attendance requests and filters records by account ID', async () => {
  api.get.mockImplementation(async url => ({ data: url === '/api/terms/' ? [term] : url.includes('/report/') ? { percentage: 100 } : [
    { id: 9, date: '2026-09-07', records: [{ student: 7, status: 'present' }, { student: 41, status: 'absent' }] },
  ] }));
  await act(async () => renderPage(<MyAttendance />, { auth: { user: { id: 41, student_id: 7 } } }));
  expect(api.get).toHaveBeenCalledWith('/api/attendance/sessions/report/?student=41&term=2');
  expect(api.get).toHaveBeenCalledWith('/api/attendance/sessions/?term=2&student=41');
  expect(screen.getByText('You are on track.')).toBeVisible();
});
test('exam results loads the canonical results URL and pushes grades after confirmation', async () => {
  api.get.mockImplementation(async url => ({ data: url === '/api/cbt/exams/' ? [{ id: 8, title: 'Maths Exam' }]
    : url.endsWith('/results/') ? { total_students: 1, results: [{ student_id: 7, name: 'Ada Student', score: 80, status: 'submitted', time_taken_seconds: 120, tab_switches: 0 }] }
    : [] }));
  api.post.mockResolvedValue({ data: { updated: 1 } });
  await act(async () => renderPage(<ExamResults />));
  expect(screen.getByText('Ada Student')).toBeVisible();
  expect(api.get).toHaveBeenCalledWith('/api/cbt/exams/8/results/');
  fireEvent.click(screen.getByRole('button', { name: /Push/ }));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/cbt/exams/8/push-to-gradebook/'));
  fireEvent.click(screen.getByRole('button', { name: 'Question Analysis' }));
});

test('notification templates can be created, edited and deleted', async () => {
  api.get.mockResolvedValue({ data: [{ id: 5, name: 'Reminder', type: 'sms', category: 'general', subject: '', body: 'Hello' }] });
  let page;
  await act(async () => { page = renderPage(<NotificationTemplates />); });
  fireEvent.click(screen.getByRole('button', { name: '+ New Template' }));
  fireEvent.change(page.container.querySelector('.modal-box input'), { target: { value: 'Welcome' } });
  fireEvent.change(page.container.querySelector('textarea'), { target: { value: 'Welcome to school' } });
  fireEvent.click(screen.getByRole('button', { name: 'Save' }));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/notifications/templates/', expect.objectContaining({ name: 'Welcome', body: 'Welcome to school' })));
  await waitFor(() => expect(page.container.querySelector('.modal-box')).toBeNull());
  fireEvent.click(screen.getByRole('button', { name: 'Edit' }));
  fireEvent.change(page.container.querySelector('.modal-box input'), { target: { value: 'Updated reminder' } });
  fireEvent.click(screen.getByRole('button', { name: 'Save' }));
  await waitFor(() => expect(api.put).toHaveBeenCalledWith('/api/notifications/templates/5/', expect.objectContaining({ name: 'Updated reminder' })));
  await waitFor(() => expect(page.container.querySelector('.modal-box')).toBeNull());
  fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
  await waitFor(() => expect(api.delete).toHaveBeenCalledWith('/api/notifications/templates/5/'));
});
test('fee schedule editing submits term, class level, category and amount', async () => {
  api.get.mockImplementation(async url => ({ data: url === '/api/terms/' ? [term]
    : url === '/api/class-levels/' ? [{ id: 3, name: 'JSS1' }]
    : url === '/api/fees/categories/' ? [{ id: 4, name: 'Tuition', is_compulsory: true }]
    : [{ class_level: 3, fee_category: 4, amount: '1000' }] }));
  await act(async () => renderPage(<FeeSetup />));
  fireEvent.change(screen.getByRole('spinbutton'), { target: { value: '1500' } });
  fireEvent.click(screen.getByRole('button', { name: /Save Schedule/ }));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/fees/schedule/', {
    term_id: 2, schedules: [{ class_level_id: 3, fee_category_id: 4, amount: '1500' }],
  }));
  expect(await screen.findByText('Fee schedule saved.')).toBeVisible();
});

test('teacher opens a register, marks absence with a remark, saves and locks it', async () => {
  api.get.mockImplementation(async url => ({ data: url === '/api/terms/' ? [term]
    : url === '/api/class-arms/' ? [{ id: 3, name: 'JSS1 A' }] : url.includes('/periods/') ? [] : { attendance_mode: 'daily' } }));
  const session = { id: 6, date: '2026-09-07', class_name: 'JSS1 A', is_finalized: false,
    records: [{ student: 7, student_name: 'Ada Student', student_admission: 'S001', status: 'present', remark: '' }] };
  api.post.mockResolvedValue({ data: session });
  api.patch.mockResolvedValue({ data: session });
  await act(async () => renderPage(<TakeAttendance />));
  expect(screen.getAllByRole('combobox')[0]).toHaveValue('2');
  fireEvent.change(screen.getAllByRole('combobox')[1], { target: { value: '3' } });
  fireEvent.click(screen.getByRole('button', { name: 'Open Register' }));
  expect(await screen.findByText('Ada Student')).toBeVisible();
  expect(api.post).toHaveBeenCalledWith('/api/attendance/sessions/start/', expect.objectContaining({ class_arm: 3, term: 2, mode: 'daily' }));
  fireEvent.click(screen.getByTitle('Absent'));
  fireEvent.change(screen.getByPlaceholderText(/Remark/), { target: { value: 'Reported ill' } });
  fireEvent.click(screen.getByRole('button', { name: /Save Attendance/ }));
  await waitFor(() => expect(api.patch).toHaveBeenCalledWith('/api/attendance/sessions/6/submit/', {
    records: [{ student_id: 7, status: 'absent', remark: 'Reported ill' }],
  }));
  await waitFor(() => expect(screen.getByRole('button', { name: /Lock Register/ })).toBeEnabled());
  fireEvent.click(screen.getByRole('button', { name: /Lock Register/ }));
  expect(await screen.findByText(/Register locked successfully/)).toBeVisible();
  expect(api.patch).toHaveBeenCalledWith('/api/attendance/sessions/6/finalize/');
  expect(screen.getByTitle('Present')).toBeDisabled();
});

test.each([false, true])('teacher saves scores with publish=%s using backend payload fields', async publish => {
  api.get.mockImplementation(async url => ({ data: url === '/api/terms/' ? [term]
    : url === '/api/sessions/' ? [{ id: 1, name: '2026/2027' }]
    : url === '/api/class-arms/' ? [{ id: 3, name: 'JSS1 A' }]
    : url === '/api/subjects/' ? [{ id: 4, name: 'Mathematics' }]
    : url.includes('grade-scale') ? { bands: [] }
    : url.includes('/students/') ? [{ id: 7, user: 41, full_name: 'Ada Student', admission_number: 'S001' }] : [] }));
  await act(async () => renderPage(<ScoreEntry />));
  const selects = screen.getAllByRole('combobox');
  fireEvent.change(selects[1], { target: { value: '1' } });
  fireEvent.change(selects[2], { target: { value: '3' } });
  fireEvent.change(selects[3], { target: { value: '4' } });
  await screen.findByText('Ada Student');
  fireEvent.change(screen.getAllByRole('spinbutton')[0], { target: { value: '8' } });
  fireEvent.click(screen.getByRole('button', { name: publish ? /Publish/ : /Save Draft/ }));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/gradebook/entries/bulk-update/', {
    class_arm: 3, subject: 4, term: 2, session: 1,
    scores: [{ student_id: 41, first_test: 8, second_test: 0, assignment: 0, project: 0, practical: 0, exam_score: 0 }],
  }));
  if (publish) expect(api.post).toHaveBeenCalledWith('/api/gradebook/entries/publish/?class_arm=3&subject=4&term=2');
  expect(await screen.findByText(publish ? /Scores saved and published/ : /Scores saved as draft/)).toBeVisible();
});

test.each(['fees', 'results'])('parent child %s uses the appropriate linked identifier', async mode => {
  api.get.mockImplementation(url => {
    if (url === '/api/parent/children/') return Promise.resolve({ data: [{ student_id: 7, user_id: 41, name: 'Ada Student' }] });
    if (url === '/api/terms/') return Promise.resolve({ data: [term] });
    if (mode === 'results') return Promise.reject({ response: { status: 404 } });
    return Promise.resolve({ data: [] });
  });
  await act(async () => renderPage(<ChildDetails mode={mode} />, { route: '/parent/:section/:studentId', path: `/parent/${mode}/7` }));
  expect(screen.getByRole('heading', { name: 'Ada Student' })).toBeVisible();
  expect(api.get).toHaveBeenCalledWith(mode === 'fees' ? '/api/fees/student/7/?term=2' : '/api/results/slip-data/41/?term=2');
});
test('parent child details do not load private data for an unlinked child', async () => {
  api.get.mockResolvedValue({ data: [] });
  await act(async () => renderPage(<ChildDetails mode="results" />, { route: '/parent/results/:studentId', path: '/parent/results/7' }));
  expect(screen.getByRole('alert')).toHaveTextContent('not linked');
  expect(api.get).toHaveBeenCalledTimes(1);
});
