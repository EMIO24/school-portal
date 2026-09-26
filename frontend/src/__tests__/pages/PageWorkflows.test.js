import React from 'react';
import { act, screen, fireEvent, waitFor } from '@testing-library/react';
import { renderPage } from '../../testSupport/renderPage';
import ChangePassword from '../../pages/public/ChangePassword';
import CheckResult from '../../pages/public/CheckResult';
import ParentLogin from '../../pages/parent/ParentLogin';
import BulkImportPage from '../../pages/admin/BulkImportPage';
import Fees from '../../pages/student/Fees';
import MyResult from '../../pages/student/MyResult';
import ExamRoom from '../../pages/student/ExamRoom';
import ExamReview from '../../pages/student/ExamReview';
import Notifications from '../../pages/admin/Notifications';
import FeeCollection from '../../pages/admin/FeeCollection';
import { downloadReport } from '../../services/pdf';
import api, { authAPI, tokenStore } from '../../services/api';
import axios from 'axios';

jest.mock('../../services/api', () => ({
  __esModule: true, default: { get: jest.fn(), post: jest.fn(), patch: jest.fn() },
  authAPI: { changePassword: jest.fn() }, tokenStore: { setTokens: jest.fn() },
}));
jest.mock('axios', () => ({ __esModule: true, default: { post: jest.fn() } }));
jest.mock('../../services/pdf', () => ({ downloadReport: jest.fn() }));
const originalFetch = global.fetch;
beforeEach(() => {
  jest.clearAllMocks();
  global.fetch = jest.fn();
  api.get.mockResolvedValue({ data: [] });
  api.post.mockResolvedValue({ data: {} });
});
afterEach(() => { global.fetch = originalFetch; jest.restoreAllMocks(); });

test('ChangePassword rejects mismatched confirmation before calling the API', () => {
  const { container } = renderPage(<ChangePassword />);
  fireEvent.change(screen.getByLabelText('Current Password'), { target: { value: 'OldPassword1!' } });
  fireEvent.change(screen.getByLabelText('New Password'), { target: { value: 'NewPassword1!' } });
  fireEvent.change(screen.getByLabelText('Confirm New Password'), { target: { value: 'DifferentPassword1!' } });
  fireEvent.submit(container.querySelector('form'));
  expect(screen.getByRole('alert')).toHaveTextContent('Passwords do not match');
  expect(authAPI.changePassword).not.toHaveBeenCalled();
});

test('ChangePassword submits valid credentials and updates authentication state', async () => {
  authAPI.changePassword.mockResolvedValue({ data: {} });
  const { container, auth } = renderPage(<ChangePassword />);
  for (const [label, value] of [['Current Password', 'OldPassword1!'], ['New Password', 'NewPassword1!'], ['Confirm New Password', 'NewPassword1!']]) {
    fireEvent.change(screen.getByLabelText(label), { target: { value } });
  }
  fireEvent.submit(container.querySelector('form'));
  expect(await screen.findByRole('heading', { name: 'Password Changed!' })).toBeVisible();
  expect(authAPI.changePassword).toHaveBeenCalledWith({ current_password: 'OldPassword1!', new_password: 'NewPassword1!', confirm_password: 'NewPassword1!' });
  expect(auth.updateUser).toHaveBeenCalledWith({ mustChangePassword: false });
});

test.each([[403, 'Incorrect PIN'], [404, 'No record found'], [500, 'Something went wrong']])('CheckResult handles HTTP %s', async (status, message) => {
  axios.post.mockRejectedValue({ response: { status, data: {} } });
  const { container } = renderPage(<CheckResult />);
  fireEvent.change(screen.getByLabelText('Admission Number'), { target: { value: ' ab-123 ' } });
  fireEvent.change(screen.getByLabelText('Serial Number'), { target: { value: ' cd-456 ' } });
  fireEvent.change(screen.getByLabelText('PIN'), { target: { value: '1234567890' } });
  fireEvent.submit(container.querySelector('form'));
  expect(await screen.findByText(new RegExp(message))).toBeVisible();
  expect(axios.post).toHaveBeenCalledWith(expect.stringContaining('/api/results/check/'), {
    admission_number: 'AB-123', serial_number: 'CD-456', pin: '1234567890',
  }, { headers: {} });
});

