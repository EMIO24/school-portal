import React from 'react';
import {fireEvent,screen,waitFor} from '@testing-library/react';
import {renderPage} from '../../testSupport/renderPage';
import StaffForm from '../../pages/admin/StaffForm';
import StudentParents from '../../components/admin/StudentParents';
import TeacherDashboard from '../../pages/teacher/TeacherDashboard';
import SubjectAssignment from '../../pages/admin/SubjectAssignment';
import {referenceOptions} from '../../services/referenceOptions';
import api from '../../services/api';
jest.mock('../../services/api',()=>({__esModule:true,default:{get:jest.fn(),patch:jest.fn(),post:jest.fn(),delete:jest.fn()}}));
beforeEach(()=>jest.resetAllMocks());

test('reference selectors load later pages without following external next URLs',async()=>{
  api.get.mockResolvedValueOnce({data:{results:[{id:1}],next:'https://external.test/not-followed'}}).mockResolvedValueOnce({data:{results:[{id:21}],next:null}});
  expect((await referenceOptions('/api/class-arms/')).data).toEqual([{id:1},{id:21}]);
  expect(api.get).toHaveBeenNthCalledWith(2,'/api/class-arms/?page=2');
});

test('staff edits send corrected identity while keeping role fixed',async()=>{
  api.get.mockImplementation(async url=>({data:url.includes('/staff/')?{id:9,first_name:'Ada',last_name:'Teacher',email:'ada@example.test',role:'teacher',employment_status:'active'}:[]}));
  api.patch.mockResolvedValue({data:{id:9}});
  renderPage(<StaffForm/>,{path:'/staff/9/edit',route:'/staff/:id/edit'});
  fireEvent.change(await screen.findByLabelText('First Name'),{target:{value:'Corrected'}});
  fireEvent.click(screen.getByRole('button',{name:/Save Changes/i}));
  await waitFor(()=>expect(api.patch).toHaveBeenCalledWith('/api/staff/9/',expect.objectContaining({new_first_name:'Corrected',new_email:'ada@example.test'})));
  expect(api.patch.mock.calls[0][1]).not.toHaveProperty('new_role');
});

test('administrator can find an existing parent and reuse verified details',async()=>{
  api.get.mockImplementation(async (url,options)=>({data:options?.params?.search?[{first_name:'Parent',last_name:'One',email:'parent@example.test',phone:'08012345678'}]:[]}));
  api.post.mockResolvedValue({data:{id:1}});
  renderPage(<StudentParents studentId={4}/>);
  await screen.findByText(/No parent has portal access/);
  fireEvent.change(screen.getByLabelText('Find an existing parent'),{target:{value:'Parent'}});
  fireEvent.click(screen.getByRole('button',{name:'Find parent'}));
  fireEvent.click(await screen.findByRole('button',{name:/Use Parent One/}));
  expect(screen.getByLabelText('Parent email')).toHaveValue('parent@example.test');
  fireEvent.click(screen.getByRole('checkbox'));
  fireEvent.click(screen.getByRole('button',{name:'Grant parent access'}));
  await waitFor(()=>expect(api.post).toHaveBeenCalledWith('/api/students/4/parents/',expect.objectContaining({email:'parent@example.test'})));
});

test('parent correction explains its scope and targets the existing link',async()=>{
  api.get.mockResolvedValue({data:[{id:7,name:'Parent One',first_name:'Parent',last_name:'One',email:'parent@example.test',phone:'08012345678',relationship:'guardian',is_active:true}]});
  api.patch.mockResolvedValue({data:{id:7}});
  renderPage(<StudentParents studentId={4}/>);
  fireEvent.click(await screen.findByRole('button',{name:'Edit Parent One'}));
  expect(screen.getByText(/every linked child/)).toBeVisible();
  fireEvent.change(screen.getByLabelText('First name'),{target:{value:'Corrected'}});
  fireEvent.click(screen.getByLabelText(/I have verified/));
  fireEvent.click(screen.getByRole('button',{name:'Save parent account'}));
  await waitFor(()=>expect(api.patch).toHaveBeenCalledWith('/api/students/4/parents/',expect.objectContaining({first_name:'Corrected'}),{params:{link:7}}));
});

test('teacher dashboard shows assigned work with paginated next steps',async()=>{
  api.get.mockResolvedValue({data:{results:[{id:1,class_arm_name:'JSS1 A',subject_name:'Mathematics',term_name:'First',session_name:'2026/27'}],next:null}});
  renderPage(<TeacherDashboard/>,{auth:{user:{role:'teacher',first_name:'Ada'}}});
  expect(await screen.findByText(/JSS1 A/)).toHaveTextContent('Mathematics');
  expect(api.get).toHaveBeenCalledWith('/api/subject-assignments/?mine=true&page=1');
  expect(screen.getByRole('button',{name:'Next'})).toBeDisabled();
});

test('failed staff loading cannot overwrite an existing account',async()=>{
  api.get.mockImplementation(url=>url.includes('/staff/')?Promise.reject(new Error('offline')):Promise.resolve({data:[]}));
  renderPage(<StaffForm/>,{path:'/staff/9/edit',route:'/staff/:id/edit'});
  expect(await screen.findByRole('alert')).toHaveTextContent('Could not load this staff member');
  expect(screen.queryByRole('button',{name:/Save Changes/i})).not.toBeInTheDocument();
});

test('failed assignment loading blocks replacement until a successful retry',async()=>{
  let failed=true;
  api.get.mockImplementation(async url=>{
    if(url.includes('/subject-assignments/?')){if(failed)throw new Error('offline');return {data:{results:[],next:null}};}
    if(url.includes('/grid/'))return {data:{grid:{},arms:[],subjects:[],assignment_counts:{}}};
    if(url.includes('/sessions/'))return {data:[{id:1,name:'2026/27',terms:[{id:1,name:'First term'}]}]};
    if(url.includes('/staff/'))return {data:[{id:1,full_name:'Ada Teacher',staff_id:'STAFF1'}]};
    return {data:[]};
  });
  renderPage(<SubjectAssignment/>);
  fireEvent.click(await screen.findByRole('button',{name:'First term'}));
  fireEvent.click(screen.getByRole('button',{name:/Ada Teacher/}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Retry before saving');
  expect(screen.getByRole('button',{name:/Saving/})).toBeDisabled();
  failed=false;fireEvent.click(screen.getByRole('button',{name:'Retry'}));
  await waitFor(()=>expect(screen.getByRole('button',{name:/Save.*Assignment/i})).toBeEnabled());
  expect(api.post).not.toHaveBeenCalled();
});
