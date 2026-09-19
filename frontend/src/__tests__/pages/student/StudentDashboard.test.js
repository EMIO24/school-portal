import { screen } from '@testing-library/react';
import { renderPage } from '../../../testSupport/renderPage';
import Dashboard from '../../../pages/student/StudentDashboard';
test('shows working role-specific shortcuts', () => {
  renderPage(<Dashboard/>, {auth:{user:{role:'student',firstName:'Ada'}}});
  expect(screen.getByRole('heading',{name:'Welcome, Ada.'})).toBeVisible();
  expect(screen.getByRole('link',{name:/Your timetable/})).toBeVisible();
});
