import React from 'react';
import {fireEvent, screen, waitFor} from '@testing-library/react';
import {renderPage} from '../../testSupport/renderPage';
import MigrationCentre from '../../pages/admin/MigrationCentre';
import api from '../../services/api';

jest.mock('../../services/api', () => ({__esModule: true, default: {get: jest.fn(), post: jest.fn(), patch: jest.fn()}}));
beforeEach(() => jest.resetAllMocks());

test('administrator maps columns, validates, confirms, and sees updated readiness', async () => {
  const setup = {steps: [{key: 'classes', label: 'Classes and arms', complete: false}], missing_assignments: 0};
  api.get.mockImplementation(async url => ({data: url === '/api/migration/'
    ? {domains: [{key: 'classes', required: ['class_level', 'class_arm'], columns: ['class_level', 'class_arm']}]}
    : setup}));
  api.post.mockImplementation(async url => {
    if (url.endsWith('/inspect/')) return {data: {
      headers: ['Class Level', 'Class Arm'],
      rows: [{'Class Level': 'JSS1', 'Class Arm': 'A'}, {'Class Level': 'JSS1', 'Class Arm': ''}],
      row_numbers: [2, 3], total_rows: 2, format: 'csv',
      suggested_mapping: {'Class Level': 'class_level', 'Class Arm': 'class_arm'},
    }};
    if (url.endsWith('/validate/')) return {data: {mode: 'validate', total_rows: 2,
      counts: {CREATE: 1, REUSE: 0, REJECT: 1}, warnings: [],
      rows: [{row: 2, action: 'CREATE'}, {row: 3, action: 'REJECT', field: 'class_arm', reason: 'Required value is empty.'}]}};
    setup.steps[0].complete = true;
    return {data: {mode: 'import', total_rows: 2, counts: {CREATE: 1, REUSE: 0, REJECT: 1},
      warnings: [], rows: [{row: 2, action: 'CREATE'}, {row: 3, action: 'REJECT', field: 'class_arm', reason: 'Required value is empty.'}]}};
  });
  const confirm = jest.spyOn(window, 'confirm').mockReturnValue(true);
  renderPage(<MigrationCentre />);
  expect(await screen.findByText(/Required: class_level, class_arm/)).toBeVisible();
  const file = new File(['Class Level,Class Arm\nJSS1,A\nJSS1,'], 'classes.csv', {type: 'text/csv'});
  Object.defineProperty(file, 'text', {value: async () => 'Class Level,Class Arm\nJSS1,A\nJSS1,'});
  fireEvent.change(screen.getByLabelText('Spreadsheet file'), {target: {files: [file]}});
  await screen.findByText(/2 rows found/);
  expect(screen.getByLabelText('Class Level')).toHaveValue('class_level');
  expect(screen.getByLabelText('Class Arm')).toHaveValue('class_arm');
  fireEvent.click(screen.getByRole('button', {name: 'Validate file'}));
  expect(await screen.findByText(/Total 2; create 1; reuse 0; reject 1/)).toBeVisible();
  expect(screen.getByText(/Row 3 — class_arm/)).toBeVisible();
  fireEvent.click(screen.getByRole('button', {name: 'Confirm import'}));
  await waitFor(() => expect(api.post).toHaveBeenCalledTimes(3));
  expect(confirm).toHaveBeenCalled();
  expect(await screen.findByText(/1 of 1 setup checks complete/)).toBeVisible();
  const validateCall = api.post.mock.calls.find(([url]) => url.endsWith('/validate/'));
  expect(validateCall[1].get('mapping')).toContain('"Class Level":"class_level"');
  confirm.mockRestore();
});

