import React from 'react';
import {screen,fireEvent} from '@testing-library/react';
import {renderPage} from '../../testSupport/renderPage';
import UserGuide from '../../pages/public/UserGuide';
import PortalNavigation from '../../components/common/PortalNavigation';
import {downloadReport} from '../../services/pdf';
jest.mock('../../services/pdf',()=>({downloadReport:jest.fn()}));
beforeEach(()=>jest.clearAllMocks());
test.each([['superadmin','Superadmin / platform owner'],['school_admin','School administrator'],['teacher','Staff / teachers'],['parent','Parent / guardian'],['student','Student']])('selects the guide for %s', (role,title)=>{
 renderPage(<UserGuide allowDownloads={role==='superadmin'}/>,{auth:{user:{role}}});expect(screen.getByRole('heading',{name:title})).toBeVisible();
});
test('downloads role and complete guides as PDFs',()=>{
 renderPage(<UserGuide allowDownloads/>,{auth:{user:{role:'superadmin'}}});
 fireEvent.change(screen.getByLabelText('Choose your guide'),{target:{value:'school_admin'}});
 fireEvent.click(screen.getByRole('button',{name:'Download this guide (PDF)'}));
 expect(downloadReport).toHaveBeenCalledWith('School administrator guide',expect.arrayContaining(['Manage students and staff']),'school_admin-user-guide.pdf');
 fireEvent.click(screen.getByRole('button',{name:'Download all guides (PDF)'}));
 expect(downloadReport).toHaveBeenLastCalledWith('School portal user guide',expect.arrayContaining(['Parent / guardian','Student','Staff / teachers']),'school-portal-user-guide.pdf');
});
test('can switch to getting-started instructions',()=>{
 renderPage(<UserGuide/>);fireEvent.change(screen.getByLabelText('Choose your guide'),{target:{value:'start'}});expect(screen.getByRole('heading',{name:'Getting started'})).toBeVisible();
});
test('mobile navigation closes with Escape and restores scrolling',()=>{
 renderPage(<PortalNavigation><p>Page content</p></PortalNavigation>);
 fireEvent.click(screen.getByRole('button',{name:'Explore portal'}));
 expect(document.body.style.overflow).toBe('hidden');
 expect(screen.getByRole('button',{name:'Close navigation'})).toBeInTheDocument();
 fireEvent.keyDown(document,{key:'Escape'});
 expect(screen.getByRole('button',{name:'Explore portal'})).toHaveAttribute('aria-expanded','false');expect(document.body.style.overflow).toBe('');
});

test.each(['school_admin','teacher','parent','student'])('does not offer downloads to %s',role=>{
 renderPage(<UserGuide allowDownloads/>,{auth:{user:{role}}});
 expect(screen.queryByRole('button',{name:/Download/})).not.toBeInTheDocument();
 expect(screen.getByLabelText('Choose your guide')).toBeVisible();
});
test('public/read-only guide view has no download buttons, even for a signed-in superadmin',()=>{
 renderPage(<UserGuide/>,{auth:{user:{role:'superadmin'}}});
 expect(screen.queryByRole('button',{name:/Download/})).not.toBeInTheDocument();
});

test.each(['school_admin','teacher','parent','student'])('does not expose the superadmin guide to %s',role=>{
 renderPage(<UserGuide/>,{auth:{user:{role}}});
 expect(screen.queryByRole('option',{name:'Superadmin / platform owner'})).not.toBeInTheDocument();
 expect(screen.queryByRole('heading',{name:'Superadmin / platform owner'})).not.toBeInTheDocument();
});
test('public help does not list the superadmin guide',()=>{
 renderPage(<UserGuide/>,{auth:{user:null,isAuthenticated:false}});
 expect(screen.queryByRole('option',{name:'Superadmin / platform owner'})).not.toBeInTheDocument();
});
