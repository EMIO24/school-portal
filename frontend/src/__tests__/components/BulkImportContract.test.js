import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import BulkImport, { parseCSVPreview } from '../../components/admin/BulkImport';
import api from '../../services/api';
jest.mock('../../services/api', () => ({ __esModule: true, default: { post: jest.fn() } }));
beforeEach(() => jest.clearAllMocks());
afterEach(() => jest.restoreAllMocks());

test('CSV preview handles BOM, CRLF, quotes, commas, multiline fields and blank lines', () => {
  expect(parseCSVPreview('\uFEFFname,note\r\nAda,"Hello, ""friend""\nWelcome"\r\n\r\n')).toEqual({
    headers: ['name', 'note'], rows: [{ name: 'Ada', note: 'Hello, "friend"\nWelcome' }], totalRows: 1,
  });
});
test.each(['name,name\na,b', ',name\na,b', 'name,note\na', 'name\n"a'])('CSV preview rejects malformed input %s', text => {
  expect(() => parseCSVPreview(text)).toThrow();
});
test('CSV preview preserves header-only and empty files and caps previews without losing totals', () => {
  expect(parseCSVPreview('')).toEqual({ headers: [], rows: [], totalRows: 0 });
  expect(parseCSVPreview('name')).toEqual({ headers: ['name'], rows: [], totalRows: 0 });
  expect(parseCSVPreview('name\nAda\nObi', 1)).toEqual({ headers: ['name'], rows: [{ name: 'Ada' }], totalRows: 2 });
});
test('staff upload submits the selected file, displays partial errors and can reset', async () => {
  api.post.mockResolvedValue({ data: { success_count: 1, error_count: 1, errors: [{ row: 3, reason: 'Duplicate email' }] } });
  const complete = jest.fn();
  const { container } = render(<BulkImport requiredCols={['email']} endpoint="/api/staff/bulk-import/" entityLabel="Staff" onComplete={complete} />);
  const file = new File(['email\nada@example.com\nada@example.com'], 'staff.CSV');
  fireEvent.change(container.querySelector('input[type=file]'), { target: { files: [file] } });
  fireEvent.click(await screen.findByRole('button', { name: 'Import 2 Staff' }));
  expect(await screen.findByText('Duplicate email')).toBeVisible();
  expect(api.post.mock.calls[0][0]).toBe('/api/staff/bulk-import/');
  expect(api.post.mock.calls[0][1].get('file')).toBe(file);
  expect(complete).toHaveBeenCalledWith(expect.objectContaining({ success_count: 1 }));
  fireEvent.click(screen.getByRole('button', { name: 'Import Another File' }));
  expect(screen.getByRole('button', { name: 'Upload CSV file' })).toBeVisible();
});
test('an upload failure permits retry and a malformed file prevents submission', async () => {
  api.post.mockRejectedValueOnce({ response: { data: { error: 'Import unavailable' } } }).mockResolvedValue({ data: { success_count: 1, error_count: 0 } });
  const { container } = render(<BulkImport requiredCols={['email']} />);
  fireEvent.change(container.querySelector('input[type=file]'), { target: { files: [new File(['email\na@example.com'], 'data.csv')] } });
  fireEvent.click(await screen.findByRole('button', { name: 'Import 1 Students' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Import unavailable');
  fireEvent.click(screen.getByRole('button', { name: 'Import 1 Students' }));
  await waitFor(() => expect(api.post).toHaveBeenCalledTimes(2));
});
test('malformed CSV and missing headers cannot be uploaded', async () => {
  const { container } = render(<BulkImport requiredCols={['email']} />);
  fireEvent.change(container.querySelector('input[type=file]'), { target: { files: [new File(['email\n"broken'], 'data.csv')] } });
  expect(await screen.findByRole('alert')).toHaveTextContent('not closed');
  expect(screen.getByRole('button', { name: /Import .*Students/ })).toBeDisabled();
  expect(api.post).not.toHaveBeenCalled();
});
