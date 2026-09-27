import React from 'react';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { renderPage } from '../../testSupport/renderPage';
import TeachingOperations from '../../pages/teacher/TeachingOperations';
import api from '../../services/api';

jest.mock('../../services/api', () => ({ __esModule: true, default: { get: jest.fn(), put: jest.fn() } }));

const lesson = outcome => ({
  slot_id: 4, class_arm: 2, class_name: 'JSS2A', subject: 3, subject_name: 'Mathematics',
  period_name: 'Period 3', period_start: '10:00', period_end: '11:00',
  scheduled_teacher: 7, scheduled_teacher_name: 'Teacher Ada', actual_teacher: null,
  actual_teacher_name: '', outcome, note: '', revision: outcome ? 1 : 0,
});
beforeEach(() => {
  jest.clearAllMocks();
  api.get.mockResolvedValue({ data: { holiday: false, lessons: [lesson(null)] } });
  api.put.mockResolvedValue({ data: lesson('delivered') });
});

test('teacher sees dated lesson and records delivered outcome from a card', async () => {
  const current = [lesson(null)];
  api.get.mockImplementation(async () => ({ data: { holiday: false, lessons: current } }));
  api.put.mockImplementation(async () => { current[0] = lesson('delivered'); return { data: current[0] }; });
  renderPage(<TeachingOperations />, { auth: { user: { role: 'teacher' } } });
  expect(await screen.findByText(/JSS2A · Mathematics/)).toBeVisible();
  expect(screen.getByText('Outcome not recorded')).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'Record outcome' }));
  fireEvent.click(screen.getByRole('button', { name: 'Save outcome' }));
  await waitFor(() => expect(api.put).toHaveBeenCalledWith(
    expect.stringMatching(/\/api\/timetable\/lessons\/4\//),
    { outcome: 'delivered', note: '', revision: 0 },
  ));
  expect(await screen.findByRole('status')).toHaveTextContent('Lesson outcome saved.');
  expect(screen.getByText('Delivered')).toBeVisible();
});

test('uncertain save reads authoritative outcome before claiming success', async () => {
  let reads = 0;
  api.get.mockImplementation(async () => {
    reads += 1;
    return { data: { holiday: false, lessons: [lesson(reads > 1 ? 'missed' : null)] } };
  });
  api.put.mockRejectedValue(new Error('connection lost'));
  renderPage(<TeachingOperations />, { auth: { user: { role: 'teacher' } } });
  await screen.findByText('Outcome not recorded');
  fireEvent.click(screen.getByRole('button', { name: 'Record outcome' }));
  fireEvent.click(screen.getByRole('button', { name: 'Save outcome' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('could not be confirmed');
  expect(screen.queryByText('Lesson outcome saved.')).not.toBeInTheDocument();
});

test('admin can filter and choose a substitute', async () => {
  api.get.mockImplementation(async url => ({ data: url.startsWith('/api/staff/')
    ? [{ user: 8, full_name: 'Substitute', employment_status: 'active' }]
    : { holiday: false, lessons: [lesson(null)] } }));
  renderPage(<TeachingOperations admin />);
  await screen.findByText('Outcome not recorded');
  fireEvent.change(screen.getByLabelText('Filter outcome'), { target: { value: 'missed' } });
  expect(screen.getByText('No scheduled lessons or recorded outcomes for this date.')).toBeVisible();
  fireEvent.change(screen.getByLabelText('Filter outcome'), { target: { value: '' } });
  fireEvent.click(screen.getByRole('button', { name: 'Record outcome' }));
  fireEvent.change(screen.getByLabelText('Lesson outcome'), { target: { value: 'substituted' } });
  expect(screen.getByLabelText('Substitute teacher')).toHaveValue('');
  expect(screen.getAllByRole('option', { name: 'Substitute' })).toHaveLength(2);
});

test('date change reloads lessons and admin can record cancellation', async () => {
  api.get.mockImplementation(async url => ({ data: url.startsWith('/api/staff/')
    ? [] : { holiday: false, lessons: [lesson(null)] } }));
  renderPage(<TeachingOperations admin />);
  await screen.findByText('Outcome not recorded');
  fireEvent.change(screen.getByLabelText('Lesson date'), { target: { value: '2026-09-21' } });
  await waitFor(() => expect(api.get).toHaveBeenCalledWith('/api/timetable/lessons/',
    { params: { date: '2026-09-21' } }));
  fireEvent.click(screen.getByRole('button', { name: 'Record outcome' }));
  fireEvent.change(screen.getByLabelText('Lesson outcome'), { target: { value: 'cancelled' } });
  fireEvent.click(screen.getByRole('button', { name: 'Save outcome' }));
  await waitFor(() => expect(api.put).toHaveBeenCalledWith(
    '/api/timetable/lessons/4/2026-09-21/',
    { outcome: 'cancelled', note: '', revision: 0 },
  ));
});

test('stale correction reloads current revision before another save', async () => {
  let reads = 0;
  api.get.mockImplementation(async () => {
    reads += 1;
    return { data: { holiday: false, lessons: [{ ...lesson('missed'), revision: reads > 1 ? 2 : 1 }] } };
  });
  api.put.mockRejectedValue({ response: { status: 409, data: { detail: 'The lesson changed.' } } });
  renderPage(<TeachingOperations admin />);
  fireEvent.click(await screen.findByRole('button', { name: 'Review / correct' }));
  fireEvent.change(screen.getByLabelText('Lesson outcome'), { target: { value: 'cancelled' } });
  fireEvent.click(screen.getByRole('button', { name: 'Save outcome' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Review its latest outcome');
  expect(screen.getByLabelText('Lesson outcome')).toHaveValue('missed');
});
