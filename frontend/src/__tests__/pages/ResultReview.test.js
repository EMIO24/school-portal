import React from 'react';
import {fireEvent,screen} from '@testing-library/react';
import {renderPage} from '../../testSupport/renderPage';
import ResultReview from '../../pages/admin/ResultReview';
import api from '../../services/api';
import {referenceOptions} from '../../services/referenceOptions';

jest.mock('../../services/api',()=>({__esModule:true,default:{get:jest.fn(),post:jest.fn()}}));
jest.mock('../../services/referenceOptions',()=>({referenceOptions:jest.fn(async()=>({data:[{id:1,name:'Math'}]}))}));

test('reconciles an uncertain publication response against the authoritative sheet',async()=>{
  referenceOptions.mockResolvedValue({data:[{id:1,name:'Math'}]});
  let published=false;
  api.get.mockImplementation(async()=>({data:{students:[{user:7,full_name:'Test Student'}],entries:[{id:9,student:7,review_state:'approved',is_published:published,policy:1,component_scores:{test:8},total_score:8,grade:'A'}],configuration:{components:[{key:'test',name:'Test',maximum:10}]}}}));
  api.post.mockImplementationOnce(async()=>{published=true;throw new Error('connection lost after commit');});
  const confirm=jest.spyOn(window,'confirm').mockReturnValue(true);
  renderPage(<ResultReview classArm={1} term={1}/>);
  fireEvent.change(await screen.findByLabelText('Review subject'),{target:{value:'1'}});
  fireEvent.click(await screen.findByRole('button',{name:'Publish approved scores'}));
  expect(await screen.findByText(/refreshed sheet confirms it/)).toBeVisible();
  expect(screen.getByText('Published / locked')).toBeVisible();
  expect(api.post).toHaveBeenCalledTimes(1);
  confirm.mockRestore();
});

test('opens the review subject supplied by the principal source link', async () => {
  window.history.pushState({}, '', '/admin/results?term=1&class_arm=1&subject=1');
  referenceOptions.mockResolvedValue({ data: [{ id: 1, name: 'Math' }] });
  api.get.mockResolvedValue({ data: { students: [], entries: [], configuration: { components: [] } } });
  renderPage(<ResultReview classArm={1} term={1}/>);
  expect(await screen.findByLabelText('Review subject')).toHaveValue('1');
  expect(api.get).toHaveBeenCalledWith('/api/gradebook/entries/sheet/?class_arm=1&term=1&subject=1');
  window.history.pushState({}, '', '/');
});
