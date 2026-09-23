import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import PaymentExceptions from '../../pages/payments/PaymentExceptions';
import api from '../../services/api';
jest.mock('../../services/api', () => ({ __esModule: true, default: { get: jest.fn(), post: jest.fn(), patch: jest.fn() } }));
const base = '/api/platform/payment-exceptions/';
const entry = { id: 1, school_id: 4, reference: 'SCH-case', kind: 'refund', status: 'under_review', reason: 'Mistaken payment',
  updated_at: '2026-09-23', admin_notes: 'Investigating', payment: { amount: '100', currency: 'NGN', kind: 'fees', status: 'success', mode: 'test', allocations: [] }, history: [] };
beforeEach(() => { jest.resetAllMocks(); api.get.mockImplementation(async url => ({ data: url === base ? { results: [entry], next_before: null } : entry })); });
test('owner can inspect and record approval without calling a provider', async () => {
  api.patch.mockResolvedValue({ data: { ...entry, status: 'approved' } });
  render(<PaymentExceptions/>);
  expect(api.get).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText('Open exception operations'));
  fireEvent.click(await screen.findByText('Inspect case 1'));
  fireEvent.change(await screen.findByLabelText('Next case state'), { target: { value: 'approved' } });
  fireEvent.change(screen.getByLabelText('Internal investigation note'), { target: { value: 'Approved after investigation' } });
  fireEvent.click(screen.getByText('Record case update'));
  await waitFor(() => expect(api.patch).toHaveBeenCalledWith(base + '1/', { expected_status: 'under_review', status: 'approved', admin_notes: 'Approved after investigation', provider_ref: '' }));
  expect(api.post).not.toHaveBeenCalled();
  expect(screen.getByText(/does not send money/)).toBeVisible();
});
test('owner can report a suspected duplicate using an existing payment reference', async () => {
  api.post.mockResolvedValue({ data: { id: 1 } });
  render(<PaymentExceptions/>);
  fireEvent.click(screen.getByText('Open exception operations'));
  fireEvent.change(await screen.findByLabelText('Payment reference'), { target: { value: 'SCH-case' } });
  fireEvent.change(screen.getByLabelText('Report type'), { target: { value: 'duplicate' } });
  fireEvent.change(screen.getByLabelText('Reason'), { target: { value: 'Two charges reported' } });
  await waitFor(() => expect(screen.getByText('Create case')).toBeEnabled());
  fireEvent.click(screen.getByText('Create case'));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith(base, { reference: 'SCH-case', kind: 'duplicate', reason: 'Two charges reported' }));
});
