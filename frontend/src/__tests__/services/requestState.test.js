import { classifyRequestFailure } from '../../services/requestState';

test('distinguishes safe read failures from uncertain write outcomes', () => {
  expect(classifyRequestFailure(new Error('timeout')).kind).toBe('network');
  expect(classifyRequestFailure(new Error('timeout'), { mutation: true }).kind).toBe('unknown');
  expect(classifyRequestFailure({ code: 'ECONNABORTED' }).kind).toBe('timeout');
  expect(classifyRequestFailure({ response: { status: 403 } }).kind).toBe('authorization');
  expect(classifyRequestFailure({ response: { status: 422 } }).kind).toBe('validation');
  expect(classifyRequestFailure({ response: { status: 503 } }).kind).toBe('server');
});
