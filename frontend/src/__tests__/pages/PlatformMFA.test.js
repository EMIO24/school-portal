import React from 'react';
import { screen, fireEvent } from '@testing-library/react';
import { renderPage } from '../../testSupport/renderPage';
import PlatformMFA from '../../pages/platform/PlatformMFA';
import PlatformTeam from '../../pages/platform/PlatformTeam';
import api from '../../services/api';
jest.mock('../../services/api', () => ({ __esModule: true, default: { post: jest.fn(), get: jest.fn(), patch: jest.fn() } }));
beforeEach(() => jest.resetAllMocks());

test('enrollment requires verification and recovery-code acknowledgement before login', async () => {
  const finishLogin = jest.fn();
  const result = { access: 'access', refresh: 'refresh', recovery_codes: ['recovery-one'] };
  api.post.mockResolvedValue({ data: result });
  renderPage(<PlatformMFA challenge={{ mfa_setup_required: true, secret: 'TESTSECRET', qr_code: 'data:image/png;base64,', challenge: 'signed' }} />, { auth: { finishLogin } });
  expect(screen.getByText('TESTSECRET')).toBeVisible();
  fireEvent.change(screen.getByLabelText('Verification code'), { target: { value: '123456' } });
  fireEvent.click(screen.getByRole('button', { name: 'Verify code' }));
  expect(await screen.findByText('recovery-one')).toBeVisible();
  expect(finishLogin).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'I saved my codes - continue' }));
  expect(finishLogin).toHaveBeenCalledWith(result);
});

test('incorrect code displays an error without granting access', async () => {
  const finishLogin = jest.fn();
  api.post.mockRejectedValue({ response: { data: { detail: 'Invalid or already used code.' } } });
  renderPage(<PlatformMFA challenge={{ challenge: 'signed' }} />, { auth: { finishLogin } });
  fireEvent.change(screen.getByLabelText('Verification code'), { target: { value: 'bad' } });
  fireEvent.click(screen.getByRole('button', { name: 'Verify code' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Invalid or already used code');
  expect(finishLogin).not.toHaveBeenCalled();
});

test('read-only platform staff cannot open account management', () => {
  renderPage(<PlatformTeam />, { auth: { user: { id: 2, role: 'superadmin', platformAccess: 'viewer' } } });
  expect(screen.getByText('Owner access required')).toBeVisible();
  expect(api.get).not.toHaveBeenCalled();
});
