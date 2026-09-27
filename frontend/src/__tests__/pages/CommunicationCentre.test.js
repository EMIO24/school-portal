import React from 'react';
import {fireEvent, screen, waitFor} from '@testing-library/react';
import {renderPage} from '../../testSupport/renderPage';
import CommunicationCentre from '../../pages/admin/CommunicationCentre';
import NoticeInbox from '../../pages/common/NoticeInbox';
import api from '../../services/api';

jest.mock('../../services/api', () => ({__esModule: true, default: {get: jest.fn(), post: jest.fn()}}));

beforeEach(() => {
  jest.resetAllMocks();
  api.get.mockImplementation(async url => ({data: url.includes('/class-arms/') ? [{id: 4, full_name: 'JSS2A'}]
    : url.includes('/recipients/') ? [{id: 7, name: 'Parent One'}]
      : {results: [], next: null, count: 0}}));
  api.post.mockImplementation(async url => ({data: url.includes('/preview/')
    ? {recipient_count: 1, label: 'Parents of a class: JSS2A', students_without_linked_parent: 2}
    : {id: 42, recipient_count: 1, replayed: false}}));
  Object.defineProperty(window, 'crypto', {configurable: true, value: {randomUUID: () => 'test-key'}});
  jest.spyOn(window, 'confirm').mockReturnValue(true);
});
afterEach(() => {window.confirm.mockRestore();});

test('admin previews class parents and publishes one portal notice', async () => {
  renderPage(<CommunicationCentre />);
  fireEvent.change(screen.getByLabelText('Audience'), {target: {value: 'class_parents'}});
  fireEvent.change(await screen.findByLabelText('Class'), {target: {value: '4'}});
  fireEvent.click(screen.getByRole('button', {name: 'Preview recipients'}));
  expect(await screen.findByText('1 unique portal accounts')).toBeVisible();
  expect(screen.getByText(/2 active students have no linked parent/)).toBeVisible();
  fireEvent.change(screen.getByLabelText('Title'), {target: {value: 'Meeting'}});
  fireEvent.change(screen.getByLabelText('Message'), {target: {value: 'Please attend.'}});
  fireEvent.click(screen.getByRole('button', {name: 'Publish portal notice'}));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/communications/send/',
    expect.objectContaining({audience: 'class_parents', class_arm_id: 4, title: 'Meeting', body: 'Please attend.', channels: ['portal']}),
    {headers: {'Idempotency-Key': 'test-key'}}));
  expect(await screen.findByText(/Notice #42 is available/)).toBeVisible();
});

test('zero recipients block publishing and selected parents show account choices', async () => {
  api.post.mockResolvedValue({data: {recipient_count: 0, label: 'All linked parents', students_without_linked_parent: 0}});
  renderPage(<CommunicationCentre />);
  fireEvent.click(screen.getByRole('button', {name: 'Preview recipients'}));
  expect(await screen.findByText('No linked portal accounts in this audience.')).toBeVisible();
  expect(screen.getByRole('button', {name: 'Publish portal notice'})).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Audience'), {target: {value: 'selected_parents'}});
  expect(await screen.findByText('Parent One')).toBeVisible();
  fireEvent.click(screen.getByRole('checkbox'));
  fireEvent.click(screen.getByRole('button', {name: 'Preview recipients'}));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/communications/preview/',
    expect.objectContaining({audience: 'selected_parents', recipient_ids: [7]})));
});

test('uncertain send keeps request key and asks sender to check history', async () => {
  api.post.mockImplementation(async url => {
    if (url.includes('/preview/')) return {data: {recipient_count: 1, label: 'All linked parents'}};
    throw new Error('offline');
  });
  renderPage(<CommunicationCentre />);
  fireEvent.click(screen.getByRole('button', {name: 'Preview recipients'}));
  await screen.findByText('1 unique portal accounts');
  fireEvent.change(screen.getByLabelText('Title'), {target: {value: 'Notice'}});
  fireEvent.change(screen.getByLabelText('Message'), {target: {value: 'Body'}});
  fireEvent.click(screen.getByRole('button', {name: 'Publish portal notice'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Check history first');
  fireEvent.click(screen.getByRole('button', {name: 'Publish portal notice'}));
  await waitFor(() => expect(api.post.mock.calls.filter(([url]) => url.includes('/send/')).length).toBe(2));
  expect(api.post.mock.calls.filter(([url]) => url.includes('/send/')).map(([, , config]) => config.headers['Idempotency-Key']))
    .toEqual(['test-key', 'test-key']);
});

test('recipient inbox shows and marks notice opened', async () => {
  api.get.mockResolvedValue({data: {results: [{id: 8, title: 'Holiday', body: 'School closes early.',
    sender_name: 'Admin', published_at: '2026-09-27T12:00:00Z', read_at: null}], next: null}});
  api.post.mockResolvedValue({data: {id: 8, read_at: '2026-09-27T12:01:00Z'}});
  renderPage(<NoticeInbox />);
  fireEvent.click(await screen.findByText('Holiday'));
  expect(screen.getByText('School closes early.')).toBeVisible();
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/communications/inbox/8/read/'));
  expect(await screen.findByText(/Opened/)).toBeVisible();
});
