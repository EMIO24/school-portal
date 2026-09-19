import React from 'react';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { renderPage } from '../../testSupport/renderPage';
import PortalDesigns from '../../pages/platform/PortalDesigns';
import ProtectedRoute from '../../components/common/ProtectedRoute';
import { ThemeContext, applyThemeToDom } from '../../context/ThemeContext';
import api from '../../services/api';
jest.mock('../../services/api',()=>({__esModule:true,default:{get:jest.fn(),patch:jest.fn()}}));
const school={id:1,name:'Example School',subdomain:'example',subscription_plan:'basic',theme:{layout:'scholar',primary_color:'#173B56',secondary_color:'#256D85',accent_color:'#D8A548',font_family:"'Segoe UI', sans-serif"}};
beforeEach(()=>{jest.resetAllMocks();api.get.mockImplementation(url=>Promise.resolve({data:url.endsWith('/appearance/')?{schools:[school],plans:{free:['core'],basic:['core','attendance'],premium:['core','cbt']},features:{core:'School setup',attendance:'Attendance',cbt:'Computer-based exams'}}:school}));api.patch.mockResolvedValue({data:school});});
test('shows five designs and saves the selected layout, colours and plan to the chosen school',async()=>{
  renderPage(<PortalDesigns/>,{auth:{user:{role:'superadmin',platformAccess:'owner'}}});
  await screen.findByRole('option',{name:'Example School'});
  expect(screen.getAllByRole('button',{pressed:false}).length + screen.getAllByRole('button',{pressed:true}).length).toBe(5);
  fireEvent.change(screen.getByLabelText('Choose a school'),{target:{value:'1'}});
  await screen.findByText('The right tools for this school.');
  fireEvent.click(screen.getByRole('button',{name:/Executive Distinctive/}));
  fireEvent.change(screen.getByLabelText('Primary'),{target:{value:'#115533'}});
  fireEvent.click(screen.getByRole('radio',{name:/premium/}));
  fireEvent.click(screen.getByRole('button',{name:'Save design and activate plan'}));
  await waitFor(()=>expect(api.patch).toHaveBeenCalledWith('/api/platform/schools/1/',expect.objectContaining({subscription_plan:'premium',theme_config:expect.objectContaining({layout:'executive',primary_color:'#115533'})})));
  expect(await screen.findByRole('status')).toHaveTextContent('Saved.');
});
test('read-only staff cannot open assignment controls',()=>{
  renderPage(<PortalDesigns/>,{auth:{user:{role:'superadmin',platformAccess:'viewer'}}});
  expect(screen.getByText('Owner access required')).toBeVisible();expect(api.get).not.toHaveBeenCalled();
});
test('direct premium route shows upgrade guidance without rendering the protected page',()=>{
  renderPage(<ThemeContext.Provider value={{school:{entitlements:{features:['core'],labels:{cbt:'Computer-based exams'}}}}}><ProtectedRoute allowedRoles={['school_admin']}><p>Exam editor</p></ProtectedRoute></ThemeContext.Provider>,{path:'/admin/question-bank',route:'/admin/question-bank'});
  expect(screen.queryByText('Exam editor')).not.toBeInTheDocument();expect(screen.getByRole('link',{name:'Compare plans'})).toBeVisible();
});
test('brand colours update legacy variables and use readable text on light colours',()=>{
  applyThemeToDom({theme:{layout:'heritage',primary_color:'#FFFFFF',secondary_color:'#123456',accent_color:'#000000'}});
  const root=document.documentElement;
  expect(root.style.getPropertyValue('--primary')).toBe('#FFFFFF');expect(root.style.getPropertyValue('--color-primary')).toBe('#FFFFFF');expect(root.style.getPropertyValue('--on-primary')).toBe('#10202B');expect(root.style.getPropertyValue('--on-accent')).toBe('#FFFFFF');expect(root.dataset.portalLayout).toBe('heritage');
});
