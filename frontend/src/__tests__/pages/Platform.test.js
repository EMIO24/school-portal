import React from 'react';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { renderPage } from '../../testSupport/renderPage';
import PlatformDashboard from '../../pages/platform/PlatformDashboard';
import SchoolSignup from '../../pages/platform/SchoolSignup';
import api from '../../services/api';
jest.mock('../../services/api', () => ({ __esModule: true, default: { get: jest.fn(), post: jest.fn(), patch: jest.fn() } }));
const school = { id: 1, name: 'Greenfield', subdomain: 'greenfield', approval_status: 'pending', is_active: false,
  subscription_plan: 'free', email: 'office@greenfield.test', phone: '', address: '', platform_notes: '',
  usage: { student_count: 40, teacher_count: 3, admin_count: 1 },
  administrators: [{ id: 7, email: 'admin@greenfield.test', first_name: 'Ada', last_name: 'Test', is_active: true }], activity: [] };
beforeEach(() => { jest.resetAllMocks(); api.get.mockImplementation(async url => ({ data: url.includes('?')
  ? { summary: { schools: 1, pending: 1, active: 0, users: 44 }, results: [school], count: 1 } : school })); });

test('owner reviews a registration, approves it, and saves the renewal date', async () => {
  renderPage(<PlatformDashboard />);
  fireEvent.click(await screen.findByRole('button', { name: 'Manage Greenfield' }));
  api.post.mockResolvedValue({ data: { ...school, approval_status: 'approved', is_active: true } });
  fireEvent.click(await screen.findByRole('button', { name: 'Approve school' }));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/platform/schools/1/', { action: 'approve' }));
  await screen.findByRole('button', { name: 'Suspend school' });
  api.patch.mockResolvedValue({ data: { ...school, subscription_plan: 'premium', subscription_ends_on: '2027-01-01' } });
  fireEvent.change(screen.getByLabelText('Subscription plan'), { target: { value: 'premium' } });
  fireEvent.change(screen.getByLabelText('Renewal date'), { target: { value: '2027-01-01' } });
  fireEvent.click(screen.getByRole('button', { name: 'Save school details' }));
  await waitFor(() => expect(api.patch).toHaveBeenCalledWith('/api/platform/schools/1/', expect.objectContaining({ subscription_plan: 'premium', subscription_ends_on: '2027-01-01' })));
});

test('failed school list can be retried and filtered', async () => {
  api.get.mockRejectedValueOnce(new Error('offline'));
  renderPage(<PlatformDashboard />);
  expect(await screen.findByRole('alert')).toHaveTextContent('Could not connect');
  fireEvent.click(screen.getByRole('button', { name: 'Retry school list' }));
  await screen.findByRole('button', { name: 'Manage Greenfield' });
  fireEvent.change(screen.getByLabelText('Search schools'), { target: { value: 'green' } });
  await waitFor(() => expect(api.get).toHaveBeenCalledWith(expect.stringContaining('search=green')));
});

function fillSignup() {
  const fields = { 'School name': 'New School', 'School identifier': 'new-school', 'School contact email': 'office@new.test',
    'Administrator first name': 'New', 'Administrator last name': 'Admin', 'Administrator email': 'admin@new.test',
    'Administrator password': 'GoodPassword!2026', 'Confirm password': 'GoodPassword!2026' };
  for (const [label, value] of Object.entries(fields)) fireEvent.change(screen.getByLabelText(label, { exact: false }), { target: { value } });
}

test('public signup submits the administrator and displays pending confirmation', async () => {
  api.post.mockResolvedValue({ data: { subdomain: 'new-school', approval_status: 'pending' } });
  renderPage(<SchoolSignup />); fillSignup();
  fireEvent.click(screen.getByRole('button', { name: 'Submit school registration' }));
  expect(await screen.findByRole('heading', { name: 'Registration submitted' })).toBeVisible();
  expect(api.post).toHaveBeenCalledWith('/api/platform/register/', expect.objectContaining({ name: 'New School', administrator: expect.objectContaining({ email: 'admin@new.test' }) }));
  expect(screen.getByRole('link', { name: 'School sign in' })).toHaveAttribute('href', '/login?school=new-school');
});

test('signup validates matching passwords and preserves fields after a server error', async () => {
  renderPage(<SchoolSignup />); fillSignup();
  fireEvent.change(screen.getByLabelText('Confirm password'), { target: { value: 'different' } });
  fireEvent.click(screen.getByRole('button', { name: 'Submit school registration' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Passwords do not match');
  expect(api.post).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText('Confirm password'), { target: { value: 'GoodPassword!2026' } });
  api.post.mockRejectedValue({ response: { data: { subdomain: ['Already in use.'] } } });
  fireEvent.click(screen.getByRole('button', { name: 'Submit school registration' }));
  await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Already in use'));
  expect(screen.getByLabelText('School name')).toHaveValue('New School');
});
