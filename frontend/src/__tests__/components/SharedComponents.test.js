import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import GradeCell, { GradeBadge, ComputedCell, rowClass } from '../../components/teacher/GradeCell';
import TimetableGrid, { TimetableLegend } from '../../components/timetable/TimetableGrid';
import EntryModal from '../../components/timetable/EntryModal';
import QuestionEditor from '../../components/cbt/QuestionEditor';
import BulkImport from '../../components/admin/BulkImport';
import LoadingScreen from '../../components/common/LoadingScreen';
import api from '../../services/api';

jest.mock('../../services/api', () => ({ __esModule: true, default: { get: jest.fn(), post: jest.fn(), patch: jest.fn() } }));

beforeEach(() => { jest.clearAllMocks(); localStorage.clear(); api.get.mockResolvedValue({ data: [] }); });
afterEach(() => jest.restoreAllMocks());

test('LoadingScreen renders cached school branding and an accessible status', () => {
  localStorage.setItem('school_theme', JSON.stringify({ name: 'Test School', logo: '/logo.png' }));
  render(<LoadingScreen />);
  expect(screen.getByRole('status', { name: 'Loading school portal' })).toBeVisible();
  expect(screen.getByRole('img', { name: 'Test School logo' })).toHaveAttribute('src', '/logo.png');
});

test('LoadingScreen survives corrupt cached branding', () => {
  localStorage.setItem('school_theme', '{broken');
  render(<LoadingScreen />);
  expect(screen.getByRole('status')).toBeVisible();
  expect(screen.queryByRole('img')).not.toBeInTheDocument();
});

test.each([['A1', 'row-pass'], ['D7', 'row-warn'], ['F9', 'row-fail'], ['', '']])('GradeBadge displays %s and its band is classified', (grade, expected) => {
  render(<GradeBadge grade={grade} />);
  expect(screen.getByText(grade || '—')).toBeVisible();
  expect(rowClass(grade)).toBe(expected);
});

test.each([[0, '0'], [12.55, '12.6'], [20, '20'], [null, '—']])('ComputedCell formats %s', (value, text) => {
  render(<ComputedCell value={value} />);
  expect(screen.getByText(text)).toBeVisible();
});

test('GradeCell reports numeric changes, clearing, and Tab navigation', () => {
  const change = jest.fn(), tab = jest.fn();
  const { rerender } = render(<table><tbody><tr><GradeCell value={4} max={10} onChange={change} onTab={tab} fieldName="First test" autoFocus /></tr></tbody></table>);
  const input = screen.getByRole('spinbutton', { name: 'First test' });
  expect(input).toHaveFocus();
  expect(input).toHaveAttribute('max', '10');
  fireEvent.change(input, { target: { value: '7.5' } });
  expect(change).toHaveBeenLastCalledWith(7.5);
  fireEvent.change(input, { target: { value: '' } });
  expect(change).toHaveBeenLastCalledWith('');
  fireEvent.keyDown(input, { key: 'Tab' });
  expect(tab).toHaveBeenCalledTimes(1);
  rerender(<table><tbody><tr><GradeCell value={4} onChange={change} disabled hasError /></tr></tbody></table>);
  expect(screen.getByRole('spinbutton')).toBeDisabled();
  expect(screen.getByRole('spinbutton')).toHaveClass('has-error');
});

const period = { id: 1, name: 'Period 1', start_time: '08:00:00', end_time: '09:00:00' };
const lesson = { id: 2, period: 1, day_of_week: 'MON', subject: 3, subject_name: 'Mathematics', teacher_name: 'Ada Okafor' };

test('TimetableGrid displays lessons and supports mouse and keyboard slot selection', () => {
  const select = jest.fn();
  render(<TimetableGrid periods={[period]} entries={[lesson]} editable onCellClick={select} />);
  fireEvent.click(screen.getByRole('button', { name: 'Monday Period 1: Mathematics' }));
  expect(select).toHaveBeenLastCalledWith('MON', period, lesson);
  fireEvent.keyDown(screen.getByRole('button', { name: 'Tuesday Period 1: empty' }), { key: 'Enter' });
  expect(select).toHaveBeenLastCalledWith('TUE', period, null);
  expect(screen.getByText('Ada Okafor')).toBeVisible();
});

test('TimetableGrid prevents edits in read-only mode and break periods', () => {
  const select = jest.fn();
  const { rerender } = render(<TimetableGrid periods={[period]} entries={[lesson]} onCellClick={select} />);
  fireEvent.click(screen.getByText('Mathematics'));
  expect(select).not.toHaveBeenCalled();
  rerender(<TimetableGrid periods={[{ ...period, is_break: true }]} editable onCellClick={select} />);
  expect(screen.queryByRole('button')).not.toBeInTheDocument();
});

test('TimetableGrid and legend support an empty timetable and custom categories', () => {
  render(<><TimetableGrid /><TimetableLegend categories={[{ name: 'Robotics', bg: 'blue' }]} /></>);
  expect(screen.getByText('No periods configured')).toBeVisible();
  expect(screen.getByLabelText('Subject categories')).toHaveTextContent('Robotics');
});

const modalProps = () => ({
  isOpen: true, period, day: 'MON', onClose: jest.fn(), onSave: jest.fn().mockResolvedValue(),
  onDelete: jest.fn().mockResolvedValue(), subjects: [{ id: 3, name: 'Mathematics' }],
  teachers: [{ id: 4, first_name: 'Ada', last_name: 'Okafor' }],
});

