import React from 'react';
import { render, screen } from '@testing-library/react';
import App from '../App';
import api, { authAPI, tokenStore } from '../services/api';

jest.mock('../services/api', () => ({
  __esModule: true, default: { get: jest.fn(), post: jest.fn() },
  authAPI: { refresh: jest.fn(), me: jest.fn() },
  tokenStore: { getRefresh: jest.fn(), setTokens: jest.fn(), clearAll: jest.fn() },
}));
jest.mock('axios', () => ({ __esModule: true, default: { post: jest.fn() } }));
const originalFetch = global.fetch;
beforeEach(() => {
  jest.clearAllMocks();
  localStorage.clear();
  tokenStore.getRefresh.mockReturnValue(null);
  global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => ({ name: 'Test School' }) });
  api.get.mockResolvedValue({ data: [] });
  authAPI.refresh.mockResolvedValue({ data: { access: 'access', refresh: 'refresh' } });
});
afterEach(() => { global.fetch = originalFetch; });

test.each(['/admin/dashboard', '/teacher/dashboard', '/student/dashboard', '/parent/dashboard'])('App sends anonymous visitors from %s to login', async path => {
  window.history.replaceState({}, '', path);
  render(<App />);
  expect(await screen.findByRole('heading', { name: 'Sign In' })).toBeVisible();
  expect(window.location.pathname).toBe('/login');
});

test.each(['/', '/unknown'])('App displays the public homepage from %s', async path => {
  window.history.replaceState({}, '', path);
  render(<App />);
  expect(await screen.findByRole('heading', { name: 'Your school deserves a portal that feels like yours.' })).toBeVisible();
  expect(window.location.pathname).toBe('/');
});

test.each([
  ['school_admin', 'Dashboard', '/admin/dashboard'],
  ['teacher', /^Welcome,/, '/teacher/dashboard'],
  ['student', /^Welcome,/, '/student/dashboard'],
])('App restores a %s session and opens its dashboard', async (role, title, path) => {
  tokenStore.getRefresh.mockReturnValue('refresh');
  authAPI.me.mockResolvedValue({ data: { id: 1, role, full_name: 'Ada Okafor', must_change_password: false } });
  window.history.replaceState({}, '', '/login');
  render(<App />);
  expect(await screen.findByRole('heading', { name: title })).toBeVisible();
  expect(window.location.pathname).toBe(path);
});

test('App prevents a student from opening the admin dashboard', async () => {
  tokenStore.getRefresh.mockReturnValue('refresh');
  authAPI.me.mockResolvedValue({ data: { id: 1, role: 'student' } });
  window.history.replaceState({}, '', '/admin/dashboard');
  render(<App />);
  expect(await screen.findByRole('heading', { name: /^Welcome,/ })).toBeVisible();
  expect(window.location.pathname).toBe('/student/dashboard');
});

test.each([['/parent/login', 'Parent Portal'], ['/check-result', 'Result Checker']])('App exposes the public page %s', async (path, heading) => {
  window.history.replaceState({}, '', path);
  render(<App />);
  expect(await screen.findByRole('heading', { name: heading })).toBeVisible();
});
