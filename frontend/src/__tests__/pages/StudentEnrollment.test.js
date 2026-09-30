import React from 'react';
import {fireEvent, screen, waitFor} from '@testing-library/react';
import {renderPage} from '../../testSupport/renderPage';
import StudentProfilePage from '../../pages/admin/StudentProfile';
import api from '../../services/api';

jest.mock('../../services/api', () => ({
  __esModule: true,
  default: {get: jest.fn(), post: jest.fn()},
}));

beforeEach(() => {
  jest.resetAllMocks();
  api.get.mockImplementation(async url => {
    if (url === '/api/students/1/') {
      return {data: {
        id: 1,
        full_name: 'Ada Student',
        admission_number: 'WF0001',
        email: 'ada@student.test',
        status: 'active',
        current_class: 21,
        current_class_name: 'JSS1A',
        guardian_name: '',
        guardian_phone: '',
        guardian_email: '',
        guardian_relationship: '',
      }};
    }
    if (url === '/api/class-arms/') {
      return {data: [
        {id: 21, full_name: 'JSS1A'},
        {id: 22, full_name: 'JSS2A'},
      ]};
    }
    if (url === '/api/students/1/parents/') {
      return {data: []};
    }
    return {data: {}};
  });
});

test('student profile surfaces safe server message when same-session class change is blocked', async () => {
  api.post.mockRejectedValue({
    response: {
      data: {
        error: 'This student already has a current-session class placement. Use the class-transfer workflow to change classes safely.',
      },
    },
  });

  const {container} = renderPage(<StudentProfilePage />, {
    path: '/admin/students/1',
    route: '/admin/students/:id',
  });

  expect(await screen.findByRole('heading', {name: 'Ada Student', level: 1})).toBeVisible();

  const select = container.querySelector('.sp-assign-select');
  fireEvent.change(select, {target: {value: '22'}});
  fireEvent.click(screen.getByRole('button', {name: 'Assign'}));

  await waitFor(() => expect(api.post).toHaveBeenCalledWith(
    '/api/students/1/assign-class/',
    {class_arm: '22'},
  ));

  expect(await screen.findByRole('status')).toHaveTextContent(
    'Use the class-transfer workflow to change classes safely.'
  );
});
