import React from 'react';
import {fireEvent, screen, waitFor} from '@testing-library/react';
import {renderPage} from '../../testSupport/renderPage';
import Admissions from '../../pages/admin/Admissions';
import Welfare from '../../pages/admin/Welfare';
import Campuses from '../../pages/admin/Campuses';
import StudentRecords from '../../pages/admin/StudentRecords';
import api from '../../services/api';

jest.mock('../../services/api', () => ({
  __esModule: true,
  default: {get: jest.fn(), post: jest.fn(), patch: jest.fn(), put: jest.fn(), delete: jest.fn()},
}));

beforeEach(() => {
  jest.clearAllMocks();
  window.confirm = jest.fn(() => true);
});

test('no-arm admission sends admit decision without a fake class arm', async () => {
  const application = {
    id: 5,
    application_number: 'ADM-TEST',
    first_name: 'Ada',
    last_name: 'Learner',
    applying_class_level: 2,
    applying_class_level_name: 'JSS1',
    preferred_campus: null,
    preferred_campus_name: '',
    guardian_name: 'Grace',
    guardian_phone: '0800',
    status: 'offered',
  };
  api.get.mockImplementation(async url => {
    if (url === '/api/operations/admissions/') return {data: [application]};
    if (url === '/api/class-levels/') return {data: [{id: 2, name: 'JSS1'}]};
    if (url === '/api/class-arms/') return {data: [{id: 9, class_level: 2, full_name: 'JSS1', is_default: true}]};
    if (url === '/api/campuses/') return {data: []};
    return {data: []};
  });
  api.post.mockResolvedValue({data: {...application, status: 'admitted', admitted_student: 10}});

  renderPage(<Admissions />);
  expect(await screen.findByText(/ADM-TEST/)).toBeVisible();
  fireEvent.click(screen.getByRole('button', {name: 'Admit'}));

  await waitFor(() => expect(api.post).toHaveBeenCalledWith(
    '/api/operations/admissions/5/decision/',
    {decision: 'admit'},
  ));
});

test('class teacher welfare form never offers health or safeguarding', async () => {
  api.get.mockImplementation(async url => {
    if (url === '/api/operations/welfare/') return {data: []};
    if (url === '/api/students/') return {data: [{id: 7, full_name: 'Sam Student', current_class_name: 'JSS1'}]};
    return {data: []};
  });

  renderPage(<Welfare />, {auth: {user: {id: 20, role: 'class_teacher'}}});
  expect(await screen.findByRole('heading', {name: 'Student welfare'})).toBeVisible();
  const category = screen.getByLabelText('Category');
  expect(category).toHaveTextContent('attendance');
  expect(category).not.toHaveTextContent('health');
  expect(category).not.toHaveTextContent('safeguarding');
});

test('campus page displays operational class student and staff counts', async () => {
  api.get.mockResolvedValue({data: [{
    id: 3, name: 'West Campus', code: 'WEST', is_primary: true, is_active: true,
    address: 'West Road', class_count: 6, student_count: 240, staff_count: 18,
  }]});

  renderPage(<Campuses />);
  expect(await screen.findByText('West Campus (WEST)')).toBeVisible();
  expect(screen.getByText('6 classes · 240 students · 18 staff')).toBeVisible();
});

test('official student record creates an append-only correction reference', async () => {
  api.get.mockImplementation(async url => {
    if (url === '/api/students/71/') return {data: {id: 71, full_name: 'Ada Test'}};
    if (url === '/api/operations/student-records/71/') return {data: [{
      id: 4, kind: 'identity', title: 'Original identity', details: '',
      document_url: '', effective_date: '2026-09-01', supersedes: null,
    }]};
    return {data: []};
  });
  api.post.mockResolvedValue({data: {id: 5}});

  renderPage(<StudentRecords />, {path: '/test/71', route: '/test/:id'});
  expect(await screen.findByText(/Original identity/, {selector: 'strong'})).toBeVisible();

  fireEvent.change(screen.getByLabelText('Type'), {target: {value: 'identity'}});
  fireEvent.change(screen.getByLabelText('Corrects earlier entry'), {target: {value: '4'}});
  fireEvent.change(screen.getByLabelText('Title'), {target: {value: 'Corrected identity'}});
  fireEvent.click(screen.getByRole('button', {name: 'Add entry'}));

  await waitFor(() => expect(api.post).toHaveBeenCalledWith(
    '/api/operations/student-records/71/',
    expect.objectContaining({kind: 'identity', title: 'Corrected identity', supersedes: 4}),
  ));
});
