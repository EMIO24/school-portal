import React from 'react';
import {fireEvent, screen, waitFor} from '@testing-library/react';
import {renderPage} from '../../testSupport/renderPage';
import AcademicStandards from '../../pages/admin/AcademicStandards';
import api from '../../services/api';

jest.mock('../../services/api', () => ({
  __esModule: true,
  default: {get: jest.fn(), post: jest.fn(), put: jest.fn()},
}));

beforeEach(() => {
  jest.resetAllMocks();
  api.get.mockImplementation(async url => {
    if (url === '/api/curriculum/standards/sources/') return {data: {sources: []}};
    if (url === '/api/curriculum/standards/') return {data: {standards: [{
      id: 7, title: 'JSS1 Mathematics Standard', class_level: 1, class_level_name: 'JSS1',
      subject: 2, subject_name: 'Mathematics', curriculum_source: 'Recorded source',
      curriculum_version_label: '2026', revision: 1, status: 'approved',
    }]}};
    if (url === '/api/class-levels/') return {data: [{id: 1, name: 'JSS1'}]};
    if (url === '/api/subjects/') return {data: [{id: 2, name: 'Mathematics'}]};
    if (url === '/api/sessions/') return {data: [{id: 3, name: '2026/27'}]};
    if (url === '/api/terms/') return {data: [{id: 4, name: 'first', session: 3, session_name: '2026/27'}]};
    throw new Error('Unexpected GET: ' + url);
  });
});

test('management generates a term scheme from an approved standard without overwriting in the UI', async () => {
  api.post.mockResolvedValueOnce({data: {plan: 9, standard: 7, topics: 12}});
  renderPage(<AcademicStandards />);

  expect(await screen.findByText('JSS1 Mathematics Standard')).toBeVisible();
  fireEvent.change(screen.getByLabelText('Approved standard'), {target: {value: '7'}});
  fireEvent.change(screen.getByLabelText('Scheme term'), {target: {value: '4'}});
  fireEvent.click(screen.getByRole('button', {name: 'Generate scheme'}));

  await waitFor(() => expect(api.post).toHaveBeenCalledWith(
    '/api/curriculum/standards/7/generate-plan/',
    {term: 4},
  ));
  expect(await screen.findByText('Scheme generated with 12 topics.')).toBeVisible();
});
