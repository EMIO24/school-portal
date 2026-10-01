import React from 'react';
import {fireEvent, screen, waitFor} from '@testing-library/react';
import {renderPage} from '../../testSupport/renderPage';
import Promotion from '../../pages/admin/Promotion';
import api from '../../services/api';

jest.mock('../../services/api', () => ({
  __esModule: true,
  default: {get: jest.fn(), post: jest.fn()},
}));

beforeEach(() => {
  jest.resetAllMocks();
  api.get.mockImplementation(async url => {
    if (url === '/api/sessions/') return {data: [
      {id: 1, name: '2026/27', start_date: '2026-09-01'},
      {id: 2, name: '2027/28', start_date: '2027-09-01'},
    ]};
    if (url === '/api/class-levels/') return {data: [
      {id: 11, name: 'JSS1', order_index: 1},
      {id: 12, name: 'JSS2', order_index: 2},
    ]};
    if (url === '/api/class-arms/') return {data: [
      {id: 21, class_level: 11, full_name: 'JSS1A'},
      {id: 22, class_level: 12, full_name: 'JSS2A'},
    ]};
    return {data: []};
  });
  api.post.mockImplementation(async url => {
    if (url.startsWith('/api/promotion/evaluate/')) return {data: [{
      student_id: 31,
      student_name: 'Ada Student',
      class: 'JSS1A',
      class_arm_id: 21,
      class_level_id: 11,
      session_avg: 75,
      subjects_passed: 8,
      attendance_pct: 95,
      criteria_met: true,
      recommended: 'promoted',
    }]};
    return {data: {executed: 1, graduated: 0}};
  });
});

test('promotion requires and submits a higher destination class', async () => {
  const {container} = renderPage(<Promotion />);

  await waitFor(() => expect(api.get).toHaveBeenCalledWith('/api/class-arms/'));

  const sourceSession = container.querySelector('.promo-controls > select');
  fireEvent.change(sourceSession, {target: {value: '1'}});
  fireEvent.click(screen.getByRole('button', {name: 'Evaluate Students'}));

  expect(await screen.findByText('Ada Student')).toBeVisible();

  fireEvent.click(screen.getByRole('button', {name: /Stage All Decisions/}));
  fireEvent.click(screen.getByRole('button', {name: 'Confirm & Save Decisions'}));
  expect(await screen.findByText('Select the destination academic session.')).toBeVisible();

  const destinationSession = screen.getByLabelText('Destination session');
  fireEvent.change(destinationSession, {target: {value: '2'}});
  fireEvent.click(screen.getByRole('button', {name: 'Confirm & Save Decisions'}));
  expect(await screen.findByText('Select a destination class for Ada Student.')).toBeVisible();

  fireEvent.change(
    screen.getByRole('combobox', {name: 'Destination class for Ada Student'}),
    {target: {value: '22'}},
  );
  fireEvent.click(screen.getByRole('button', {name: 'Confirm & Save Decisions'}));

  await waitFor(() => expect(api.post).toHaveBeenCalledWith(
    '/api/promotion/execute/',
    [expect.objectContaining({
      student_id: 31,
      session_id: 1,
      to_session_id: 2,
      to_class_id: 22,
      decision: 'promoted',
      criteria_met: true,
    })],
  ));
});
