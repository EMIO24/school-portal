import React from 'react';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { renderPage } from '../../testSupport/renderPage';
import CurriculumManager from '../../pages/admin/CurriculumManager';
import LessonCoverage from '../../pages/teacher/LessonCoverage';
import TeacherScheme from '../../pages/teacher/TeacherScheme';
import api from '../../services/api';

jest.mock('../../services/api', () => ({ __esModule: true, default: { get: jest.fn(), post: jest.fn(), patch: jest.fn(), put: jest.fn(), delete: jest.fn() } }));

const plan = { id: 1, summary: { total: 1, not_started: 1, partial: 0, covered: 0 },
  weeks: [{ id: 2, number: 2, label: '', topics: [{ id: 3, title: 'Fractions', description: '', position: 1,
    archived: false, state: 'not_started', objectives: [{ id: 4, text: 'Compare fractions', position: 1 }] }] }] };

beforeEach(() => {
  jest.clearAllMocks();
  api.get.mockImplementation(async url => ({ data: url.includes('/curriculum/lessons/')
    ? { lesson: 9, outcome: 'delivered', plan, coverage: {} }
    : url.includes('/curriculum/plans/') ? { plan }
      : url.includes('/class-arms/') ? [{ id: 1, name: 'A', class_level: 1 }]
        : [{ id: 1, name: 'First' }] }));
  api.put.mockResolvedValue({ data: { state: 'covered', revision: 1 } });
  api.post.mockResolvedValue({ data: { topic: 3 } });
  api.patch.mockResolvedValue({ data: { topic: 3 } });
});

test('teacher sees objectives and records coverage from a lesson', async () => {
  renderPage(<LessonCoverage lessonId={9} />);
  expect(await screen.findByText('Compare fractions')).toBeVisible();
  fireEvent.change(screen.getByLabelText('Coverage for Fractions'), { target: { value: 'covered' } });
  fireEvent.click(screen.getByRole('button', { name: 'Save coverage' }));
  await waitFor(() => expect(api.put).toHaveBeenCalledWith('/api/curriculum/lessons/9/topics/3/',
    { state: 'covered', note: '', revision: 0 }));
  expect(await screen.findByRole('status')).toHaveTextContent('Coverage saved.');
});

test('uncertain coverage response reads back before claiming success', async () => {
  api.put.mockRejectedValue(new Error('Network lost'));
  renderPage(<LessonCoverage lessonId={9} />);
  fireEvent.click(await screen.findByRole('button', { name: 'Save coverage' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('could not be confirmed');
});

test('teacher can inspect assigned scheme before delivery and see configured breaks', async () => {
  api.get.mockResolvedValue({ data: { lesson: null, outcome: null, plan, coverage: {},
    holidays: [{ id: 5, name: 'Midterm break', start_date: '2026-10-10', end_date: '2026-10-12' }] } });
  renderPage(<LessonCoverage slotId={4} />);
  expect(await screen.findByText('Compare fractions')).toBeVisible();
  expect(screen.getByText(/Midterm break/)).toBeVisible();
  expect(screen.queryByRole('button', { name: 'Save coverage' })).not.toBeInTheDocument();
  expect(api.get).toHaveBeenCalledWith('/api/curriculum/slots/4/');
});

test('teacher scheme lists only server-provided assignments and shows week progress', async () => {
  api.get.mockImplementation(async url => ({ data: url.includes('/assignments/')
    ? { assignments: [{ term: 1, term_name: 'First Term', class_arm: 1, class_name: 'JSS1A',
      class_level: 1, subject: 1, subject_name: 'Math' }] }
    : { plan, holidays: [] } }));
  renderPage(<TeacherScheme />);
  const selector = await screen.findByLabelText('Assigned class and subject');
  fireEvent.change(selector, { target: { value: '0' } });
  expect(await screen.findByText('Compare fractions')).toBeVisible();
  expect(screen.getByText(/0 of 1 topics covered/)).toBeVisible();
  expect(api.get).toHaveBeenCalledWith('/api/curriculum/plans/', { params: {
    term: 1, class_level: 1, subject: 1, class_arm: 1,
  } });
});

test('admin selects context and can create a topic with objectives', async () => {
  renderPage(<CurriculumManager />);
  await screen.findAllByRole('option', { name: 'First' });
  fireEvent.change(screen.getByLabelText('Term'), { target: { value: '1' } });
  fireEvent.change(screen.getByLabelText('Class level'), { target: { value: '1' } });
  fireEvent.change(screen.getByLabelText('Subject'), { target: { value: '1' } });
  expect(await screen.findByText('Fractions')).toBeVisible();
  fireEvent.change(screen.getByLabelText('Topic title'), { target: { value: 'Decimals' } });
  fireEvent.change(screen.getByLabelText('Learning objectives (one per line)'), { target: { value: 'Read decimals\nCompare decimals' } });
  fireEvent.click(screen.getByRole('button', { name: 'Add topic' }));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/curriculum/plans/', expect.objectContaining({
    title: 'Decimals', objectives: ['Read decimals', 'Compare decimals'], week: 1,
  })));
});

test('admin can open edit and see progress from class arm', async () => {
  renderPage(<CurriculumManager />);
  await screen.findAllByRole('option', { name: 'First' });
  fireEvent.change(screen.getByLabelText('Term'), { target: { value: '1' } });
  fireEvent.change(screen.getByLabelText('Class level'), { target: { value: '1' } });
  fireEvent.change(screen.getByLabelText('Subject'), { target: { value: '1' } });
  fireEvent.change(screen.getByLabelText('Class arm for progress'), { target: { value: '1' } });
  expect(await screen.findByLabelText('Curriculum progress')).toHaveTextContent('1 not started');
  fireEvent.click(screen.getByRole('button', { name: 'Edit' }));
  expect(screen.getByLabelText('Topic title')).toHaveValue('Fractions');
  expect(screen.getByLabelText('Learning objectives (one per line)')).toHaveValue('Compare fractions');
});
