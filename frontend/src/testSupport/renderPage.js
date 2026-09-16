import React from 'react';
import { render } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext';
import { ThemeContext } from '../context/ThemeContext';

export const school = { name: 'Test School', logo: '', motto: 'Learning together' };
export const user = {
  id: 7, student_id: 3, first_name: 'Ada', last_name: 'Okafor',
  full_name: 'Ada Okafor', role: 'school_admin', email: 'ada@example.com',
};

export function renderPage(element, options = {}) {
  const auth = {
    user, isAuthenticated: true, isLoading: false, error: null,
    login: jest.fn(), logout: jest.fn(), clearError: jest.fn(), updateUser: jest.fn(),
    ...options.auth,
  };
  return {
    auth,
    ...render(
      <MemoryRouter initialEntries={[options.path || '/test/1']}
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ThemeContext.Provider value={{ school, loading: false, error: null, refetch: jest.fn() }}>
          <AuthContext.Provider value={auth}>
            <Routes>
              <Route path={options.route || '/test/:id'} element={element} />
              <Route path="*" element={<p>Navigation destination</p>} />
            </Routes>
          </AuthContext.Provider>
        </ThemeContext.Provider>
      </MemoryRouter>
    ),
  };
}
