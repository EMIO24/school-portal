import React from 'react';
import {fireEvent,screen,waitFor} from '@testing-library/react';
import {renderPage} from '../../testSupport/renderPage';
import FeeCollection from '../../pages/admin/FeeCollection';
import api from '../../services/api';

jest.mock('../../services/api',()=>({__esModule:true,default:{get:jest.fn(),post:jest.fn()}}));

test('uncertain manual-payment response retries identical details and key',async()=>{
  api.get.mockImplementation(async url=>{
    if(url==='/api/terms/')return {data:[{id:1,name:'First term',is_current:true}]};
    if(url==='/api/class-arms/')return {data:[]};
    if(url.startsWith('/api/fees/ledger/accounts/'))return {data:{results:[{student_id:7,student_name:'Test Student',class:'JSS1A',state:'active',total_fees:1000,paid:0,outstanding:1000,credit:0}],next:null,previous:null}};
    if(url.startsWith('/api/fees/student/'))return {data:[{schedule:{id:4,fee_category_name:'Tuition'},outstanding:1000}]};
    throw new Error('Unexpected GET '+url);
  });
  api.post.mockRejectedValueOnce(new Error('connection lost')).mockResolvedValueOnce({data:{id:12}});
  renderPage(<FeeCollection/>);
  fireEvent.click(await screen.findByRole('button',{name:'Record Payment'}));
  expect(api.get.mock.calls.map(call => call[0])).toContain('/api/fees/student/7/?term=1');
  fireEvent.click(await screen.findByRole('button',{name:'Record'}));
  expect(await screen.findByText(/Could not confirm whether this payment was recorded/)).toBeVisible();
  expect(screen.getByRole('button',{name:'Retry same payment'})).toBeEnabled();
  const first=api.post.mock.calls[0][1];
  fireEvent.click(screen.getByRole('button',{name:'Retry same payment'}));
  await waitFor(()=>expect(api.post).toHaveBeenCalledTimes(2));
  expect(api.post.mock.calls[1][1]).toEqual(first);
  await waitFor(()=>expect(screen.queryByRole('button',{name:'Retry same payment'})).not.toBeInTheDocument());
});

test('does not present a previous term balance while the next term loads or after a read failure', async () => {
  api.get.mockReset();
  api.get.mockImplementation(url => {
    if (url === '/api/terms/') return Promise.resolve({ data: [
      { id: 1, name: 'First term', is_current: true }, { id: 2, name: 'Second term' },
    ] });
    if (url === '/api/class-arms/') return Promise.resolve({ data: [] });
    if (url.includes('term=1')) return Promise.resolve({ data: { results: [
      { student_id: 7, student_name: 'Test Student', class: 'JSS1A', state:'active', total_fees: 1000, paid: 0, outstanding: 1000, credit:0 },
    ], next: null, previous: null } });
    return Promise.reject(new Error('connection lost'));
  });
  renderPage(<FeeCollection />);
  expect(await screen.findByText('Test Student')).toBeInTheDocument();
  fireEvent.change(screen.getAllByRole('combobox')[0], { target: { value: '2' } });
  expect(screen.queryByText('₦1,000')).not.toBeInTheDocument();
  expect(await screen.findByRole('alert')).toHaveTextContent("We couldn't reach Paideia");
  expect(screen.queryByText('Test Student')).not.toBeInTheDocument();
});

test('unknown account is not shown as zero and charge generation refreshes balances', async () => {
  api.get.mockReset(); api.post.mockReset();
  api.get.mockImplementation(async url => {
    if (url === '/api/terms/') return {data: [{id: 1, name: 'First', is_current: true}]};
    if (url === '/api/class-arms/') return {data: []};
    return {data: {results: [{student_id: 7, student_name: 'Test Student', class: 'JSS1A',
      state: 'uninitialized', total_fees: null, paid: null, outstanding: null, credit: null}],
      summary: {total_expected: '0.00', total_collected: '0.00', total_outstanding: '0.00', unknown_accounts: 1},
      next: null, previous: null}};
  });
  api.post.mockResolvedValue({data: {created: 1, existing: 0, legacy_skipped: 0}});
  const confirm = jest.spyOn(window, 'confirm').mockReturnValue(true);
  renderPage(<FeeCollection />);
  expect(await screen.findByText('Unknown')).toBeVisible();
  expect(screen.getAllByText('Not verified')).toHaveLength(2);
  fireEvent.click(screen.getByRole('button', {name: 'Generate charges'}));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/fees/ledger/charges/', {term_id: 1}));
  expect(await screen.findByText(/1 charges created/)).toBeVisible();
  confirm.mockRestore();
});

test('fully credited ledger balance is settled even without a cash payment', async () => {
  api.get.mockReset();
  api.get.mockImplementation(async url => {
    if (url === '/api/terms/') return {data: [{id: 1, name: 'First', is_current: true}]};
    if (url === '/api/class-arms/') return {data: []};
    return {data: {results: [{student_id: 7, student_name: 'Test Student', class: 'JSS1A',
      state: 'active', total_fees: '100.00', paid: '0.00', outstanding: '0.00', credit: '0.00'}],
      next: null, previous: null}};
  });
  renderPage(<FeeCollection />);
  expect(await screen.findByText('Paid')).toBeVisible();
  expect(screen.queryByRole('button', {name: 'Record Payment'})).not.toBeInTheDocument();
});
