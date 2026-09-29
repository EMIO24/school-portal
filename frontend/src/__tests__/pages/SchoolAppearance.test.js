import React from 'react';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { renderPage } from '../../testSupport/renderPage';
import SchoolAppearance from '../../pages/admin/SchoolAppearance';
import api from '../../services/api';
jest.mock('../../services/api',()=>({__esModule:true,default:{get:jest.fn(),patch:jest.fn()}}));
beforeEach(()=>{jest.resetAllMocks();api.get.mockResolvedValue({data:{name:'Example School',motto:'Learn',logo:'',theme:{layout:'heritage',primary_color:'#55334C',secondary_color:'#79566B',accent_color:'#C3A05A',font_family:'Georgia, serif'}}});api.patch.mockResolvedValue({data:{}});});
test('school admin previews ten designs and saves own theme only',async()=>{
  renderPage(<SchoolAppearance/>,{auth:{user:{role:'school_admin'}}});
  expect(await screen.findByRole('heading',{name:'School appearance'})).toBeVisible();
  await screen.findByRole('button',{name:/Nova Contemporary energy/});
  expect(screen.getAllByRole('button',{pressed:false}).length+screen.queryAllByRole('button',{pressed:true}).length).toBe(10);
  fireEvent.click(screen.getByRole('button',{name:/Nova Contemporary energy/}));
  expect(screen.getAllByLabelText('nova layout preview')).toHaveLength(2);
  fireEvent.click(screen.getByRole('button',{name:'Save appearance'}));
  await waitFor(()=>expect(api.patch).toHaveBeenCalledWith('/api/school/appearance/',{theme_config:expect.objectContaining({layout:'nova'})}));
  expect(api.patch.mock.calls[0][1]).not.toHaveProperty('subscription_plan');
});