test('ParentLogin requests an OTP, rejects invalid codes, then accepts a valid code', async () => {
  global.fetch.mockResolvedValueOnce({ ok: true })
    .mockResolvedValueOnce({ ok: false, json: async () => ({ error: 'Invalid OTP.' }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ access: 'access', refresh: 'refresh' }) });
  const loadUser = jest.fn().mockResolvedValue();
  renderPage(<ParentLogin />, { auth: { loadUser } });
  expect(screen.getByRole('button', { name: 'Send OTP' })).toBeDisabled();
  fireEvent.change(screen.getByPlaceholderText('080xxxxxxxx'), { target: { value: '08012345678' } });
  fireEvent.click(screen.getByRole('button', { name: 'Send OTP' }));
  const code = await screen.findByPlaceholderText('123456');
  fireEvent.change(code, { target: { value: '123456' } });
  fireEvent.click(screen.getByRole('button', { name: 'Verify & Login' }));
  expect(await screen.findByText('Invalid OTP.')).toBeVisible();
  expect(tokenStore.setTokens).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Verify & Login' }));
  expect(await screen.findByText('Navigation destination')).toBeVisible();
  expect(loadUser).toHaveBeenCalledTimes(1);
  expect(tokenStore.setTokens).toHaveBeenCalledWith({ access: 'access', refresh: 'refresh' });
});

test('ParentLogin accepts the backend email-login response for a parent', async () => {
  global.fetch.mockResolvedValue({ ok: true, json: async () => ({
    access: 'access', refresh: 'refresh', role: 'parent', user: { id: 1, role: 'parent' },
  }) });
  const { container } = renderPage(<ParentLogin />, { auth: { loadUser: jest.fn().mockResolvedValue() } });
  fireEvent.click(screen.getByRole('button', { name: /Email/i }));
  fireEvent.change(screen.getByPlaceholderText('parent@email.com'), { target: { value: 'parent@example.com' } });
  fireEvent.change(container.querySelector('input[type=password]'), { target: { value: 'Password1!' } });
  fireEvent.click(screen.getByRole('button', { name: 'Login', exact: true }));
  await waitFor(() => expect(tokenStore.setTokens).toHaveBeenCalledWith({ access: 'access', refresh: 'refresh' }));
  expect(screen.getByText('Navigation destination')).toBeVisible();
});

test('BulkImportPage sends staff CSV to the staff endpoint', async () => {
  api.post.mockResolvedValue({ data: { success_count: 0, error_count: 0, errors: [] } });
  const { container } = renderPage(<BulkImportPage type="staff" />);
  const csv = 'first_name,last_name,email,role\nAda,Okafor,ada@example.com,teacher';
  fireEvent.change(container.querySelector('input[type=file]'), { target: { files: [new File([csv], 'staff.csv')] } });
  await screen.findByRole('cell', { name: 'Ada' });
  fireEvent.click(screen.getByRole('button', { name: 'Import 1 Staff' }));
  await waitFor(() => expect(api.post).toHaveBeenCalled());
  expect(api.post.mock.calls[0][0]).toBe('/api/staff/bulk-import/');
  expect(screen.getByRole('heading', { name: 'Bulk Staff Import' })).toBeVisible();
});

test('Fees only offers payment for selected unpaid schedules and handles gateway failure', async () => {
  api.get.mockImplementation(async url => ({ data: url.includes('/terms/')
    ? [{ id: 1, name: 'First Term', is_current: true }]
    : [{ schedule: { id: 2, fee_category_name: 'Tuition' }, amount: 1000, paid: 0, outstanding: 1000, payments: [] }] }));
  api.post.mockRejectedValue({ response: { status: 502 } });
  jest.spyOn(window, 'alert').mockImplementation(() => {});
  await act(async () => { renderPage(<Fees />); });
  expect(screen.queryByRole('button', { name: /Pay Online/ })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('checkbox'));
  const pay = screen.getByRole('button', { name: /Pay Online/ });
  expect(pay).toBeEnabled();
  fireEvent.click(pay);
  await waitFor(() => expect(window.alert).toHaveBeenCalledWith('Payment initiation failed. Please try again.'));
  expect(api.post).toHaveBeenCalledWith('/api/fees/pay/initiate/', { student_id: 3, fee_schedule_ids: [2] });
  expect(pay).toBeEnabled();
});

test('manual payment retry reuses one idempotency key', async () => {
  api.get.mockImplementation(async url => {
    if (url.includes('/terms/')) return { data: [{ id: 1, name: 'First', is_current: true }] };
    if (url.includes('/class-arms/')) return { data: [] };
    if (url.includes('/outstanding/')) return { data: [{ student_id: 3, student_name: 'Ada Student', class: 'JSS1A', total_fees: 1000, paid: 0, outstanding: 1000 }] };
    if (url.includes('/fees/student/')) return { data: [{ schedule: { id: 2, fee_category_name: 'Tuition' }, outstanding: 1000 }] };
    return { data: [] };
  });
  api.post.mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce({ data: { id: 9 } });
  jest.spyOn(window, 'alert').mockImplementation(() => {});
  renderPage(<FeeCollection />);
  fireEvent.click(await screen.findByRole('button', { name: 'Record Payment' }));
  const record = await screen.findByRole('button', { name: 'Record' });
  fireEvent.click(record);
  await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1));
  const retry = await screen.findByRole('button', { name: 'Record' });
  await waitFor(() => expect(retry).toBeEnabled());
  fireEvent.click(retry);
  await waitFor(() => expect(api.post).toHaveBeenCalledTimes(2));
  const first = api.post.mock.calls[0][1];
  const second = api.post.mock.calls[1][1];
  expect(first.idempotency_key.length).toBeGreaterThanOrEqual(8);
  expect(second.idempotency_key).toBe(first.idempotency_key);
});