test('explicitly ignored column is sent as ignored rather than remapped', async () => {
  api.get.mockImplementation(async url => ({data: url === '/api/migration/'
    ? {domains: [{key: 'classes', required: ['class_level', 'class_arm'], columns: ['class_level', 'class_arm']}]}
    : {steps: [], missing_assignments: 0}}));
  api.post.mockImplementation(async url => {
    if (url.endsWith('/inspect/')) return {data: {
      headers: ['Class Level', 'Class Arm'],
      rows: [{'Class Level': 'JSS1', 'Class Arm': 'A'}],
      row_numbers: [2], total_rows: 1, format: 'csv',
      suggested_mapping: {'Class Level': 'class_level', 'Class Arm': 'class_arm'},
    }};
    throw {response: {data: {error: 'Map required columns: class_level'}}};
  });
  renderPage(<MigrationCentre />);
  await screen.findByText(/Required: class_level, class_arm/);
  const file = new File(['Class Level,Class Arm\nJSS1,A'], 'classes.csv', {type: 'text/csv'});
  Object.defineProperty(file, 'text', {value: async () => 'Class Level,Class Arm\nJSS1,A'});
  fireEvent.change(screen.getByLabelText('Spreadsheet file'), {target: {files: [file]}});
  await screen.findByText(/1 rows found/);
  fireEvent.change(screen.getByLabelText('Class Level'), {target: {value: ''}});
  fireEvent.click(screen.getByRole('button', {name: 'Validate file'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Map required columns');
  const validateCall = api.post.mock.calls.find(([url]) => url.endsWith('/validate/'));
  expect(JSON.parse(validateCall[1].get('mapping'))['Class Level']).toBeNull();
});


test('query parameter opens the requested high-volume import domain', async () => {
  api.get.mockImplementation(async url => ({data: url === '/api/migration/'
    ? {domains: [
        {key: 'classes', required: ['class_level', 'class_arm'], columns: ['class_level', 'class_arm']},
        {key: 'timetable', required: ['class_level', 'class_arm', 'subject_code', 'teacher_email', 'day', 'period'],
          columns: ['class_level', 'class_arm', 'subject_code', 'teacher_email', 'day', 'period']},
      ]}
    : {steps: [], missing_assignments: 0}}));
  renderPage(<MigrationCentre />, {path: '/admin/migration?type=timetable', route: '/admin/migration'});
  expect(await screen.findByText('Timetable entries')).toBeVisible();
  expect(screen.getByLabelText('Data type')).toHaveValue('timetable');
  expect(screen.getByText(/Uses the current term/)).toBeVisible();
  expect(screen.getByText(/Required: class_level, class_arm, subject_code, teacher_email, day, period/)).toBeVisible();
});


test('Batch 20 exposes historical migration domains and provenance history', async () => {
  api.get.mockImplementation(async url => {
    if (url === '/api/migration/') return {data: {domains: [
      {key: 'classes', required: ['class_level', 'class_arm'], columns: ['class_level', 'class_arm']},
      {key: 'historical_enrollments',
       required: ['student_ref', 'session', 'class_level', 'class_arm', 'enrolled_on', 'status'],
       columns: ['student_ref', 'session', 'class_level', 'class_arm', 'enrolled_on', 'exited_on', 'status', 'entry_reason']},
    ]}};
    if (url === '/api/migration/jobs/') return {data: [{
      id: 41, domain: 'historical_enrollments', original_filename: 'placements.csv',
      status: 'completed', total_rows: 418, create_count: 418, reuse_count: 0,
      review_count: 0, reject_count: 0,
    }]};
    if (url === '/api/migration/mappings/') return {data: []};
    if (url === '/api/migration/conflicts/?status=open') return {data: []};
    return {data: {steps: [], missing_assignments: 0}};
  });

  renderPage(<MigrationCentre />, {
    path: '/admin/migration?type=historical_enrollments',
    route: '/admin/migration',
  });

  expect(await screen.findByRole('heading', {name: 'Migration command centre'})).toBeVisible();
  expect(screen.getByLabelText('Data type')).toHaveValue('historical_enrollments');
  expect(screen.getByText(/Past placements never rewrite current_class/)).toBeVisible();
  expect(await screen.findByText(/#41 Historical student placements/)).toBeVisible();
  expect(screen.getByText(/418 created/)).toBeVisible();
});

test('Batch 20 shows reconciliation conflicts and allows a human resolution', async () => {
  api.get.mockImplementation(async url => {
    if (url === '/api/migration/') return {data: {domains: [
      {key: 'classes', required: ['class_level', 'class_arm'], columns: ['class_level', 'class_arm']},
    ]}};
    if (url === '/api/migration/jobs/') return {data: []};
    if (url === '/api/migration/mappings/') return {data: []};
    if (url === '/api/migration/conflicts/?status=open') return {data: [{
      id: 9, job_id: 3, domain: 'historical_sessions', row_number: 2,
      source_identity: '2024/25', conflict_type: 'session_dates',
      candidate_matches: [{id: 2, name: '2024/25'}], status: 'open',
    }]};
    return {data: {steps: [], missing_assignments: 0}};
  });
  api.patch.mockResolvedValue({data: {id: 9, status: 'resolved'}});

  renderPage(<MigrationCentre />);
  expect(await screen.findByText(/Row 2 · session dates/)).toBeVisible();
  expect(screen.getByText('2024/25')).toBeVisible();

  fireEvent.click(screen.getByRole('button', {name: 'Mark resolved'}));
  await waitFor(() => expect(api.patch).toHaveBeenCalledWith(
    '/api/migration/conflicts/',
    {id: 9, action: 'resolved', resolution: {reviewed_in: 'migration_centre'}},
  ));
});
