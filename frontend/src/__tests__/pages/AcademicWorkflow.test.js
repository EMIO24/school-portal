import React from 'react';
import {fireEvent,screen,waitFor} from '@testing-library/react';
import {renderPage} from '../../testSupport/renderPage';
import ScoringConfiguration from '../../pages/admin/ScoringConfiguration';
import ResultReview from '../../pages/admin/ResultReview';
import ScoreEntry from '../../pages/teacher/ScoreEntry';
import api from '../../services/api';
jest.mock('../../services/api',()=>({__esModule:true,default:{get:jest.fn(),post:jest.fn(),put:jest.fn()}}));
const config={components:[{key:'ca',name:'Continuous assessment',maximum:'40',kind:'assessment'},{key:'exam',name:'Exam',maximum:'60',kind:'exam'}],bands:[{grade:'A',remark:'Excellent',min_score:'0',max_score:'100'}],locked:false};
const row={id:9,student:101,policy:1,component_scores:{ca:'32',exam:'40'},total_score:'72',grade:'A',remark:'Excellent',review_state:'submitted',is_published:false};
beforeEach(()=>{
  jest.resetAllMocks();
  api.get.mockImplementation(async url=>{
    if(url.includes('/configuration/'))return {data:config};
    if(url.includes('/sheet/'))return {data:{configuration:config,students:[{user:101,full_name:'Ada Student'}],entries:[row],session:1}};
    if(url==='/api/terms/')return {data:[{id:1,name:'First term',session:1,is_current:true}]};
    if(url==='/api/sessions/')return {data:[{id:1,name:'2026/27'}]};
    if(url==='/api/class-arms/')return {data:[{id:1,name:'JSS1A'}]};
    return {data:[{id:1,name:'Math'}]};
  });
});

test('administrator edits term assessment and sees server validation feedback',async()=>{
  renderPage(<ScoringConfiguration/>);await screen.findByRole('option',{name:/First term/});
  fireEvent.change(screen.getByLabelText('Assessment term'),{target:{value:'1'}});
  await screen.findByDisplayValue('Continuous assessment');
  fireEvent.change(screen.getAllByLabelText('Maximum score')[0],{target:{value:'50'}});
  api.put.mockRejectedValue({response:{data:{components:['Assessment components total 110. The total must equal 100.']}}});
  fireEvent.click(screen.getByRole('button',{name:'Save assessment and grading'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('total 110');
  expect(api.put).toHaveBeenCalledWith('/api/gradebook/configuration/?term=1',expect.objectContaining({components:expect.arrayContaining([expect.objectContaining({maximum:'50'})])}));
});

test('used configuration is visibly locked',async()=>{
  const original=api.get.getMockImplementation();
  api.get.mockImplementation(url=>url.includes('/configuration/')?Promise.resolve({data:{...config,locked:true}}):original(url));
  renderPage(<ScoringConfiguration/>);await screen.findByRole('option',{name:/First term/});
  fireEvent.change(screen.getByLabelText('Assessment term'),{target:{value:'1'}});
  await screen.findByText(/This term has scores/);
  expect(screen.getByRole('button',{name:'Save assessment and grading'})).toBeDisabled();
});

test('review shows stored grades and permits approval before publication',async()=>{
  api.post.mockResolvedValue({data:{approve:1}});
  renderPage(<ResultReview classArm="1" term="1"/>);
  await screen.findByRole('option',{name:'Math'});
  fireEvent.change(screen.getByLabelText('Review subject'),{target:{value:'1'}});
  await screen.findByText('Ada Student');expect(screen.getByText('A')).toBeVisible();
  expect(screen.getByRole('button',{name:'Publish approved scores'})).toBeDisabled();
  fireEvent.click(screen.getByRole('button',{name:'Approve reviewed scores'}));
  await waitFor(()=>expect(api.post).toHaveBeenCalledWith('/api/gradebook/entries/approve/',{class_arm:1,term:1,subject:1}));
});

test('submitted sheet uses configured maxima and locks teacher inputs',async()=>{
  renderPage(<ScoreEntry/>);await screen.findByRole('option',{name:'Math'});
  fireEvent.change(screen.getByLabelText('Class'),{target:{value:'1'}});
  fireEvent.change(screen.getByLabelText('Subject'),{target:{value:'1'}});
  await screen.findByText('Ada Student');
  expect(screen.getByLabelText('Continuous assessment')).toHaveAttribute('max','40');
  expect(screen.getByLabelText('Continuous assessment')).toBeDisabled();
  expect(screen.getByText('A')).toBeVisible();
  expect(screen.getByRole('button',{name:'Submit for review'})).toBeDisabled();
});

test('teacher submits saved drafts through the review endpoint',async()=>{
  const original=api.get.getMockImplementation();
  api.get.mockImplementation(async url=>{const r=await original(url);if(url.includes('/sheet/'))r.data.entries=[{...row,review_state:'draft'}];return r;});
  api.post.mockResolvedValue({data:{submit:1}});
  renderPage(<ScoreEntry/>);await screen.findByRole('option',{name:'Math'});
  fireEvent.change(screen.getByLabelText('Class'),{target:{value:'1'}});
  fireEvent.change(screen.getByLabelText('Subject'),{target:{value:'1'}});
  await screen.findByText('Ada Student');fireEvent.click(screen.getByRole('button',{name:'Submit for review'}));
  await waitFor(()=>expect(api.post).toHaveBeenCalledWith('/api/gradebook/entries/submit/',{class_arm:1,subject:1,term:1}));
});