test('fee collection paginates debtors while retaining school-wide totals', async () => {
  api.get.mockImplementation(async url => {
    if (url.includes('/terms/')) return { data: [{ id: 1, name: 'First', is_current: true }] };
    if (url.includes('/class-arms/')) return { data: [] };
    if (url.includes('/outstanding/')) return { data: {
      count: 500, next: url.includes('page=2') ? null : 'next', previous: url.includes('page=2') ? 'previous' : null,
      summary: { total_expected: 500000, total_collected: 200000, total_outstanding: 300000 },
      results: [{ student_id: 3, student_name: 'Ada Student', class: 'JSS1A', total_fees: 1000, paid: 400, outstanding: 600 }],
    } };
    return { data: [] };
  });
  renderPage(<FeeCollection />);
  expect(await screen.findByText('₦500,000')).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'Next' }));
  await waitFor(() => expect(api.get).toHaveBeenCalledWith('/api/fees/outstanding/?term=1&page=2'));
  expect(screen.getByText('Page 2')).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'Download Debtors PDF' }));
  await waitFor(() => expect(downloadReport).toHaveBeenCalledWith(
    'Outstanding school fees', expect.any(Array), 'debtors.pdf'
  ));
});

test('MyResult explains when a selected term has no published result', async () => {
  api.get.mockImplementation(url => url.includes('/terms/')
    ? Promise.resolve({ data: [{ id: 1, name: 'First Term', is_current: true }] })
    : Promise.reject({ response: { status: 404 } }));
  await act(async () => { renderPage(<MyResult />); });
  expect(screen.getByText(/Results are not available yet for this term/)).toBeVisible();
});

test('ExamReview displays question, answer, explanation, and score', async () => {
  api.get.mockResolvedValue({ data: { score: 100, questions: [{ id: 1, question_text: 'Two plus two?', question_type: 'fill_blank', correct_answer: '4', selected_option: '4', is_correct: true, explanation: 'Add two pairs.' }] } });
  await act(async () => { renderPage(<ExamReview />, { route: '/test/:examId' }); });
  expect(screen.getByText('100%')).toBeVisible();
  expect(screen.getByText('Two plus two?')).toBeVisible();
  expect(screen.getByText(/Add two pairs/)).toBeVisible();
});

test('ExamRoom confirms submission and displays the returned score', async () => {
  api.post.mockImplementation(async url => ({ data: url.endsWith('/start/') ? {
    session_id: 1, questions: [{ id: 1, question_text: 'Two plus two?', question_type: 'mcq', options: [{ id: 'A', text: '4' }] }],
    time_remaining_seconds: 600, allow_review: true,
  } : { score: 100, total_questions: 1, correct_answers: 1 } }));
  api.get.mockResolvedValue({ data: { saved_answers: [{ question: 1, selected_option: 'A' }] } });
  await act(async () => { renderPage(<ExamRoom />, { route: '/test/:examId' }); });
  fireEvent.click(screen.getByRole('button', { name: 'Submit' }));
  expect(screen.getByText('Submit Exam?')).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'Yes, Submit' }));
  expect(await screen.findByRole('heading', { name: 'Exam Submitted!' })).toBeVisible();
  expect(screen.getByText('100%')).toBeVisible();
  expect(api.post).toHaveBeenCalledWith('/api/cbt/exams/1/submit/');
});

test('Notifications sends the composed message and reports the delivery summary', async () => {
  api.post.mockResolvedValue({ data: { sent: 2, failed: 0 } });
  const { container } = renderPage(<Notifications />);
  await act(async () => {});
  fireEvent.change(container.querySelector('textarea'), { target: { value: 'School opens Monday.' } });
  fireEvent.click(screen.getByRole('button', { name: /Send/i }));
  expect(await screen.findByText(/2 sent, 0 failed, 0 skipped/)).toBeVisible();
  expect(api.post).toHaveBeenCalledWith('/api/notifications/send/', expect.objectContaining({ channel: 'email', recipient_type: 'all_parents', message: 'School opens Monday.' }), expect.objectContaining({headers: expect.objectContaining({'Idempotency-Key': expect.any(String)})}));
});
