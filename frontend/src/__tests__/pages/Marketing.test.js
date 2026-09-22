import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { MarketingPage } from '../../pages/public/Marketing';
import api from '../../services/api';

jest.mock('../../services/api', () => ({ __esModule: true, default: { post: jest.fn() } }));

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
