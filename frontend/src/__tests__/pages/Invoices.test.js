import React from 'react';
import {fireEvent, screen, waitFor} from '@testing-library/react';
import {renderPage} from '../../testSupport/renderPage';
import Invoices from '../../pages/payments/Invoices';
import api from '../../services/api';
import {downloadFile} from '../../services/download';
jest.mock('../../services/api', () => ({__esModule:true,default:{get:jest.fn(),post:jest.fn()}}));
jest.mock('../../services/download', () => ({downloadFile:jest.fn()}));
const invoice = {id:1,invoice_number:'PAI-TEST',school_name:'Invoice School',session_name:'2026/27',term_name:'First term',
  plan:'premium',active_student_count:102,standard_rate:'1500.00',discount_percentage:10,discount_amount:'15300.00',
  effective_rate:'1350.0000',subtotal:'153000.00',final_amount:'137700.00',issue_date:'2026-09-01',due_date:'2026-09-15',
  status:'overdue',subscription_months:3,payment_attempts:[]};
beforeEach(() => {
  jest.resetAllMocks();
  api.get.mockImplementation(async url => ({data:url.endsWith('/1/') ? invoice : {results:[invoice],count:1,next:null}}));
});
async function openInvoice(owner=false) {
  renderPage(<Invoices owner={owner} schools={[{id:1,name:'Invoice School'}]}/>);
  fireEvent.click(await screen.findByRole('button',{name:'Review invoice PAI-TEST'}));
  return screen.findByRole('region',{name:'Invoice details'});
}
test('school reviews immutable pricing and submits only invoice ID', async () => {
  await openInvoice();
  expect(screen.getByText('102')).toBeVisible();
  expect(screen.getByText('Discount (10%)')).toBeVisible();
  expect(screen.getByText('3 months')).toBeVisible();
  api.post.mockRejectedValue({response:{data:{error:'Payment is pending. Check payment before retrying.'}}});
  fireEvent.click(screen.getByRole('button',{name:/Pay.*137,700/}));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/fees/subscription/',{invoice_id:1}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Payment is pending');
  expect(screen.queryByLabelText('Invoice school')).not.toBeInTheDocument();
});
test('paid invoice provides invoice and single receipt downloads without checkout', async () => {
  api.get.mockImplementation(async url => ({data:url.endsWith('/1/') ? {...invoice,status:'paid',paid_at:'2026-09-02',receipt_number:'RCP-PAI-TEST',payment_reference:'SCH-test'} : {results:[invoice],next:null}}));
  await openInvoice();
  expect(screen.queryByRole('button',{name:/^Pay /})).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'Download receipt'}));
  expect(downloadFile).toHaveBeenCalledWith('/api/fees/subscription/invoices/1/receipt.pdf','RCP-PAI-TEST.pdf');
  fireEvent.click(screen.getByRole('button',{name:'Download invoice PDF'}));
  expect(downloadFile).toHaveBeenCalledWith('/api/fees/subscription/invoices/1/invoice.pdf','PAI-TEST.pdf');
});
test('void invoice cannot be paid', async () => {
  api.get.mockImplementation(async url => ({data:url.endsWith('/1/') ? {...invoice,status:'void',void_reason:'Incorrect term'} : {results:[invoice],next:null}}));
  await openInvoice();
  expect(screen.getByText(/This invoice has been voided/)).toBeVisible();
  expect(screen.queryByRole('button',{name:/^Pay /})).not.toBeInTheDocument();
});
test('owner filters invoices and reconciles using existing endpoint', async () => {
  api.get.mockImplementation(async url => ({data:url.endsWith('/1/') ? {...invoice,payment_attempts:[{reference:'SCH-test',status:'pending',amount:'137700',received_amount:null}]} : {results:[invoice],next:null}}));
  await openInvoice(true);
  fireEvent.change(screen.getByLabelText('Invoice school'),{target:{value:'1'}});
  await waitFor(() => expect(api.get).toHaveBeenCalledWith('/api/platform/invoices/',{params:{page:1,school:'1'}}));
  api.post.mockResolvedValue({data:{status:'success'}});
  fireEvent.click(screen.getByRole('button',{name:'Check payment'}));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/platform/payments/',{reference:'SCH-test'}));
  expect(await screen.findByText(/Payment verified/)).toBeVisible();
  expect(screen.queryByRole('button',{name:/^Pay /})).not.toBeInTheDocument();
});
test('unconfirmed legacy duration disables checkout and owner can explicitly confirm', async () => {
  api.get.mockImplementation(async url => ({data:url.endsWith('/1/') ? {...invoice,subscription_months:null} : {results:[invoice],next:null}}));
  await openInvoice(true);
  fireEvent.change(screen.getByLabelText('Billing duration (months)'),{target:{value:'6'}});
  api.post.mockResolvedValue({data:{}});
  fireEvent.click(screen.getByRole('button',{name:'Confirm billing duration'}));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/platform/invoices/1/',{action:'set_duration',months:6}));
});
test('failed list can be retried and empty state gives next step', async () => {
  api.get.mockRejectedValueOnce(new Error('offline')).mockResolvedValue({data:{results:[],next:null}});
  renderPage(<Invoices/>);
  expect(await screen.findByRole('alert')).toHaveTextContent('Please try again');
  fireEvent.click(screen.getByRole('button',{name:'Retry invoices'}));
  expect(await screen.findByText(/Your invoice will appear here/)).toBeVisible();
});
