import React from 'react';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { renderPage } from '../../testSupport/renderPage';
import CalendarSettings from '../../pages/admin/CalendarSettings';
import api from '../../services/api';

jest.mock('../../services/api',()=>({__esModule:true,default:{get:jest.fn(),post:jest.fn(),patch:jest.fn(),delete:jest.fn()}}));

const holiday={id:9,term:2,name:'Christmas Break',start_date:'2026-12-20',end_date:'2026-12-31',holiday_type:'public'};
const sessions=[{id:1,name:'2026/27',start_date:'2026-09-01',end_date:'2027-07-31',is_current:true,terms:[{id:2,session:1,name:'first',name_display:'First Term',start_date:'2026-09-01',end_date:'2026-12-31',is_current:true,holidays:[holiday]}]}];

beforeEach(()=>{jest.resetAllMocks();api.get.mockResolvedValue({data:sessions});api.post.mockResolvedValue({data:holiday});api.patch.mockResolvedValue({data:{...holiday,name:'Christmas Holiday'}});api.delete.mockResolvedValue({});});

test('renders saved holidays and creates a holiday before reloading sessions',async()=>{
  renderPage(<CalendarSettings/>);
  expect(await screen.findByText('Christmas Break')).toBeVisible();
  fireEvent.click(screen.getByRole('button',{name:'+ Holiday'}));
  fireEvent.change(screen.getByLabelText('Holiday name'),{target:{value:'Mid-term Break'}});
  fireEvent.change(screen.getByLabelText('Start date'),{target:{value:'2026-10-10'}});
  fireEvent.change(screen.getByLabelText('End date'),{target:{value:'2026-10-12'}});
  fireEvent.click(screen.getByRole('button',{name:'Add holiday'}));
  await waitFor(()=>expect(api.post).toHaveBeenCalledWith('/api/holidays/',expect.objectContaining({term:2,name:'Mid-term Break'})));
  expect(api.get).toHaveBeenCalledTimes(2);
});

test('edits and deletes an existing holiday and reloads after each change',async()=>{
  window.confirm=jest.fn(()=>true);
  renderPage(<CalendarSettings/>);await screen.findByText('Christmas Break');
  fireEvent.click(screen.getByRole('button',{name:'Edit'}));
  fireEvent.change(screen.getByLabelText('Holiday name'),{target:{value:'Christmas Holiday'}});
  fireEvent.click(screen.getByRole('button',{name:'Save correction'}));
  await waitFor(()=>expect(api.patch).toHaveBeenCalledWith('/api/holidays/9/',expect.objectContaining({name:'Christmas Holiday'})));
  await screen.findByText(/Holiday corrected/);
  await waitFor(()=>expect(screen.getByRole('button',{name:'Delete'})).not.toBeDisabled());
  fireEvent.click(screen.getByRole('button',{name:'Delete'}));
  await waitFor(()=>expect(api.delete).toHaveBeenCalledWith('/api/holidays/9/'));
  expect(api.get).toHaveBeenCalledTimes(3);
});

test('shows term-boundary validation instead of a generic holiday failure',async()=>{
  api.post.mockRejectedValue({response:{status:400,data:{start_date:['Holiday dates must stay within the selected term.']}}});
  renderPage(<CalendarSettings/>);await screen.findByText('Christmas Break');
  fireEvent.click(screen.getByRole('button',{name:'+ Holiday'}));
  fireEvent.change(screen.getByLabelText('Holiday name'),{target:{value:'Bad date'}});
  fireEvent.change(screen.getByLabelText('Start date'),{target:{value:'2026-08-01'}});
  fireEvent.change(screen.getByLabelText('End date'),{target:{value:'2026-09-02'}});
  fireEvent.click(screen.getByRole('button',{name:'Add holiday'}));
  expect(await screen.findByText(/Holiday dates must stay within the selected term/)).toBeVisible();
});


test('previews rollover readiness without executing it',async()=>{
  const destination={
    id:3,name:'2027/28',start_date:'2027-09-01',end_date:'2028-07-31',is_current:false,
    terms:[{id:4,session:3,name:'first',name_display:'First Term',start_date:'2027-09-01',end_date:'2027-12-17',is_current:false,holidays:[]}],
  };
  api.get.mockResolvedValue({data:[...sessions,destination]});
  api.post.mockImplementation((url)=>{
    if(url.includes('/rollover-preview/')){
      return Promise.resolve({data:{
        rollover_id:11,status:'preparing',ready:false,
        source_session:{id:1,name:'2026/27'},
        destination_session:{id:3,name:'2027/28'},
        summary:{source_students:1,decided:0,unresolved:1,promoted:0,repeated:0,graduated:0,withdrawn:0},
        blockers:[{code:'MISSING_PROMOTION_DECISION',message:'Students are still missing year-end decisions.',count:1}],
        warnings:[],
        students:[{student_id:5,student_name:'Ada Student',source_class:'JSS1A',ready:false,issues:[{code:'MISSING_PROMOTION_DECISION',message:'A year-end promotion, repeat, graduation, or withdrawal decision is required.'}]}],
      }});
    }
    return Promise.resolve({data:holiday});
  });

  renderPage(<CalendarSettings/>);
  const previewButton=await screen.findByRole('button',{name:'Rollover Preview'});
  fireEvent.click(previewButton);

  await waitFor(()=>expect(api.post).toHaveBeenCalledWith('/api/sessions/1/rollover-preview/',{destination_session_id:3}));
  expect(await screen.findByText('Rollover is not ready')).toBeVisible();
  expect(screen.getByText('Students are still missing year-end decisions.')).toBeVisible();
  expect(screen.getByText(/Preview only/)).toBeVisible();
  expect(api.post).not.toHaveBeenCalledWith('/api/sessions/3/set-current/');
});

test('shows the backend rollover blocker when direct session activation is refused',async()=>{
  const destination={id:3,name:'2027/28',start_date:'2027-09-01',end_date:'2028-07-31',is_current:false,terms:[]};
  api.get.mockResolvedValue({data:[...sessions,destination]});
  api.post.mockRejectedValueOnce({response:{status:400,data:['The current session still has active student placements. Complete the academic rollover before activating the next session.']}});

  renderPage(<CalendarSettings/>);
  fireEvent.click(await screen.findByRole('button',{name:'Set Active'}));

  expect(await screen.findByText(/Complete the academic rollover before activating the next session/)).toBeVisible();
});
