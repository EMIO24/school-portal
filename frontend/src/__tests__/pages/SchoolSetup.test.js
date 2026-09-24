import React from 'react';
import {fireEvent,screen,waitFor} from '@testing-library/react';
import {renderPage} from '../../testSupport/renderPage';
import SchoolSetup from '../../pages/admin/SchoolSetup';
import StudentParents from '../../components/admin/StudentParents';
import api from '../../services/api';
jest.mock('../../services/api',()=>({__esModule:true,default:{get:jest.fn(),post:jest.fn(),patch:jest.fn(),delete:jest.fn()}}));
const setup={identity:{name:'Basic Academy',motto:'Learn',address:'School Road',phone:'08000000000',email:'school@test.invalid',logo:''},
  steps:[{key:'identity',label:'School identity',complete:true,url:'/admin/setup#identity'},{key:'assignments',label:'Teacher assignments',complete:false,url:'/admin/subject-assignments'}],
  missing_assignments:2,assessment:{first_test:10,exam_score:60},class_level_choices:[['JSS1','JSS 1']]};
beforeEach(()=>{jest.resetAllMocks();api.get.mockImplementation(async url=>({data:url==='/api/school/setup/'?setup:[]}));});

test('setup reports gaps and saves only school identity fields',async()=>{
  renderPage(<SchoolSetup/>);
  expect(await screen.findByText('1 of 2 setup checks complete')).toBeVisible();
  expect(screen.getByRole('link',{name:'Teacher assignments'})).toHaveAttribute('href','/admin/subject-assignments');
  fireEvent.change(screen.getByLabelText('School name'),{target:{value:'Updated Academy'}});
  api.patch.mockResolvedValue({data:{}});
  fireEvent.click(screen.getByRole('button',{name:'Save school identity'}));
  await waitFor(()=>expect(api.patch).toHaveBeenCalledWith('/api/school/setup/',expect.objectContaining({name:'Updated Academy'})));
  expect(api.patch.mock.calls[0][1]).not.toHaveProperty('logo');
  expect(api.patch.mock.calls[0][1]).not.toHaveProperty('subscription_plan');
});

test('setup creates a class through the existing endpoint',async()=>{
  renderPage(<SchoolSetup/>);await screen.findByText('1 of 2 setup checks complete');
  fireEvent.change(screen.getByLabelText('New class level'),{target:{value:'JSS1'}});
  api.post.mockResolvedValue({data:{id:1}});
  fireEvent.click(screen.getByRole('button',{name:'Add class level'}));
  await waitFor(()=>expect(api.post).toHaveBeenCalledWith('/api/class-levels/',{name:'JSS1'}));
});

test('setup load failure has a working retry',async()=>{
  api.get.mockRejectedValueOnce(new Error('offline'));
  renderPage(<SchoolSetup/>);
  expect(await screen.findByRole('alert')).toBeVisible();
  fireEvent.click(screen.getByRole('button',{name:'Retry'}));
  expect(await screen.findByText('1 of 2 setup checks complete')).toBeVisible();
});

test('parent linking is explicit and scoped to the selected student',async()=>{
  renderPage(<StudentParents studentId={71}/>);
  expect(await screen.findByText(/No parent has portal access/)).toBeVisible();
  for(const [label,value] of [['First name','Parent'],['Last name','One'],['Parent email','parent@test.invalid'],['Parent login phone','08000000000']])
    fireEvent.change(screen.getByLabelText(label),{target:{value}});
  fireEvent.click(screen.getByRole('checkbox'));
  api.post.mockResolvedValue({data:{id:1}});
  fireEvent.click(screen.getByRole('button',{name:'Grant parent access'}));
  await waitFor(()=>expect(api.post).toHaveBeenCalledWith('/api/students/71/parents/',expect.objectContaining({email:'parent@test.invalid',phone:'08000000000'})));
  expect(await screen.findByRole('status')).toHaveTextContent('Parent linked');
});
