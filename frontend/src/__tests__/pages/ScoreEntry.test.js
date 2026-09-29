import React from 'react';
import {fireEvent,screen,waitFor} from '@testing-library/react';
import {renderPage} from '../../testSupport/renderPage';
import ScoreEntry from '../../pages/teacher/ScoreEntry';
import api from '../../services/api';
jest.mock('../../services/api',()=>({__esModule:true,default:{get:jest.fn(),post:jest.fn()}}));

beforeEach(()=>{api.get.mockReset();api.post.mockReset();});

test('teacher loads the complete class sheet and saves a draft without publishing',async()=>{
  const students=Array.from({length:24},(_,i)=>({id:i+1,user:i+101,full_name:'Student '+(i+1),admission_number:'ADM'+i}));
  api.get.mockImplementation(async url=>{
    if(url.includes('/sheet/'))return {data:{students,entries:[],session:1,configuration:{components:[{key:"test",name:"1st Test",maximum:"40"},{key:"exam",name:"Exam",maximum:"60"}]}}};
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
  await waitFor(()=>expect(api.post).toHaveBeenCalledWith('/api/gradebook/entries/bulk-update/',expect.objectContaining({session:1,scores:expect.arrayContaining([expect.objectContaining({student_id:101,component_scores:{test:8,exam:null}})])})));
  expect(api.post.mock.calls.every(([url])=>!url.includes('/publish/'))).toBe(true);
});

test('failed draft save keeps entered scores and retry reloads the persisted draft',async()=>{
  let stored=false;
  api.get.mockImplementation(async url=>{
    if(url.includes('/sheet/'))return {data:{students:[{user:101,full_name:'Test Student'}],entries:stored?[{student:101,policy:1,component_scores:{test:8,exam:null},review_state:'draft',is_published:false}]:[],session:1,configuration:{components:[{key:'test',name:'1st Test',maximum:'40'},{key:'exam',name:'Exam',maximum:'60'}]}}};
    if(url==='/api/terms/')return {data:[{id:1,name:'First term',session:1,is_current:true}]};
    if(url==='/api/sessions/')return {data:[{id:1,name:'2026/27'}]};
    if(url==='/api/class-arms/')return {data:[{id:1,name:'JSS1A'}]};
    return {data:[{id:1,name:'Math'}]};
  });
  api.post.mockRejectedValueOnce(new Error('connection lost')).mockImplementationOnce(async()=>{stored=true;return {data:{errors:{},updated:[]}};});
  renderPage(<ScoreEntry/>,{auth:{user:{role:'teacher'}}});
  await screen.findByRole('option',{name:'Math'});
  fireEvent.change(screen.getByLabelText('Class'),{target:{value:'1'}});
  fireEvent.change(screen.getByLabelText('Subject'),{target:{value:'1'}});
  const score=await screen.findByLabelText('1st Test');
  fireEvent.change(score,{target:{value:'8'}});
  fireEvent.click(screen.getByRole('button',{name:/Save Draft/}));
  expect(await screen.findByText(/Could not confirm the save/)).toBeVisible();
  expect(screen.getByLabelText('1st Test')).toHaveValue(8);
  expect(screen.getByText(/Unsaved changes/)).toBeVisible();
  fireEvent.click(screen.getByRole('button',{name:/Save Draft/}));
  expect(await screen.findByText(/Draft saved/)).toBeVisible();
  expect(screen.getByLabelText('1st Test')).toHaveValue(8);
  expect(api.post).toHaveBeenCalledTimes(2);
  expect(screen.queryByText(/Unsaved changes/)).not.toBeInTheDocument();
});

test('unsaved score edits block changing the sheet when the teacher cancels',async()=>{
  api.get.mockImplementation(async url=>{
    if(url.includes('/sheet/'))return {data:{students:[{user:101,full_name:'Test Student'}],entries:[],session:1,configuration:{components:[{key:'test',name:'1st Test',maximum:'40'}]}}};
    if(url==='/api/terms/')return {data:[{id:1,name:'First term',session:1,is_current:true}]};
    if(url==='/api/sessions/')return {data:[{id:1,name:'2026/27'}]};
    if(url==='/api/class-arms/')return {data:[{id:1,name:'JSS1A'}]};
    return {data:[{id:1,name:'Math'}]};
  });
  renderPage(<ScoreEntry/>,{auth:{user:{role:'teacher'}}});
  await screen.findByRole('option',{name:'Math'});
  fireEvent.change(screen.getByLabelText('Class'),{target:{value:'1'}});
  fireEvent.change(screen.getByLabelText('Subject'),{target:{value:'1'}});
  fireEvent.change(await screen.findByLabelText('1st Test'),{target:{value:'8'}});
  const confirm=jest.spyOn(window,'confirm').mockReturnValue(false);
  fireEvent.change(screen.getByLabelText('Class'),{target:{value:''}});
  expect(confirm).toHaveBeenCalled();
  expect(screen.getByLabelText('Class')).toHaveValue('1');
  expect(screen.getByLabelText('1st Test')).toHaveValue(8);
  confirm.mockRestore();
});


test('teacher imports a CSV into the selected draft sheet before saving',async()=>{
  const students=[
    {id:1,user:101,full_name:'Ada Student',admission_number:'ADM001'},
    {id:2,user:102,full_name:'Ben Student',admission_number:'ADM002'},
  ];
  api.get.mockImplementation(async url=>{
    if(url.includes('/sheet/'))return {data:{students,entries:[],session:1,configuration:{components:[
      {key:'test',name:'1st Test',maximum:'40'},{key:'exam',name:'Exam',maximum:'60'}]}}};
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
  expect(await screen.findByText('Ben Student')).toBeVisible();

  const file=new File(
    ['admission_number,test,exam\nADM001,12,45\nADM002,20,50'],
    'scores.csv',{type:'text/csv'}
  );
  Object.defineProperty(file,'text',{value:async()=> 'admission_number,test,exam\nADM001,12,45\nADM002,20,50'});
  fireEvent.change(screen.getByLabelText('Score CSV file'),{target:{files:[file]}});
  expect(await screen.findByText(/2 score rows imported into this draft/)).toBeVisible();
  const tests=screen.getAllByLabelText('1st Test');
  const exams=screen.getAllByLabelText('Exam');
  expect(tests[0]).toHaveValue(12); expect(exams[0]).toHaveValue(45);
  expect(tests[1]).toHaveValue(20); expect(exams[1]).toHaveValue(50);
  expect(api.post).not.toHaveBeenCalled();

  fireEvent.click(screen.getByRole('button',{name:/Save Draft/}));
  await waitFor(()=>expect(api.post).toHaveBeenCalledWith(
    '/api/gradebook/entries/bulk-update/',
    expect.objectContaining({scores:expect.arrayContaining([
      expect.objectContaining({student_id:101,component_scores:{test:12,exam:45}}),
      expect.objectContaining({student_id:102,component_scores:{test:20,exam:50}}),
    ])})
  ));
});
