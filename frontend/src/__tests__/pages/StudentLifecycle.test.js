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
  jest.spyOn(window, 'confirm').mockReturnValue(true);
  api.get.mockImplementation(async url => {
    if (url === '/api/students/1/') {
      return {data: {
        id: 1,
        full_name: 'Ada Student',
        admission_number: 'LIFE001',
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
      return {data: [{id: 21, full_name: 'JSS1A'}]};
    }
    if (url === '/api/students/1/parents/') {
      return {data: []};
    }
    return {data: {}};
  });
});

afterEach(() => {
  window.confirm.mockRestore();
});

test('suspension uses the controlled lifecycle endpoint', async () => {
  api.post.mockResolvedValue({data: {
    id: 1,
    full_name: 'Ada Student',
    admission_number: 'LIFE001',
    email: 'ada@student.test',
    status: 'suspended',
    current_class: 21,
    current_class_name: 'JSS1A',
  }});

  renderPage(<StudentProfilePage />, {
    path: '/admin/students/1',
    route: '/admin/students/:id',
  });

  fireEvent.click(await screen.findByRole('button', {name: 'Suspend Student'}));

  await waitFor(() => expect(api.post).toHaveBeenCalledWith(
    '/api/students/1/lifecycle/',
    {action: 'suspend', reason: ''}
  ));
  expect(await screen.findByText('suspended')).toBeVisible();
  expect(screen.getByRole('button', {name: 'Reactivate Student'})).toBeVisible();
});

test('withdrawal sends date and reason through lifecycle endpoint', async () => {
  api.post.mockResolvedValue({data: {
    id: 1,
    full_name: 'Ada Student',
    admission_number: 'LIFE001',
    email: 'ada@student.test',
    status: 'withdrawn',
    current_class: null,
    current_class_name: null,
  }});

  renderPage(<StudentProfilePage />, {
    path: '/admin/students/1',
    route: '/admin/students/:id',
  });

  fireEvent.change(await screen.findByLabelText('Lifecycle reason'), {
    target: {value: 'Relocated'},
  });
  const dateInput = screen.getByLabelText('Withdrawal date');
  fireEvent.change(dateInput, {target: {value: '2026-09-30'}});
  fireEvent.click(screen.getByRole('button', {name: 'Withdraw Student'}));

  await waitFor(() => expect(api.post).toHaveBeenCalledWith(
    '/api/students/1/lifecycle/',
    {
      action: 'withdraw',
      reason: 'Relocated',
      effective_date: '2026-09-30',
    }
  ));
  expect(await screen.findByText(/closed/i)).toBeVisible();
});
