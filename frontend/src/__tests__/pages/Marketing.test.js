import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { MarketingPage } from '../../pages/public/Marketing';
import api from '../../services/api';
import { openSchoolLogin } from '../../services/schoolAccess';

jest.mock('../../services/api', () => ({ __esModule: true, default: { get: jest.fn(), post: jest.fn() } }));
jest.mock('../../services/schoolAccess', () => ({ openSchoolLogin: jest.fn() }));

function show(page) {
  return render(<MemoryRouter><MarketingPage page={page}/></MemoryRouter>);
}

test('pricing shows the approved plans and automatic school-size discount', () => {
  show('pricing');
  expect(screen.getByText('₦800', { exact: false })).toBeVisible();
  expect(screen.getByText('₦1,500', { exact: false })).toBeVisible();
  expect(screen.getByText(/100\+ active students\? 10% off/)).toBeVisible();
  expect(screen.queryByText('Enterprise')).not.toBeInTheDocument();
});

test('role showcase changes with keyboard navigation', () => {
  show('home');
  expect(screen.getAllByAltText('Paideia administrator dashboard showing school operations')[0]).toHaveAttribute('src', expect.stringContaining('/media/product/'));
  const admin = screen.getByRole('tab', { name: 'Administrator' });
  fireEvent.keyDown(admin, { key: 'ArrowRight' });
  expect(screen.getByRole('tab', { name: 'Teacher' })).toHaveAttribute('aria-selected', 'true');
  expect(screen.getByRole('tabpanel')).toHaveTextContent('Record attendance');
  expect(screen.getByAltText('Paideia teacher dashboard showing classroom tools')).toBeVisible();
});

test('demo request uses the existing API and shows confirmation', async () => {
  api.post.mockResolvedValueOnce({ data: { detail: 'Received' } });
  show('demo');
  fireEvent.change(screen.getByLabelText('School name *'), { target: { value: 'River School' } });
  fireEvent.change(screen.getByLabelText('Your name *'), { target: { value: 'Ada' } });
  fireEvent.change(screen.getByLabelText('Work email *'), { target: { value: 'ada@river.test' } });
  fireEvent.change(screen.getByLabelText('Phone number *'), { target: { value: '08012345678' } });
  fireEvent.change(screen.getByLabelText('Approximate active students *'), { target: { value: '120' } });
  fireEvent.change(screen.getByLabelText('Location *'), { target: { value: 'Lagos' } });
  fireEvent.click(screen.getByRole('button', { name: 'Send request ↗' }));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/demo-requests/', expect.objectContaining({ school_name: 'River School', website: '' })));
  expect(await screen.findByText('Your request is with us.')).toBeVisible();
});

test('school access resolves a name and opens the existing tenant login', async () => {
  api.get.mockResolvedValueOnce({ data: { found: true, slug: 'bright-future' } });
  show('access');
  fireEvent.change(screen.getByLabelText('School name'), { target: { value: '  Bright   Future College  ' } });
  fireEvent.click(screen.getByRole('button', { name: 'Continue →' }));
  await waitFor(() => expect(api.get).toHaveBeenCalledWith('/api/school-lookup/', { params: { name: 'Bright Future College' } }));
  expect(openSchoolLogin).toHaveBeenCalledWith('bright-future');
});

test('school access handles an unknown school without exposing a directory', async () => {
  api.get.mockResolvedValueOnce({ data: { found: false } });
  show('access');
  fireEvent.change(screen.getByLabelText('School name'), { target: { value: 'Unknown Academy' } });
  fireEvent.click(screen.getByRole('button', { name: 'Continue →' }));
  expect(await screen.findByText("We couldn't find that school. Check the name and try again.")).toBeVisible();
  expect(openSchoolLogin).not.toHaveBeenCalled();
});