test('EntryModal validates a subject and sends the selected lesson', async () => {
  const props = modalProps();
  render(<EntryModal {...props} />);
  expect(screen.getByRole('button', { name: 'Add lesson' })).toBeDisabled();
  expect(props.onSave).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText('Subject *'), { target: { value: '3' } });
  fireEvent.change(screen.getByLabelText('Teacher'), { target: { value: '4' } });
  fireEvent.click(screen.getByRole('button', { name: /Save|Add lesson/i }));
  await waitFor(() => expect(props.onSave).toHaveBeenCalledWith({ subject: 3, teacher: 4, period: 1, day_of_week: 'MON' }));
});

test('EntryModal displays server conflicts and confirms removal', async () => {
  const props = modalProps();
  props.onSave.mockRejectedValue({ response: { data: { teacher: 'Teacher already booked.' } } });
  jest.spyOn(window, 'confirm').mockReturnValue(true);
  render(<EntryModal {...props} entry={lesson} />);
  fireEvent.click(screen.getByRole('button', { name: 'Update' }));
  expect(await screen.findByText(/Teacher already booked/)).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'Remove' }));
  await waitFor(() => expect(props.onDelete).toHaveBeenCalledWith(2));
});

test('EntryModal stays hidden when closed', () => {
  render(<EntryModal {...modalProps()} isOpen={false} />);
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});

test('QuestionEditor validates missing text and can cancel', () => {
  const close = jest.fn();
  render(<QuestionEditor subjects={[]} classLevels={[]} onClose={close} />);
  fireEvent.click(screen.getByRole('button', { name: 'Save Question' }));
  expect(screen.getByText(/Question text is required/)).toBeVisible();
  expect(api.post).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
  expect(close).toHaveBeenCalledTimes(1);
});

test('QuestionEditor saves an edited question and updates the live preview', async () => {
  const saved = jest.fn();
  api.patch.mockResolvedValue({ data: { id: 1, question_text: 'Updated question' } });
  render(<QuestionEditor question={{ id: 1, subject: 2, class_level: 3, question_type: 'fill_blank', question_text: 'Old question', correct_answer: '4' }} subjects={[]} classLevels={[]} onSaved={saved} />);
  fireEvent.change(screen.getByPlaceholderText(/Type the question/), { target: { value: 'Updated question' } });
  expect(screen.getByText('Updated question', { selector: 'div' })).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'Update Question' }));
  await waitFor(() => expect(saved).toHaveBeenCalledWith({ id: 1, question_text: 'Updated question' }));
  expect(api.patch).toHaveBeenCalledWith('/api/cbt/questions/1/', expect.objectContaining({ question_text: 'Updated question', options: [] }));
});

test('QuestionEditor uploads an image file and removes the URL input', async () => {
  api.post.mockResolvedValue({ data: { url: 'https://images.example.test/question.png' } });
  render(<QuestionEditor question={{ id: 1, subject: 2, class_level: 3, question_type: 'fill_blank', question_text: 'Image question', correct_answer: '4' }} subjects={[]} classLevels={[]} onSaved={jest.fn()} onClose={jest.fn()} />);
  const file = new File(['image'], 'diagram.png', { type: 'image/png' });
  fireEvent.change(screen.getByLabelText('Choose question image (optional)'), { target: { files: [file] } });
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/cbt/questions/image/', expect.any(FormData), expect.any(Object)));
  expect(screen.queryByText('Image URL (optional)')).not.toBeInTheDocument();
  expect(await screen.findByText('diagram.png')).toBeVisible();
  expect(screen.getByRole('img')).toHaveAttribute('src', 'https://images.example.test/question.png');
});

const csv = 'first_name,last_name,email,gender,dob,class_level,guardian_name,guardian_phone\nAda,Okafor,ada@example.com,female,2010-01-01,JSS1,Parent,08012345678';

test('BulkImport rejects non-CSV files and disables uploads with missing columns', async () => {
  const { container } = render(<BulkImport />);
  const input = container.querySelector('input[type=file]');
  fireEvent.change(input, { target: { files: [new File(['bad'], 'bad.txt')] } });
  expect(screen.getByRole('alert')).toHaveTextContent('Only .csv files are accepted');
  fireEvent.change(input, { target: { files: [new File(['first_name\nAda'], 'missing.csv')] } });
  expect(await screen.findByText('Missing required columns:')).toBeVisible();
  expect(screen.getByRole('button', { name: /Import \d/ })).toBeDisabled();
});

test('BulkImport previews CSV, uploads FormData, shows row errors, and resets', async () => {
  const complete = jest.fn();
  const result = { success_count: 1, error_count: 1, errors: [{ row: 3, reason: 'Email already exists' }] };
  api.post.mockResolvedValue({ data: result });
  const { container } = render(<BulkImport onComplete={complete} />);
  const file = new File([csv], 'students.csv', { type: 'text/csv' });
  fireEvent.change(container.querySelector('input[type=file]'), { target: { files: [file] } });
  expect(await screen.findByRole('cell', { name: 'Ada' })).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: /Import \d/ }));
  expect(await screen.findByText('Email already exists')).toBeVisible();
  expect(api.post.mock.calls[0][1].get('file')).toBe(file);
  expect(complete).toHaveBeenCalledWith(result);
  fireEvent.click(screen.getByRole('button', { name: 'Import Another File' }));
  expect(screen.getByRole('button', { name: 'Upload CSV file' })).toBeVisible();
});
