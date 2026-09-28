import React from 'react';
import {fireEvent, screen, waitFor} from '@testing-library/react';
import {renderPage} from '../../testSupport/renderPage';
import FinanceAccount from '../../pages/admin/FinanceAccount';
import api from '../../services/api';

jest.mock('../../services/api', () => ({__esModule: true, default: {get: jest.fn(), post: jest.fn()}}));

const account = {student_name: 'Ada Student', state: 'active', balance: '1000.00',
  outstanding: '1000.00', credit: '0.00', results: [{id: 11, kind: 'charge', description: 'Tuition',
    amount: '1000.00', running_balance: '1000.00', effective_date: '2026-09-01'}], next: null,
  legacy_receipts: []};
const fee = [{schedule: {id: 4, fee_category_name: 'Tuition', term_name: 'First'},
  charge_state: 'charged', outstanding: '1000.00'}];

beforeEach(() => {
  jest.clearAllMocks();
  api.get.mockImplementation(async url => ({data: url.includes('/ledger/student/') ? account : fee}));
  api.post.mockResolvedValue({data: {id: 12}});
  jest.spyOn(window, 'confirm').mockReturnValue(true);
});
afterEach(() => jest.restoreAllMocks());

test('admin sees account history and records a discount with a retry key', async () => {
  renderPage(<FinanceAccount />, {path: '/admin/finance/7', route: '/admin/finance/:studentId'});
  expect(await screen.findByText('Ada Student')).toBeVisible();
  expect(await screen.findByText('Tuition')).toBeVisible();
  fireEvent.change(screen.getByLabelText('Change type'), {target: {value: 'discount'}});
  fireEvent.change(screen.getByLabelText('Fee item'), {target: {value: '4'}});
  fireEvent.change(screen.getByLabelText('Amount (₦)'), {target: {value: '50.00'}});
  fireEvent.change(screen.getByLabelText('Reason / verification reference'), {target: {value: 'Approved sibling discount'}});
  fireEvent.click(screen.getByRole('button', {name: 'Record change'}));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/fees/ledger/changes/',
    expect.objectContaining({kind: 'discount', amount: '50.00', fee_schedule_id: 4,
      reason: 'Approved sibling discount', idempotency_key: expect.any(String)})));
});

test('uncertain finance write retains identical payload and retry key', async () => {
  api.post.mockRejectedValueOnce(new Error('connection lost')).mockResolvedValueOnce({data: {id: 13}});
  renderPage(<FinanceAccount />, {path: '/admin/finance/7', route: '/admin/finance/:studentId'});
  await screen.findByText('Ada Student');
  await waitFor(() => expect(screen.getByLabelText('Change type')).toHaveValue('payment'));
  fireEvent.change(screen.getByLabelText('Fee item'), {target: {value: '4'}});
  fireEvent.change(screen.getByLabelText('Amount (₦)'), {target: {value: '250.00'}});
  fireEvent.click(screen.getByRole('button', {name: 'Record change'}));
  expect(await screen.findByText(/response is uncertain/)).toBeVisible();
  const first = api.post.mock.calls[0];
  fireEvent.click(screen.getByRole('button', {name: 'Retry same request'}));
  await waitFor(() => expect(api.post).toHaveBeenCalledTimes(2));
  expect(api.post.mock.calls[1]).toEqual(first);
});

test('unverified balance is shown as unknown', async () => {
  api.get.mockImplementation(async url => ({data: url.includes('/ledger/student/')
    ? {...account, state: 'legacy_review', balance: null, outstanding: null, results: []}
    : []}));
  renderPage(<FinanceAccount />, {path: '/admin/finance/7', route: '/admin/finance/:studentId'});
  expect(await screen.findByText(/Opening balance requires school verification/)).toBeVisible();
  expect(screen.getByLabelText('Change type')).toHaveValue('opening');
  expect(screen.queryByText('₦0')).not.toBeInTheDocument();
});
