import { schoolLoginPath } from '../../services/schoolAccess';

test('school login path preserves the existing slug-based login flow', () => {
  expect(schoolLoginPath('bright-future')).toBe('/login?school=bright-future');
});
