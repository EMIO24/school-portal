import React from 'react';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { renderPage } from '../../../testSupport/renderPage';
import TimetableBuilder from '../../../pages/admin/TimetableBuilder';
import api from '../../../services/api';
jest.mock('../../../services/api', () => ({
  __esModule: true, default: { get: jest.fn(), post: jest.fn() },
}));
let periods;
beforeEach(() => {
  jest.resetAllMocks();
  periods = [];
  api.get.mockImplementation(async url => {
    if (url === '/api/terms/') return { data: [{ id: 1, name: 'First Term', is_current: true }] };
    if (url === '/api/class-arms/') return { data: [{ id: 2, full_name: 'JSS1A' }] };
    if (url.includes('/grid/')) return { data: { periods, entries: [] } };
    if (url.includes('/periods/')) return { data: { results: periods, next: null } };
    return { data: [] };
  });
  api.post.mockImplementation(async (url, data) => {
    const period = { ...data, id: 9 };
    periods.push(period);
    return { data: period };
  });
});
async function openForm() {
  fireEvent.click(screen.getByRole('button', { name: 'Add Period' }));
  await waitFor(() => expect(screen.getByRole('button', { name: 'Save Period' })).toBeEnabled());
  for (const [label, value] of [['Period name', 'Period 2'], ['Start time', '09:00'], ['End time', '10:00']]) {
    fireEvent.change(screen.getByLabelText(label), { target: { value } });
  }
}
test('creates a period without selecting a class and shows it when the class is selected', async () => {
  renderPage(<TimetableBuilder />);
  await openForm();
  fireEvent.click(screen.getByRole('button', { name: 'Save Period' }));
  expect(await screen.findByRole('status')).toHaveTextContent('Period 2 saved');
  expect(api.post).toHaveBeenCalledWith('/api/timetable/periods/', {
    name: 'Period 2', start_time: '09:00', end_time: '10:00', order_index: 1, is_break: false,
  });
  fireEvent.change(screen.getByLabelText('Class'), { target: { value: '2' } });
  expect(await screen.findByText('Period 2')).toBeVisible();
});
test('appends a break immediately to the selected timetable using the next display order', async () => {
  periods = [{ id: 1, name: 'Period 1', start_time: '08:00', end_time: '09:00', order_index: 4, is_break: false }];
  renderPage(<TimetableBuilder />);
  await screen.findByRole('option', { name: 'JSS1A' });
  fireEvent.change(screen.getByLabelText('Class'), { target: { value: '2' } });
  await screen.findByText('Period 1');
  await openForm();
  expect(screen.getByLabelText('Display order')).toHaveValue(5);
  fireEvent.click(screen.getByLabelText('Break (no lessons)'));
  fireEvent.click(screen.getByRole('button', { name: 'Save Period' }));
  expect(await screen.findByText('Period 2')).toBeVisible();
  expect(api.post).toHaveBeenCalledWith('/api/timetable/periods/', expect.objectContaining({ order_index: 5, is_break: true }));
});
test('rejects an end time before the start without posting', async () => {
  renderPage(<TimetableBuilder />);
  await openForm();
  fireEvent.change(screen.getByLabelText('End time'), { target: { value: '08:00' } });
  fireEvent.click(screen.getByRole('button', { name: 'Save Period' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('End time must be after start time');
  expect(api.post).not.toHaveBeenCalled();
});
test('keeps input and displays backend errors so the user can retry', async () => {
  api.post.mockRejectedValue({ response: { data: { order_index: ['Display order already exists.'] } } });
  renderPage(<TimetableBuilder />);
  await openForm();
  fireEvent.click(screen.getByRole('button', { name: 'Save Period' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Display order already exists');
  expect(screen.getByLabelText('Period name')).toHaveValue('Period 2');
  expect(screen.getByRole('button', { name: 'Save Period' })).toBeEnabled();
});