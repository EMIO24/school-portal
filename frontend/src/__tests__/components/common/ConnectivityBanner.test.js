import React from 'react';
import { act, render, screen } from '@testing-library/react';
import ConnectivityBanner from '../../../components/common/ConnectivityBanner';

test('shows offline state and then a brief recovery notice without retrying work', () => {
  jest.useFakeTimers();
  render(<ConnectivityBanner />);
  act(() => window.dispatchEvent(new Event('offline')));
  expect(screen.getByRole('status')).toHaveTextContent("You're offline");
  act(() => window.dispatchEvent(new Event('online')));
  expect(screen.getByRole('status')).toHaveTextContent('Connection restored');
  act(() => jest.advanceTimersByTime(5000));
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
  jest.useRealTimers();
});
