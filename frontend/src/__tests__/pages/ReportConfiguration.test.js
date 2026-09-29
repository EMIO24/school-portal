import React from 'react';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { renderPage } from '../../testSupport/renderPage';
import ReportConfiguration from '../../pages/admin/ReportConfiguration';
import ScratchCards from '../../pages/admin/ScratchCards';
import api from '../../services/api';

jest.mock('../../services/api', () => ({ __esModule: true, default: {
  get: jest.fn(), patch: jest.fn(), post: jest.fn(),
} }));
jest.mock('../../services/download', () => ({ downloadFile: jest.fn() }));

const config = { layout: 'classic', title: 'Student Academic Report', watermark: 'none',
  show_comments: true, show_attendance: true, show_position: true,
  show_skills: true, show_next_term: true };

beforeEach(() => { jest.resetAllMocks(); });

test('admin saves bounded presentation controls without sending academic facts', async () => {
  api.get.mockResolvedValue({ data: config });
  api.patch.mockImplementation(async (url, body) => ({ data: body }));
  renderPage(<ReportConfiguration />);
  expect(await screen.findByRole('heading', { name: 'Report cards' })).toBeVisible();
  fireEvent.change(screen.getByLabelText('Layout'), { target: { value: 'modern' } });
  fireEvent.click(screen.getByLabelText('Class position'));
  fireEvent.click(screen.getByRole('button', { name: 'Save report settings' }));
  await waitFor(() => expect(api.patch).toHaveBeenCalledWith('/api/results/report-configuration/',
    expect.objectContaining({ layout: 'modern', show_position: false })));
  expect(api.patch.mock.calls[0][1]).not.toHaveProperty('scores');
});

test('batch administration displays revoked count and revokes only unused cards', async () => {
  const card = { id: 7, serial_number: 'QA-0001', term_name: 'First Term', is_used: false, revoked_at: null };
  api.get.mockImplementation(async url => ({ data:
    url === '/api/terms/' ? [] : url.startsWith('/api/scratch-cards/?') ? [card] :
    [{ batch_name: 'First', total: 1, used: 0, unused: 1, revoked: 0, created_at: '2026-09-01' }],
  }));
  api.post.mockResolvedValue({ data: { revoked: true } });
  jest.spyOn(window, 'confirm').mockReturnValue(true);
  renderPage(<ScratchCards />);
  fireEvent.click(await screen.findByRole('button', { name: 'View cards' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Revoke' }));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/scratch-cards/7/revoke/'));
  window.confirm.mockRestore();
});
