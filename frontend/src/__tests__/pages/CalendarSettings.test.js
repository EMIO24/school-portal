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
