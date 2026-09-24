import React from 'react';
import {fireEvent,screen,waitFor} from '@testing-library/react';
import {renderPage} from '../../testSupport/renderPage';
import ScoreEntry from '../../pages/teacher/ScoreEntry';
import api from '../../services/api';
jest.mock('../../services/api',()=>({__esModule:true,default:{get:jest.fn(),post:jest.fn()}}));

test('teacher loads the complete class sheet and saves a draft without publishing',async()=>{
  const students=Array.from({length:24},(_,i)=>({id:i+1,user:i+101,full_name:'Student '+(i+1),admission_number:'ADM'+i}));
  api.get.mockImplementation(async url=>{
    if(url.includes('/sheet/'))return {data:{students,entries:[],session:1}};
    if(url.includes('grade-scale'))return {data:{bands:[{min_score:0,max_score:100,grade:'A1',remark:'Excellent'}]}};
    if(url==='/api/terms/')return {data:[{id:1,name:'First term',session:1,is_current:true}]};
    if(url==='/api/sessions/')return {data:[{id:1,name:'2026/27'}]};
    if(url==='/api/class-arms/')return {data:[{id:1,name:'JSS1A'}]};
    return {data:[{id:1,name:'Math'}]};
  });
  api.post.mockResolvedValue({data:{errors:{},updated:[]}});
  renderPage(<ScoreEntry/>,{auth:{user:{role:'teacher'}}});
  await screen.findByRole('option',{name:'Math'});
  fireEvent.change(screen.getByLabelText('Class'),{target:{value:'1'}});
  fireEvent.change(screen.getByLabelText('Subject'),{target:{value:'1'}});
  expect(await screen.findByText('Student 24')).toBeVisible();
  expect(screen.queryByRole('button',{name:/Publish/})).not.toBeInTheDocument();
  fireEvent.change(screen.getAllByLabelText('1st Test')[0],{target:{value:'8'}});
  fireEvent.click(screen.getByRole('button',{name:/Save Draft/}));
  await waitFor(()=>expect(api.post).toHaveBeenCalledWith('/api/gradebook/entries/bulk-update/',expect.objectContaining({session:1,scores:expect.arrayContaining([expect.objectContaining({student_id:101,first_test:8})])})));
  expect(api.post.mock.calls.every(([url])=>!url.includes('/publish/'))).toBe(true);
});
