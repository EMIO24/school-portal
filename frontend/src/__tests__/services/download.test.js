import api from '../../services/api';
import { downloadFile } from '../../services/download';
jest.mock('../../services/api', () => ({ __esModule: true, default: { get: jest.fn() } }));
const originalCreate = URL.createObjectURL, originalRevoke = URL.revokeObjectURL;
beforeEach(() => {
  jest.clearAllMocks();
  URL.createObjectURL = jest.fn().mockReturnValue('blob:download');
  URL.revokeObjectURL = jest.fn();
  jest.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
  jest.spyOn(window, 'alert').mockImplementation(() => {});
});
afterEach(() => { jest.restoreAllMocks(); URL.createObjectURL = originalCreate; URL.revokeObjectURL = originalRevoke; });
test('protected downloads go through the authenticated API client and release blob URLs', async () => {
  const blob = new Blob(['PDF'], { type: 'application/pdf' });
  api.get.mockResolvedValue({ data: blob });
  expect(await downloadFile('/api/results/slip/41/?term=2', 'result.pdf')).toBe(true);
  expect(api.get).toHaveBeenCalledWith('/api/results/slip/41/?term=2', { responseType: 'blob' });
  expect(URL.createObjectURL).toHaveBeenCalledWith(blob);
  expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:download');
  expect(document.querySelector('a[download]')).toBeNull();
});
test('failed downloads report a recoverable error without opening a blob', async () => {
  api.get.mockRejectedValue(new Error('Network failure'));
  expect(await downloadFile('/api/results/slip/41/?term=2', 'result.pdf')).toBe(false);
  expect(window.alert).toHaveBeenCalledWith('Could not download the file. Please try again.');
  expect(URL.createObjectURL).not.toHaveBeenCalled();
});
