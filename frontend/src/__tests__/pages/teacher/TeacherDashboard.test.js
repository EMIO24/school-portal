import { screen } from '@testing-library/react';
import { renderPage } from '../../../testSupport/renderPage';
import Dashboard from '../../../pages/teacher/TeacherDashboard';
test('shows working role-specific shortcuts', () => {
  renderPage(<Dashboard/>, {auth:{user:{role:'teacher',firstName:'Ada'}}});
  expect(screen.getByRole('heading',{name:'Welcome, Ada.'})).toBeVisible();
  expect(screen.getByRole('link',{name:/Take attendance/})).toBeVisible();
});
