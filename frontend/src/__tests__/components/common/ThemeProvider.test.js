import { THEME_CACHE_KEY } from "../../../context/ThemeContext";
import { MemoryRouter } from "react-router-dom";
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ThemeProvider from '../../../components/common/ThemeProvider';

const originalFetch = global.fetch;
beforeEach(() => { localStorage.clear(); global.fetch = jest.fn(); });
afterEach(() => { global.fetch = originalFetch; document.documentElement.removeAttribute('style'); });

test('ThemeProvider gates content while loading, then applies and caches school branding', async () => {
  let resolve;
  global.fetch.mockReturnValue(new Promise(done => { resolve = done; }));
  render(<MemoryRouter initialEntries={['/login']}><ThemeProvider><p>Portal content</p></ThemeProvider></MemoryRouter>);
  expect(screen.getByRole('status')).toBeVisible();
  expect(screen.queryByText('Portal content')).not.toBeInTheDocument();
  const school = { name: 'Test School', theme: { primary_color: '#123456' } };
  resolve({ ok: true, json: async () => school });
  expect(await screen.findByText('Portal content')).toBeVisible();
  expect(document.documentElement.style.getPropertyValue('--color-primary')).toBe('#123456');
  expect(JSON.parse(localStorage.getItem(THEME_CACHE_KEY))).toEqual(school);
});

test('ThemeProvider shows an error and retries successfully', async () => {
  global.fetch.mockRejectedValueOnce(new Error('Offline')).mockResolvedValue({ ok: true, json: async () => ({ name: 'Recovered School' }) });
  render(<MemoryRouter initialEntries={['/login']}><ThemeProvider><p>Portal content</p></ThemeProvider></MemoryRouter>);
  expect(await screen.findByRole('heading', { name: 'School Not Found' })).toBeVisible();
  expect(screen.getByText('Offline')).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'Try Again' }));
  expect(await screen.findByText('Portal content')).toBeVisible();
  expect(global.fetch).toHaveBeenCalledTimes(2);
});

test('ThemeProvider keeps cached content available when refresh fails', async () => {
  localStorage.setItem(THEME_CACHE_KEY, JSON.stringify({ name: 'Cached School' }));
  global.fetch.mockRejectedValue(new Error('Offline'));
  render(<MemoryRouter><ThemeProvider><p>Portal content</p></ThemeProvider></MemoryRouter>);
  expect(screen.getByText('Portal content')).toBeVisible();
  await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));
  expect(screen.queryByText('School Not Found')).not.toBeInTheDocument();
});

test.each(['/', '/features', '/pricing', '/demo', '/contact', '/privacy', '/terms', '/access'])(
  'marketing route %s renders while tenant theme is loading', path => {
    global.fetch.mockReturnValue(new Promise(() => {}));
    render(<MemoryRouter initialEntries={[path]}><ThemeProvider><p>Marketing content</p></ThemeProvider></MemoryRouter>);
    expect(screen.getByText('Marketing content')).toBeVisible();
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  }
);

test('marketing content stays visible when tenant theme lookup fails', async () => {
  global.fetch.mockRejectedValue(new Error('School not found'));
  render(<MemoryRouter initialEntries={['/features']}><ThemeProvider><p>Marketing content</p></ThemeProvider></MemoryRouter>);
  expect(screen.getByText('Marketing content')).toBeVisible();
  await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));
  expect(screen.queryByText('School Not Found')).not.toBeInTheDocument();
});
