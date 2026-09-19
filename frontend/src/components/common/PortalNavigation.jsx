import { useTheme } from '../../context/ThemeContext';
import { featureForRoute, hasFeature } from '../../services/features';
import React, { useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import './PortalNavigation.css';

export const ROLE_LINKS = {
  school_admin: [
    ['dashboard', 'Dashboard'], ['calendar', 'Calendar'], ['students', 'Students'],
    ['students/new', 'Add student'], ['students/import', 'Import students'],
    ['staff', 'Staff'], ['staff/new', 'Add staff'], ['staff/import', 'Import staff'],
    ['subjects', 'Subjects'], ['subject-assignments', 'Subject assignments'],
    ['attendance', 'Attendance'], ['timetable', 'Timetable'], ['results', 'Results'],
    ['scratch-cards', 'Scratch cards'], ['question-bank', 'Question bank'],
    ['exam-manager', 'Exams'], ['exam-results', 'Exam results'],
    ['notifications', 'Notifications'], ['notification-templates', 'Notification templates'],
    ['subscription', 'Portal subscription'], ['fee-setup', 'Fee setup'], ['fee-collection', 'Fee collection'], ['promotion', 'Promotion'],
  ].map(([path, label]) => [`/admin/${path}`, label]),
  teacher: [['dashboard', 'Dashboard'], ['attendance', 'Take attendance'], ['scores', 'Scores'],
    ['domains', 'Student development'], ['timetable', 'My timetable']].map(([path, label]) => [`/teacher/${path}`, label]),
  student: [['dashboard', 'Dashboard'], ['attendance', 'Attendance'], ['timetable', 'Timetable'],
    ['results', 'Results'], ['exams', 'Exams'], ['fees', 'Fees'], ['performance', 'Performance']]
    .map(([path, label]) => [`/student/${path}`, label]),
  parent: [['/parent/dashboard', 'Dashboard']],
  superadmin: [['/superadmin/appearance', 'Portal designs'], ['/superadmin/payments', 'Payments'], ['/superadmin/dashboard', 'Schools'], ['/superadmin/team', 'Platform staff and activity']],
};

export default function PortalNavigation({ children }) {
  const [open, setOpen] = useState(false);
  const { isAuthenticated, user, logout } = useAuth();
  const { school } = useTheme();
  const location = useLocation();
  React.useEffect(() => {setOpen(false);}, [location.pathname]);
  React.useEffect(() => {
    if (!open) return;
    const previous = document.activeElement;
    const oldOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const nav = document.getElementById('workspace-links');
    nav?.querySelector('button')?.focus();
    const keydown = event => {
      if (event.key === 'Escape') {event.preventDefault();setOpen(false);}
      if (event.key === 'Tab') {
        const items = [...(nav?.querySelectorAll('a,button') || [])].filter(e => e.getClientRects().length && !e.disabled);
        const first = items[0], last = items[items.length-1];
        if (event.shiftKey && document.activeElement === first) {event.preventDefault();last?.focus();}
        else if (!event.shiftKey && document.activeElement === last) {event.preventDefault();first?.focus();}
      }
    };
    const resize = () => {if (window.innerWidth > 1024) setOpen(false);};
    document.addEventListener('keydown',keydown);window.addEventListener('resize',resize);
    return () => {document.body.style.overflow=oldOverflow;document.removeEventListener('keydown',keydown);window.removeEventListener('resize',resize);previous?.focus?.();};
  }, [open]);
  if (!isAuthenticated || !user || /\/(login|change-password)$/.test(location.pathname) || location.pathname.startsWith('/payments/return') || location.pathname === '/school-preview') return <>{children}</>;
  const platform = user.role === 'superadmin';
  const layout = platform ? 'platform' : school?.theme?.layout || 'scholar';
  const links = (ROLE_LINKS[user.role] || []).filter(([to]) => platform || hasFeature(school, featureForRoute(to)));
  const active = links.find(([to]) => location.pathname === to);
  const name = platform ? 'Platform administration' : school?.name || 'School portal';
  const displayName = user.fullName || user.full_name || user.firstName || user.email;
  return <div className={'workspace layout-' + layout}>
    <a className="workspace-skip" href="#workspace-content">Skip to content</a>
    {open && <button className="workspace-backdrop" aria-label="Close navigation" onClick={()=>setOpen(false)}/>}
    <aside className={'workspace-sidebar' + (open ? ' is-open' : '')}>
      <div className="workspace-brand">{!platform && school?.logo ? <img src={school.logo} alt=""/> : <span className="workspace-monogram" aria-hidden="true">{name.split(' ').slice(0,2).map(w=>w[0]).join('')}</span>}<div><strong>{name}</strong><small>{platform ? 'Owner workspace' : school?.motto || 'Learn. Grow. Achieve.'}</small></div></div>
      <button className="workspace-menu" aria-expanded={open} aria-controls="workspace-links" onClick={()=>setOpen(v=>!v)}>{open ? 'Close menu' : 'Explore portal'}</button>
      <nav id="workspace-links" className="workspace-links" aria-label="Portal navigation">
        <button className="workspace-drawer-close" onClick={()=>setOpen(false)}>Close menu <span aria-hidden="true">×</span></button>
        <span className="workspace-nav-caption">{platform ? 'MANAGEMENT' : 'YOUR WORKSPACE'}</span>
        {links.map(([to,label],i)=><NavLink key={to} to={to} end onClick={()=>setOpen(false)}><span className="workspace-nav-icon" aria-hidden="true">{String(i+1).padStart(2,'0')}</span><span>{label}</span><span className="workspace-nav-arrow" aria-hidden="true">›</span></NavLink>)}
        <div className="workspace-account"><NavLink to={platform ? "/superadmin/guide" : "/user-guide"}>User guide</NavLink><NavLink to={platform ? '/platform/change-password' : '/change-password'}>Change password</NavLink><button onClick={logout}>Sign out</button></div>
      </nav>
      {!platform && <div className="workspace-plan"><span className="workspace-status-dot"/>{school?.entitlements?.plan || 'School'} workspace</div>}
    </aside>
    <div className="workspace-body">
      <header className="workspace-topbar"><div><span className="workspace-eyebrow">{platform ? 'Your platform, at a glance' : 'Welcome to your school portal'}</span><strong>{active?.[1] || 'School workspace'}</strong></div><div className="workspace-person"><span className="workspace-avatar">{displayName?.slice(0,1).toUpperCase()}</span><div><strong>{displayName}</strong><small>{user.role.replace('_',' ')}</small></div></div></header>
      <div id="workspace-content" tabIndex={-1} className="workspace-content">{children}</div>
      <footer className="workspace-footer"><span>{name}</span><span>{platform ? 'School management, made clear.' : school?.motto || 'A place for every learner.'}</span></footer>
    </div>
  </div>;
}
