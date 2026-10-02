import React from 'react';
import {fireEvent, screen, waitFor} from '@testing-library/react';
import {renderPage} from '../../testSupport/renderPage';
import StudentPresence from '../../pages/common/StudentPresence';
import api from '../../services/api';

jest.mock('../../services/api', () => ({__esModule: true, default: {
  get: jest.fn(), post: jest.fn(), patch: jest.fn(),
}}));

beforeEach(() => {
  jest.clearAllMocks();
  window.confirm = jest.fn(() => true);
});

test('school admin can configure optional clockout and arrival cutoff', async () => {
  api.get.mockImplementation(async url => {
    if (url === '/api/attendance/presence/settings/') return {data: {
      arrival_cutoff_time: '07:45', student_clockout_enabled: false,
      classes: [{id: 1, name: 'JSS1A'}],
    }};
    if (url === '/api/attendance/presence/') return {data: {
      students: [{student_id: 5, student_name: 'Ada Student', admission_number: 'ADM-1', presence: null}],
    }};
    return {data: {}};
  });
  api.patch.mockResolvedValue({data: {
    arrival_cutoff_time: '07:45', student_clockout_enabled: true,
    classes: [{id: 1, name: 'JSS1A'}],
  }});

  renderPage(<StudentPresence />);
  expect(await screen.findByText('Student Presence')).toBeVisible();
  expect(screen.getByLabelText('Late after')).toHaveValue('07:45');
  fireEvent.click(screen.getByLabelText(/Enable student clock-out/));
  fireEvent.click(screen.getByRole('button', {name: 'Save presence settings'}));
  await waitFor(() => expect(api.patch).toHaveBeenCalledWith(
    '/api/attendance/presence/settings/',
    {arrival_cutoff_time: '07:45', student_clockout_enabled: true},
  ));
});

test('class teacher records arrival and clocks out only through presence API', async () => {
  let clocked = false;
  api.get.mockImplementation(async url => {
    if (url === '/api/attendance/presence/settings/') return {data: {
      arrival_cutoff_time: '07:45', student_clockout_enabled: true,
      classes: [{id: 1, name: 'JSS1A'}],
    }};
    if (url === '/api/attendance/presence/') return {data: {
      students: [{
        student_id: 5, student_name: 'Ada Student', admission_number: 'ADM-1',
        presence: clocked ? {arrival_time: '08:17', late: true, departure_time: '15:26'}
          : {arrival_time: '08:17', late: true, departure_time: null},
      }],
    }};
    return {data: {}};
  });
  api.post.mockImplementation(async url => {
    if (url.endsWith('/clock-out/')) clocked = true;
    return {data: {}};
  });

  renderPage(<StudentPresence />, {
    auth: {user: {id: 12, role: 'class_teacher', full_name: 'Chi Teacher'}},
  });
  expect(await screen.findByText('08:17')).toBeVisible();
  expect(screen.getByText('Late')).toBeVisible();
  fireEvent.click(screen.getByRole('button', {name: 'Clock out'}));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith(
    '/api/attendance/presence/clock-out/', {student: 5},
  ));
  expect(await screen.findByText('15:26')).toBeVisible();
  expect(screen.queryByText('School settings')).not.toBeInTheDocument();
});
