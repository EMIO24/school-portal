import React from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import api from '../../../services/api';
import MyAssignments from '../../../pages/student/MyAssignments';
import ExamRoom from '../../../pages/student/ExamRoom';

jest.mock('../../../services/api', () => ({get:jest.fn(),post:jest.fn()}));

beforeEach(() => {jest.clearAllMocks();});

test('assignment connection failure preserves the draft and does not submit it', async () => {
  api.get.mockImplementation(url => Promise.resolve({data: url.endsWith('/my-submission/')
    ? {status:'not_started'} : [{id:7,title:'Chemistry practice',kind:'practice',status:'published',
      due_at:'2099-10-01T12:00:00Z',maximum:'10',instructions:'Explain atoms',question_snapshot:[]}]}));
  api.post.mockRejectedValue(new Error('offline'));
  jest.spyOn(window,'confirm').mockReturnValue(true);
  render(<MyAssignments/>);
  fireEvent.click(await screen.findByText(/Chemistry practice · practice/));
  const answer = await screen.findByLabelText('Written response');
  fireEvent.change(answer,{target:{value:'My work remains here'}});
  fireEvent.click(screen.getByText('Submit assignment'));
  await screen.findByRole('alert');
  expect(answer.value).toBe('My work remains here');
  expect(api.post.mock.calls.some(([url])=>url.endsWith('/submit/'))).toBe(false);
  window.confirm.mockRestore();
});

test('CBT failed answer save stays visible and blocks manual submission', async () => {
  api.post.mockImplementation(url => url.endsWith('/start/')
    ? Promise.resolve({data:{questions:[{id:4,question_text:'Atom?',question_type:'mcq',options:[{id:'A',text:'Yes'},{id:'B',text:'No'}]}],time_remaining_seconds:3600}})
    : Promise.reject(new Error('offline')));
  api.get.mockResolvedValue({data:{saved_answers:[],tab_switch_count:0}});
  render(<MemoryRouter initialEntries={['/student/exam/3']}><Routes><Route path="/student/exam/:examId" element={<ExamRoom/>}/></Routes></MemoryRouter>);
  fireEvent.click(await screen.findByText('Yes'));
  await screen.findByText('Save failed');
  fireEvent.click(screen.getByText('Submit'));
  fireEvent.click(screen.getByText('Yes, Submit'));
  await waitFor(()=>expect(screen.getByRole('alert').textContent).toMatch(/answers remain on this page/i));
  expect(api.post.mock.calls.some(([url])=>url.endsWith('/submit/'))).toBe(false);
});
