import React from 'react';
import {fireEvent, screen, waitFor} from '@testing-library/react';
import {renderPage} from '../../testSupport/renderPage';
import StudentProfilePage from '../../pages/admin/StudentProfile';
import api from '../../services/api';

jest.mock('../../services/api', () => ({
  __esModule: true,
  default: {get: jest.fn(), post: jest.fn()},
}));

let studentData;

beforeEach(() => {
  jest.resetAllMocks();
  jest.spyOn(window, 'confirm').mockReturnValue(true);
  studentData = {
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
  };
  api.get.mockImplementation(async url => {
    if (url === '/api/students/1/') {
      return {data: studentData};
    }
    if (url === '/api/class-arms/') {
      return {data: [
        {id: 21, full_name: 'JSS1A'},
        {id: 22, full_name: 'JSS1B'},
      ]};
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

test('placed student uses controlled transfer workflow', async () => {
  api.post.mockResolvedValue({
    data: {
      student: {
        ...studentData,
        current_class: 22,
        current_class_name: 'JSS1B',
      },
      source_enrollment: {status: 'transferred'},
      destination_enrollment: {status: 'active'},
    },
  });

  const {container} = renderPage(<StudentProfilePage />, {
    path: '/admin/students/1',
    route: '/admin/students/:id',
  });

  expect(await screen.findByRole('heading', {name: 'Ada Student', level: 1})).toBeVisible();
  expect(screen.getByRole('button', {name: 'Transfer'})).toBeDisabled();

  const select = container.querySelector('.sp-assign-select');
  fireEvent.change(select, {target: {value: '22'}});
  fireEvent.change(screen.getByLabelText('Transfer effective date'), {
    target: {value: '2026-09-30'},
  });
  fireEvent.change(screen.getByLabelText('Transfer reason'), {
    target: {value: 'Class balancing'},
  });
  fireEvent.click(screen.getByRole('button', {name: 'Transfer'}));

  await waitFor(() => expect(api.post).toHaveBeenCalledWith(
    '/api/students/1/transfer-class/',
    {
      class_arm: '22',
      effective_date: '2026-09-30',
      reason: 'Class balancing',
    },
  ));

  expect(await screen.findByRole('status')).toHaveTextContent(
    'Student transferred successfully.'
  );
  expect(screen.getAllByText('JSS1B').length).toBeGreaterThan(0);
});

test('unassigned student still uses initial assignment workflow', async () => {
  studentData = {
    ...studentData,
    current_class: null,
    current_class_name: null,
  };
  api.post.mockResolvedValue({
    data: {
      ...studentData,
      current_class: 21,
      current_class_name: 'JSS1A',
    },
  });

  const {container} = renderPage(<StudentProfilePage />, {
    path: '/admin/students/1',
    route: '/admin/students/:id',
  });

  expect(await screen.findByRole('button', {name: 'Assign'})).toBeVisible();
  const select = container.querySelector('.sp-assign-select');
  fireEvent.change(select, {target: {value: '21'}});
  fireEvent.click(screen.getByRole('button', {name: 'Assign'}));

  await waitFor(() => expect(api.post).toHaveBeenCalledWith(
    '/api/students/1/assign-class/',
    {class_arm: '21'},
  ));
});


test('transfer workflow surfaces safe backend validation message', async () => {
  api.post.mockRejectedValue({
    response: {
      data: {
        error: 'Transfer date must be after the current placement start date.',
      },
    },
  });

  const {container} = renderPage(<StudentProfilePage />, {
    path: '/admin/students/1',
    route: '/admin/students/:id',
  });

  await screen.findByRole('heading', {name: 'Ada Student', level: 1});
  fireEvent.change(container.querySelector('.sp-assign-select'), {
    target: {value: '22'},
  });
  fireEvent.change(screen.getByLabelText('Transfer effective date'), {
    target: {value: '2026-09-01'},
  });
  fireEvent.click(screen.getByRole('button', {name: 'Transfer'}));

  expect(await screen.findByRole('status')).toHaveTextContent(
    'Transfer date must be after the current placement start date.'
  );
});
