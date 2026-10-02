import React from 'react';
import {fireEvent, screen, waitFor} from '@testing-library/react';
import {renderPage} from '../../testSupport/renderPage';
import TakeAttendance from '../../pages/teacher/TakeAttendance';
import api from '../../services/api';
import {referenceOptions} from '../../services/referenceOptions';

jest.mock('../../services/api', () => ({__esModule: true, default: {get: jest.fn(), post: jest.fn(), patch: jest.fn()}}));
jest.mock('../../services/referenceOptions', () => ({referenceOptions: jest.fn()}));

const session = status => ({id: 9, class_name: 'JSS1A', date: '2026-09-26', is_finalized: false,
  records: [{student: 101, student_name: 'Test Student', student_admission: 'ADM1', status, remark: ''}]});

beforeEach(() => {
  jest.clearAllMocks();
  referenceOptions.mockImplementation(async url => ({data: url === '/api/terms/'
    ? [{id: 1, name: 'First term', is_current: true}]
    : [{id: 1, name: 'JSS1A'}]}));
  api.get.mockImplementation(async url => ({data: url === '/api/school/me/'
    ? {attendance_mode: 'daily'} : url === '/api/timetable/periods/' ? [] : session('present')}));
  api.post.mockResolvedValue({data: session('present')});
});

test('uncertain attendance save keeps marks until the register confirms them', async () => {
  api.patch.mockRejectedValue(new Error('connection lost'));
  renderPage(<TakeAttendance />);
  await screen.findByRole('option', {name: 'JSS1A'});
  fireEvent.change(screen.getAllByRole('combobox')[1], {target: {value: '1'}});
  fireEvent.click(screen.getByRole('button', {name: /Open Register/}));
  await screen.findByText('Test Student');
  fireEvent.click(screen.getByTitle('Absent'));
  fireEvent.click(screen.getByRole('button', {name: /Save Attendance/}));
  expect(await screen.findByText(/Could not confirm the save/)).toBeVisible();
  expect(screen.getByTitle('Absent')).toHaveClass('active');
  api.get.mockImplementation(async url => ({data: url.includes('/api/attendance/sessions/9/')
    ? session('absent') : {attendance_mode: 'daily'}}));
  fireEvent.click(screen.getByRole('button', {name: /Save Attendance/}));
  expect(await screen.findByText(/register confirms your entries/)).toBeVisible();
  await waitFor(() => expect(api.patch).toHaveBeenCalledTimes(2));
});


test('late attendance sends the recorded arrival time as presence evidence', async () => {
  api.patch.mockResolvedValue({data: session('late')});
  renderPage(<TakeAttendance />);
  await screen.findByRole('option', {name: 'JSS1A'});
  fireEvent.change(screen.getAllByRole('combobox')[1], {target: {value: '1'}});
  fireEvent.click(screen.getByRole('button', {name: /Open Register/}));
  await screen.findByText('Test Student');

  fireEvent.click(screen.getByTitle('Late'));
  const arrival = screen.getByLabelText('Arrival time for Test Student');
  fireEvent.change(arrival, {target: {value: '08:17'}});
  fireEvent.click(screen.getByRole('button', {name: /Save Attendance/}));

  await waitFor(() => expect(api.patch).toHaveBeenCalled());
  const call = api.patch.mock.calls.find(([url]) => url.includes('/api/attendance/sessions/9/submit/'));
  expect(call[1].records[0]).toEqual(expect.objectContaining({
    student_id: 101,
    status: 'late',
    arrival_time: '08:17',
  }));
});
