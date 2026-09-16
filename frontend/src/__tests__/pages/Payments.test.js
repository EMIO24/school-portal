import React from 'react';
import {screen, fireEvent, waitFor} from '@testing-library/react';
import {renderPage} from '../../testSupport/renderPage';
import {PaymentReturn, Subscription, PlatformPayments} from '../../pages/payments/Payments';
import api from '../../services/api';
jest.mock('../../services/api', () => ({__esModule:true, default:{get:jest.fn(),post:jest.fn()}}));
beforeEach(() => {jest.resetAllMocks();window.history.replaceState({},'', '/payments/return?reference=SCH-test');});
afterEach(() => window.history.replaceState({},'', '/'));
test('callback verifies on server before displaying success', async () => {
  api.get.mockResolvedValue({data:{status:'success',kind:'fees',amount:'10000',receipts:[]}});
  renderPage(<PaymentReturn/>);
  expect(await screen.findByText('Payment verified')).toBeVisible();
  expect(api.get).toHaveBeenCalledWith('/api/fees/pay/verify/',{params:{reference:'SCH-test'}});
});
test('pending verification does not display success and supports retry', async () => {
  api.get.mockResolvedValue({data:{status:'pending',kind:'fees',amount:'10000',receipts:[]}});
  renderPage(<PaymentReturn/>);
  expect(await screen.findByText('Payment pending')).toBeVisible();
  expect(screen.queryByText('Payment verified')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'Check again'}));
  await waitFor(() => expect(api.get).toHaveBeenCalledTimes(2));
});
test('signed out callback does not attempt verification', () => {
  renderPage(<PaymentReturn/>,{auth:{isAuthenticated:false,user:null}});
  expect(screen.getByRole('link',{name:'Sign in'})).toBeVisible();
  expect(api.get).not.toHaveBeenCalled();
});
test('school sees configured price and billing period', async () => {
  api.get.mockResolvedValue({data:{plan:'free',ends_on:null,offers:[{plan:'basic',amount:'75000',months:3}],orders:[]}});
  renderPage(<Subscription/>);
  expect(await screen.findByText(/75,000.00 \/ 3 months/)).toBeVisible();
  expect(screen.getByRole('button',{name:'Pay with Paystack'})).toBeEnabled();
});
test('read-only staff cannot load owner payment settings', () => {
  renderPage(<PlatformPayments/>,{auth:{user:{role:'superadmin',platformAccess:'viewer'}}});
  expect(screen.getByText('Only platform owners can manage payment settings.')).toBeVisible();
  expect(api.get).not.toHaveBeenCalled();
});
