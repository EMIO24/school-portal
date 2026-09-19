import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { useTheme } from '../../context/ThemeContext';
import { hasFeature, featureForRoute } from '../../services/features';
const destinations = {
  student:[['/student/timetable','Your timetable','Know where your next lesson takes you.'],['/student/results','Your results','See your progress, one term at a time.'],['/student/exams','Exams','Prepare for and take your scheduled exams.'],['/student/fees','School fees','View balances, pay securely and save receipts.']],
  teacher:[['/teacher/attendance','Take attendance','Start the day with your class register.'],['/teacher/scores','Enter scores','Keep every learner up to date.'],['/teacher/timetable','Your timetable','Plan your teaching week.'],['/teacher/domains','Student development','Record the skills beyond the classroom.']],
  school_admin:[['/admin/students','Student directory','Every learner, in one place.'],['/admin/calendar','Academic calendar','Build a well-organised school year.'],['/admin/fee-collection','Fee collection','Stay on top of payments and balances.'],['/admin/question-bank','Question bank','Create richer assessments for your learners.']],
};
export default function WorkspaceHome({compact=false}) {
  const {user}=useAuth();const {school}=useTheme();
  const items=(destinations[user?.role] || []).filter(([to])=>hasFeature(school,featureForRoute(to)));
  return <section className={'workspace-home'+(compact?' compact':'')}>
    <div className="workspace-welcome"><div><span className="workspace-eyebrow">A new day. New possibilities.</span><h1>{compact ? 'Your school, connected.' : 'Welcome, '+(user?.firstName || user?.first_name || 'learner')+'.'}</h1><p>{school?.motto || 'Everything you need to make today a little more organised.'}</p></div><div className="workspace-welcome-mark" aria-hidden="true"><span/><span/><span/></div></div>
    <div className="workspace-shortcuts">{items.map(([to,title,description],i)=><Link to={to} key={to}><span className="shortcut-number">0{i+1}</span><h2>{title}</h2><p>{description}</p><span className="shortcut-arrow" aria-hidden="true">↗</span></Link>)}</div>
  </section>;
}
